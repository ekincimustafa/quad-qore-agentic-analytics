"""Offline HTTP harness checks, with explicitly selected and budgeted live plans."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Literal
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

from app.api.economic_question import EconomicQuestionRequest, get_economic_question_model
from app.api.main import create_app
from app.connectors import llm_client
from app.services import economic_question as service
from app.services.housing_filter import run_housing_filter
from app.services.inflation_comparison import compare_inflation_years as reference_comparison


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals/economic_question_cases.json"
FIXTURES = {
    "both": ROOT / "docs/economic-question-api-example.json",
    "cpi_history": ROOT / "docs/economic-question-cpi-example.json",
    "comparison": ROOT / "docs/economic-question-comparison-example.json",
    "comparison_missing_history": ROOT / "docs/economic-question-comparison-missing-history-example.json",
    "housing_filter": ROOT / "evals/fixtures/economic-housing-filter.json",
}
ENDPOINT = "/analysis/economic/question"
MODEL_DECISION = TypeAdapter(service.ModelDecision)
_SAFE_PROVIDER_ERROR_CODES = frozenset({
    "timeout",
    "authentication_failed",
    "access_denied",
    "rate_limited",
    "connection_failed",
    "invalid_response",
    "provider_unavailable",
    "request_rejected",
    "provider_error",
})
_SAFE_PLAN_FIELDS = frozenset({
    "status", "analysis_id", "reason", "start_period", "end_period",
    "first_year", "second_year", "conditions", "metric", "operator", "threshold",
})
_SAFE_VALIDATION_TYPES = frozenset({
    "missing", "extra_forbidden", "literal_error", "value_error", "model_type",
    "float_type", "float_parsing", "finite_number", "int_type", "int_parsing",
    "string_type", "string_pattern_mismatch", "string_too_short", "string_too_long",
    "too_short", "too_long", "greater_than_equal", "less_than_equal",
})


def _invalid_plan_diagnostics(text: object) -> dict:
    """Classify a rejected response using closed labels; never retain its content."""
    if not isinstance(text, str):
        return {"format": "non_text"}
    if len(text) > service.MAX_PLAN_CHARACTERS:
        return {"format": "too_long"}
    if text.lstrip().startswith("```"):
        return {"format": "code_fence_prefix"}
    try:
        decoded = json.loads(text)
    except (ValueError, RecursionError):
        return {"format": "invalid_json"}
    if not isinstance(decoded, dict):
        return {"format": "json_non_object"}

    # Narrow diagnostics to the declared, known branch; union errors from other
    # branches would otherwise misleadingly list their unrelated required fields.
    validator = MODEL_DECISION
    status, analysis_id = decoded.get("status"), decoded.get("analysis_id")
    if status == "ready":
        if analysis_id == service.HOUSING_FILTER_ID:
            validator = TypeAdapter(service.EconomicHousingFilterReadyPlan)
        elif analysis_id == service.COMPARISON_ID:
            validator = TypeAdapter(service.EconomicComparisonReadyPlan)
        elif analysis_id in (service.HOUSING_ID, service.INFLATION_ID):
            validator = TypeAdapter(service.EconomicReadyPlan)
    elif status == "clarification_required":
        validator = TypeAdapter(service.EconomicClarification)
    elif status == "unsupported":
        validator = TypeAdapter(service.EconomicUnsupported)
    try:
        validator.validate_json(text)
    except ValidationError as error:
        errors = error.errors(include_input=False, include_context=False, include_url=False)
        return {
            "format": "json_object", "schema_valid": False,
            "error_types": sorted({
                item["type"] if item["type"] in _SAFE_VALIDATION_TYPES else "other"
                for item in errors
            }),
            "error_fields": sorted({
                part for item in errors for part in item["loc"]
                if isinstance(part, str) and part in _SAFE_PLAN_FIELDS
            }),
        }
    return {"format": "json_object", "schema_valid": True}


class ComparisonExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    observed_month_counts: tuple[int, int]
    december_annual_inflation_pct: tuple[float | None, float | None]
    second_minus_first_december_annual_inflation_pp: float | None


class EconomicCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(pattern=r"^EQ-[0-9]{3}$")
    question: str = Field(min_length=1, max_length=2_000)
    fixture: Literal[
        "both", "cpi_history", "comparison", "comparison_missing_history",
        "housing_filter", "housing_only", "none",
    ] = "both"
    offline_response: dict[str, Any]
    expected_decision: service.EconomicDecision
    accepted_model_decisions: list[service.ModelDecision] | None = Field(default=None, min_length=1)
    rationale: str = ""
    expected_observed_month_count: int | None = Field(default=None, ge=1)
    expected_matched_periods: list[str] | None = None
    expected_comparison: ComparisonExpectation | None = None

    @model_validator(mode="after")
    def expectations(self) -> EconomicCase:
        if not self.question.strip():
            raise ValueError("Case question must not be blank.")
        ready = isinstance(
            self.expected_decision,
            (service.EconomicReadyPlan, service.EconomicHousingFilterReadyPlan),
        )
        comparison = isinstance(self.expected_decision, service.EconomicComparisonReadyPlan)
        if ready != (self.expected_observed_month_count is not None):
            raise ValueError("Only single-analysis ready cases need an observation count.")
        if comparison != (self.expected_comparison is not None):
            raise ValueError("Only comparison ready cases need comparison expectations.")
        housing = ready and self.expected_decision.analysis_id in {
            service.HOUSING_ID, service.HOUSING_FILTER_ID,
        }
        if housing != (self.expected_matched_periods is not None):
            raise ValueError("Only Housing ready cases need matching periods.")
        if self.fixture != "none" and isinstance(self.expected_decision, service.EconomicDataUnavailable):
            if self.accepted_model_decisions is None:
                raise ValueError("Data-unavailable cases with a planner need explicit model expectations.")
        return self

    def model_expectations(self) -> list[dict]:
        if self.fixture == "none":
            return []
        return [plan.model_dump() for plan in (self.accepted_model_decisions or [self.expected_decision])]


class EconomicSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0"]
    cases: list[EconomicCase] = Field(min_length=1, max_length=45)

    @model_validator(mode="after")
    def unique_ids(self) -> EconomicSuite:
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Case IDs must be unique.")
        return self


def _payload(case: EconomicCase, fixtures: dict[str, dict]) -> dict:
    if case.fixture == "none":
        return {"question": case.question}
    fixture = {
        "cpi_history": "cpi_history",
        "comparison": "comparison",
        "comparison_missing_history": "comparison_missing_history",
        "housing_filter": "housing_filter",
    }.get(case.fixture, "both")
    payload = copy.deepcopy(fixtures[fixture])
    payload["question"] = case.question
    if case.fixture == "housing_only":
        payload.pop("inflation")
    return payload


def select_cases(cases: list[EconomicCase], ids: list[str] | None) -> list[EconomicCase]:
    if ids is None:
        return cases
    lookup = {case.id: case for case in cases}
    if not ids or len(ids) != len(set(ids)) or any(key not in lookup for key in ids):
        raise ValueError("Select known, unique case IDs.")
    return [lookup[key] for key in ids]


def _reference(client: TestClient, payload: dict, analysis_id: str, start: str, end: str) -> dict:
    housing = analysis_id == service.HOUSING_ID
    response = client.post(
        "/analysis/housing" if housing else "/analysis/inflation",
        json={**payload["housing" if housing else "inflation"], "start_period": start, "end_period": end},
    )
    if response.status_code != 200:
        raise ValueError("The synthetic reference input is invalid.")
    return response.json()


def _comparison_reference(payload: dict, plan: service.EconomicComparisonReadyPlan) -> dict:
    frame = pd.DataFrame(payload["inflation"]["cpi_monthly"])
    return reference_comparison(
        frame,
        first_year=plan.first_year,
        second_year=plan.second_year,
        source_ref=payload["inflation"]["source_ref"],
    ).model_dump(mode="json")


def _filter_reference(payload: dict, plan: service.EconomicHousingFilterReadyPlan) -> dict:
    housing = payload["housing"]
    return run_housing_filter(
        pd.DataFrame(housing["bddk_monthly"]),
        pd.DataFrame(housing["evds_monthly"]),
        start_period=plan.start_period,
        end_period=plan.end_period,
        conditions=plan.conditions,
        bddk_source_ref=housing["bddk_source_ref"],
        evds_source_refs=housing["evds_source_refs"],
    ).model_dump(mode="json")


def _close(actual: float | None, expected: float | None) -> bool:
    if expected is None or actual is None:
        return actual is expected
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9)


def _normalized_housing_filter(value: Any) -> Any:
    """Compare AND conditions in any order without altering reported values."""
    if not isinstance(value, dict) or value.get("analysis_id") != service.HOUSING_FILTER_ID:
        return value
    conditions = value.get("conditions")
    if not isinstance(conditions, (list, tuple)):
        return value
    return {
        **value,
        "conditions": sorted(
            conditions,
            key=lambda condition: json.dumps(
                condition, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            ),
        ),
    }


def _normalized_match(actual: Any, expected: Any) -> bool:
    return _normalized_housing_filter(actual) == _normalized_housing_filter(expected)


def _prepare(client: TestClient, cases: list[EconomicCase], fixtures: dict[str, dict]) -> dict[str, dict]:
    """Validate fixtures and human calculation expectations before any provider call."""
    references = {}
    checked = set()
    for case in cases:
        payload = _payload(case, fixtures)
        EconomicQuestionRequest.model_validate(payload)
        if case.fixture not in checked:
            for group, analysis_id in [("housing", service.HOUSING_ID), ("inflation", service.INFLATION_ID)]:
                if group in payload:
                    data = payload[group]
                    periods = [row["period"] for row in data["bddk_monthly" if group == "housing" else "cpi_monthly"]]
                    _reference(client, payload, analysis_id, min(periods), max(periods))
            checked.add(case.fixture)
        plan = case.expected_decision
        if isinstance(plan, service.EconomicReadyPlan):
            reference = _reference(client, payload, plan.analysis_id, plan.start_period, plan.end_period)
            evidence = reference["evidence"]
            if evidence["observed_month_count"] != case.expected_observed_month_count or (
                plan.analysis_id == service.HOUSING_ID
                and evidence["matched_periods"] != case.expected_matched_periods
            ):
                raise ValueError("Human evidence expectations disagree with the synthetic fixture.")
            references[case.id] = reference
        elif isinstance(plan, service.EconomicHousingFilterReadyPlan):
            reference = _filter_reference(payload, plan)
            if (
                reference["observed_month_count"] != case.expected_observed_month_count
                or list(reference["matched_periods"]) != case.expected_matched_periods
            ):
                raise ValueError("Human evidence expectations disagree with the synthetic fixture.")
            references[case.id] = reference
        elif isinstance(plan, service.EconomicComparisonReadyPlan):
            reference = _comparison_reference(payload, plan)
            expected = case.expected_comparison
            assert expected is not None
            years = reference["years"]
            counts = tuple(item["evidence"]["observed_month_count"] for item in years)
            december_rates = tuple(item["evidence"]["observations"][-1]["annual_inflation_pct"] for item in years)
            december_periods = tuple(item["evidence"]["observations"][-1]["period"] for item in years)
            if (
                [item["year"] for item in years] != [plan.first_year, plan.second_year]
                or december_periods != (f"{plan.first_year:04d}-12", f"{plan.second_year:04d}-12")
                or counts != expected.observed_month_counts
                or not all(_close(actual, wanted) for actual, wanted in zip(
                    december_rates, expected.december_annual_inflation_pct,
                ))
                or not _close(
                    reference["second_minus_first_december_annual_inflation_pp"],
                    expected.second_minus_first_december_annual_inflation_pp,
                )
            ):
                raise ValueError("Human comparison expectations disagree with the synthetic fixture.")
            references[case.id] = reference
    return references


def _check_analysis(reference: dict | None, body: dict, case: EconomicCase) -> str | None:
    plan = case.expected_decision
    analysis = body["analysis"]
    if isinstance(plan, service.EconomicComparisonReadyPlan):
        if analysis is None or analysis["analysis_id"] != plan.analysis_id:
            return "reference_or_analysis_mismatch"
        return None if analysis["evidence"] == reference else "evidence_mismatch"
    if isinstance(plan, service.EconomicHousingFilterReadyPlan):
        if analysis is None or analysis["analysis_id"] != plan.analysis_id:
            return "reference_or_analysis_mismatch"
        if not _normalized_match(analysis["evidence"], reference):
            return "evidence_mismatch"
        if analysis["evidence"]["observed_month_count"] != case.expected_observed_month_count:
            return "observation_count_mismatch"
        if list(analysis["evidence"]["matched_periods"]) != case.expected_matched_periods:
            return "housing_result_mismatch"
        return None
    if not isinstance(plan, service.EconomicReadyPlan):
        return None if analysis is None else "unexpected_analysis"
    housing = plan.analysis_id == service.HOUSING_ID
    if analysis is None or analysis["analysis_id"] != plan.analysis_id:
        return "reference_or_analysis_mismatch"
    if analysis["evidence"] != reference["evidence"]:
        return "evidence_mismatch"
    if analysis["evidence"]["observed_month_count"] != case.expected_observed_month_count:
        return "observation_count_mismatch"
    if housing and (
        analysis["chart"] != reference["chart"]
        or analysis["evidence"]["matched_periods"] != case.expected_matched_periods
    ):
        return "housing_result_mismatch"
    return None


def evaluate_cases(
    cases: list[EconomicCase], fixtures: dict[str, dict], *, live: bool = False,
    model_call: service.ModelCall | None = None, max_model_calls: int | None = None,
    model_name: str | None = None,
) -> dict:
    if not cases:
        raise ValueError("At least one selected case is required.")
    if live:
        if not callable(model_call) or type(max_model_calls) is not int or max_model_calls <= 0:
            raise ValueError("Live evaluation requires a callable and a positive total call budget.")
    elif model_call is not None or max_model_calls is not None:
        raise ValueError("Offline mode cannot receive a provider or live budget.")
    app = create_app()
    rows = []
    live_calls = 0
    stopped = None
    with (
        TestClient(app) as client,
        patch.object(service, "run_housing_analysis", wraps=service.run_housing_analysis) as housing,
        patch.object(service, "run_housing_filter", wraps=service.run_housing_filter) as housing_filter,
        patch.object(service, "build_inflation_evidence", wraps=service.build_inflation_evidence) as inflation,
        patch.object(service, "compare_inflation_years", wraps=service.compare_inflation_years) as comparison,
    ):
        references = _prepare(client, cases, fixtures)
        for case in cases:
            row = {
                "id": case.id, "question": case.question, "fixture": case.fixture,
                "expected_decision": case.expected_decision.model_dump(),
                "accepted_model_decisions": case.model_expectations(),
                "actual_decision": None, "actual_model_decision": None, "http_status": None,
                "model_decision_matches_expectation": None,
                "application_decision_matches_expectation": None,
                "python_blocked_ready_plan": False,
                "outcome": "skipped", "reason": stopped,
                "model_call_attempts": 0, "stub_calls": 0, "housing_calls": 0,
                "filter_calls": 0, "inflation_calls": 0, "comparison_calls": 0,
                "provider_error_code": None,
                "invalid_plan_diagnostics": None,
            }
            if live and (stopped or live_calls >= max_model_calls):
                row["reason"] = stopped or "budget_exhausted"
                rows.append(row)
                continue
            housing.reset_mock()
            housing_filter.reset_mock()
            inflation.reset_mock()
            comparison.reset_mock()
            model_calls = []
            actual_model_text = None
            limit_error = None
            provider_error_code = None
            attempts_before = live_calls

            def model(prompt):
                nonlocal live_calls, actual_model_text, limit_error, provider_error_code
                if live and (live_calls >= max_model_calls or model_calls):
                    limit_error = "model_call_limit_exceeded"
                    raise RuntimeError("Evaluation call limit reached.")
                model_calls.append(prompt)
                if live:
                    live_calls += 1  # Failed provider requests consume the budget too.
                    try:
                        actual_model_text = model_call(prompt)
                    except llm_client.LLMRequestError as exc:
                        if isinstance(exc.code, str) and exc.code in _SAFE_PROVIDER_ERROR_CODES:
                            provider_error_code = exc.code
                        raise
                else:
                    actual_model_text = json.dumps(case.offline_response, ensure_ascii=False)
                return actual_model_text

            app.dependency_overrides[get_economic_question_model] = lambda: model
            payload = _payload(case, fixtures)
            reason = None
            body = {}
            try:
                response = client.post(ENDPOINT, json=payload)
                body = response.json()
                row["http_status"] = response.status_code
                expected = case.expected_decision
                expected_json = expected.model_dump(mode="json")
                expected_status = "ok" if isinstance(
                    expected,
                    (
                        service.EconomicReadyPlan,
                        service.EconomicComparisonReadyPlan,
                        service.EconomicHousingFilterReadyPlan,
                    ),
                ) else expected.status
                if response.status_code == 200:
                    row["application_decision_matches_expectation"] = (
                        body.get("status") == expected_status
                        and _normalized_match(body.get("decision"), expected_json)
                    )
                if response.status_code == 502:
                    reason = "invalid_plan" if body["detail"]["code"] == "invalid_question_plan" else "model_call_failed"
                    if reason == "invalid_plan":
                        row["invalid_plan_diagnostics"] = _invalid_plan_diagnostics(actual_model_text)
                elif response.status_code != 200 or body.get("status") != expected_status:
                    reason = "status_mismatch"
                elif not _normalized_match(body["decision"], expected_json):
                    reason = "decision_mismatch"
                else:
                    reason = _check_analysis(references.get(case.id), body, case)
                if response.status_code == 200 and model_calls:
                    row["actual_model_decision"] = MODEL_DECISION.validate_json(actual_model_text).model_dump()
                    row["model_decision_matches_expectation"] = any(
                        _normalized_match(row["actual_model_decision"], accepted)
                        for accepted in row["accepted_model_decisions"]
                    )
                    row["python_blocked_ready_plan"] = (
                        row["actual_model_decision"]["status"] == "ready"
                        and body.get("status") != "ok"
                        and body.get("analysis") is None
                    )
                    if not row["model_decision_matches_expectation"]:
                        reason = reason or "model_decision_mismatch"
                expected_housing = int(
                    isinstance(expected, service.EconomicReadyPlan) and expected.analysis_id == service.HOUSING_ID
                )
                expected_filter = int(isinstance(expected, service.EconomicHousingFilterReadyPlan))
                expected_inflation = int(
                    isinstance(expected, service.EconomicReadyPlan) and expected.analysis_id == service.INFLATION_ID
                )
                expected_comparison = int(isinstance(expected, service.EconomicComparisonReadyPlan))
                if (
                    housing.call_count, housing_filter.call_count, inflation.call_count,
                    comparison.call_count,
                ) != (expected_housing, expected_filter, expected_inflation, expected_comparison):
                    reason = reason or "analysis_call_count_mismatch"
                if len(model_calls) != (0 if case.fixture == "none" else 1):
                    reason = reason or "planning_call_count_mismatch"
            except Exception:
                reason = "evaluation_error"
            reason = limit_error or reason
            row.update({
                "outcome": "passed" if reason is None else "failed", "reason": reason,
                "actual_decision": body.get("decision"),
                "model_call_attempts": live_calls - attempts_before,
                "stub_calls": 0 if live else len(model_calls),
                "housing_calls": housing.call_count, "inflation_calls": inflation.call_count,
                "filter_calls": housing_filter.call_count,
                "comparison_calls": comparison.call_count,
                "provider_error_code": provider_error_code,
            })
            rows.append(row)
            if live and reason is not None:
                stopped = "not_run_after_failure"
    return {
        "schema_version": "1.0", "mode": "live_model" if live else "offline_stub",
        "measurement": "selected_live_cases" if live else "harness_behavior_only",
        "synthetic_data": True, "model": model_name if live else None,
        "max_model_calls": max_model_calls,
        "retry_policy": "no_retries_stop_on_first_failure" if live else "no_provider_calls",
        "live_model_call_attempts": live_calls, "selected_case_ids": [case.id for case in cases],
        "selected_cases": len(rows), "passed_cases": sum(row["outcome"] == "passed" for row in rows),
        "failed_cases": sum(row["outcome"] == "failed" for row in rows),
        "skipped_cases": sum(row["outcome"] == "skipped" for row in rows),
        "all_selected_cases_passed": bool(rows) and all(row["outcome"] == "passed" for row in rows),
        "results": rows,
    }


def _source_revision() -> dict:
    """Identify the source tree without invoking a shell or printing file names."""
    try:
        root = Path(__file__).resolve().parents[1]
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True)
        status = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root,
                                capture_output=True, text=True, check=True)
        return {"source_commit": commit.stdout.strip(), "source_dirty": bool(status.stdout)}
    except (OSError, subprocess.CalledProcessError):
        return {"source_commit": None, "source_dirty": None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Konut/TÜFE soru değerlendirmesi; varsayılan offline")
    parser.add_argument("--live", action="store_true", help="Ayrı kullanıcı onayından sonra gerçek planlayıcı")
    parser.add_argument("--case", action="append", dest="case_ids", help="Tekrarlanabilir, sıralı vaka kimliği")
    parser.add_argument("--max-model-calls", type=int, help="Başarısız istekler dahil kesin toplam çağrı sınırı")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.live and (not args.case_ids or args.max_model_calls is None or args.max_model_calls <= 0):
        parser.error("--live açık --case seçimi ve pozitif --max-model-calls gerektirir.")
    if not args.live and args.max_model_calls is not None:
        parser.error("Çağrı bütçesi yalnız --live ile kullanılır.")
    try:
        output = (args.output or ROOT / f"out/economic-question-eval-{'live' if args.live else 'offline'}.json").resolve()
        output.relative_to((ROOT / "out").resolve())
        if output in {CASES_PATH.resolve(), *(path.resolve() for path in FIXTURES.values())}:
            raise ValueError("Reports must not overwrite evaluation inputs.")
        if output.exists():
            if args.live or json.loads(output.read_text(encoding="utf-8")).get("mode") != "offline_stub":
                raise ValueError("Do not overwrite live or unrelated reports.")
        case_bytes = CASES_PATH.read_bytes()
        cases = select_cases(EconomicSuite.model_validate_json(case_bytes).cases, args.case_ids)
        fixture_bytes = {key: path.read_bytes() for key, path in FIXTURES.items()}
        metadata = {**_source_revision(), "case_set_sha256": hashlib.sha256(case_bytes).hexdigest(),
                    "fixture_sha256": {key: hashlib.sha256(raw).hexdigest() for key, raw in fixture_bytes.items()},
                    "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        model_name = None
        if args.live:
            settings = llm_client.read_llm_settings()
            model_name = settings.chat_model.replace(settings.api_key, "[REDACTED]")
            metadata["llm_request_settings"] = {
                "timeout_seconds": settings.timeout_seconds,
                "reasoning_effort": settings.reasoning_effort,
                "max_retries": 0,
            }
        output.parent.mkdir(parents=True, exist_ok=True)
        # Reserve the output before spending calls; live reports are never overwritten.
        with output.open("x" if args.live else "w", encoding="utf-8") as stream:
            report = evaluate_cases(cases, {key: json.loads(raw) for key, raw in fixture_bytes.items()},
                live=args.live, model_call=llm_client.ask_llm if args.live else None,
                max_model_calls=args.max_model_calls, model_name=model_name)
            report.update(metadata)
            stream.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError, KeyError, llm_client.LLMConfigurationError):
        print("Değerlendirme girdileri veya out/ altındaki rapor konumu geçersiz.")
        return 2
    print(f"Mod: {report['mode']} / {report['measurement']}")
    for row in report["results"]:
        print(f"{row['id']}: {row['outcome']} ({row['reason'] or 'ok'})")
    print(f"Geçen={report['passed_cases']}/{report['selected_cases']}; "
          f"canlı çağrı denemesi={report['live_model_call_attempts']}; rapor={output}")
    return 0 if report["all_selected_cases_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

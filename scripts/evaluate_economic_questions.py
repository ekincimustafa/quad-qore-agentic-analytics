"""Offline HTTP harness checks, with explicitly selected and budgeted live plans."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Literal
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.api.economic_question import EconomicQuestionRequest, get_economic_question_model
from app.api.main import create_app
from app.connectors import llm_client
from app.services import economic_question as service


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals/economic_question_cases.json"
FIXTURES = {
    "both": ROOT / "docs/economic-question-api-example.json",
    "cpi_history": ROOT / "docs/economic-question-cpi-example.json",
}
ENDPOINT = "/analysis/economic/question"
MODEL_DECISION = TypeAdapter(service.ModelDecision)


class EconomicCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(pattern=r"^EQ-[0-9]{3}$")
    question: str = Field(min_length=1, max_length=2_000)
    fixture: Literal["both", "cpi_history", "housing_only", "none"] = "both"
    offline_response: dict[str, Any]
    expected_decision: service.EconomicDecision
    accepted_model_decisions: list[service.ModelDecision] | None = Field(default=None, min_length=1)
    rationale: str = ""
    expected_observed_month_count: int | None = Field(default=None, ge=1)
    expected_matched_periods: list[str] | None = None

    @model_validator(mode="after")
    def expectations(self) -> EconomicCase:
        if not self.question.strip():
            raise ValueError("Case question must not be blank.")
        ready = isinstance(self.expected_decision, service.EconomicReadyPlan)
        if ready != (self.expected_observed_month_count is not None):
            raise ValueError("Only ready cases need an observation count.")
        housing = ready and self.expected_decision.analysis_id == service.HOUSING_ID
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
    cases: list[EconomicCase] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_ids(self) -> EconomicSuite:
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Case IDs must be unique.")
        return self


def _payload(case: EconomicCase, fixtures: dict[str, dict]) -> dict:
    if case.fixture == "none":
        return {"question": case.question}
    payload = copy.deepcopy(fixtures["cpi_history" if case.fixture == "cpi_history" else "both"])
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
    return references


def _check_analysis(reference: dict | None, body: dict, case: EconomicCase) -> str | None:
    plan = case.expected_decision
    if not isinstance(plan, service.EconomicReadyPlan):
        return None if body["analysis"] is None else "unexpected_analysis"
    housing = plan.analysis_id == service.HOUSING_ID
    analysis = body["analysis"]
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
        patch.object(service, "build_inflation_evidence", wraps=service.build_inflation_evidence) as inflation,
    ):
        references = _prepare(client, cases, fixtures)
        for case in cases:
            row = {
                "id": case.id, "question": case.question, "fixture": case.fixture,
                "expected_decision": case.expected_decision.model_dump(),
                "accepted_model_decisions": case.model_expectations(),
                "actual_decision": None, "actual_model_decision": None, "http_status": None,
                "outcome": "skipped", "reason": stopped,
                "model_call_attempts": 0, "stub_calls": 0, "housing_calls": 0, "inflation_calls": 0,
            }
            if live and (stopped or live_calls >= max_model_calls):
                row["reason"] = stopped or "budget_exhausted"
                rows.append(row)
                continue
            housing.reset_mock()
            inflation.reset_mock()
            model_calls = []
            actual_model_text = None
            limit_error = None
            attempts_before = live_calls

            def model(prompt):
                nonlocal live_calls, actual_model_text, limit_error
                if live and (live_calls >= max_model_calls or model_calls):
                    limit_error = "model_call_limit_exceeded"
                    raise RuntimeError("Evaluation call limit reached.")
                model_calls.append(prompt)
                if live:
                    live_calls += 1  # Failed provider requests consume the budget too.
                    actual_model_text = model_call(prompt)
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
                expected_status = "ok" if isinstance(expected, service.EconomicReadyPlan) else expected.status
                if response.status_code == 502:
                    reason = "invalid_plan" if body["detail"]["code"] == "invalid_question_plan" else "model_call_failed"
                elif response.status_code != 200 or body.get("status") != expected_status:
                    reason = "status_mismatch"
                elif body["decision"] != expected.model_dump():
                    reason = "decision_mismatch"
                else:
                    reason = _check_analysis(references.get(case.id), body, case)
                if response.status_code == 200 and model_calls:
                    row["actual_model_decision"] = MODEL_DECISION.validate_json(actual_model_text).model_dump()
                    if row["actual_model_decision"] not in row["accepted_model_decisions"]:
                        reason = reason or "model_decision_mismatch"
                expected_calls = int(isinstance(expected, service.EconomicReadyPlan))
                if housing.call_count + inflation.call_count != expected_calls:
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

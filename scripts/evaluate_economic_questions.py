"""Offline HTTP evaluation of the bounded two-analysis harness; no live mode."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Literal
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.economic_question import get_economic_question_model
from app.api.main import create_app
from app.services import economic_question as service


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "evals/economic_question_cases.json"
FIXTURES = {
    "both": ROOT / "docs/economic-question-api-example.json",
    "cpi_history": ROOT / "docs/economic-question-cpi-example.json",
}
ENDPOINT = "/analysis/economic/question"


class EconomicCase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(pattern=r"^EQ-[0-9]{3}$")
    question: str = Field(min_length=1, max_length=2_000)
    fixture: Literal["both", "cpi_history", "housing_only", "none"] = "both"
    offline_response: dict[str, Any]
    expected_decision: service.EconomicDecision
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
        return self


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


def _check_analysis(client: TestClient, payload: dict, body: dict, case: EconomicCase) -> str | None:
    plan = case.expected_decision
    if not isinstance(plan, service.EconomicReadyPlan):
        return None if body["analysis"] is None else "unexpected_analysis"
    housing = plan.analysis_id == service.HOUSING_ID
    direct = client.post(
        "/analysis/housing" if housing else "/analysis/inflation",
        json={**payload["housing" if housing else "inflation"],
              "start_period": plan.start_period, "end_period": plan.end_period},
    )
    analysis = body["analysis"]
    if direct.status_code != 200 or analysis["analysis_id"] != plan.analysis_id:
        return "reference_or_analysis_mismatch"
    if analysis["evidence"] != direct.json()["evidence"]:
        return "evidence_mismatch"
    if analysis["evidence"]["observed_month_count"] != case.expected_observed_month_count:
        return "observation_count_mismatch"
    if housing and (
        analysis["chart"] != direct.json()["chart"]
        or analysis["evidence"]["matched_periods"] != case.expected_matched_periods
    ):
        return "housing_result_mismatch"
    return None


def evaluate_cases(cases: list[EconomicCase], fixtures: dict[str, dict]) -> dict:
    app = create_app()
    rows = []
    with (
        TestClient(app) as client,
        patch.object(service, "run_housing_analysis", wraps=service.run_housing_analysis) as housing,
        patch.object(service, "build_inflation_evidence", wraps=service.build_inflation_evidence) as inflation,
    ):
        for case in cases:
            housing.reset_mock()
            inflation.reset_mock()
            model_calls = []

            def model(prompt):
                model_calls.append(prompt)
                return json.dumps(case.offline_response, ensure_ascii=False)

            app.dependency_overrides[get_economic_question_model] = lambda: model
            payload = _payload(case, fixtures)
            reason = None
            body = {}
            try:
                response = client.post(ENDPOINT, json=payload)
                body = response.json()
                expected = case.expected_decision
                expected_status = "ok" if isinstance(expected, service.EconomicReadyPlan) else expected.status
                if response.status_code != 200 or body.get("status") != expected_status:
                    reason = "status_mismatch"
                elif body["decision"] != expected.model_dump():
                    reason = "decision_mismatch"
                else:
                    reason = _check_analysis(client, payload, body, case)
                expected_calls = int(isinstance(expected, service.EconomicReadyPlan))
                if housing.call_count + inflation.call_count != expected_calls:
                    reason = reason or "analysis_call_count_mismatch"
                if len(model_calls) != (0 if case.fixture == "none" else 1):
                    reason = reason or "planning_call_count_mismatch"
            except Exception:
                reason = "evaluation_error"
            rows.append({
                "id": case.id, "outcome": "passed" if reason is None else "failed", "reason": reason,
                "actual_decision": body.get("decision"), "stub_calls": len(model_calls),
                "housing_calls": housing.call_count, "inflation_calls": inflation.call_count,
            })
    return {
        "schema_version": "1.0", "mode": "offline_stub", "measurement": "harness_behavior_only",
        "synthetic_data": True, "live_model_call_attempts": 0,
        "selected_cases": len(rows), "passed_cases": sum(row["outcome"] == "passed" for row in rows),
        "all_selected_cases_passed": bool(rows) and all(row["outcome"] == "passed" for row in rows),
        "results": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Konut/TÜFE soru API'sinin offline stub değerlendirmesi")
    parser.add_argument("--output", type=Path, default=ROOT / "out/economic-question-eval-offline.json")
    args = parser.parse_args(argv)
    try:
        output = args.output.resolve()
        output.relative_to((ROOT / "out").resolve())
        if output in {CASES_PATH.resolve(), *(path.resolve() for path in FIXTURES.values())}:
            raise ValueError("Reports must not overwrite evaluation inputs.")
        case_bytes = CASES_PATH.read_bytes()
        cases = EconomicSuite.model_validate_json(case_bytes).cases
        fixture_bytes = {key: path.read_bytes() for key, path in FIXTURES.items()}
        report = evaluate_cases(cases, {key: json.loads(raw) for key, raw in fixture_bytes.items()})
        report["case_set_sha256"] = hashlib.sha256(case_bytes).hexdigest()
        report["fixture_sha256"] = {key: hashlib.sha256(raw).hexdigest() for key, raw in fixture_bytes.items()}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError):
        print("Değerlendirme girdileri veya out/ altındaki rapor konumu geçersiz.")
        return 2
    print(f"Mod: {report['mode']} / {report['measurement']}")
    for row in report["results"]:
        print(f"{row['id']}: {row['outcome']} ({row['reason'] or 'ok'})")
    print(f"Geçen={report['passed_cases']}/{report['selected_cases']}; canlı çağrı=0; rapor={output}")
    return 0 if report["all_selected_cases_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

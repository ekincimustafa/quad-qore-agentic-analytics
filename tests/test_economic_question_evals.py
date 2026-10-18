"""The offline evaluation command measures harness behavior and exposes failures."""

import json

import httpx
import pytest

from app.connectors import llm_client
from scripts import evaluate_economic_questions as evaluator


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No live HTTP/model/settings access is allowed")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(llm_client, "ask_llm", forbidden)
    monkeypatch.setattr(llm_client, "read_llm_settings", forbidden)


def test_offline_command_runs_curated_cases_and_counts_only_question_executions(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    report_path = tmp_path / "out/report.json"
    assert evaluator.main(["--output", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["measurement"] == "harness_behavior_only"
    assert report["live_model_call_attempts"] == 0
    assert report["passed_cases"] == report["selected_cases"] == 12
    assert sum(row["stub_calls"] for row in report["results"]) == 11
    assert sum(row["housing_calls"] for row in report["results"]) == 1
    assert sum(row["inflation_calls"] for row in report["results"]) == 2
    assert report["case_set_sha256"] and len(report["fixture_sha256"]) == 2


def test_valid_but_wrong_stub_plan_makes_command_fail(tmp_path, monkeypatch):
    suite = json.loads(evaluator.CASES_PATH.read_text(encoding="utf-8"))
    case = suite["cases"][6]
    case["offline_response"] = suite["cases"][0]["offline_response"]
    case_path = tmp_path / "cases.json"
    case_path.write_text(json.dumps({"schema_version": "1.0", "cases": [case]}), encoding="utf-8")
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    monkeypatch.setattr(evaluator, "CASES_PATH", case_path)
    report_path = tmp_path / "out/report.json"
    assert evaluator.main(["--output", str(report_path)]) == 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert not report["all_selected_cases_passed"]
    assert report["results"][0]["reason"] == "status_mismatch"
    assert report["results"][0]["housing_calls"] == 1


def test_report_cannot_overwrite_case_inputs():
    before = evaluator.CASES_PATH.read_bytes()
    assert evaluator.main(["--output", str(evaluator.CASES_PATH)]) == 2
    assert evaluator.CASES_PATH.read_bytes() == before


def test_command_does_not_offer_live_mode():
    with pytest.raises(SystemExit) as error:
        evaluator.main(["--live"])
    assert error.value.code == 2

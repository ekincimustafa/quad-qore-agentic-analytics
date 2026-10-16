"""Test evaluator failures as well as success; no real model is contacted."""

import json
from types import SimpleNamespace

import httpx
import pytest

from app.connectors.llm_client import LLMConfigurationError
from scripts import evaluate_housing_questions as evaluator


@pytest.fixture(autouse=True)
def no_real_model(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No provider/network/settings access in offline tests")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(evaluator, "ask_llm", forbidden)
    monkeypatch.setattr(evaluator, "read_llm_settings", forbidden)


@pytest.fixture
def cases():
    return evaluator.load_cases()


@pytest.fixture
def payload():
    return json.loads(evaluator.FIXTURE_PATH.read_text(encoding="utf-8"))


def stub_for(cases, calls):
    answers = {case.question: case.offline_response for case in cases}

    def call(prompt):
        calls.append(prompt)
        request = json.loads(prompt.split("İSTEK_VERİSİ:\n", 1)[1])
        return json.dumps(answers[request["question"]])

    return call


def test_offline_command_runs_all_cases_without_key_or_network(tmp_path, capsys):
    path = tmp_path / "offline.json"
    assert evaluator.main(["--output", str(path)]) == 0
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["mode"] == "offline_stub"
    assert report["measurement"] == "harness_behavior_only"
    assert report["selected_cases"] == report["passed_cases"] == 9
    assert report["executed_cases"] == report["stub_calls"] == 9
    assert report["live_model_call_attempts"] == 0 and report["model"] is None
    assert report["failed_cases"] == report["skipped_cases"] == 0
    assert len(report["case_set_sha256"]) == len(report["fixture_sha256"]) == 64
    assert "harness_behavior_only" in capsys.readouterr().out
    assert report["results"][0]["evidence_summary"]["matched_periods"] == ["2021-02"]


def test_injected_live_mode_checks_all_decisions_and_limits_calls(cases, payload):
    calls = []
    report = evaluator.evaluate_cases(
        cases, payload, live=True, model_call=stub_for(cases, calls),
        max_model_calls=len(cases), model_name="test-model",
    )
    assert report["all_selected_cases_passed"]
    assert report["mode"] == "live_model" and report["model"] == "test-model"
    assert report["passed_cases"] == report["live_model_call_attempts"] == len(cases)
    assert report["stub_calls"] == 0 and len(calls) == len(cases)


def test_valid_but_wrong_period_fails_evaluation(cases, payload):
    wrong = dict(cases[0].offline_response, start_period="2021-02")
    report = evaluator.evaluate_cases(
        cases[:1], payload, live=True, model_call=lambda _: json.dumps(wrong), max_model_calls=1,
    )
    assert report["failed_cases"] == 1 and not report["all_selected_cases_passed"]
    assert report["results"][0]["reason"] == "decision_mismatch"


@pytest.mark.parametrize("response", [
    "not JSON private-key",
    '{"status":"ready","analysis_id":"web_search","start_period":"2021-01","end_period":"2021-03"}',
    '{"status":"ready","analysis_id":"housing_rate_down_real_credit_not_up","start_period":"2021-01","end_period":"2021-03","sql":"private-key"}',
])
def test_invalid_model_output_is_failure_without_raw_body(cases, payload, response):
    report = evaluator.evaluate_cases(
        cases[:1], payload, live=True, model_call=lambda _: response, max_model_calls=1,
    )
    assert report["failed_cases"] == 1
    assert report["results"][0]["reason"] == "invalid_plan"
    assert "private-key" not in json.dumps(report)


def test_model_call_failure_stops_remaining_live_cases(cases, payload):
    calls = []

    def fail(prompt):
        calls.append(prompt)
        raise RuntimeError("private-key secret-provider-body")

    report = evaluator.evaluate_cases(
        cases[:3], payload, live=True, model_call=fail, max_model_calls=3,
    )
    assert len(calls) == report["live_model_call_attempts"] == 1
    assert report["executed_cases"] == report["failed_cases"] == 1
    assert report["skipped_cases"] == 2 and not report["all_selected_cases_passed"]
    assert report["results"][0]["reason"] == "model_call_failed"
    assert all(row["reason"] == "not_run_after_model_call_failure" for row in report["results"][1:])
    assert "private-key" not in json.dumps(report) and "secret-provider-body" not in json.dumps(report)


def test_insufficient_budget_is_rejected_before_model_call(cases, payload):
    calls = []
    with pytest.raises(ValueError, match="budget"):
        evaluator.evaluate_cases(
            cases[:3], payload, live=True, model_call=lambda p: calls.append(p), max_model_calls=2,
        )
    assert calls == []


def test_offline_mode_rejects_live_callable(cases, payload):
    with pytest.raises(ValueError, match="Offline"):
        evaluator.evaluate_cases(cases, payload, model_call=lambda _: "must not run")


def test_hard_budget_still_holds_if_harness_attempts_an_extra_call(monkeypatch, cases, payload):
    original = evaluator.run_housing_question
    calls = []

    def double_call(*args, **kwargs):
        kwargs["model_call"]("extra call")
        return original(*args, **kwargs)

    def model(prompt):
        calls.append(prompt)
        return json.dumps(cases[0].offline_response)

    monkeypatch.setattr(evaluator, "run_housing_question", double_call)
    report = evaluator.evaluate_cases(
        cases[:1], payload, live=True, model_call=model, max_model_calls=1,
    )
    assert len(calls) == report["live_model_call_attempts"] == 1
    assert report["failed_cases"] == 1 and not report["all_selected_cases_passed"]


def test_wrong_fixture_expectation_fails_before_model_call(cases, payload):
    bad_case = cases[0].model_copy(update={"expected_matched_periods": ["2021-03"]})
    calls = []
    with pytest.raises(ValueError, match="expectations"):
        evaluator.evaluate_cases(
            [bad_case], payload, live=True, model_call=lambda p: calls.append(p), max_model_calls=1,
        )
    assert calls == []


def test_changed_chart_is_not_reported_as_success(monkeypatch, cases, payload):
    original = evaluator.run_housing_question

    def altered(*args, **kwargs):
        result = original(*args, **kwargs)
        result.analysis.chart["data"][0]["name"] = "altered trace"
        return result

    monkeypatch.setattr(evaluator, "run_housing_question", altered)
    report = evaluator.evaluate_cases(cases[:1], payload)
    assert report["failed_cases"] == 1
    assert report["results"][0]["reason"] == "chart_mismatch"


@pytest.mark.parametrize("args", [
    ["--live"], ["--live", "--max-model-calls", "1"],
    ["--max-model-calls", "9"],
])
def test_bad_cli_budget_never_reads_settings(args):
    with pytest.raises(SystemExit) as error:
        evaluator.main(args)
    assert error.value.code == 2


@pytest.mark.parametrize("ids", [["HQ-999"], ["HQ-001", "HQ-001"]])
def test_invalid_case_selection_is_rejected(cases, ids):
    with pytest.raises(ValueError):
        evaluator.select_cases(cases, ids)


def test_input_file_cannot_be_overwritten():
    with pytest.raises(SystemExit) as error:
        evaluator.main(["--output", str(evaluator.CASES_PATH)])
    assert error.value.code == 2


def test_live_cli_records_model_safely_and_returns_nonzero_for_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(evaluator, "read_llm_settings", lambda: SimpleNamespace(
        api_key="private-key", chat_model="test/private-key",
    ))
    monkeypatch.setattr(evaluator, "ask_llm", lambda _: "private-key invalid JSON")
    path = tmp_path / "live.json"
    code = evaluator.main([
        "--live", "--max-model-calls", "1", "--case", "HQ-001", "--output", str(path),
    ])
    report = json.loads(path.read_text(encoding="utf-8"))
    assert code == 1 and report["failed_cases"] == 1
    assert report["model"] == "test/[REDACTED]"
    assert "private-key" not in path.read_text(encoding="utf-8")


def test_live_configuration_failure_does_not_contact_model(monkeypatch, tmp_path):
    def fail():
        raise LLMConfigurationError("LLM_API_KEY boş bırakılamaz.")
    monkeypatch.setattr(evaluator, "read_llm_settings", fail)
    path = tmp_path / "live.json"
    assert evaluator.main([
        "--live", "--max-model-calls", "1", "--case", "HQ-001", "--output", str(path),
    ]) == 2
    assert not path.exists()

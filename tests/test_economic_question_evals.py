"""Offline harness and selected live-mode control flow; providers are always fake."""

import json

import httpx
import pytest

from app.connectors import llm_client
from scripts import evaluate_economic_questions as evaluator
from tests.test_llm_client import _mock_provider, _response


REAL_ASK = llm_client.ask_llm
REAL_SETTINGS = llm_client.read_llm_settings


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
    assert report["passed_cases"] == report["selected_cases"] == 28
    assert sum(row["stub_calls"] for row in report["results"]) == 27
    assert sum(row["housing_calls"] for row in report["results"]) == 4
    assert sum(row["inflation_calls"] for row in report["results"]) == 5
    assert report["case_set_sha256"] and len(report["fixture_sha256"]) == 2
    assert report["source_commit"] and report["evaluator_sha256"]
    assert report["results"][0]["expected_decision"] == report["results"][0]["actual_decision"]


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
    assert report["results"][0]["housing_calls"] == 0
    assert report["results"][0]["python_blocked_ready_plan"] is True
    assert report["results"][0]["model_decision_matches_expectation"] is False


def test_report_cannot_overwrite_case_inputs():
    before = evaluator.CASES_PATH.read_bytes()
    assert evaluator.main(["--output", str(evaluator.CASES_PATH)]) == 2
    assert evaluator.CASES_PATH.read_bytes() == before


@pytest.mark.parametrize("args", [
    ["--live"], ["--live", "--max-model-calls", "1"],
    ["--live", "--case", "EQ-013"],
    ["--live", "--case", "EQ-013", "--max-model-calls", "0"],
    ["--live", "--case", "EQ-013", "--max-model-calls", "-1"],
    ["--max-model-calls", "2"],
])
def test_cli_requires_explicit_selection_and_positive_live_budget_before_settings(args):
    with pytest.raises(SystemExit) as error:
        evaluator.main(args)
    assert error.value.code == 2


@pytest.fixture
def cases():
    return evaluator.EconomicSuite.model_validate_json(evaluator.CASES_PATH.read_bytes()).cases


@pytest.fixture
def fixtures():
    return {name: json.loads(path.read_text(encoding="utf-8")) for name, path in evaluator.FIXTURES.items()}


@pytest.fixture
def fake_provider(monkeypatch):
    """Use the existing SDK mock helper; never read local keys or reach the network."""
    monkeypatch.setattr(llm_client, "ask_llm", REAL_ASK)
    monkeypatch.setattr(llm_client, "read_llm_settings", REAL_SETTINGS)
    monkeypatch.setattr(llm_client, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "5")
    return lambda handler: _mock_provider(monkeypatch, handler)


def answers_for(cases):
    answers = {case.question: case.offline_response for case in cases}

    def handler(request):
        prompt = json.loads(request.content)["messages"][0]["content"]
        question = json.loads(prompt.split("İSTEK_VERİSİ:\n", 1)[1])["question"]
        return _response(json.dumps(answers[question], ensure_ascii=False))
    return handler


def test_live_cli_with_fake_sdk_provider_selects_cases_in_order_and_records_attempts(
    tmp_path, monkeypatch, cases, fake_provider,
):
    selected = evaluator.select_cases(cases, ["EQ-016", "EQ-013", "EQ-020", "EQ-025"])
    requests, clients, options = fake_provider(answers_for(selected))
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    args = ["--live", "--max-model-calls", "4"]
    for case in selected:
        args.extend(["--case", case.id])
    assert evaluator.main(args) == 0
    report = json.loads((tmp_path / "out/economic-question-eval-live.json").read_text(encoding="utf-8"))
    assert report["mode"] == "live_model" and report["measurement"] == "selected_live_cases"
    assert report["synthetic_data"] and report["model"] == "test-model"
    assert report["selected_case_ids"] == [case.id for case in selected]
    assert len(requests) == report["live_model_call_attempts"] == 4
    assert all(option["max_retries"] == 0 for option in options)
    assert all(client.is_closed() for client in clients)
    assert report["passed_cases"] == 4 and report["failed_cases"] == report["skipped_cases"] == 0
    assert all(row["model_call_attempts"] == 1 and row["stub_calls"] == 0 for row in report["results"])
    assert all(row["actual_model_decision"] in row["accepted_model_decisions"] for row in report["results"])
    assert all(row["model_decision_matches_expectation"] is True
               and row["application_decision_matches_expectation"] is True
               and row["python_blocked_ready_plan"] is False for row in report["results"])
    assert "private-test-key" not in json.dumps(report)
    assert not (tmp_path / "out/economic-question-eval-offline.json").exists()


def test_budget_exhaustion_skips_remaining_cases_without_request(cases, fixtures, fake_provider):
    selected = cases[:3]
    requests, _, _ = fake_provider(answers_for(selected))
    report = evaluator.evaluate_cases(selected, fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=1)
    assert len(requests) == report["live_model_call_attempts"] == report["passed_cases"] == 1
    assert report["skipped_cases"] == 2 and not report["all_selected_cases_passed"]
    assert all(row["reason"] == "budget_exhausted" and row["model_call_attempts"] == 0
               for row in report["results"][1:])


@pytest.mark.parametrize("status", [429, 503])
def test_provider_failure_is_counted_and_stops_without_retry_or_secret(
    cases, fixtures, fake_provider, status,
):
    requests, _, options = fake_provider(lambda request: httpx.Response(status, json={
        "error": {"message": "private-test-key secret-upstream-body"},
    }))
    report = evaluator.evaluate_cases(cases[:3], fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=3)
    assert len(requests) == report["live_model_call_attempts"] == 1
    assert options[0]["max_retries"] == 0
    assert report["failed_cases"] == 1 and report["skipped_cases"] == 2
    assert report["results"][0]["reason"] == "model_call_failed"
    assert report["results"][0]["http_status"] == 502
    assert all(row["reason"] == "not_run_after_failure" for row in report["results"][1:])
    assert "private-test-key" not in json.dumps(report) and "secret-upstream-body" not in json.dumps(report)


@pytest.mark.parametrize("kind", ["invalid", "wrong_period", "wrong_analysis", "wrong_outside_period"])
def test_invalid_or_schema_valid_wrong_plan_fails_and_stops(cases, fixtures, fake_provider, kind):
    selected = evaluator.select_cases(cases, ["EQ-006", "EQ-013"]) if kind == "wrong_outside_period" else cases[:2]
    answer = dict(selected[0].offline_response)
    if kind == "wrong_period":
        answer["start_period"] = "2021-02"
    elif kind == "wrong_analysis":
        answer["analysis_id"] = "cpi_inflation_summary"
    elif kind == "wrong_outside_period":
        answer["start_period"] = "2019-01"  # Same outside_coverage result, wrong raw plan.
    content = 'not JSON private-test-key' if kind == "invalid" else json.dumps(answer)
    requests, _, _ = fake_provider(lambda request: _response(content))
    report = evaluator.evaluate_cases(selected, fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=2)
    assert len(requests) == report["live_model_call_attempts"] == 1
    assert report["failed_cases"] == report["skipped_cases"] == 1
    assert report["results"][0]["reason"] == {
        "invalid": "invalid_plan", "wrong_period": "status_mismatch",
        "wrong_analysis": "decision_mismatch", "wrong_outside_period": "decision_mismatch",
    }[kind]
    assert report["results"][1]["reason"] == "not_run_after_failure"
    assert "private-test-key" not in json.dumps(report)


def test_safe_outside_clarification_is_accepted_without_forcing_a_ready_plan(cases, fixtures):
    selected = evaluator.select_cases(cases, ["EQ-006"])
    report = evaluator.evaluate_cases(selected, fixtures, live=True, max_model_calls=1,
        model_call=lambda _: json.dumps({"status": "clarification_required", "reason": "outside_coverage"}))
    assert report["all_selected_cases_passed"]
    assert report["results"][0]["housing_calls"] == report["results"][0]["inflation_calls"] == 0


@pytest.mark.parametrize("case_id,reason,analysis_id", [
    ("EQ-020", "period_required", "cpi_inflation_summary"),
    ("EQ-022", "metric_ambiguous", "housing_rate_down_real_credit_not_up"),
])
def test_observed_ambiguous_ready_plan_is_blocked_but_model_still_fails_offline(
    cases, fixtures, fake_provider, case_id, reason, analysis_id,
):
    """Replay both observed mistakes through HTTP with a fake SDK provider."""
    selected = evaluator.select_cases(cases, [case_id, "EQ-010"])
    observed = {"status": "ready", "analysis_id": analysis_id,
                "start_period": "2021-01", "end_period": "2021-03"}
    requests, _, _ = fake_provider(lambda request: _response(json.dumps(observed)))
    report = evaluator.evaluate_cases(selected, fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=2)
    row = report["results"][0]
    assert len(requests) == report["live_model_call_attempts"] == 1
    assert row["expected_decision"] == {"status": "clarification_required", "reason": reason}
    assert row["actual_model_decision"] == observed
    assert row["actual_decision"] == row["expected_decision"]
    assert row["model_decision_matches_expectation"] is False
    assert row["application_decision_matches_expectation"] is True
    assert row["python_blocked_ready_plan"] is True
    assert row["outcome"] == "failed" and row["reason"] == "model_decision_mismatch"
    assert row["housing_calls"] == row["inflation_calls"] == 0
    assert report["results"][1]["outcome"] == "skipped"
    assert report["results"][1]["reason"] == "not_run_after_failure"


def test_open_ended_month_ready_plan_reports_model_failure_and_python_block(
    cases, fixtures, fake_provider,
):
    base = evaluator.select_cases(cases, ["EQ-028"])[0]
    case = base.model_copy(update={
        "question": "2021 Ocak ayından itibaren TÜFE değişimlerini göster.",
    })
    observed = {
        "status": "ready",
        "analysis_id": "cpi_inflation_summary",
        "start_period": "2021-01",
        "end_period": "2021-01",
    }
    requests, _, _ = fake_provider(lambda request: _response(json.dumps(observed)))

    report = evaluator.evaluate_cases(
        [case], fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=1,
    )

    row = report["results"][0]
    assert len(requests) == report["live_model_call_attempts"] == 1
    assert row["actual_model_decision"] == observed
    assert row["actual_decision"] == row["expected_decision"]
    assert row["model_decision_matches_expectation"] is False
    assert row["application_decision_matches_expectation"] is True
    assert row["python_blocked_ready_plan"] is True
    assert row["outcome"] == "failed" and row["reason"] == "model_decision_mismatch"
    assert row["housing_calls"] == row["inflation_calls"] == 0


@pytest.mark.parametrize("budget", [1, 2])
def test_hard_limit_blocks_a_second_planner_invocation(cases, fixtures, monkeypatch, budget):
    original = evaluator.service.run_economic_question
    calls = []

    def double_call(*args, **kwargs):
        kwargs["model_call"]("extra")
        return original(*args, **kwargs)

    from app.api import economic_question as api
    monkeypatch.setattr(api, "run_economic_question", double_call)

    def model(prompt):
        calls.append(prompt)
        return json.dumps(cases[0].offline_response)

    report = evaluator.evaluate_cases(cases[:1], fixtures, live=True, model_call=model, max_model_calls=budget)
    assert len(calls) == report["live_model_call_attempts"] == 1
    assert report["results"][0]["reason"] == "model_call_limit_exceeded"


def test_calculation_drift_stops_before_next_provider_call(cases, fixtures, fake_provider, monkeypatch):
    from dataclasses import replace

    original = evaluator.service.run_housing_analysis

    def altered(*args, **kwargs):
        result = original(*args, **kwargs)
        chart = json.loads(json.dumps(result.chart))
        chart["data"][0]["name"] = "changed"
        return replace(result, chart=chart)

    monkeypatch.setattr(evaluator.service, "run_housing_analysis", altered)
    requests, _, _ = fake_provider(answers_for(cases[:2]))
    report = evaluator.evaluate_cases(cases[:2], fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=2)
    assert len(requests) == report["live_model_call_attempts"] == 1
    assert report["results"][0]["reason"] == "housing_result_mismatch"
    assert report["results"][1]["reason"] == "not_run_after_failure"


def test_bad_fixture_expectation_spends_no_provider_calls(cases, fixtures):
    bad = cases[0].model_copy(update={"expected_matched_periods": ["2021-03"]})
    calls = []
    with pytest.raises(ValueError, match="expectations"):
        evaluator.evaluate_cases([bad], fixtures, live=True,
            model_call=lambda prompt: calls.append(prompt), max_model_calls=1)
    assert not calls


@pytest.mark.parametrize("ids", [["EQ-999"], ["EQ-001", "EQ-001"]])
def test_bad_selection_never_contacts_or_configures_provider(ids, tmp_path, monkeypatch):
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    args = ["--live", "--max-model-calls", "2"]
    for case_id in ids:
        args.extend(["--case", case_id])
    assert evaluator.main(args) == 2


def test_live_report_is_not_overwritten_before_provider_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    path = tmp_path / "out/economic-question-eval-live.json"
    path.parent.mkdir()
    path.write_text('{"mode":"live_model","preserved":true}', encoding="utf-8")
    before = path.read_bytes()
    assert evaluator.main(["--live", "--case", "EQ-013", "--max-model-calls", "1"]) == 2
    assert evaluator.main(["--output", str(path)]) == 2
    assert path.read_bytes() == before


def test_offline_cannot_receive_provider(cases, fixtures):
    with pytest.raises(ValueError, match="Offline"):
        evaluator.evaluate_cases(cases, fixtures, model_call=lambda _: "forbidden")

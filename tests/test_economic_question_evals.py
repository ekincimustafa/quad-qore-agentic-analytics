"""Offline harness and selected live-mode control flow; providers are always fake."""

import copy
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
    assert report["passed_cases"] == report["selected_cases"] == 45
    assert sum(row["stub_calls"] for row in report["results"]) == 44
    assert sum(row["housing_calls"] for row in report["results"]) == 4
    assert sum(row["filter_calls"] for row in report["results"]) == 5
    assert sum(row["inflation_calls"] for row in report["results"]) == 5
    assert sum(row["comparison_calls"] for row in report["results"]) == 3
    assert report["case_set_sha256"] and len(report["fixture_sha256"]) == 5
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


def test_wrong_filter_threshold_is_blocked_without_a_filter_call(tmp_path, monkeypatch):
    suite = json.loads(evaluator.CASES_PATH.read_text(encoding="utf-8"))
    case = next(item for item in suite["cases"] if item["id"] == "EQ-025")
    case["offline_response"]["conditions"][1]["threshold"] = 1.0
    case_path = tmp_path / "cases.json"
    case_path.write_text(json.dumps({"schema_version": "1.0", "cases": [case]}), encoding="utf-8")
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    monkeypatch.setattr(evaluator, "CASES_PATH", case_path)
    report_path = tmp_path / "out/report.json"
    assert evaluator.main(["--output", str(report_path)]) == 1
    row = json.loads(report_path.read_text(encoding="utf-8"))["results"][0]
    assert row["reason"] == "status_mismatch"
    assert row["filter_calls"] == 0
    assert row["python_blocked_ready_plan"] is True
    assert row["model_decision_matches_expectation"] is False


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
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    return lambda handler: _mock_provider(monkeypatch, handler)


def test_live_report_records_effective_options_without_secrets(tmp_path, monkeypatch, cases, fake_provider):
    requests, _, _ = fake_provider(answers_for(cases))
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    output = tmp_path / "out/options.json"
    assert evaluator.main([
        "--live", "--case", "EQ-043", "--max-model-calls", "1", "--output", str(output),
    ]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["llm_request_settings"] == {
        "timeout_seconds": 5.0, "reasoning_effort": "low", "max_retries": 0,
        "response_format": "json_schema",
    }
    assert len(requests) == 1
    assert json.loads(requests[0].content)["reasoning_effort"] == "low"
    assert json.loads(requests[0].content)["response_format"]["type"] == "json_schema"
    assert "private-test-key" not in output.read_text(encoding="utf-8")


def answers_for(cases):
    answers = {case.question: case.offline_response for case in cases}

    def handler(request):
        prompt = json.loads(request.content)["messages"][0]["content"]
        question = json.loads(prompt.split("İSTEK_VERİSİ:\n", 1)[1])["question"]
        answer = {key: None for key in evaluator.service.EconomicModelResponse.model_fields}
        answer.update(answers[question])
        return _response(json.dumps(answer, ensure_ascii=False))
    return handler


_FILTER_METRICS = (
    "interest_rate_change_pp",
    "real_housing_loan_change_pct",
    "nominal_housing_loan_change_pct",
    "housing_loan_interest_rate_pct",
)


def _mutated_filter_response(response, kind):
    answer = copy.deepcopy(response)
    conditions = answer["conditions"]
    if kind == "wrong_direction":
        conditions[0]["operator"] = "lt" if conditions[0]["operator"] in {"gt", "gte"} else "gt"
    elif kind == "wrong_threshold":
        conditions[0]["threshold"] += 1.0
    elif kind == "wrong_metric":
        used = {condition["metric"] for condition in conditions}
        conditions[0]["metric"] = next(metric for metric in _FILTER_METRICS if metric not in used)
    elif kind == "missing":
        conditions.pop()
    elif kind == "extra":
        used = {condition["metric"] for condition in conditions}
        conditions.append({
            "metric": next(metric for metric in _FILTER_METRICS if metric not in used),
            "operator": "lt",
            "threshold": 100.0,
        })
    elif kind == "duplicate":
        conditions.append(copy.deepcopy(conditions[0]))
    else:
        raise AssertionError(f"Unknown mutation: {kind}")
    return answer


def test_live_cli_with_fake_sdk_provider_selects_cases_in_order_and_records_attempts(
    tmp_path, monkeypatch, cases, fake_provider,
):
    selected = evaluator.select_cases(cases, ["EQ-016", "EQ-013", "EQ-020", "EQ-025", "EQ-029", "EQ-038", "EQ-010"])
    requests, clients, options = fake_provider(answers_for(selected))
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    args = ["--live", "--max-model-calls", "7"]
    for case in selected:
        args.extend(["--case", case.id])
    assert evaluator.main(args) == 0
    report = json.loads((tmp_path / "out/economic-question-eval-live.json").read_text(encoding="utf-8"))
    assert report["mode"] == "live_model" and report["measurement"] == "selected_live_cases"
    assert report["synthetic_data"] and report["model"] == "test-model"
    assert report["selected_case_ids"] == [case.id for case in selected]
    assert len(requests) == report["live_model_call_attempts"] == 7
    assert all(option["max_retries"] == 0 for option in options)
    assert all(client.is_closed() for client in clients)
    assert report["passed_cases"] == 7 and report["failed_cases"] == report["skipped_cases"] == 0
    assert all("anyOf" not in json.loads(req.content)["response_format"]["json_schema"]["schema"] for req in requests)
    assert all(row["model_call_attempts"] == 1 and row["stub_calls"] == 0 for row in report["results"])
    assert all(row["provider_error_code"] is None for row in report["results"])
    assert all(row["actual_model_decision"] in row["accepted_model_decisions"] for row in report["results"])
    assert all(row["model_decision_matches_expectation"] is True
               and row["application_decision_matches_expectation"] is True
               and row["python_blocked_ready_plan"] is False for row in report["results"])
    assert "private-test-key" not in json.dumps(report)
    assert not (tmp_path / "out/economic-question-eval-offline.json").exists()


@pytest.mark.parametrize("provider_decision", ["ready", "observed_clarification"])
def test_compact_comparison_prompt_keeps_wire_schema_and_honest_failure_reporting(
    cases, fixtures, fake_provider, provider_decision,
):
    # Existing independent oracles, different natural wording. Stub responses
    # check the harness, never model understanding.
    questions = [
        "2023 ve 2024 yıllarının TÜFE aylık ve yıllık değişimlerini karşılaştır.",
        "2024 ile 2023 tam takvim yıllarındaki aylık ve yıllık TÜFE değişimlerini kıyasla.",
    ]
    selected = [
        case.model_copy(update={"question": question})
        for case, question in zip(evaluator.select_cases(cases, ["EQ-029", "EQ-030"]), questions)
    ]
    plans = {case.question: case.offline_response for case in selected}
    observed = {"status": "clarification_required", "reason": "question_ambiguous"}

    def provider(request):
        message = json.loads(request.content)["messages"][0]["content"]
        question = json.loads(message.split("İSTEK_VERİSİ:\n", 1)[1])["question"]
        envelope = {key: None for key in evaluator.service.EconomicModelResponse.model_fields}
        envelope.update(observed if provider_decision == "observed_clarification" else plans[question])
        return _response(json.dumps(envelope))

    requests, clients, options = fake_provider(provider)
    report = evaluator.evaluate_cases(
        selected, fixtures, live=True,
        model_call=evaluator.service.ask_economic_plan, max_model_calls=2,
    )
    expected_calls = 2 if provider_decision == "ready" else 1
    assert len(requests) == report["live_model_call_attempts"] == expected_calls
    assert all(option["max_retries"] == 0 for option in options)
    assert all(client.is_closed() for client in clients)
    for request in requests:
        body = json.loads(request.content)
        contract = body["response_format"]["json_schema"]
        assert body["response_format"]["type"] == "json_schema" and contract["strict"] is True
        assert contract["schema"] == evaluator.service.EconomicModelResponse.model_json_schema()
        instructions, payload = body["messages"][0]["content"].split("İSTEK_VERİSİ:\n", 1)
        assert json.loads(payload)["question"] in questions
        # The full schema stays in response_format, without a second schema in
        # the message. Human-readable field and analysis instructions remain.
        assert '"$defs"' not in instructions and '"properties"' not in instructions
        assert all(field in instructions for field in contract["schema"]["required"])
        assert all(analysis in instructions for analysis in (
            evaluator.service.HOUSING_ID, evaluator.service.HOUSING_FILTER_ID,
            evaluator.service.INFLATION_ID, evaluator.service.COMPARISON_ID,
        ))
    if provider_decision == "ready":
        assert report["passed_cases"] == 2
        assert all(row["comparison_calls"] == 1 for row in report["results"])
        assert all(row["actual_model_decision"] == row["actual_decision"] for row in report["results"])
    else:
        row = report["results"][0]
        assert row["outcome"] == "failed" and row["reason"] == "status_mismatch"
        assert row["actual_model_decision"] == row["actual_decision"] == observed
        assert row["model_decision_matches_expectation"] is False
        assert row["application_decision_matches_expectation"] is False
        assert row["housing_calls"] == row["filter_calls"] == row["inflation_calls"] == row["comparison_calls"] == 0
        assert report["results"][1]["reason"] == "not_run_after_failure"


@pytest.mark.parametrize("kind", ["valid", "fence", "wrong_condition", "schema_rejected"])
def test_cli_filter_uses_structured_planner_and_preserves_failure_boundaries(
    tmp_path, monkeypatch, cases, fake_provider, kind,
):
    selected = evaluator.select_cases(cases, ["EQ-038", "EQ-040"])
    answer = copy.deepcopy(selected[0].offline_response)
    if kind == "wrong_condition":
        answer["conditions"][0]["operator"] = "lt"
    envelope = {key: None for key in evaluator.service.EconomicModelResponse.model_fields}
    envelope.update(answer)
    content = json.dumps(envelope)
    if kind == "fence":
        content = "```json\n" + content + "\n```"
    requests, clients, options = fake_provider(lambda request: (
        httpx.Response(400, json={"error": {"message": "private-test-key secret-upstream-body"}})
        if kind == "schema_rejected" else _response(content)
    ))
    monkeypatch.setattr(evaluator, "ROOT", tmp_path)
    output = tmp_path / "out/structured.json"
    # One permitted request: a successful first case leaves the second budget-
    # skipped; every failure stops before it, without a text-mode fallback.
    assert evaluator.main([
        "--live", "--case", "EQ-038", "--case", "EQ-040",
        "--max-model-calls", "1", "--output", str(output),
    ]) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    row = report["results"][0]
    body = json.loads(requests[0].content)
    schema = body["response_format"]["json_schema"]["schema"]
    assert body["response_format"]["type"] == "json_schema"
    assert schema["type"] == "object" and "anyOf" not in schema
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["$defs"]["HousingFilterCondition"]["properties"]["operator"]["enum"] == ["lt", "lte", "gt", "gte"]
    assert schema["properties"]["conditions"]["anyOf"][0]["maxItems"] == 3
    assert report["live_model_call_attempts"] == len(requests) == 1
    assert options[0]["max_retries"] == 0 and clients[0].is_closed()
    assert row["filter_calls"] == (1 if kind == "valid" else 0)
    assert row["housing_calls"] == row["inflation_calls"] == row["comparison_calls"] == 0
    if kind == "valid":
        assert row["outcome"] == "passed"  # Includes the independent April oracle.
        assert row["actual_model_decision"] == answer
        assert report["results"][1]["reason"] == "budget_exhausted"
    else:
        assert row["outcome"] == "failed"
        assert report["results"][1]["reason"] == "not_run_after_failure"
    if kind == "fence":
        assert row["reason"] == "invalid_plan"
        assert row["invalid_plan_diagnostics"] == {"format": "code_fence_prefix"}
    elif kind == "wrong_condition":
        assert row["python_blocked_ready_plan"] is True
        assert row["model_decision_matches_expectation"] is False
    elif kind == "schema_rejected":
        assert row["provider_error_code"] == "request_rejected"
    assert "private-test-key" not in output.read_text(encoding="utf-8")
    assert "secret-upstream-body" not in output.read_text(encoding="utf-8")


def test_budget_exhaustion_skips_remaining_cases_without_request(cases, fixtures, fake_provider):
    selected = cases[:3]
    requests, _, _ = fake_provider(answers_for(selected))
    report = evaluator.evaluate_cases(selected, fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=1)
    assert len(requests) == report["live_model_call_attempts"] == report["passed_cases"] == 1
    assert report["skipped_cases"] == 2 and not report["all_selected_cases_passed"]
    assert all(row["reason"] == "budget_exhausted" and row["model_call_attempts"] == 0
               for row in report["results"][1:])


@pytest.mark.parametrize(("status", "code"), [(429, "rate_limited"), (503, "provider_unavailable")])
def test_provider_failure_is_counted_and_stops_without_retry_or_secret(
    cases, fixtures, fake_provider, status, code,
):
    requests, _, options = fake_provider(lambda request: httpx.Response(status, json={
        "error": {"message": "private-test-key secret-upstream-body"},
    }))
    report = evaluator.evaluate_cases(cases[:3], fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=3)
    assert len(requests) == report["live_model_call_attempts"] == 1
    assert options[0]["max_retries"] == 0
    assert report["failed_cases"] == 1 and report["skipped_cases"] == 2
    row = report["results"][0]
    assert row["reason"] == "model_call_failed"
    assert row["http_status"] == 502
    assert row["provider_error_code"] == code
    assert row["housing_calls"] == row["filter_calls"] == 0
    assert row["inflation_calls"] == row["comparison_calls"] == 0
    assert all(row["reason"] == "not_run_after_failure" for row in report["results"][1:])
    assert all(row["provider_error_code"] is None for row in report["results"][1:])
    assert "private-test-key" not in json.dumps(report) and "secret-upstream-body" not in json.dumps(report)


@pytest.mark.parametrize(("raised", "expected"), [
    (llm_client.LLMRequestError("timeout", "private-test-key timeout body"), "timeout"),
    (llm_client.LLMRequestError("access_denied", "secret-upstream-body"), "access_denied"),
    (llm_client.LLMRequestError("request_rejected", "private-test-key"), "request_rejected"),
    (llm_client.LLMRequestError("unknown_code", "private-test-key secret-upstream-body"), None),
    (ValueError("private-test-key secret-upstream-body"), None),
])
def test_wrapper_records_only_known_safe_provider_error_codes(
    cases, fixtures, raised, expected,
):
    def failing_model(_):
        raise raised

    report = evaluator.evaluate_cases(
        cases[:2], fixtures, live=True, model_call=failing_model, max_model_calls=2,
    )
    row = report["results"][0]
    assert len(report["results"]) == 2
    assert report["live_model_call_attempts"] == row["model_call_attempts"] == 1
    assert report["failed_cases"] == 1 and report["skipped_cases"] == 1
    assert row["reason"] == "model_call_failed" and row["provider_error_code"] == expected
    assert row["housing_calls"] == row["filter_calls"] == 0
    assert row["inflation_calls"] == row["comparison_calls"] == 0
    assert report["results"][1]["reason"] == "not_run_after_failure"
    assert report["results"][1]["provider_error_code"] is None
    serialized = json.dumps(report)
    assert "private-test-key" not in serialized and "secret-upstream-body" not in serialized
    assert "unknown_code" not in serialized


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


@pytest.mark.parametrize("analysis_id,fields,missing,extra", [
    (
        "housing_condition_filter", {"first_year": 2023, "second_year": 2024},
        ["conditions", "end_period", "start_period"], ["first_year", "second_year"],
    ),
    (
        "cpi_two_year_comparison", {"start_period": "2021-01", "end_period": "2021-06", "conditions": []},
        ["first_year", "second_year"], ["conditions", "end_period", "start_period"],
    ),
])
def test_diagnostics_distinguish_which_plan_has_missing_and_extra_fields(
    analysis_id, fields, missing, extra,
):
    diagnostic = evaluator._invalid_plan_diagnostics(json.dumps({
        "status": "ready", "analysis_id": analysis_id, **fields,
    }))
    assert diagnostic["missing_fields"] == missing
    assert diagnostic["extra_fields"] == extra
    assert diagnostic["decision_header"] == {"status": "ready", "analysis_id": analysis_id}
    assert diagnostic["schema_valid"] is False


@pytest.mark.parametrize(("kind", "expected_format", "field"), [
    ("fence", "code_fence_prefix", None),
    ("not_json", "invalid_json", None),
    ("array", "json_non_object", None),
    ("missing_conditions", "json_object", "conditions"),
    ("wrong_metric", "json_object", "metric"),
    ("extra_secret_key", "json_object", None),
])
def test_invalid_plan_records_safe_diagnostics_without_repair_or_retry(
    cases, fixtures, fake_provider, kind, expected_format, field,
):
    selected = evaluator.select_cases(cases, ["EQ-038", "EQ-040"])
    answer = copy.deepcopy(selected[0].offline_response)
    if kind == "missing_conditions":
        answer.pop("conditions")
    elif kind == "wrong_metric":
        answer["conditions"][0]["metric"] = "secret-upstream-body"
    elif kind == "extra_secret_key":
        answer["private-test-key"] = "secret-upstream-body"
    content = json.dumps(answer)
    if kind == "fence":
        content = "```json\n" + content + "\n```"
    elif kind == "not_json":
        content = "private-test-key secret-upstream-body"
    elif kind == "array":
        content = "[]"
    requests, _, _ = fake_provider(lambda request: _response(content))
    report = evaluator.evaluate_cases(
        selected, fixtures, live=True, model_call=llm_client.ask_llm, max_model_calls=2,
    )
    row = report["results"][0]
    diagnostic = row["invalid_plan_diagnostics"]
    assert row["reason"] == "invalid_plan"
    assert diagnostic["format"] == expected_format
    if field:
        assert field in diagnostic["error_fields"]
        assert diagnostic["schema_valid"] is False
    if kind == "missing_conditions":
        assert diagnostic["error_fields"] == ["conditions"]
        assert diagnostic["error_types"] == ["missing"]
        assert diagnostic["missing_fields"] == ["conditions"]
        assert diagnostic["extra_fields"] == []
        assert diagnostic["decision_header"] == {
            "status": "ready", "analysis_id": "housing_condition_filter",
        }
    assert row["actual_model_decision"] is None and row["actual_decision"] is None
    assert row["filter_calls"] == row["housing_calls"] == 0
    assert row["inflation_calls"] == row["comparison_calls"] == 0
    assert len(requests) == report["live_model_call_attempts"] == 1
    assert report["results"][1]["reason"] == "not_run_after_failure"
    assert report["results"][1]["invalid_plan_diagnostics"] is None
    serialized = json.dumps(report)
    assert "private-test-key" not in serialized and "secret-upstream-body" not in serialized


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


def test_comparison_cases_run_one_comparison_and_keep_hand_calculated_constants(cases, fixtures):
    selected = evaluator.select_cases(cases, ["EQ-029", "EQ-030", "EQ-031"])
    report = evaluator.evaluate_cases(selected, fixtures)
    assert report["all_selected_cases_passed"]
    assert [row["comparison_calls"] for row in report["results"]] == [1, 1, 1]
    assert all(row["housing_calls"] == row["inflation_calls"] == 0 for row in report["results"])


@pytest.mark.parametrize(("case_id", "matched_periods"), [
    ("EQ-038", ["2021-04"]),
    ("EQ-039", ["2021-02", "2021-04"]),
    ("EQ-040", ["2021-06"]),
    ("EQ-041", ["2021-02", "2021-06"]),
])
def test_positive_housing_filter_cases_use_fixed_oracle_and_one_filter_call(
    cases, fixtures, case_id, matched_periods,
):
    case = evaluator.select_cases(cases, [case_id])[0]
    reference = evaluator._filter_reference(evaluator._payload(case, fixtures), case.expected_decision)
    assert list(reference["matched_periods"]) == case.expected_matched_periods == matched_periods
    assert reference["observed_month_count"] == case.expected_observed_month_count == 6

    report = evaluator.evaluate_cases([case], fixtures)
    row = report["results"][0]
    assert report["all_selected_cases_passed"] and row["outcome"] == "passed"
    assert row["filter_calls"] == 1
    assert row["housing_calls"] == row["inflation_calls"] == row["comparison_calls"] == 0


@pytest.mark.parametrize("case_id", ["EQ-038", "EQ-040", "EQ-041"])
def test_reversed_housing_filter_conditions_pass_and_next_case_runs(
    cases, fixtures, fake_provider, case_id,
):
    selected = evaluator.select_cases(cases, [case_id, "EQ-010"])
    reversed_response = copy.deepcopy(selected[0].offline_response)
    reversed_response["conditions"].reverse()
    selected = [selected[0].model_copy(update={"offline_response": reversed_response}), selected[1]]
    requests, _, _ = fake_provider(answers_for(selected))
    report = evaluator.evaluate_cases(
        selected, fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=2,
    )
    assert len(requests) == report["live_model_call_attempts"] == 2, {
        key: report["results"][0][key] for key in (
            "outcome", "reason", "application_decision_matches_expectation",
            "model_decision_matches_expectation", "actual_decision",
        )
    }
    assert report["all_selected_cases_passed"]
    row = report["results"][0]
    assert json.loads(json.dumps(row["actual_model_decision"])) == reversed_response
    assert row["actual_model_decision"] != row["expected_decision"]
    assert row["application_decision_matches_expectation"] is True
    assert row["model_decision_matches_expectation"] is True
    assert row["filter_calls"] == 1
    assert row["housing_calls"] == row["inflation_calls"] == row["comparison_calls"] == 0
    assert report["results"][1]["outcome"] == "passed"


def test_reversed_housing_filter_conditions_still_respect_the_call_budget(cases, fixtures, fake_provider):
    selected = evaluator.select_cases(cases, ["EQ-038", "EQ-040"])
    reversed_first = copy.deepcopy(selected[0].offline_response)
    reversed_first["conditions"].reverse()
    selected = [selected[0].model_copy(update={"offline_response": reversed_first}), selected[1]]
    requests, _, _ = fake_provider(answers_for(selected))
    report = evaluator.evaluate_cases(
        selected, fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=1,
    )
    assert len(requests) == report["live_model_call_attempts"] == 1
    assert report["results"][0]["outcome"] == "passed"
    assert report["results"][0]["filter_calls"] == 1
    assert report["results"][1]["outcome"] == "skipped"
    assert report["results"][1]["reason"] == "budget_exhausted"
    assert report["results"][1]["model_call_attempts"] == 0


@pytest.mark.parametrize(
    "kind",
    ["wrong_direction", "wrong_threshold", "wrong_metric", "missing", "extra", "duplicate"],
)
@pytest.mark.parametrize("case_id", ["EQ-038", "EQ-040", "EQ-041"])
def test_wrong_housing_filter_conditions_still_fail_without_analysis(
    cases, fixtures, case_id, kind,
):
    case = evaluator.select_cases(cases, [case_id])[0]
    answer = _mutated_filter_response(case.offline_response, kind)
    report = evaluator.evaluate_cases(
        [case], fixtures, live=True,
        model_call=lambda _: json.dumps(answer), max_model_calls=1,
    )
    row = report["results"][0]
    assert not report["all_selected_cases_passed"]
    assert json.loads(json.dumps(row["actual_model_decision"])) == answer
    assert row["application_decision_matches_expectation"] is False
    assert row["model_decision_matches_expectation"] is False
    assert row["python_blocked_ready_plan"] is True
    assert row["housing_calls"] == row["filter_calls"] == 0
    assert row["inflation_calls"] == row["comparison_calls"] == 0


def test_housing_filter_comparison_ignores_only_condition_order(cases, fixtures):
    case = evaluator.select_cases(cases, ["EQ-038"])[0]
    plan = case.expected_decision.model_dump(mode="json")
    reversed_plan = {**plan, "conditions": list(reversed(plan["conditions"]))}
    assert evaluator._normalized_match(reversed_plan, plan)
    assert not evaluator._normalized_match(
        {**plan, "conditions": plan["conditions"][:1]}, plan,
    )
    assert not evaluator._normalized_match(
        {**plan, "conditions": [*plan["conditions"], plan["conditions"][0]]}, plan,
    )

    reference = evaluator._filter_reference(evaluator._payload(case, fixtures), case.expected_decision)
    reversed_evidence = {
        **reference, "conditions": list(reversed(reference["conditions"])),
    }
    assert evaluator._normalized_match(reversed_evidence, reference)
    for field, value in [
        ("observed_month_count", reference["observed_month_count"] + 1),
        ("matched_periods", ["2021-05"]),
        ("results", []),
    ]:
        assert not evaluator._normalized_match({**reversed_evidence, field: value}, reference)

    wrong_unit = copy.deepcopy(reversed_evidence)
    wrong_unit["conditions"][0]["unit"] = "percent" if wrong_unit["conditions"][0]["unit"] == "percentage_point" else "percentage_point"
    assert not evaluator._normalized_match(wrong_unit, reference)

    for kind in ["wrong_direction", "wrong_threshold", "wrong_metric", "missing", "extra", "duplicate"]:
        changed = copy.deepcopy(plan)
        if kind == "missing":
            changed["conditions"].pop()
        elif kind == "extra":
            changed["conditions"].append({
                "metric": "housing_loan_interest_rate_pct", "operator": "lt", "threshold": 100.0,
            })
        elif kind == "duplicate":
            changed["conditions"].append(copy.deepcopy(changed["conditions"][0]))
        else:
            changed = _mutated_filter_response(changed, kind)
        assert not evaluator._normalized_match(changed, plan)

    assert plan == case.expected_decision.model_dump(mode="json")
    assert list(reversed(reversed_plan["conditions"])) == plan["conditions"]


def test_negative_housing_filter_cases_execute_no_analysis(cases, fixtures):
    selected = evaluator.select_cases(cases, ["EQ-042", "EQ-043", "EQ-044", "EQ-045"])
    report = evaluator.evaluate_cases(selected, fixtures)
    assert report["all_selected_cases_passed"]
    for row in report["results"]:
        assert row["actual_decision"] == row["expected_decision"]
        assert row["housing_calls"] == row["filter_calls"] == 0
        assert row["inflation_calls"] == row["comparison_calls"] == 0


@pytest.mark.parametrize(("case_id", "response"), [
    ("EQ-038", {
        "status": "ready", "analysis_id": "housing_condition_filter",
        "start_period": "2021-01", "end_period": "2021-06",
        "conditions": [
            {"metric": "interest_rate_change_pp", "operator": "lt", "threshold": 0.0},
            {"metric": "real_housing_loan_change_pct", "operator": "gt", "threshold": 0.0},
        ],
    }),
    ("EQ-039", {
        "status": "ready", "analysis_id": "housing_condition_filter",
        "start_period": "2021-01", "end_period": "2021-06",
        "conditions": [
            {"metric": "real_housing_loan_change_pct", "operator": "gt", "threshold": 3.0},
        ],
    }),
    ("EQ-041", {
        "status": "ready", "analysis_id": "housing_condition_filter",
        "start_period": "2021-01", "end_period": "2021-06",
        "conditions": [
            {"metric": "housing_loan_interest_rate_pct", "operator": "gt", "threshold": 18.0},
        ],
    }),
    ("EQ-042", {
        "status": "ready", "analysis_id": "housing_rate_down_real_credit_not_up",
        "start_period": "2021-01", "end_period": "2021-06",
    }),
])
def test_wrong_filter_or_legacy_ready_plans_fail_without_analysis(cases, fixtures, case_id, response):
    case = evaluator.select_cases(cases, [case_id])[0]
    report = evaluator.evaluate_cases(
        [case], fixtures, live=True,
        model_call=lambda _: json.dumps(response), max_model_calls=1,
    )
    row = report["results"][0]
    assert not report["all_selected_cases_passed"] and row["outcome"] == "failed"
    assert row["model_decision_matches_expectation"] is False
    assert row["python_blocked_ready_plan"] is True
    assert row["housing_calls"] == row["filter_calls"] == 0
    assert row["inflation_calls"] == row["comparison_calls"] == 0


def test_new_filter_live_path_counts_attempts_and_stops_on_first_failure(cases, fixtures, fake_provider):
    selected = evaluator.select_cases(cases, ["EQ-038", "EQ-040", "EQ-043"])
    answers = {case.question: case.offline_response for case in selected}
    wrong = {
        "status": "ready", "analysis_id": "housing_rate_down_real_credit_not_up",
        "start_period": "2021-01", "end_period": "2021-06",
    }

    def handler(request):
        prompt = json.loads(request.content)["messages"][0]["content"]
        question = json.loads(prompt.split("İSTEK_VERİSİ:\n", 1)[1])["question"]
        return _response(json.dumps(
            wrong if question == selected[1].question else answers[question],
            ensure_ascii=False,
        ))

    requests, _, _ = fake_provider(handler)
    report = evaluator.evaluate_cases(
        selected, fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=3,
    )
    assert len(requests) == report["live_model_call_attempts"] == 2
    assert report["passed_cases"] == 1 and report["failed_cases"] == 1
    assert report["skipped_cases"] == 1
    assert report["results"][0]["filter_calls"] == 1
    assert report["results"][1]["reason"] == "status_mismatch"
    assert report["results"][1]["filter_calls"] == report["results"][1]["housing_calls"] == 0
    assert report["results"][2]["reason"] == "not_run_after_failure"


def test_bad_comparison_expectation_spends_no_provider_calls(cases, fixtures):
    base = evaluator.select_cases(cases, ["EQ-029"])[0]
    wrong = base.expected_comparison.model_copy(
        update={"second_minus_first_december_annual_inflation_pp": 6.0},
    )
    calls = []
    with pytest.raises(ValueError, match="comparison expectations"):
        evaluator.evaluate_cases([base.model_copy(update={"expected_comparison": wrong})], fixtures,
            live=True, model_call=lambda prompt: calls.append(prompt), max_model_calls=1)
    assert not calls


def test_missing_interior_month_is_rejected_before_provider(cases, fixtures):
    selected = evaluator.select_cases(cases, ["EQ-029"])
    broken = copy.deepcopy(fixtures)
    broken["comparison"]["inflation"]["cpi_monthly"] = [
        row for row in broken["comparison"]["inflation"]["cpi_monthly"] if row["period"] != "2023-06"
    ]
    calls = []
    with pytest.raises(ValueError):
        evaluator.evaluate_cases(selected, broken, live=True,
            model_call=lambda prompt: calls.append(prompt), max_model_calls=1)
    assert not calls


def test_python_blocks_wrong_comparison_ready_plan_and_marks_raw_model_failure(
    cases, fixtures, fake_provider,
):
    selected = evaluator.select_cases(cases, ["EQ-035", "EQ-010"])
    observed = {"status": "ready", "analysis_id": "cpi_two_year_comparison",
                "first_year": 2023, "second_year": 2024}
    requests, _, _ = fake_provider(lambda request: _response(json.dumps(observed)))
    report = evaluator.evaluate_cases(selected, fixtures, live=True,
        model_call=llm_client.ask_llm, max_model_calls=2)
    row = report["results"][0]
    assert len(requests) == report["live_model_call_attempts"] == 1
    assert row["actual_model_decision"] == observed
    assert row["actual_decision"] == row["expected_decision"] == {
        "status": "unsupported", "reason": "unsupported_analysis",
    }
    assert row["model_decision_matches_expectation"] is False
    assert row["application_decision_matches_expectation"] is True
    assert row["python_blocked_ready_plan"] is True
    assert row["outcome"] == "failed" and row["reason"] == "model_decision_mismatch"
    assert row["comparison_calls"] == row["housing_calls"] == row["inflation_calls"] == 0
    assert report["results"][1]["reason"] == "not_run_after_failure"



@pytest.mark.parametrize(
    ("case_id", "first_year", "second_year"),
    [("EQ-032", 2023, 2023), ("EQ-034", 2023, 2024)],
)
def test_invalid_comparison_ready_is_not_an_accepted_model_decision(
    cases, fixtures, case_id, first_year, second_year,
):
    selected = evaluator.select_cases(cases, [case_id, "EQ-029"])
    observed = {"status": "ready", "analysis_id": "cpi_two_year_comparison",
                "first_year": first_year, "second_year": second_year}
    calls = []

    def fake_model(prompt):
        calls.append(prompt)
        return json.dumps(observed)

    report = evaluator.evaluate_cases(
        selected, fixtures, live=True, model_call=fake_model, max_model_calls=2,
    )
    row = report["results"][0]
    expected = {"status": "clarification_required", "reason": "period_required"}
    assert len(calls) == report["live_model_call_attempts"] == 1
    assert row["accepted_model_decisions"] == [expected]
    assert row["actual_model_decision"] == observed
    assert row["actual_decision"] == row["expected_decision"] == expected
    assert row["application_decision_matches_expectation"] is True
    assert row["model_decision_matches_expectation"] is False
    assert row["python_blocked_ready_plan"] is True
    assert row["outcome"] == "failed" and row["reason"] == "model_decision_mismatch"
    assert row["comparison_calls"] == row["housing_calls"] == row["inflation_calls"] == 0
    assert not report["all_selected_cases_passed"]
    assert report["results"][1]["reason"] == "not_run_after_failure"

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

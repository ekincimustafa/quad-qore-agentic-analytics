"""Offline HTTP behavior for question -> plan -> real analysis -> response."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.housing import get_housing_narrator
from app.api.housing_question import get_housing_question_model
from app.api.main import create_app
from app.connectors import llm_client
from app.services import housing_question
from app.tools.housing_narrator import narrate_housing_evidence


ENDPOINT = "/analysis/housing/question"


@pytest.fixture(autouse=True)
def forbid_real_provider_and_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External HTTP/model calls are forbidden in offline tests")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(llm_client, "ask_llm", forbidden)


@pytest.fixture
def payload():
    path = Path(__file__).resolve().parents[1] / "docs/housing-question-api-example.json"
    return json.loads(path.read_text(encoding="utf-8"))


def ready(**changes):
    return {
        "status": "ready", "analysis_id": housing_question.ANALYSIS_ID,
        "start_period": "2021-01", "end_period": "2021-03", **changes,
    }


def client_with_model(model, narrator=None):
    app = create_app()
    app.dependency_overrides[get_housing_question_model] = lambda: model
    if narrator is not None:
        app.dependency_overrides[get_housing_narrator] = lambda: narrator
    return TestClient(app)


def test_documented_question_reaches_real_analysis_and_matches_direct_api(payload):
    calls = []

    def model(prompt):
        calls.append(prompt)
        assert payload["question"] in prompt
        return json.dumps(ready())

    def forbidden_narrator(_):
        raise AssertionError("Narration is not requested")

    with client_with_model(model, forbidden_narrator) as client:
        response = client.post(ENDPOINT, json=payload)
        direct_payload = {key: value for key, value in payload.items() if key != "question"}
        direct_payload.update(start_period="2021-01", end_period="2021-03")
        direct = client.post("/analysis/housing", json=direct_payload)
    assert response.status_code == direct.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["decision"] == ready()
    assert body["available_period"] == {"start_period": "2021-01", "end_period": "2021-03"}
    assert body["evidence"] == direct.json()["evidence"]
    assert body["chart"] == direct.json()["chart"]
    assert body["evidence"]["matched_periods"] == ["2021-02"]
    assert body["narration"] is None
    assert len(calls) == 1


@pytest.mark.parametrize("decision,expected_status", [
    ({"status": "clarification_required", "reason": "period_required"}, "clarification_required"),
    ({"status": "clarification_required", "reason": "metric_ambiguous"}, "clarification_required"),
    ({"status": "unsupported", "reason": "unsupported_analysis"}, "unsupported"),
    (ready(start_period="2020-12"), "clarification_required"),
])
def test_non_executable_decisions_return_clear_http_results_without_analysis(
    monkeypatch, payload, decision, expected_status,
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Analysis/narration must not run")
    monkeypatch.setattr(housing_question, "run_housing_analysis", forbidden)
    with client_with_model(lambda _: json.dumps(decision), forbidden) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == expected_status
    assert body["message"].strip()
    assert body["evidence"] is None and body["chart"] is None and body["narration"] is None
    if decision["status"] == "ready":
        assert body["decision"]["reason"] == "outside_coverage"
        assert "2021-01" in body["message"] and "2021-03" in body["message"]


@pytest.mark.parametrize("key,value", [
    ("question", "   "), ("question", "x" * 2_001),
    ("bddk_monthly", []), ("evds_monthly", []),
    ("bddk_source_ref", "  "), ("evds_source_refs", ""),
    ("start_period", "1900-01"), ("analysis_id", "web_search"),
    ("coverage", {"start_period": "1900-01", "end_period": "9999-12"}),
    ("model", "unintended-provider"), ("path", "../../.env"),
    ("include_narration", "true"),
])
def test_invalid_body_fails_before_model_call(payload, key, value):
    calls = []
    payload[key] = value
    with client_with_model(lambda prompt: calls.append(prompt)) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 422
    assert calls == []


@pytest.mark.parametrize("problem", ["gap", "duplicate", "year_zero", "no_overlap", "invalid_number"])
def test_invalid_rows_fail_before_model_call(payload, problem):
    calls = []
    if problem == "gap":
        payload["evds_monthly"].pop(1)
    elif problem == "duplicate":
        payload["bddk_monthly"].append(payload["bddk_monthly"][0].copy())
    elif problem == "year_zero":
        payload["bddk_monthly"][0]["period"] = "0000-01"
    elif problem == "no_overlap":
        for row in payload["evds_monthly"]:
            row["period"] = row["period"].replace("2021", "2022")
    else:
        payload["evds_monthly"][0]["cpi_index"] = -1
    with client_with_model(lambda prompt: calls.append(prompt)) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 422
    assert calls == []


def test_coverage_comes_from_shared_input_months_not_default_dates(payload):
    payload["bddk_monthly"].pop(0)
    calls = []

    def model(prompt):
        calls.append(prompt)
        request = json.loads(prompt.split("İSTEK_VERİSİ:\n", 1)[1])
        assert request["available_period"] == {"start_period": "2021-02", "end_period": "2021-03"}
        return json.dumps(ready(start_period="2021-02"))

    with client_with_model(model) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200
    assert response.json()["evidence"]["observed_month_count"] == 2
    assert len(calls) == 1


@pytest.mark.parametrize("plan", [
    "not JSON private-key",
    json.dumps(ready(analysis_id="web_search")),
    json.dumps(ready(sql="SELECT * FROM private_table")),
])
def test_bad_model_plan_is_safe_502_and_never_reaches_analysis(monkeypatch, payload, plan):
    calls = []

    def model(prompt):
        calls.append(prompt)
        return plan

    def forbidden(*args, **kwargs):
        raise AssertionError("Bad plan must not run")

    monkeypatch.setattr(housing_question, "run_housing_analysis", forbidden)
    with client_with_model(model) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "invalid_question_plan"
    assert "private-key" not in response.text and "private_table" not in response.text
    assert len(calls) == 1


def test_provider_failure_is_safe_502_and_not_retried(payload):
    calls = []

    def fail(prompt):
        calls.append(prompt)
        raise RuntimeError("private-key secret-provider-body")

    with client_with_model(fail) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "question_planning_failed"
    assert "private-key" not in response.text and "secret-provider-body" not in response.text
    assert len(calls) == 1


def test_default_dependency_uses_configured_client(monkeypatch, payload):
    calls = []

    def model(prompt):
        calls.append(prompt)
        return json.dumps(ready())

    monkeypatch.setattr(llm_client, "ask_llm", model)
    with TestClient(create_app()) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200
    assert len(calls) == 1


def test_optional_narration_runs_existing_validation_after_analysis(payload):
    payload["include_narration"] = True
    narration_calls = []

    def narrator(evidence):
        narration_calls.append(evidence)
        return narrate_housing_evidence(evidence, lambda _: json.dumps({"results": [{
            "period": "2021-02", "housing_loan_interest_rate_pct": 9.0,
            "interest_rate_change_pp": -1.0, "real_housing_loan_change_pct": -9.0909,
        }]}))

    with client_with_model(lambda _: json.dumps(ready()), narrator) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200
    assert len(narration_calls) == 1
    assert "nedensellik kanıtlamaz" in response.json()["narration"]


def test_narration_failure_returns_502_without_partial_analysis(payload):
    payload["include_narration"] = True

    def fail(_):
        raise RuntimeError("private-key")

    with client_with_model(lambda _: json.dumps(ready()), fail) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "narration_failed"
    assert "private-key" not in response.text and "evidence" not in response.json()


def test_openapi_documents_question_and_three_response_states():
    with TestClient(create_app()) as client:
        schema = client.get("/openapi.json").json()
    response = schema["paths"][ENDPOINT]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response["discriminator"]["propertyName"] == "status"
    assert len(response["oneOf"]) == 3
    request = schema["components"]["schemas"]["HousingQuestionRequest"]
    assert request["additionalProperties"] is False
    assert "start_period" not in request["properties"] and "coverage" not in request["properties"]

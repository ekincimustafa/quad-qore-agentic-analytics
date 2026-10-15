"""API checks with the default LLM dependency and no live provider."""

import json

import pytest
from fastapi.testclient import TestClient

from app.api.housing import get_housing_demo_paths
from app.api.main import create_app
from app.connectors import llm_client
from tests.test_housing_analysis_api import _payload
from tests.test_housing_demo_api import _write_demo_files


@pytest.mark.parametrize("endpoint", ["/analysis/housing", "/analysis/housing/demo"])
def test_default_api_without_narration_never_reads_llm_settings(monkeypatch, tmp_path, endpoint):
    def must_not_run():
        raise AssertionError("LLM settings must not be read")
    monkeypatch.setattr(llm_client, "read_llm_settings", must_not_run)
    application = create_app()
    paths = _write_demo_files(tmp_path)
    application.dependency_overrides[get_housing_demo_paths] = lambda: paths
    request = _payload() if endpoint.endswith("/housing") else {
        "start_period": "2021-01", "end_period": "2021-03", "include_narration": False,
    }
    response = TestClient(application).post(endpoint, json=request)
    assert response.status_code == 200
    assert response.json()["narration"] is None
    assert response.json()["evidence"]["matched_periods"] == ["2021-02"]


@pytest.mark.parametrize("endpoint", ["/analysis/housing", "/analysis/housing/demo"])
def test_narration_keeps_deterministic_evidence_chart_and_safe_text(monkeypatch, tmp_path, endpoint):
    calls = []
    def model(prompt):
        calls.append(prompt)
        return json.dumps({"results": [{
            "period": "2021-02", "housing_loan_interest_rate_pct": 9.0,
            "interest_rate_change_pp": -1.0, "real_housing_loan_change_pct": -9.0909,
        }]})
    monkeypatch.setattr(llm_client, "ask_llm", model)
    application = create_app()
    paths = _write_demo_files(tmp_path)
    application.dependency_overrides[get_housing_demo_paths] = lambda: paths
    request = _payload() if endpoint.endswith("/housing") else {
        "start_period": "2021-01", "end_period": "2021-03", "include_narration": False,
    }
    with TestClient(application) as client:
        before = client.post(endpoint, json=request).json()
        request["include_narration"] = True
        response = client.post(endpoint, json=request)
    assert response.status_code == 200
    after = response.json()
    assert len(calls) == 1
    assert after["evidence"] == before["evidence"]
    assert after["chart"] == before["chart"]
    assert "konut kredisi faizi %9" in after["narration"]
    assert "nedensellik kanıtlamaz" in after["narration"]


def test_public_api_does_not_expose_provider_exception(monkeypatch):
    def fail(prompt):
        raise RuntimeError("private-test-key secret-upstream-body")
    monkeypatch.setattr(llm_client, "ask_llm", fail)
    request = _payload()
    request["include_narration"] = True
    response = TestClient(create_app()).post("/analysis/housing", json=request)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "narration_failed"
    assert "private-test-key" not in response.text
    assert "secret-upstream-body" not in response.text


def test_missing_llm_configuration_is_controlled_and_never_creates_client(monkeypatch):
    monkeypatch.setattr(llm_client, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("LLM_API_KEY", "")
    def must_not_run(settings):
        raise AssertionError("Client must not be created")
    monkeypatch.setattr(llm_client, "create_llm_client", must_not_run)
    request = _payload()
    request["include_narration"] = True
    response = TestClient(create_app()).post("/analysis/housing", json=request)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "narration_failed"

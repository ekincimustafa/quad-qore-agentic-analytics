import json
from pathlib import Path

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.connectors import llm_client
from app.services.inflation_analysis import build_inflation_evidence


ENDPOINT = "/analysis/inflation"


@pytest.fixture(autouse=True)
def no_network_or_model_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Inflation calculations must not use HTTP or a model")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(llm_client, "ask_llm", forbidden)
    monkeypatch.setattr(llm_client, "read_llm_settings", forbidden)


@pytest.fixture
def payload():
    return json.loads((Path(__file__).resolve().parents[1] / "docs/inflation-api-example.json").read_text(encoding="utf-8"))


def test_documented_example_matches_service_without_model_access(payload):
    with TestClient(create_app()) as client:
        response = client.post(ENDPOINT, json=payload)
        assert client.get("/health").status_code == 200
    assert response.status_code == 200
    evidence = response.json()["evidence"]
    direct = build_inflation_evidence(pd.DataFrame(payload["cpi_monthly"]),
        start_period=payload["start_period"], end_period=payload["end_period"], source_ref=payload["source_ref"])
    assert evidence == direct.model_dump(mode="json")
    assert evidence["first_to_last_index_change_pct"] == pytest.approx(-1)
    assert evidence["observations"][0]["monthly_inflation_pct"] is None
    assert evidence["observations"][1]["monthly_inflation_pct"] == pytest.approx(10)
    assert all(row["annual_inflation_pct"] is None for row in evidence["observations"])
    assert evidence["source_ref"].startswith("synthetic://")
    assert "NaN" not in response.text


@pytest.mark.parametrize("key,value", [
    ("cpi_monthly", []), ("source_ref", " "), ("source_ref", "None"),
    ("start_period", "2021-03"), ("start_period", "0000-01"),
    ("end_period", "2022-01"), ("end_period", "2021-1"),
    ("include_narration", True), ("question", "hesapla"),
    ("path", "../../.env"), ("model", "unrequested"), ("base_year", 2020),
])
def test_invalid_or_extra_request_fields_return_422(payload, key, value):
    if key == "start_period" and value == "2021-03":
        payload["end_period"] = "2021-01"
    payload[key] = value
    with TestClient(create_app()) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize("value", [0, -1, True, "110", None])
def test_invalid_index_type_or_value_returns_422(payload, value):
    payload["cpi_monthly"][1]["cpi_index"] = value
    with TestClient(create_app()) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize("problem", ["duplicate", "gap", "invalid_year"])
def test_semantic_row_errors_have_safe_error_response(payload, problem):
    if problem == "duplicate":
        payload["cpi_monthly"].append(payload["cpi_monthly"][0].copy())
    elif problem == "gap":
        payload["cpi_monthly"].pop(1)
    else:
        payload["cpi_monthly"][0]["period"] = "0000-01"
    payload["source_ref"] = "private-local-reference"
    with TestClient(create_app()) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_inflation_input"
    assert "private-local-reference" not in response.text


@pytest.mark.parametrize("value", [float("inf"), -float("inf"), float("nan")])
def test_nonfinite_json_is_rejected(payload, value):
    payload["cpi_monthly"][1]["cpi_index"] = value
    with TestClient(create_app()) as client:
        response = client.post(ENDPOINT, content=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_inflation_input"


def test_nonfinite_extra_field_and_malformed_json_have_safe_errors(payload):
    payload["api_key"] = float("nan")
    with TestClient(create_app()) as client:
        extra = client.post(ENDPOINT, content=json.dumps(payload), headers={"Content-Type": "application/json"})
        malformed = client.post(ENDPOINT, content='{"source_ref": "private-reference",', headers={"Content-Type": "application/json"})
    assert extra.status_code == malformed.status_code == 422
    assert "private-reference" not in malformed.text
    assert "NaN" not in extra.text


def test_openapi_separates_cpi_analysis_from_question_planning():
    with TestClient(create_app()) as client:
        schema = client.get("/openapi.json").json()
    assert ENDPOINT in schema["paths"]
    assert "/analysis/housing/question" in schema["paths"]
    request = schema["components"]["schemas"]["InflationRequest"]
    assert request["additionalProperties"] is False
    assert set(request["required"]) == {"cpi_monthly", "start_period", "end_period", "source_ref"}

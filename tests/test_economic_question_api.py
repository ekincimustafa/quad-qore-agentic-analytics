"""HTTP behavior of the two-analysis endpoint with no live provider access."""

import copy
import json
from pathlib import Path

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api.economic_question import get_economic_question_model
from app.api.main import create_app
from app.connectors import llm_client
from app.lakehouse.gold import GoldAnalysisError
from app.services import economic_question as service
from app.services.inflation_analysis import InflationEvidence
from app.services.inflation_comparison import compare_inflation_years
from app.tools.inflation_chart import build_inflation_chart


ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "/analysis/economic/question"


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External model/settings/HTTP access is forbidden")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(llm_client, "ask_llm", forbidden)
    monkeypatch.setattr(llm_client, "read_llm_settings", forbidden)


@pytest.fixture
def payload():
    return json.loads((ROOT / "docs/economic-question-api-example.json").read_text(encoding="utf-8"))


def ready(analysis_id=service.HOUSING_ID, **changes):
    return {"status": "ready", "analysis_id": analysis_id,
            "start_period": "2021-01", "end_period": "2021-03", **changes}


def client_with_model(model):
    app = create_app()
    app.dependency_overrides[get_economic_question_model] = lambda: model
    return TestClient(app)


@pytest.mark.parametrize("analysis_id", [service.HOUSING_ID, service.INFLATION_ID])
def test_documented_requests_call_one_service_and_equal_direct_api(monkeypatch, payload, analysis_id):
    if analysis_id == service.INFLATION_ID:
        cpi = json.loads((ROOT / "docs/economic-question-cpi-example.json").read_text(encoding="utf-8"))
        payload["inflation"] = cpi["inflation"]
        payload["question"] = cpi["question"]
    calls, prompts = [], []
    original_housing, original_cpi = service.run_housing_analysis, service.build_inflation_evidence

    def housing(*args, **kwargs):
        calls.append(service.HOUSING_ID)
        return original_housing(*args, **kwargs)

    def inflation(*args, **kwargs):
        calls.append(service.INFLATION_ID)
        return original_cpi(*args, **kwargs)

    monkeypatch.setattr(service, "run_housing_analysis", housing)
    monkeypatch.setattr(service, "build_inflation_evidence", inflation)

    def model(prompt):
        prompts.append(prompt)
        assert payload["question"] in prompt
        assert "synthetic://" not in prompt
        return json.dumps(ready(analysis_id))

    is_housing = analysis_id == service.HOUSING_ID
    with client_with_model(model) as client:
        response = client.post(ENDPOINT, json=payload)
        direct = client.post(
            "/analysis/housing" if is_housing else "/analysis/inflation",
            json={**payload["housing" if is_housing else "inflation"],
                  "start_period": "2021-01", "end_period": "2021-03"},
        )
    assert response.status_code == direct.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["decision"] == ready(analysis_id)
    assert calls == [analysis_id] and len(prompts) == 1
    assert body["analysis"]["analysis_id"] == analysis_id
    assert body["analysis"]["evidence"] == direct.json()["evidence"]
    if is_housing:
        assert body["analysis"]["chart"] == direct.json()["chart"]
        assert body["analysis"]["evidence"]["matched_periods"] == ["2021-02"]
    else:
        assert body["available_periods"]["inflation"]["start_period"] == "2020-01"
        jan = body["analysis"]["evidence"]["observations"][0]
        assert jan["monthly_inflation_pct"] == pytest.approx(4.0)
        assert jan["annual_inflation_pct"] == pytest.approx(30.0)
        assert body["analysis"]["evidence"]["cpi_base_year"] == 2025
        evidence = InflationEvidence.model_validate(body["analysis"]["evidence"])
        assert body["analysis"]["chart"] == build_inflation_chart(evidence)
        chart = body["analysis"]["chart"]
        assert len(chart["data"]) == 3
        for trace, field in zip(chart["data"], ("cpi_index", "monthly_inflation_pct", "annual_inflation_pct")):
            assert trace["y"] == [getattr(row, field) for row in evidence.observations]
        assert chart["data"][0]["x"] == [f"{row.period}-01" for row in evidence.observations]


COMPARISON_PERIODS = pd.period_range("2022-12", "2024-12", freq="M").astype(str).tolist()
COMPARISON_INDEX = [
    100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 112.0, 114.0, 116.0, 118.0, 119.0, 119.5,
    120.0, 123.0, 126.0, 129.0, 132.0, 135.0, 138.0, 141.0, 144.0, 146.0, 147.0, 148.5,
    150.0,
]


def comparison_payload(question="2023 ve 2024 TÜFE değişimlerini karşılaştır."):
    return {
        "question": question,
        "inflation": {
            "cpi_monthly": [
                {"period": period, "cpi_index": value}
                for period, value in zip(COMPARISON_PERIODS, COMPARISON_INDEX)
            ],
            "source_ref": "synthetic://comparison",
        },
    }


def comparison_ready(first=2023, second=2024):
    return {"status": "ready", "analysis_id": service.COMPARISON_ID,
            "first_year": first, "second_year": second}


def test_comparison_endpoint_matches_existing_core_and_exposes_typed_evidence(monkeypatch):
    calls = []
    original = service.compare_inflation_years

    def comparison(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "compare_inflation_years", comparison)
    with client_with_model(lambda _: json.dumps(comparison_ready(2024, 2023))) as client:
        response = client.post(
            ENDPOINT,
            json=comparison_payload("2024 ile 2023 Aralık yıllık TÜFE enflasyonunu karşılaştır."),
        )
    assert response.status_code == 200
    body = response.json()
    direct = compare_inflation_years(
        pd.DataFrame({"period": COMPARISON_PERIODS, "cpi_index": COMPARISON_INDEX}),
        first_year=2024, second_year=2023, source_ref="synthetic://comparison",
    )
    assert calls == [{"first_year": 2024, "second_year": 2023, "source_ref": "synthetic://comparison"}]
    assert body["status"] == "ok"
    assert body["decision"] == comparison_ready(2024, 2023)
    assert body["analysis"] == {
        "analysis_id": service.COMPARISON_ID, "evidence": direct.model_dump(mode="json"),
    }
    assert body["analysis"]["evidence"]["second_minus_first_december_annual_inflation_pp"] == pytest.approx(-5.0)
    assert [year["evidence"]["observed_month_count"] for year in body["analysis"]["evidence"]["years"]] == [12, 12]
    assert body["available_periods"]["inflation"] == {"start_period": "2022-12", "end_period": "2024-12"}


@pytest.mark.parametrize("question,plan,expected", [
    ("2023 ve 2024 TÜFE değişimlerini karşılaştır.", comparison_ready(2024, 2023),
     {"status": "clarification_required", "reason": "period_required"}),
    ("2023 ve 2024 TÜFE değişimlerini karşılaştır.", ready(service.INFLATION_ID, start_period="2023-01", end_period="2024-12"),
     {"status": "clarification_required", "reason": "period_required"}),
    ("2023 Aralık ile 2024 Aralık yıllıklandırılmış TÜFE enflasyonunu karşılaştır.", comparison_ready(2023, 2024),
     {"status": "unsupported", "reason": "unsupported_analysis"}),
    ("2023 ve 2024 yıllıklandırılmış TÜFE enflasyonunu karşılaştır.", comparison_ready(2023, 2024),
     {"status": "unsupported", "reason": "unsupported_analysis"}),
    ("2023 ve 2024 ortalama TÜFE enflasyonunu karşılaştır.", comparison_ready(2023, 2024),
     {"status": "unsupported", "reason": "unsupported_analysis"}),
    ("2023 Ocak ile 2024 Ocak TÜFE değişimlerini karşılaştır.", comparison_ready(2023, 2024),
     {"status": "unsupported", "reason": "unsupported_analysis"}),
    ("2023-01 ile 2024-01 TÜFE değişimlerini karşılaştır.", comparison_ready(2023, 2024),
     {"status": "unsupported", "reason": "unsupported_analysis"}),
    ("2023 ve 2024 konut kredisi faizlerini karşılaştır.", comparison_ready(2023, 2024),
     {"status": "unsupported", "reason": "unsupported_analysis"}),
    ("2021 ve 2024 TÜFE değişimlerini karşılaştır.", comparison_ready(2021, 2024),
     {"status": "clarification_required", "reason": "outside_coverage"}),
])
def test_wrong_comparison_ready_plans_are_blocked_before_analysis(
    monkeypatch, question, plan, expected,
):
    def forbidden(*args, **kwargs):
        raise AssertionError("A blocked comparison plan must not run an analysis")

    monkeypatch.setattr(service, "compare_inflation_years", forbidden)
    monkeypatch.setattr(service, "build_inflation_evidence", forbidden)
    with client_with_model(lambda _: json.dumps(plan)) as client:
        response = client.post(ENDPOINT, json=comparison_payload(question))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == expected["status"]
    assert body["decision"] == expected
    assert body["analysis"] is None


@pytest.mark.parametrize("decision,mode,expected", [
    ({"status": "clarification_required", "reason": "period_required"}, "both", "clarification_required"),
    ({"status": "clarification_required", "reason": "metric_ambiguous"}, "both", "clarification_required"),
    ({"status": "unsupported", "reason": "unsupported_analysis"}, "both", "unsupported"),
    (ready(service.INFLATION_ID, start_period="2020-12"), "both", "clarification_required"),
    (ready(service.INFLATION_ID), "housing_only", "data_unavailable"),
    (ready(), "none", "data_unavailable"),
])
def test_non_ready_results_never_execute_analysis(monkeypatch, payload, decision, mode, expected):
    calls = []
    if mode == "housing_only":
        payload.pop("inflation")
    elif mode == "none":
        payload = {"question": payload["question"]}
    elif decision.get("start_period") == "2020-12":
        payload["question"] = "2020 Aralık-2021 Mart TÜFE değişimlerini göster."

    def forbidden(*args, **kwargs):
        raise AssertionError("Non-ready results must not execute either analysis")

    def model(prompt):
        calls.append(prompt)
        return json.dumps(decision)

    monkeypatch.setattr(service, "run_housing_analysis", forbidden)
    monkeypatch.setattr(service, "build_inflation_evidence", forbidden)
    with client_with_model(model) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == expected and body["analysis"] is None
    assert body["message"].strip()
    assert len(calls) == (0 if mode == "none" else 1)
    if decision.get("start_period") == "2020-12":
        assert body["decision"]["reason"] == "outside_coverage"


@pytest.mark.parametrize("question", [
    "2021 Ocak ayından itibaren TÜFE değişimlerini göster.",
    "2021 Ocak'tan sonraki TÜFE değişimlerini göster.",
])
def test_open_ended_single_month_ready_plan_is_blocked_before_analysis(
    monkeypatch, payload, question,
):
    cpi = json.loads((ROOT / "docs/economic-question-cpi-example.json").read_text(encoding="utf-8"))
    payload["inflation"] = cpi["inflation"]
    payload["question"] = question
    model_calls = []

    def forbidden(*args, **kwargs):
        raise AssertionError("Open-ended period must not execute an analysis")

    def model(prompt):
        model_calls.append(prompt)
        return json.dumps(ready(service.INFLATION_ID, end_period="2021-01"))

    monkeypatch.setattr(service, "run_housing_analysis", forbidden)
    monkeypatch.setattr(service, "build_inflation_evidence", forbidden)
    with client_with_model(model) as client:
        response = client.post(ENDPOINT, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "clarification_required"
    assert body["decision"] == {"status": "clarification_required", "reason": "period_required"}
    assert body["analysis"] is None
    assert len(model_calls) == 1


@pytest.mark.parametrize("problem", [
    "blank_question", "long_question", "path", "model", "analysis_id", "coverage", "include_narration",
    "nested_path", "empty_housing", "empty_cpi", "source", "boolean", "numeric_string", "nan", "infinity",
    "duplicate", "gap", "year_zero",
])
def test_bad_requests_return_safe_422_before_model_and_analysis(monkeypatch, payload, problem):
    if problem == "blank_question":
        payload["question"] = "   "
    elif problem == "long_question":
        payload["question"] = "x" * 2001
    elif problem in {"path", "model", "analysis_id", "coverage", "include_narration"}:
        payload[problem] = "private-input-marker"
    elif problem == "nested_path":
        payload["housing"]["path"] = "../../private-input-marker"
    elif problem == "empty_housing":
        payload["housing"]["bddk_monthly"] = []
    elif problem == "empty_cpi":
        payload["inflation"]["cpi_monthly"] = []
    elif problem == "source":
        payload["inflation"]["source_ref"] = "None"
    elif problem in {"boolean", "numeric_string", "nan", "infinity"}:
        payload["housing"]["evds_monthly"][0]["cpi_index"] = {
            "boolean": True, "numeric_string": "100", "nan": float("nan"), "infinity": float("inf"),
        }[problem]
    elif problem == "duplicate":
        payload["housing"]["bddk_monthly"].append(copy.deepcopy(payload["housing"]["bddk_monthly"][0]))
    elif problem == "gap":
        payload["inflation"]["cpi_monthly"].pop(1)
    else:
        payload["housing"]["bddk_monthly"][0]["period"] = "0000-01"

    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid request must not reach model or analysis")

    monkeypatch.setattr(service, "run_housing_analysis", forbidden)
    monkeypatch.setattr(service, "build_inflation_evidence", forbidden)
    with client_with_model(forbidden) as client:
        response = client.post(ENDPOINT, content=json.dumps(payload), headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_economic_input"
    assert "private-input-marker" not in response.text


@pytest.mark.parametrize("plan", [
    "not JSON private-provider-body", json.dumps(ready("web_search")),
    json.dumps(ready(sql="SELECT private_input")), json.dumps(ready(path="../../.env")),
    json.dumps(ready(service.INFLATION_ID, model="private-provider")), "x" * 8001,
])
def test_invalid_model_plan_is_safe_502_with_zero_analysis(monkeypatch, payload, plan):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid plan must not execute an analysis")

    monkeypatch.setattr(service, "run_housing_analysis", forbidden)
    monkeypatch.setattr(service, "build_inflation_evidence", forbidden)
    with client_with_model(lambda _: plan) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "invalid_question_plan"
    assert "private" not in response.text and ".env" not in response.text


def test_model_error_is_safe_not_retried_and_never_runs_analysis(monkeypatch, payload):
    calls = []

    def fail(prompt):
        calls.append(prompt)
        raise RuntimeError("private-token provider-body")

    def forbidden(*args, **kwargs):
        raise AssertionError("Failed planning must not execute an analysis")

    monkeypatch.setattr(service, "run_housing_analysis", forbidden)
    monkeypatch.setattr(service, "build_inflation_evidence", forbidden)
    with client_with_model(fail) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 502 and len(calls) == 1
    assert response.json()["detail"]["code"] == "question_planning_failed"
    assert "private-token" not in response.text


def test_analysis_failure_does_not_fall_back_to_other_service(monkeypatch, payload):
    def fail(*args, **kwargs):
        raise GoldAnalysisError("private-data-body")

    def forbidden(*args, **kwargs):
        raise AssertionError("The other analysis must not be tried")

    monkeypatch.setattr(service, "run_housing_analysis", fail)
    monkeypatch.setattr(service, "build_inflation_evidence", forbidden)
    with client_with_model(lambda _: json.dumps(ready())) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 422
    assert "private-data-body" not in response.text


@pytest.mark.parametrize("content", ["{", "[]", "null"])
def test_malformed_or_non_object_json_is_safe_422(content):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid JSON must not reach the model")

    with client_with_model(forbidden) as client:
        response = client.post(ENDPOINT, content=content, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_economic_input"


def test_cpi_chart_failure_is_safe_422_without_retry(monkeypatch, payload):
    from app.api import economic_question as api
    from app.tools.inflation_chart import InflationChartError

    payload["question"] = "2021 Ocak-Mart TÜFE değişimlerini göster."
    prompts = []

    def model(prompt):
        prompts.append(prompt)
        return json.dumps(ready(service.INFLATION_ID))

    def broken_chart(evidence):
        raise InflationChartError("private-chart-detail")

    monkeypatch.setattr(api, "build_inflation_chart", broken_chart)
    with client_with_model(model) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_economic_input"
    assert "private-chart-detail" not in response.text
    assert len(prompts) == 1

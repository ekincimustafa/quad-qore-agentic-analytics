from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.housing import get_housing_narrator
from app.api.main import create_app


def _payload() -> dict:
    return {
        "bddk_monthly": [
            {"period": "2021-01", "nominal_housing_loan_mn_try": 100.0},
            {"period": "2021-02", "nominal_housing_loan_mn_try": 100.0},
            {"period": "2021-03", "nominal_housing_loan_mn_try": 100.0},
        ],
        "evds_monthly": [
            {
                "period": "2021-01",
                "housing_loan_interest_rate_pct": 10.0,
                "weekly_observation_count": 4,
                "cpi_index": 100.0,
                "housing_price_index": 100.0,
            },
            {
                "period": "2021-02",
                "housing_loan_interest_rate_pct": 9.0,
                "weekly_observation_count": 4,
                "cpi_index": 110.0,
                "housing_price_index": 101.0,
            },
            {
                "period": "2021-03",
                "housing_loan_interest_rate_pct": 11.0,
                "weekly_observation_count": 5,
                "cpi_index": 120.0,
                "housing_price_index": 102.0,
            },
        ],
        "start_period": "2021-01",
        "end_period": "2021-03",
        "include_narration": False,
    }


def test_housing_endpoint_returns_verified_evidence_without_calling_mia():
    application = create_app()

    def must_not_run(_evidence):
        raise AssertionError("MIA should not be called")

    application.dependency_overrides[get_housing_narrator] = lambda: must_not_run
    response = TestClient(application).post("/analysis/housing", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["narration"] is None
    assert body["evidence"]["matched_periods"] == ["2021-02"]
    assert len(body["chart"]["data"]) == 6


def test_housing_endpoint_uses_injected_narrator_when_requested():
    application = create_app()
    application.dependency_overrides[get_housing_narrator] = (
        lambda: lambda evidence: f"verified={evidence.matched_month_count}"
    )
    payload = _payload()
    payload["include_narration"] = True

    response = TestClient(application).post("/analysis/housing", json=payload)

    assert response.status_code == 200
    assert response.json()["narration"] == "verified=1"


def test_housing_endpoint_returns_422_for_incomplete_periods():
    payload = _payload()
    payload["evds_monthly"].pop()

    response = TestClient(create_app()).post("/analysis/housing", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_analysis_input"


def test_housing_endpoint_returns_502_when_narration_fails():
    application = create_app()

    def failing_narrator(_evidence):
        raise RuntimeError("upstream unavailable")

    application.dependency_overrides[get_housing_narrator] = lambda: failing_narrator
    payload = _payload()
    payload["include_narration"] = True

    response = TestClient(application).post("/analysis/housing", json=payload)

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "narration_failed"


def test_openapi_schema_contains_housing_analysis_endpoint():
    response = TestClient(create_app()).get("/openapi.json")

    assert response.status_code == 200
    assert "/analysis/housing" in response.json()["paths"]

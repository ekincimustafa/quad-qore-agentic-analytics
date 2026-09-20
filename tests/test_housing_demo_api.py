from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from app.api.housing import get_housing_demo_paths, get_housing_narrator
from app.api.main import create_app
from app.services.housing_demo import HousingDemoPaths


def _write_demo_files(tmp_path) -> HousingDemoPaths:
    periods = ["2021-01", "2021-02", "2021-03"]
    bddk_path = tmp_path / "bddk.parquet"
    evds_path = tmp_path / "evds.csv"
    pd.DataFrame(
        {
            "period": periods,
            "nominal_housing_loan_mn_try": [100.0, 100.0, 100.0],
        }
    ).to_parquet(bddk_path, index=False)
    pd.DataFrame(
        {
            "period": periods,
            "housing_loan_interest_rate_pct": [10.0, 9.0, 11.0],
            "weekly_observation_count": [4, 4, 5],
            "cpi_index": [100.0, 110.0, 120.0],
            "housing_price_index": [100.0, 101.0, 102.0],
        }
    ).to_csv(evds_path, index=False)
    return HousingDemoPaths(bddk_path, evds_path)


def _request() -> dict:
    return {
        "start_period": "2021-01",
        "end_period": "2021-03",
        "include_narration": False,
    }


def test_demo_endpoint_loads_server_side_silver_files(tmp_path):
    application = create_app()
    paths = _write_demo_files(tmp_path)
    application.dependency_overrides[get_housing_demo_paths] = lambda: paths

    def must_not_run(_evidence):
        raise AssertionError("MIA should not be called")

    application.dependency_overrides[get_housing_narrator] = lambda: must_not_run
    response = TestClient(application).post(
        "/analysis/housing/demo",
        json=_request(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["evidence"]["matched_periods"] == ["2021-02"]
    assert body["narration"] is None
    assert len(body["chart"]["data"]) == 6


def test_demo_endpoint_uses_injected_narrator(tmp_path):
    application = create_app()
    paths = _write_demo_files(tmp_path)
    application.dependency_overrides[get_housing_demo_paths] = lambda: paths
    application.dependency_overrides[get_housing_narrator] = (
        lambda: lambda evidence: f"verified={evidence.matched_month_count}"
    )
    request = _request()
    request["include_narration"] = True

    response = TestClient(application).post(
        "/analysis/housing/demo",
        json=request,
    )

    assert response.status_code == 200
    assert response.json()["narration"] == "verified=1"


def test_demo_endpoint_returns_503_when_data_is_unavailable(tmp_path):
    application = create_app()
    paths = HousingDemoPaths(
        tmp_path / "missing.parquet",
        tmp_path / "missing.csv",
    )
    application.dependency_overrides[get_housing_demo_paths] = lambda: paths

    response = TestClient(application).post(
        "/analysis/housing/demo",
        json=_request(),
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "demo_data_unavailable"


def test_openapi_schema_contains_file_backed_demo_endpoint():
    response = TestClient(create_app()).get("/openapi.json")

    assert response.status_code == 200
    assert "/analysis/housing/demo" in response.json()["paths"]

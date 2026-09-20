from __future__ import annotations

import pandas as pd
import pytest

from app.services.housing_demo import (
    HousingDemoDataError,
    HousingDemoPaths,
    run_file_backed_housing_demo,
)


def _write_demo_files(tmp_path):
    periods = ["2021-01", "2021-02", "2021-03"]
    bddk = pd.DataFrame(
        {
            "period": periods,
            "nominal_housing_loan_mn_try": [100.0, 100.0, 100.0],
        }
    )
    evds = pd.DataFrame(
        {
            "period": periods,
            "housing_loan_interest_rate_pct": [10.0, 9.0, 11.0],
            "weekly_observation_count": [4, 4, 5],
            "cpi_index": [100.0, 110.0, 120.0],
            "housing_price_index": [100.0, 101.0, 102.0],
        }
    )
    bddk_path = tmp_path / "bddk.parquet"
    evds_path = tmp_path / "evds.csv"
    bddk.to_parquet(bddk_path, index=False)
    evds.to_csv(evds_path, index=False)
    return HousingDemoPaths(
        bddk_silver=bddk_path,
        evds_silver=evds_path,
    )


def test_file_backed_demo_runs_existing_analysis_pipeline(tmp_path):
    result = run_file_backed_housing_demo(
        _write_demo_files(tmp_path),
        start_period="2021-01",
        end_period="2021-03",
    )

    assert result.evidence.observed_month_count == 3
    assert result.evidence.matched_periods == ("2021-02",)
    assert len(result.chart["data"]) == 6
    assert result.narration is None


def test_file_backed_demo_uses_narrator_only_when_injected(tmp_path):
    result = run_file_backed_housing_demo(
        _write_demo_files(tmp_path),
        start_period="2021-01",
        end_period="2021-03",
        narrator=lambda evidence: f"verified={evidence.matched_month_count}",
    )

    assert result.narration == "verified=1"


def test_file_backed_demo_fails_when_silver_file_is_missing(tmp_path):
    paths = HousingDemoPaths(
        bddk_silver=tmp_path / "missing.parquet",
        evds_silver=tmp_path / "missing.csv",
    )

    with pytest.raises(HousingDemoDataError, match="was not found"):
        run_file_backed_housing_demo(
            paths,
            start_period="2021-01",
            end_period="2021-03",
        )


def test_file_backed_demo_rejects_empty_silver_file(tmp_path):
    bddk_path = tmp_path / "empty.csv"
    evds_path = tmp_path / "evds.csv"
    pd.DataFrame(columns=["period"]).to_csv(bddk_path, index=False)
    pd.DataFrame({"period": ["2021-01"]}).to_csv(evds_path, index=False)

    with pytest.raises(HousingDemoDataError, match="is empty"):
        run_file_backed_housing_demo(
            HousingDemoPaths(bddk_path, evds_path),
            start_period="2021-01",
            end_period="2021-01",
        )

from __future__ import annotations

import pandas as pd
import pytest

from app.lakehouse.gold import GoldAnalysisError
from app.services.housing_analysis import (
    HousingNarrationError,
    run_housing_analysis,
)


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    bddk = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02", "2021-03"],
            "nominal_housing_loan_mn_try": [100.0, 100.0, 100.0],
        }
    )
    evds = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02", "2021-03"],
            "housing_loan_interest_rate_pct": [10.0, 9.0, 11.0],
            "weekly_observation_count": [4, 4, 5],
            "cpi_index": [100.0, 110.0, 120.0],
            "housing_price_index": [100.0, 101.0, 102.0],
        }
    )
    return bddk, evds


def _run(*, narrator=None):
    bddk, evds = _inputs()
    return run_housing_analysis(
        bddk,
        evds,
        start_period="2021-01",
        end_period="2021-03",
        bddk_source_ref="BDDK test source",
        evds_source_refs="TP.KTF12; TP.TUKFIY2025.GENEL; TP.KFE.TR",
        narrator=narrator,
    )


def test_run_housing_analysis_builds_verified_evidence():
    result = _run()

    assert result.narration is None
    assert result.evidence.observed_month_count == 3
    assert result.evidence.matched_month_count == 1
    assert result.evidence.matched_periods == ("2021-02",)


def test_run_housing_analysis_calls_injected_narrator():
    result = _run(narrator=lambda evidence: f"matched={evidence.matched_month_count}")

    assert result.narration == "matched=1"


def test_run_housing_analysis_rejects_missing_period():
    bddk, evds = _inputs()

    with pytest.raises(GoldAnalysisError, match="missing periods"):
        run_housing_analysis(
            bddk,
            evds.iloc[:-1].copy(),
            start_period="2021-01",
            end_period="2021-03",
            bddk_source_ref="BDDK test source",
            evds_source_refs="TP.KTF12; TP.TUKFIY2025.GENEL; TP.KFE.TR",
        )


def test_run_housing_analysis_wraps_narrator_failure():
    def failing_narrator(_evidence):
        raise RuntimeError("upstream unavailable")

    with pytest.raises(HousingNarrationError, match="MIA narration failed"):
        _run(narrator=failing_narrator)

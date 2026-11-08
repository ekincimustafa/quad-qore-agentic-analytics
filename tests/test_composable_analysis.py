"""Behavior checks for the same filter core across different metric combinations."""

import json

import pandas as pd
import pytest
from pydantic import ValidationError

from app.services.composable_analysis import (
    ComposableAnalysisError,
    MonthlyCondition,
    MonthlyFilterPlan,
    run_monthly_filter,
)


@pytest.fixture
def inputs():
    # Prior-year CPI is 100. Dec-Apr real loan stocks are 100, 90, 100, 90, 100.
    periods = pd.period_range("2021-01", "2022-04", freq="M").astype(str).tolist()
    evds = pd.DataFrame({
        "period": periods,
        "cpi_index": [100.0] * 12 + [160.0, 150.0, 180.0, 210.0],
        "housing_loan_interest_rate_pct": 16.0,
        "weekly_observation_count": 4,
        "housing_price_index": 100.0,
    })
    bddk = pd.DataFrame({
        "period": periods[-5:],
        "nominal_housing_loan_mn_try": [100.0, 144.0, 150.0, 162.0, 210.0],
        "bddk_source_ref": ["synthetic://bddk/denominator"] + ["synthetic://bddk/window"] * 4,
        "data_quality_note": "synthetic fixture",
    })
    # Different row orders must still join by month.
    return {
        "evds_monthly": evds.iloc[::-1],
        "bddk_monthly": bddk.sample(frac=1, random_state=8),
        "cpi_source_ref": "synthetic://cpi",
        "bddk_source_ref": "synthetic://bddk",
    }


def plan(*conditions, start="2022-01", end="2022-04"):
    return MonthlyFilterPlan(
        start_period=start, end_period=end,
        conditions=tuple(
            MonthlyCondition(metric=metric, operator=op, threshold=threshold)
            for metric, op, threshold in conditions
        ),
    )


def test_annual_cpi_above_50_and_real_credit_falling(inputs):
    result = run_monthly_filter(plan(
        ("annual_inflation_pct", "gt", 50),
        ("real_housing_loan_change_pct", "lt", 0),
    ), **inputs)
    assert result.matched_periods == ("2022-01", "2022-03")
    assert result.evaluable_month_count == 4
    assert result.observations[0].values == pytest.approx({
        "annual_inflation_pct": 60.0, "real_housing_loan_change_pct": -10.0,
    })
    assert result.sources[0].source_refs == ("synthetic://cpi",)
    assert result.sources[1].source_refs == (
        "synthetic://bddk/denominator", "synthetic://bddk/window", "synthetic://cpi",
    )


def test_monthly_cpi_not_increasing_and_real_credit_increasing(inputs):
    result = run_monthly_filter(plan(
        ("monthly_inflation_pct", "lte", 0),
        ("real_housing_loan_change_pct", "gt", 0),
    ), **inputs)
    assert result.matched_periods == ("2022-02",)
    assert result.observations[1].values == pytest.approx({
        "monthly_inflation_pct": -6.25, "real_housing_loan_change_pct": 100 / 9,
    })


def test_cpi_only_needs_no_housing_and_does_not_invent_history(inputs):
    result = run_monthly_filter(
        plan(("annual_inflation_pct", "gte", 0), start="2021-12", end="2022-02"),
        evds_monthly=inputs["evds_monthly"][["period", "cpi_index"]],
        cpi_source_ref=inputs["cpi_source_ref"],
    )
    assert result.observations[0].period == "2021-12"
    assert result.observations[0].values == {"annual_inflation_pct": None}
    assert result.observations[0].matched is None
    assert result.matched_periods == ("2022-01", "2022-02")
    assert result.evaluable_month_count == 2


@pytest.mark.parametrize("prior_value", [None, 0.0])
def test_undefined_first_credit_change_is_null_not_false(inputs, prior_value):
    bddk = inputs["bddk_monthly"]
    if prior_value is None:
        inputs["bddk_monthly"] = bddk[bddk["period"] != "2021-12"]
    else:
        bddk.loc[bddk["period"] == "2021-12", "nominal_housing_loan_mn_try"] = prior_value
    result = run_monthly_filter(plan(
        ("annual_inflation_pct", "gt", 50), ("real_housing_loan_change_pct", "lt", 0),
    ), **inputs)
    assert result.observations[0].values["real_housing_loan_change_pct"] is None
    assert result.observations[0].matched is None
    assert result.matched_periods == ("2022-03",)
    assert result.evaluable_month_count == 3
    assert json.loads(result.model_dump_json())["observations"][0]["matched"] is None


@pytest.mark.parametrize("fault", ["missing", "duplicate"])
def test_missing_or_duplicate_requested_month_is_not_silently_dropped(inputs, fault):
    bddk = inputs["bddk_monthly"]
    inputs["bddk_monthly"] = (
        bddk[bddk["period"] != "2022-02"] if fault == "missing"
        else pd.concat([bddk, bddk.iloc[:1]])
    )
    with pytest.raises(ComposableAnalysisError, match="hesaplamaya uygun değil"):
        run_monthly_filter(plan(("real_housing_loan_change_pct", "lt", 0)), **inputs)


@pytest.mark.parametrize("overrides", [
    {"end_period": "2021-12"},
    {"end_period": "2032-01"},
    {"start_period": "0000-01"},
    {"sql": "SELECT 1"},
    {"conditions": [{"metric": "policy_rate", "operator": "gt", "threshold": 0}]},
    {"conditions": [{"metric": "annual_inflation_pct", "operator": "gt", "threshold": True}]},
    {"conditions": [{"metric": "annual_inflation_pct", "operator": "gt", "threshold": "50"}]},
    {"conditions": [{"metric": "annual_inflation_pct", "operator": "gt", "threshold": float("inf")}]},
])
def test_untrusted_json_cannot_select_arbitrary_or_invalid_operations(overrides):
    raw = {
        "start_period": "2022-01", "end_period": "2022-04",
        "conditions": [{"metric": "annual_inflation_pct", "operator": "gt", "threshold": 50}],
        **overrides,
    }
    with pytest.raises(ValidationError):
        MonthlyFilterPlan.model_validate_json(json.dumps(raw))

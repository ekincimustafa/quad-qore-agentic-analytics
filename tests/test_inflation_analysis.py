import json

import pandas as pd
import pytest

from app.services.inflation_analysis import InflationAnalysisError, build_inflation_evidence


def analyze(frame, start="2021-01", end="2021-03", source="synthetic://inflation-test"):
    return build_inflation_evidence(frame, start_period=start, end_period=end, source_ref=source)


@pytest.fixture
def cpi():
    return pd.DataFrame({
        "period": ["2021-01", "2021-02", "2021-03"],
        "cpi_index": [100.0, 110.0, 99.0],
    })


def test_known_changes_are_compounded_not_summed(cpi):
    evidence = analyze(cpi)
    jan, feb, mar = evidence.observations
    assert jan.monthly_inflation_pct is None
    assert feb.monthly_inflation_pct == pytest.approx(10.0)
    assert mar.monthly_inflation_pct == pytest.approx(-10.0)
    assert evidence.first_to_last_index_change_pct == pytest.approx(-1.0)
    assert evidence.first_cpi_index == 100 and evidence.last_cpi_index == 99
    assert all(row.annual_inflation_pct is None for row in evidence.observations)
    assert evidence.observed_month_count == 3
    assert evidence.source_ref == "synthetic://inflation-test"
    assert evidence.input_origin == "caller_supplied"
    json.dumps(evidence.model_dump(), allow_nan=False)


def test_query_keeps_previous_month_and_previous_year_history():
    frame = pd.DataFrame({
        "period": pd.period_range("2020-01", "2021-03", freq="M").astype(str),
        "cpi_index": [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 125, 130, 143, 140],
    })
    evidence = analyze(frame)
    jan, feb, mar = evidence.observations
    assert [row.period for row in evidence.observations] == ["2021-01", "2021-02", "2021-03"]
    assert evidence.available_period_start == "2020-01"
    assert evidence.available_period_end == "2021-03"
    assert jan.monthly_inflation_pct == pytest.approx(4.0)
    assert jan.annual_inflation_pct == pytest.approx(30.0)
    assert feb.monthly_inflation_pct == pytest.approx(10.0)
    assert feb.annual_inflation_pct == pytest.approx((143 / 102 - 1) * 100)
    assert mar.annual_inflation_pct == pytest.approx((140 / 104 - 1) * 100)
    assert evidence.first_to_last_index_change_pct == pytest.approx((140 / 130 - 1) * 100)


def test_twelve_rows_are_not_thirteen_months_of_history():
    frame = pd.DataFrame({
        "period": pd.period_range("2021-01", "2021-12", freq="M").astype(str),
        "cpi_index": [100.0 + i for i in range(12)],
    })
    evidence = analyze(frame, end="2021-12")
    assert all(row.annual_inflation_pct is None for row in evidence.observations)


def test_one_month_index_change_is_distinct_from_monthly_inflation(cpi):
    evidence = analyze(cpi, start="2021-02", end="2021-02")
    assert evidence.observed_month_count == 1
    assert evidence.first_to_last_index_change_pct == 0
    assert evidence.observations[0].monthly_inflation_pct == pytest.approx(10)


def test_unordered_input_and_unrelated_evds_columns_do_not_change_results(cpi):
    original = cpi.copy(deep=True)
    evds = cpi.assign(housing_loan_interest_rate_pct=[20, 19, 21]).iloc[::-1]
    assert analyze(evds) == analyze(cpi)
    pd.testing.assert_frame_equal(cpi, original)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), -float("inf"), True, None, "not-a-number", 1+2j])
def test_invalid_index_is_rejected(cpi, value):
    frame = cpi.astype({"cpi_index": object})
    frame.loc[1, "cpi_index"] = value
    with pytest.raises(InflationAnalysisError):
        analyze(frame)


@pytest.mark.parametrize("period", ["0000-01", "2021-13", "2021-1", " 2021-01", "2021-01 ", None])
def test_invalid_input_period_is_rejected(cpi, period):
    cpi.loc[0, "period"] = period
    with pytest.raises(InflationAnalysisError):
        analyze(cpi)


@pytest.mark.parametrize("start,end", [("2021-03", "2021-01"), ("2020-12", "2021-03"), ("2021-01", "2021-04"), ("0000-01", "2021-03")])
def test_invalid_query_range_is_rejected(cpi, start, end):
    with pytest.raises(InflationAnalysisError):
        analyze(cpi, start=start, end=end)


def test_duplicate_months_and_missing_months_fail_closed(cpi):
    for frame in (pd.concat([cpi, cpi.iloc[[0]]]), cpi.drop(index=1)):
        with pytest.raises(InflationAnalysisError):
            analyze(frame)


def test_gap_in_supplied_history_is_not_treated_as_a_row_offset():
    # A row 12 positions back is not necessarily the same calendar month last year.
    months = list(pd.period_range("2020-01", "2021-03", freq="M").astype(str))
    months.remove("2020-06")
    frame = pd.DataFrame({"period": months, "cpi_index": [100.0] * len(months)})
    with pytest.raises(InflationAnalysisError):
        analyze(frame)


@pytest.mark.parametrize("source", ["", "   ", None, "None", "nan", "<NA>"])
def test_invalid_source_reference_is_rejected(cpi, source):
    with pytest.raises(InflationAnalysisError):
        analyze(cpi, source=source)


@pytest.mark.parametrize("frame", [None, [], pd.DataFrame(), pd.DataFrame({"period": ["2021-01"]})])
def test_invalid_table_is_rejected(frame):
    with pytest.raises(InflationAnalysisError):
        analyze(frame)


def test_duplicate_columns_are_rejected():
    frame = pd.DataFrame([["2021-01", 100, 101]], columns=["period", "cpi_index", "cpi_index"])
    with pytest.raises(InflationAnalysisError):
        analyze(frame, end="2021-01")


def test_overflowing_derived_change_is_rejected():
    frame = pd.DataFrame({"period": ["2021-01", "2021-02"], "cpi_index": [1e-308, 1e308]})
    with pytest.raises(InflationAnalysisError):
        analyze(frame, end="2021-02")

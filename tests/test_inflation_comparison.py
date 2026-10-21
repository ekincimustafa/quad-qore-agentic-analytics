import pandas as pd
import pytest

from app.services.inflation_analysis import InflationAnalysisError
from app.services.inflation_comparison import (
    InflationComparisonError,
    compare_inflation_years,
)

PERIODS = pd.period_range("2022-12", "2024-12", freq="M").astype(str).tolist()
INDEX_VALUES = [
    100.0,
    102.0,
    104.0,
    106.0,
    108.0,
    110.0,
    112.0,
    114.0,
    116.0,
    118.0,
    119.0,
    119.5,
    120.0,
    123.0,
    126.0,
    129.0,
    132.0,
    135.0,
    138.0,
    141.0,
    144.0,
    146.0,
    147.0,
    148.5,
    150.0,
]


@pytest.fixture
def cpi():
    return pd.DataFrame({"period": PERIODS, "cpi_index": INDEX_VALUES})


def compare(frame, first=2023, second=2024, source="synthetic://inflation-comparison"):
    return compare_inflation_years(
        frame,
        first_year=first,
        second_year=second,
        source_ref=source,
    )


def test_two_full_years_preserve_requested_order_and_use_december_annual_rates(cpi):
    result = compare(cpi)

    assert result.analysis_id == "cpi_two_year_comparison"
    assert [item.year for item in result.years] == [2023, 2024]
    assert [len(item.evidence.observations) for item in result.years] == [12, 12]
    assert [row.period for row in result.years[0].evidence.observations] == [
        f"2023-{month:02d}" for month in range(1, 13)
    ]
    assert [row.period for row in result.years[1].evidence.observations] == [
        f"2024-{month:02d}" for month in range(1, 13)
    ]
    assert result.years[0].evidence.observations[-1].annual_inflation_pct == pytest.approx(20.0)
    assert result.years[1].evidence.observations[-1].annual_inflation_pct == pytest.approx(25.0)
    assert result.second_minus_first_december_annual_inflation_pp == pytest.approx(5.0)


def test_reversed_year_order_changes_the_difference_sign(cpi):
    result = compare(cpi, first=2024, second=2023)

    assert [item.year for item in result.years] == [2024, 2023]
    assert result.years[0].evidence.observations[-1].annual_inflation_pct == pytest.approx(25.0)
    assert result.years[1].evidence.observations[-1].annual_inflation_pct == pytest.approx(20.0)
    assert result.second_minus_first_december_annual_inflation_pp == pytest.approx(-5.0)


def test_january_to_december_index_change_is_not_the_december_annual_rate(cpi):
    result = compare(cpi)
    first_year, second_year = result.years

    first_change = first_year.evidence.first_to_last_index_change_pct
    second_change = second_year.evidence.first_to_last_index_change_pct
    assert first_change == pytest.approx((120.0 / 102.0 - 1.0) * 100.0)
    assert second_change == pytest.approx((150.0 / 123.0 - 1.0) * 100.0)
    assert first_change != pytest.approx(20.0)
    assert second_change != pytest.approx(25.0)
    assert result.second_minus_first_december_annual_inflation_pp == pytest.approx(5.0)


def test_missing_previous_december_leaves_first_annual_rate_and_difference_null(cpi):
    frame = cpi.loc[cpi["period"] != "2022-12"].reset_index(drop=True)
    result = compare(frame)

    first_year, second_year = result.years
    assert first_year.evidence.available_period_start == "2023-01"
    assert first_year.evidence.observations[-1].annual_inflation_pct is None
    assert second_year.evidence.observations[-1].annual_inflation_pct == pytest.approx(25.0)
    assert result.second_minus_first_december_annual_inflation_pp is None


def test_missing_interior_month_is_rejected(cpi):
    frame = cpi.loc[cpi["period"] != "2023-06"].reset_index(drop=True)

    with pytest.raises(InflationAnalysisError):
        compare(frame)


@pytest.mark.parametrize("first,second", [(2021, 2023), (2023, 2025)])
def test_year_outside_full_calendar_coverage_is_rejected(cpi, first, second):
    with pytest.raises(InflationAnalysisError):
        compare(cpi, first=first, second=second)


def test_same_year_is_rejected(cpi):
    with pytest.raises(InflationComparisonError, match="farklı olmalıdır"):
        compare(cpi, first=2023, second=2023)


@pytest.mark.parametrize(
    "invalid_year",
    [True, False, 0, -2023, 10000, 2023.0, "2023", None],
)
def test_invalid_year_is_rejected(cpi, invalid_year):
    with pytest.raises(InflationComparisonError, match="tam sayı"):
        compare(cpi, first=invalid_year)
    with pytest.raises(InflationComparisonError, match="tam sayı"):
        compare(cpi, first=2023, second=invalid_year)


def test_source_reference_is_preserved_in_comparison_and_evidence(cpi):
    result = compare(cpi, source="synthetic://source-ref")

    assert result.source_ref == "synthetic://source-ref"
    assert [item.evidence.source_ref for item in result.years] == [
        "synthetic://source-ref",
        "synthetic://source-ref",
    ]


def test_unordered_input_with_extra_columns_is_not_modified(cpi):
    original = cpi.copy(deep=True)
    shuffled = cpi.assign(housing_loan_interest_rate_pct=20.0).iloc[::-1]
    shuffled_original = shuffled.copy(deep=True)

    assert compare(shuffled) == compare(cpi)
    pd.testing.assert_frame_equal(cpi, original)
    pd.testing.assert_frame_equal(shuffled, shuffled_original)

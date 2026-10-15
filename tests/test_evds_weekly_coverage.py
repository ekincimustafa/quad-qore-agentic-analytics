import pandas as pd
import pytest

from app.lakehouse.silver import monthly_housing_loan_interest_rate
from app.lakehouse.evds_weekly_coverage import assess_monthly_weekly_coverage


def test_single_week_without_verified_calendar_is_unverified():
    weekly_data = pd.DataFrame([
        {
            "Tarih": "08-01-2021",
            "TP_KTF12": "18.61",
        }
    ])

    monthly = monthly_housing_loan_interest_rate(
        weekly_data,
        start_date="2021-01-01",
        end_date="2021-01-31",
    )

    # Mevcut Silver davranışı değişmemeli.
    assert monthly.iloc[0]["housing_loan_interest_rate_pct"] == pytest.approx(18.61)
    assert monthly.iloc[0]["weekly_observation_count"] == 1

    # Resmî takvim doğrulanmadan tam kapsam iddia edilmemeli.
    coverage = assess_monthly_weekly_coverage(
        period="2021-01",
        observed_dates=["2021-01-08"],
    )

    assert coverage.status == "unverified"
    assert coverage.observed_count == 1
    assert coverage.expected_count is None

@pytest.mark.parametrize("count", [1, 4, 5])
def test_weekly_count_does_not_prove_complete_coverage(count):
    dates = [
        "2021-01-01",
        "2021-01-08",
        "2021-01-15",
        "2021-01-22",
        "2021-01-29",
    ]

    coverage = assess_monthly_weekly_coverage(
        period="2021-01",
        observed_dates=dates[:count],
    )

    assert coverage.status == "unverified"
    assert coverage.observed_count == count
    assert coverage.expected_count is None

@pytest.mark.parametrize(
    "dates",
    [
        [],
        ["2021-01-08", "2021-01-08"],
        ["2021-02-05"],
        ["2021-01-99"],
    ],
)
def test_invalid_weekly_observations_are_rejected(dates):
    with pytest.raises(ValueError):
        assess_monthly_weekly_coverage(
            period="2021-01",
            observed_dates=dates,
        )
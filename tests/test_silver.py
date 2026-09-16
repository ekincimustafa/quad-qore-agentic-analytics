import pandas as pd
import pytest

from app.lakehouse.silver import (
    merge_monthly_evds_series,
    monthly_cpi_index,
    monthly_housing_loan_interest_rate,
    monthly_housing_price_index,
    validate_monthly_evds_data,
)


def test_converts_weekly_housing_rate_to_monthly_average() -> None:
    weekly_data = pd.DataFrame(
        {
            "Tarih": [
                "01-01-2021",
                "08-01-2021",
                "15-01-2021",
                "22-01-2021",
                "29-01-2021",
            ],
            "TP_KTF12": [
                18.61,
                18.61,
                18.40,
                18.19,
                18.13,
            ],
        }
    )

    result = monthly_housing_loan_interest_rate(weekly_data)

    assert len(result) == 1
    assert result.loc[0, "period"] == "2021-01"
    assert result.loc[
        0, "housing_loan_interest_rate_pct"
    ] == pytest.approx(18.388)
    assert result.loc[0, "weekly_observation_count"] == 5


def test_filters_requested_date_range() -> None:
    weekly_data = pd.DataFrame(
        {
            "Tarih": [
                "25-12-2020",
                "01-01-2021",
                "08-01-2021",
                "03-07-2026",
            ],
            "TP_KTF12": [
                18.50,
                18.61,
                18.61,
                40.00,
            ],
        }
    )

    result = monthly_housing_loan_interest_rate(weekly_data)

    assert len(result) == 1
    assert result.loc[0, "period"] == "2021-01"
    assert result.loc[0, "weekly_observation_count"] == 2


def test_rejects_non_numeric_interest_rate() -> None:
    weekly_data = pd.DataFrame(
        {
            "Tarih": ["01-01-2021"],
            "TP_KTF12": ["invalid"],
        }
    )

    with pytest.raises(ValueError):
        monthly_housing_loan_interest_rate(weekly_data)


def test_rejects_missing_evds_columns() -> None:
    weekly_data = pd.DataFrame(
        {
            "Tarih": ["01-01-2021"],
        }
    )

    with pytest.raises(ValueError):
        monthly_housing_loan_interest_rate(weekly_data)


def test_standardizes_monthly_cpi_from_wide_export() -> None:
    raw_data = pd.DataFrame(
        {
            "Unnamed: 0": [
                "Genel Endeks",
                "Seri Açıklamaları",
                "TP.TUKFIY2025.GENEL",
            ],
            "2021-01": [
                16.125135,
                None,
                "Genel Endeks-Düzey",
            ],
            "2021-02": [
                16.271527,
                None,
                None,
            ],
        }
    )

    result = monthly_cpi_index(raw_data)

    assert len(result) == 2
    assert result.loc[0, "period"] == "2021-01"
    assert result.loc[0, "cpi_index"] == pytest.approx(16.125135)
    assert result.loc[1, "period"] == "2021-02"
    assert result.loc[1, "cpi_index"] == pytest.approx(16.271527)


def test_standardizes_monthly_housing_price_index() -> None:
    raw_data = pd.DataFrame(
        {
            "Tarih": [
                "2021-01",
                "2021-02",
                "Seri Açıklamaları",
                "TP.KFE.TR",
            ],
            "TP_KFE_TR": [
                16.49,
                16.98,
                None,
                "Konut Fiyat Endeksi (KFE)-Düzey",
            ],
        }
    )

    result = monthly_housing_price_index(raw_data)

    assert len(result) == 2
    assert result.loc[0, "period"] == "2021-01"
    assert result.loc[
        0, "housing_price_index"
    ] == pytest.approx(16.49)
    assert result.loc[1, "period"] == "2021-02"
    assert result.loc[
        1, "housing_price_index"
    ] == pytest.approx(16.98)


def test_merges_monthly_evds_series_by_period() -> None:
    housing_rate = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02"],
            "housing_loan_interest_rate_pct": [18.388, 17.985],
            "weekly_observation_count": [5, 4],
        }
    )

    cpi = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02"],
            "cpi_index": [16.125135, 16.271527],
        }
    )

    housing_price = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02"],
            "housing_price_index": [16.49, 16.98],
        }
    )

    result = merge_monthly_evds_series(
        housing_rate,
        cpi,
        housing_price,
    )

    assert len(result) == 2
    assert result["period"].is_unique

    assert result.loc[0, "period"] == "2021-01"
    assert result.loc[
        0, "housing_loan_interest_rate_pct"
    ] == pytest.approx(18.388)
    assert result.loc[0, "cpi_index"] == pytest.approx(16.125135)
    assert result.loc[
        0, "housing_price_index"
    ] == pytest.approx(16.49)


def test_merge_keeps_missing_period_visible() -> None:
    housing_rate = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02"],
            "housing_loan_interest_rate_pct": [18.388, 17.985],
            "weekly_observation_count": [5, 4],
        }
    )

    cpi = pd.DataFrame(
        {
            "period": ["2021-01"],
            "cpi_index": [16.125135],
        }
    )

    housing_price = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02"],
            "housing_price_index": [16.49, 16.98],
        }
    )

    result = merge_monthly_evds_series(
        housing_rate,
        cpi,
        housing_price,
    )

    february = result[result["period"] == "2021-02"].iloc[0]

    assert pd.isna(february["cpi_index"])

def test_ignores_evds_metadata_rows_in_weekly_rate() -> None:
    weekly_data = pd.DataFrame(
        {
            "Tarih": [
                "01-01-2021",
                "08-01-2021",
                "Seri Açıklamaları",
                "Notlar",
            ],
            "TP_KTF12": [
                18.61,
                18.41,
                None,
                None,
            ],
        }
    )

    result = monthly_housing_loan_interest_rate(weekly_data)

    assert len(result) == 1
    assert result.loc[0, "period"] == "2021-01"
    assert result.loc[0, "weekly_observation_count"] == 2


def test_rejects_invalid_date_like_weekly_observation() -> None:
    weekly_data = pd.DataFrame(
        {
            "Tarih": [
                "01-01-2021",
                "31-02-2021",
                "Seri Açıklamaları",
            ],
            "TP_KTF12": [
                18.61,
                18.40,
                None,
            ],
        }
    )

    with pytest.raises(
        ValueError,
        match="Invalid EVDS observation dates",
    ):
        monthly_housing_loan_interest_rate(weekly_data)


def test_validates_complete_66_month_evds_range() -> None:
    periods = pd.period_range(
        "2021-01",
        "2026-06",
        freq="M",
    ).astype(str)

    monthly_data = pd.DataFrame(
        {
            "period": periods,
            "housing_loan_interest_rate_pct": [20.0] * len(periods),
            "cpi_index": [50.0] * len(periods),
            "housing_price_index": [80.0] * len(periods),
            "weekly_observation_count": [4] * len(periods),
        }
    )

    assert len(monthly_data) == 66

    validate_monthly_evds_data(monthly_data)


def test_validates_60_month_demo_range() -> None:
    periods = pd.period_range(
        "2021-01",
        "2025-12",
        freq="M",
    ).astype(str)

    monthly_data = pd.DataFrame(
        {
            "period": periods,
            "housing_loan_interest_rate_pct": [20.0] * len(periods),
            "cpi_index": [50.0] * len(periods),
            "housing_price_index": [80.0] * len(periods),
            "weekly_observation_count": [4] * len(periods),
        }
    )

    assert len(monthly_data) == 60

    validate_monthly_evds_data(
        monthly_data,
        start_period="2021-01",
        end_period="2025-12",
    )


def test_validation_detects_one_source_missing_month() -> None:
    housing_rate = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02", "2021-03"],
            "housing_loan_interest_rate_pct": [18.0, 17.5, 17.0],
            "weekly_observation_count": [4, 4, 4],
        }
    )

    cpi = pd.DataFrame(
        {
            "period": ["2021-01", "2021-03"],
            "cpi_index": [16.1, 16.4],
        }
    )

    housing_price = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02", "2021-03"],
            "housing_price_index": [16.5, 17.0, 17.3],
        }
    )

    merged = merge_monthly_evds_series(
        housing_rate,
        cpi,
        housing_price,
    )

    with pytest.raises(
        ValueError,
        match="Non-numeric or missing EVDS values",
    ):
        validate_monthly_evds_data(
            merged,
            start_period="2021-01",
            end_period="2021-03",
        )


def test_validation_detects_month_missing_from_all_sources() -> None:
    housing_rate = pd.DataFrame(
        {
            "period": ["2021-01", "2021-03"],
            "housing_loan_interest_rate_pct": [18.0, 17.0],
            "weekly_observation_count": [4, 4],
        }
    )

    cpi = pd.DataFrame(
        {
            "period": ["2021-01", "2021-03"],
            "cpi_index": [16.1, 16.4],
        }
    )

    housing_price = pd.DataFrame(
        {
            "period": ["2021-01", "2021-03"],
            "housing_price_index": [16.5, 17.3],
        }
    )

    merged = merge_monthly_evds_series(
        housing_rate,
        cpi,
        housing_price,
    )

    with pytest.raises(
        ValueError,
        match="Missing expected EVDS periods",
    ):
        validate_monthly_evds_data(
            merged,
            start_period="2021-01",
            end_period="2021-03",
        )


def test_validation_rejects_duplicate_periods() -> None:
    monthly_data = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02", "2021-02"],
            "housing_loan_interest_rate_pct": [18.0, 17.5, 17.4],
            "weekly_observation_count": [4, 4, 4],
            "cpi_index": [16.1, 16.2, 16.2],
            "housing_price_index": [16.5, 17.0, 17.0],
        }
    )

    with pytest.raises(
        ValueError,
        match="Duplicate EVDS periods",
    ):
        validate_monthly_evds_data(
            monthly_data,
            start_period="2021-01",
            end_period="2021-02",
        )


def _valid_monthly_evds_row() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "period": ["2021-01"],
            "housing_loan_interest_rate_pct": [18.0],
            "cpi_index": [16.1],
            "housing_price_index": [16.5],
            "weekly_observation_count": [4],
        }
    )


def test_validation_requires_weekly_observation_count() -> None:
    monthly_data = _valid_monthly_evds_row().drop(
        columns=["weekly_observation_count"]
    )

    with pytest.raises(
        ValueError,
        match="Missing required monthly EVDS columns",
    ):
        validate_monthly_evds_data(
            monthly_data,
            start_period="2021-01",
            end_period="2021-01",
        )


@pytest.mark.parametrize(
    "column",
    [
        "cpi_index",
        "housing_price_index",
        "weekly_observation_count",
    ],
)
def test_validation_rejects_non_positive_values(
    column: str,
) -> None:
    monthly_data = _valid_monthly_evds_row()
    monthly_data.loc[0, column] = 0

    with pytest.raises(
        ValueError,
        match="must contain only positive values",
    ):
        validate_monthly_evds_data(
            monthly_data,
            start_period="2021-01",
            end_period="2021-01",
        )


def test_validation_rejects_fractional_weekly_observation_count() -> None:
    monthly_data = _valid_monthly_evds_row()
    monthly_data["weekly_observation_count"] = (
        monthly_data["weekly_observation_count"].astype(float)
    )
    monthly_data.loc[0, "weekly_observation_count"] = 2.5

    with pytest.raises(
        ValueError,
        match="weekly_observation_count must contain only integer values",
    ):
        validate_monthly_evds_data(
            monthly_data,
            start_period="2021-01",
            end_period="2021-01",
        )


@pytest.mark.parametrize(
    "column",
    [
        "housing_loan_interest_rate_pct",
        "cpi_index",
        "housing_price_index",
        "weekly_observation_count",
    ],
)
def test_validation_rejects_non_numeric_values(
    column: str,
) -> None:
    monthly_data = _valid_monthly_evds_row()
    monthly_data[column] = monthly_data[column].astype(object)
    monthly_data.loc[0, column] = "not-a-number"

    with pytest.raises(
        ValueError,
        match="Non-numeric or missing EVDS values",
    ):
        validate_monthly_evds_data(
            monthly_data,
            start_period="2021-01",
            end_period="2021-01",
        )


@pytest.mark.parametrize(
    "column",
    [
        "housing_loan_interest_rate_pct",
        "cpi_index",
        "housing_price_index",
        "weekly_observation_count",
    ],
)
def test_validation_rejects_infinite_values(
    column: str,
) -> None:
    monthly_data = _valid_monthly_evds_row()
    monthly_data[column] = monthly_data[column].astype(float)
    monthly_data.loc[0, column] = float("inf")

    with pytest.raises(
        ValueError,
        match="Non-finite EVDS values",
    ):
        validate_monthly_evds_data(
            monthly_data,
            start_period="2021-01",
            end_period="2021-01",
        )


def test_cpi_rejects_invalid_calendar_month() -> None:
    raw_data = pd.DataFrame(
        {
            "Unnamed: 0": ["Genel Endeks"],
            "2021-13": [16.1],
        }
    )

    with pytest.raises(
        ValueError,
        match="Invalid monthly period for CPI period",
    ):
        monthly_cpi_index(raw_data)


def test_kfe_rejects_invalid_calendar_month() -> None:
    raw_data = pd.DataFrame(
        {
            "Tarih": ["2021-13"],
            "TP_KFE_TR": [16.5],
        }
    )

    with pytest.raises(
        ValueError,
        match="Invalid monthly period for KFE period",
    ):
        monthly_housing_price_index(raw_data)


def test_validation_rejects_invalid_calendar_month() -> None:
    monthly_data = _valid_monthly_evds_row()
    monthly_data.loc[0, "period"] = "2021-13"

    with pytest.raises(
        ValueError,
        match="Invalid monthly period for period",
    ):
        validate_monthly_evds_data(
            monthly_data,
            start_period="2021-01",
            end_period="2021-01",
        )


def test_validation_rejects_unexpected_period() -> None:
    monthly_data = pd.concat(
        [
            _valid_monthly_evds_row(),
            pd.DataFrame(
                {
                    "period": ["2021-02"],
                    "housing_loan_interest_rate_pct": [17.5],
                    "cpi_index": [16.2],
                    "housing_price_index": [17.0],
                    "weekly_observation_count": [4],
                }
            ),
        ],
        ignore_index=True,
    )

    with pytest.raises(
        ValueError,
        match="Unexpected EVDS periods detected",
    ):
        validate_monthly_evds_data(
            monthly_data,
            start_period="2021-01",
            end_period="2021-01",
        )


def test_validation_rejects_reversed_period_range() -> None:
    monthly_data = _valid_monthly_evds_row()

    with pytest.raises(
        ValueError,
        match="start_period must be less than or equal to end_period",
    ):
        validate_monthly_evds_data(
            monthly_data,
            start_period="2021-02",
            end_period="2021-01",
        )


def test_rejects_invalid_slash_date_with_observation() -> None:
    weekly_data = pd.DataFrame(
        {
            "Tarih": [
                "01/01/2021",
                "31/02/2021",
                "Seri Açıklamaları",
            ],
            "TP_KTF12": [
                18.61,
                18.40,
                None,
            ],
        }
    )

    with pytest.raises(
        ValueError,
        match="Invalid EVDS observation dates",
    ):
        monthly_housing_loan_interest_rate(weekly_data)

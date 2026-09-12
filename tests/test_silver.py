import pandas as pd
import pytest

from app.lakehouse.silver import (
    merge_monthly_evds_series,
    monthly_cpi_index,
    monthly_housing_loan_interest_rate,
    monthly_housing_price_index,
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
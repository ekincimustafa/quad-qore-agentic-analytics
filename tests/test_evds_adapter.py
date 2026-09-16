import json

import pytest

from app.lakehouse.evds_adapter import (
    adapt_evds_api_response,
)
from app.lakehouse.silver import (
    merge_monthly_evds_series,
    monthly_cpi_index,
    monthly_housing_loan_interest_rate,
    monthly_housing_price_index,
    validate_monthly_evds_data,
)


def _raw(items: list[dict]) -> bytes:
    return json.dumps(
        {
            "totalCount": len(items),
            "items": items,
        }
    ).encode("utf-8")


def test_weekly_rate_adapter_preserves_api_observations():
    raw = _raw(
        [
            {
                "Tarih": "01-01-2021",
                "YEARWEEK": "2021-1",
                "TP_KTF12": "10.00000000",
                "UNIXTIME": {"$numberLong": "1"},
            },
            {
                "Tarih": "08-01-2021",
                "YEARWEEK": "2021-2",
                "TP_KTF12": "20.00000000",
                "UNIXTIME": {"$numberLong": "2"},
            },
        ]
    )

    result = adapt_evds_api_response(
        raw,
        "TP.KTF12",
    )

    assert list(result.columns) == [
        "Tarih",
        "TP_KTF12",
    ]
    assert result["Tarih"].tolist() == [
        "01-01-2021",
        "08-01-2021",
    ]
    assert result["TP_KTF12"].tolist() == [
        "10.00000000",
        "20.00000000",
    ]


def test_cpi_adapter_converts_api_long_format_to_silver_wide_format():
    raw = _raw(
        [
            {
                "Tarih": "2021-1",
                "TP_TUKFIY2025_GENEL": "16.12513498",
                "UNIXTIME": {"$numberLong": "1"},
            },
            {
                "Tarih": "2021-2",
                "TP_TUKFIY2025_GENEL": "16.50000000",
                "UNIXTIME": {"$numberLong": "2"},
            },
        ]
    )

    result = adapt_evds_api_response(
        raw,
        "TP.TUKFIY2025.GENEL",
    )

    assert result.loc[0, "Unnamed: 0"] == "Genel Endeks"
    assert result.loc[0, "2021-01"] == "16.12513498"
    assert result.loc[0, "2021-02"] == "16.50000000"


def test_kfe_adapter_zero_pads_api_month():
    raw = _raw(
        [
            {
                "Tarih": "2021-1",
                "TP_KFE_TR": "16.49000000",
                "UNIXTIME": {"$numberLong": "1"},
            },
            {
                "Tarih": "2021-10",
                "TP_KFE_TR": "20.00000000",
                "UNIXTIME": {"$numberLong": "2"},
            },
        ]
    )

    result = adapt_evds_api_response(
        raw,
        "TP.KFE.TR",
    )

    assert result["Tarih"].tolist() == [
        "2021-01",
        "2021-10",
    ]


def test_adapter_rejects_missing_series_value_field():
    raw = _raw(
        [
            {
                "Tarih": "2021-1",
            }
        ]
    )

    with pytest.raises(
        ValueError,
        match="missing required fields",
    ):
        adapt_evds_api_response(
            raw,
            "TP.KFE.TR",
        )


def test_cpi_adapter_rejects_duplicate_month():
    raw = _raw(
        [
            {
                "Tarih": "2021-1",
                "TP_TUKFIY2025_GENEL": "16.1",
            },
            {
                "Tarih": "2021-01",
                "TP_TUKFIY2025_GENEL": "16.2",
            },
        ]
    )

    with pytest.raises(
        ValueError,
        match="Duplicate CPI periods",
    ):
        adapt_evds_api_response(
            raw,
            "TP.TUKFIY2025.GENEL",
        )


def test_api_adapter_integrates_with_existing_silver_functions():
    rate_raw = _raw(
        [
            {
                "Tarih": "01-01-2021",
                "TP_KTF12": "10.0",
            },
            {
                "Tarih": "08-01-2021",
                "TP_KTF12": "20.0",
            },
            {
                "Tarih": "05-02-2021",
                "TP_KTF12": "30.0",
            },
        ]
    )

    cpi_raw = _raw(
        [
            {
                "Tarih": "2021-1",
                "TP_TUKFIY2025_GENEL": "16.1",
            },
            {
                "Tarih": "2021-2",
                "TP_TUKFIY2025_GENEL": "16.3",
            },
        ]
    )

    kfe_raw = _raw(
        [
            {
                "Tarih": "2021-1",
                "TP_KFE_TR": "16.49",
            },
            {
                "Tarih": "2021-2",
                "TP_KFE_TR": "17.20",
            },
        ]
    )

    rate_input = adapt_evds_api_response(
        rate_raw,
        "TP.KTF12",
    )
    cpi_input = adapt_evds_api_response(
        cpi_raw,
        "TP.TUKFIY2025.GENEL",
    )
    kfe_input = adapt_evds_api_response(
        kfe_raw,
        "TP.KFE.TR",
    )

    rate = monthly_housing_loan_interest_rate(
        rate_input,
        start_date="2021-01-01",
        end_date="2021-02-28",
    )
    cpi = monthly_cpi_index(
        cpi_input,
        start_period="2021-01",
        end_period="2021-02",
    )
    kfe = monthly_housing_price_index(
        kfe_input,
        start_period="2021-01",
        end_period="2021-02",
    )

    merged = merge_monthly_evds_series(
        rate,
        cpi,
        kfe,
    )

    validate_monthly_evds_data(
        merged,
        start_period="2021-01",
        end_period="2021-02",
    )

    assert merged["period"].tolist() == [
        "2021-01",
        "2021-02",
    ]

    assert merged[
        "housing_loan_interest_rate_pct"
    ].tolist() == [
        15.0,
        30.0,
    ]

    assert merged[
        "weekly_observation_count"
    ].tolist() == [
        2,
        1,
    ]

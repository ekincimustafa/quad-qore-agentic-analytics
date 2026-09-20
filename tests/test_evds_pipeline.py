import json
from hashlib import sha256

import pandas as pd
import pytest

from app.lakehouse.evds_pipeline import (
    build_evds_silver_from_bronze,
)


def _write_response(path, items):
    body = json.dumps(
        {
            "totalCount": len(items),
            "items": items,
        }
    ).encode("utf-8")

    path.write_bytes(body)


def _make_raw_files(
    tmp_path,
    start_period,
    end_period,
    *,
    missing_cpi_period=None,
    duplicate_kfe_period=None,
):
    periods = pd.period_range(
        start=start_period,
        end=end_period,
        freq="M",
    )

    rate_items = []
    cpi_items = []
    kfe_items = []

    for index, period in enumerate(periods):
        rate_items.extend(
            [
                {
                    "Tarih": (
                        f"01-{period.month:02d}-{period.year}"
                    ),
                    "TP_KTF12": str(10.0 + index),
                },
                {
                    "Tarih": (
                        f"15-{period.month:02d}-{period.year}"
                    ),
                    "TP_KTF12": str(20.0 + index),
                },
            ]
        )

        api_period = f"{period.year}-{period.month}"

        if str(period) != missing_cpi_period:
            cpi_items.append(
                {
                    "Tarih": api_period,
                    "TP_TUKFIY2025_GENEL": str(
                        100.0 + index
                    ),
                }
            )

        kfe_item = {
            "Tarih": api_period,
            "TP_KFE_TR": str(200.0 + index),
        }

        kfe_items.append(kfe_item)

        if str(period) == duplicate_kfe_period:
            kfe_items.append(dict(kfe_item))

    rate_path = tmp_path / "rate.json"
    cpi_path = tmp_path / "cpi.json"
    kfe_path = tmp_path / "kfe.json"

    _write_response(
        rate_path,
        rate_items,
    )
    _write_response(
        cpi_path,
        cpi_items,
    )
    _write_response(
        kfe_path,
        kfe_items,
    )

    return rate_path, cpi_path, kfe_path


@pytest.mark.parametrize(
    ("start_period", "end_period", "expected_rows"),
    [
        ("2021-01", "2025-12", 60),
        ("2021-01", "2026-06", 66),
    ],
)
def test_build_evds_silver_validates_expected_month_count(
    tmp_path,
    start_period,
    end_period,
    expected_rows,
):
    rate_path, cpi_path, kfe_path = _make_raw_files(
        tmp_path,
        start_period,
        end_period,
    )

    output = tmp_path / "evds_monthly.csv"

    result = build_evds_silver_from_bronze(
        housing_rate_path=rate_path,
        cpi_path=cpi_path,
        housing_price_path=kfe_path,
        output_path=output,
        start_period=start_period,
        end_period=end_period,
    )

    assert result.row_count == expected_rows
    assert result.start_period == start_period
    assert result.end_period == end_period
    assert result.path == output
    assert output.exists()

    assert result.sha256 == sha256(
        output.read_bytes()
    ).hexdigest()


def test_build_evds_silver_rejects_missing_month(
    tmp_path,
):
    rate_path, cpi_path, kfe_path = _make_raw_files(
        tmp_path,
        "2021-01",
        "2021-03",
        missing_cpi_period="2021-02",
    )

    with pytest.raises(
        ValueError,
        match="Non-numeric or missing EVDS values",
    ):
        build_evds_silver_from_bronze(
            housing_rate_path=rate_path,
            cpi_path=cpi_path,
            housing_price_path=kfe_path,
            output_path=tmp_path / "silver.csv",
            start_period="2021-01",
            end_period="2021-03",
        )


def test_build_evds_silver_rejects_duplicate_month(
    tmp_path,
):
    rate_path, cpi_path, kfe_path = _make_raw_files(
        tmp_path,
        "2021-01",
        "2021-03",
        duplicate_kfe_period="2021-02",
    )

    with pytest.raises(
        ValueError,
        match="Duplicate KFE periods",
    ):
        build_evds_silver_from_bronze(
            housing_rate_path=rate_path,
            cpi_path=cpi_path,
            housing_price_path=kfe_path,
            output_path=tmp_path / "silver.csv",
            start_period="2021-01",
            end_period="2021-03",
        )

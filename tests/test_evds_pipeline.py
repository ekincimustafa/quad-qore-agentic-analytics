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


def test_build_reports_unverified_weekly_coverage(tmp_path):
    rate_path, cpi_path, kfe_path = _make_raw_files(
        tmp_path,
        "2021-01",
        "2021-01",
    )

    output = tmp_path / "evds_monthly.csv"

    result = build_evds_silver_from_bronze(
        housing_rate_path=rate_path,
        cpi_path=cpi_path,
        housing_price_path=kfe_path,
        output_path=output,
        start_period="2021-01",
        end_period="2021-01",
    )

    # Mevcut Silver hesaplaması değişmemeli.
    silver = pd.read_csv(output)

    assert silver.loc[0, "housing_loan_interest_rate_pct"] == pytest.approx(15.0)
    assert silver.loc[0, "weekly_observation_count"] == 2

    # Haftalık kapsam ayrı raporlanmalı.
    report_path = output.with_suffix(".coverage.json")

    assert report_path.exists()

    report = json.loads(
        report_path.read_text(encoding="utf-8")
    )

    assert report["silver_sha256"] == result.sha256
    assert report["overall_status"] == "unverified"

    january = report["months"][0]

    assert january["period"] == "2021-01"
    assert january["status"] == "unverified"
    assert january["observed_count"] == 2
    assert january["expected_count"] is None
    assert january["observed_dates"] == [
        "2021-01-01",
        "2021-01-15",
    ]

def test_single_week_produces_unverified_coverage_report(tmp_path):
    rate_path, cpi_path, kfe_path = _make_raw_files(
        tmp_path,
        "2021-01",
        "2021-01",
    )

    # Faiz verisinde yalnızca bir haftalık gözlem bırak.
    rate_data = json.loads(
        rate_path.read_text(encoding="utf-8")
    )

    rate_data["items"] = rate_data["items"][:1]
    rate_data["totalCount"] = 1

    rate_path.write_text(
        json.dumps(rate_data),
        encoding="utf-8",
    )

    output = tmp_path / "evds_monthly.csv"

    result = build_evds_silver_from_bronze(
        housing_rate_path=rate_path,
        cpi_path=cpi_path,
        housing_price_path=kfe_path,
        output_path=output,
        start_period="2021-01",
        end_period="2021-01",
    )

    silver = pd.read_csv(output)

    # Silver mevcut gözlemden doğru ortalamayı üretmeli.
    assert silver.loc[0, "housing_loan_interest_rate_pct"] == pytest.approx(10.0)
    assert silver.loc[0, "weekly_observation_count"] == 1

    report_path = output.with_suffix(".coverage.json")

    report = json.loads(
        report_path.read_text(encoding="utf-8")
    )

    assert report["silver_sha256"] == result.sha256
    assert report["overall_status"] == "unverified"

    january = report["months"][0]

    assert january["status"] == "unverified"
    assert january["observed_count"] == 1
    assert january["expected_count"] is None
    assert january["observed_dates"] == ["2021-01-01"]

def test_build_rejects_invalid_weekly_date(tmp_path):
    rate_path, cpi_path, kfe_path = _make_raw_files(
        tmp_path,
        "2021-01",
        "2021-01",
    )

    rate_data = json.loads(
        rate_path.read_text(encoding="utf-8")
    )

    rate_data["items"][0]["Tarih"] = "99-01-2021"

    rate_path.write_text(
        json.dumps(rate_data),
        encoding="utf-8",
    )

    output = tmp_path / "evds_monthly.csv"

    with pytest.raises(ValueError):
        build_evds_silver_from_bronze(
            housing_rate_path=rate_path,
            cpi_path=cpi_path,
            housing_price_path=kfe_path,
            output_path=output,
            start_period="2021-01",
            end_period="2021-01",
        )

    assert not output.exists()
    assert not output.with_suffix(".coverage.json").exists()

def test_coverage_report_is_deterministic(tmp_path):
    rate_path, cpi_path, kfe_path = _make_raw_files(
        tmp_path,
        "2021-01",
        "2021-02",
    )

    output = tmp_path / "evds_monthly.csv"
    report_path = output.with_suffix(".coverage.json")

    def build():
        return build_evds_silver_from_bronze(
            housing_rate_path=rate_path,
            cpi_path=cpi_path,
            housing_price_path=kfe_path,
            output_path=output,
            start_period="2021-01",
            end_period="2021-02",
        )

    first_result = build()

    first_csv = output.read_bytes()
    first_report = report_path.read_bytes()

    second_result = build()

    assert output.read_bytes() == first_csv
    assert report_path.read_bytes() == first_report
    assert first_result.sha256 == second_result.sha256

    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["silver_sha256"] == second_result.sha256
    assert report["overall_status"] == "unverified"
    assert len(report["months"]) == 2
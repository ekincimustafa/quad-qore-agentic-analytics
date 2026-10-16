import json
import hashlib

import pytest

from app.lakehouse.evds_pipeline import (
    build_evds_silver_from_bronze,
)
from app.lakehouse.evds_manifest_producer import (
    build_evds_manifest,
    build_weekly_coverage_manifest_entry,
)

from app.connectors.evds import (
    EvdsRawResponse,
    store_raw_response_in_bronze,
)
from app.lakehouse.bronze import BronzeStore
from app.lakehouse.layout import LakehouseLayout
from scripts.build_evds_silver import (
    _find_bronze_for_request,
    run,
)
from scripts.download_evds import _parse_period


def _body(items):
    return json.dumps(
        {
            "totalCount": len(items),
            "items": items,
        }
    ).encode("utf-8")


def _store(
    store,
    series_code,
    frequency,
    body,
):
    raw = EvdsRawResponse(
        series_code=series_code,
        frequency=frequency,
        request_start="2021-01-01",
        request_end="2021-02-28",
        source_url=(
            "https://evds3.tcmb.gov.tr/"
            "igmevdsms-dis/test"
        ),
        downloaded_at=(
            "2026-09-16T18:00:00+00:00"
        ),
        content_type="application/json",
        body=body,
    )

    return store_raw_response_in_bronze(
        raw,
        store,
    )


def _prepare_bronze(tmp_path):
    data_root = tmp_path / "data"

    store = BronzeStore(
        LakehouseLayout(data_root)
    )

    rate = _store(
        store,
        "TP.KTF12",
        "weekly",
        _body(
            [
                {
                    "Tarih": "01-01-2021",
                    "TP_KTF12": "10",
                },
                {
                    "Tarih": "15-01-2021",
                    "TP_KTF12": "20",
                },
                {
                    "Tarih": "01-02-2021",
                    "TP_KTF12": "30",
                },
                {
                    "Tarih": "15-02-2021",
                    "TP_KTF12": "40",
                },
            ]
        ),
    )

    cpi = _store(
        store,
        "TP.TUKFIY2025.GENEL",
        "monthly",
        _body(
            [
                {
                    "Tarih": "2021-1",
                    "TP_TUKFIY2025_GENEL": "100",
                },
                {
                    "Tarih": "2021-2",
                    "TP_TUKFIY2025_GENEL": "101",
                },
            ]
        ),
    )

    kfe = _store(
        store,
        "TP.KFE.TR",
        "monthly",
        _body(
            [
                {
                    "Tarih": "2021-1",
                    "TP_KFE_TR": "200",
                },
                {
                    "Tarih": "2021-2",
                    "TP_KFE_TR": "201",
                },
            ]
        ),
    )

    return data_root, rate, cpi, kfe


def test_build_uses_existing_exact_bronze_without_network(
    tmp_path,
):
    data_root, _, _, _ = _prepare_bronze(
        tmp_path
    )

    class NetworkMustNotBeUsed:
        def download_series(self, *args, **kwargs):
            raise AssertionError(
                "Network should not be used."
            )

    output = tmp_path / "silver.csv"

    exit_code = run(
        start_period=_parse_period("2021-01"),
        end_period=_parse_period("2021-02"),
        data_root=data_root,
        output_path=output,
        client=NetworkMustNotBeUsed(),
    )

    assert exit_code == 0
    assert output.exists()

    lines = output.read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(lines) == 3


def test_build_fails_closed_when_bronze_sha_is_tampered(
    tmp_path,
):
    data_root, rate, _, _ = _prepare_bronze(
        tmp_path
    )

    rate.asset.path.write_bytes(
        rate.asset.path.read_bytes()
        + b"\n"
    )

    with pytest.raises(
        ValueError,
        match="SHA256 does not match",
    ):
        run(
            start_period=_parse_period("2021-01"),
            end_period=_parse_period("2021-02"),
            data_root=data_root,
            output_path=tmp_path / "silver.csv",
        )


def test_build_downloads_when_exact_bronze_is_missing(
    tmp_path,
):
    class FakeClient:
        def __init__(self):
            self.calls = []

        def download_series(
            self,
            series_code,
            start_date,
            end_date,
        ):
            self.calls.append(series_code)

            if series_code == "TP.KTF12":
                frequency = "weekly"
                items = [
                    {
                        "Tarih": "01-01-2021",
                        "TP_KTF12": "10",
                    },
                    {
                        "Tarih": "15-01-2021",
                        "TP_KTF12": "20",
                    },
                    {
                        "Tarih": "01-02-2021",
                        "TP_KTF12": "30",
                    },
                    {
                        "Tarih": "15-02-2021",
                        "TP_KTF12": "40",
                    },
                ]
            elif series_code == "TP.TUKFIY2025.GENEL":
                frequency = "monthly"
                items = [
                    {
                        "Tarih": "2021-1",
                        "TP_TUKFIY2025_GENEL": "100",
                    },
                    {
                        "Tarih": "2021-2",
                        "TP_TUKFIY2025_GENEL": "101",
                    },
                ]
            else:
                frequency = "monthly"
                items = [
                    {
                        "Tarih": "2021-1",
                        "TP_KFE_TR": "200",
                    },
                    {
                        "Tarih": "2021-2",
                        "TP_KFE_TR": "201",
                    },
                ]

            return EvdsRawResponse(
                series_code=series_code,
                frequency=frequency,
                request_start=start_date.isoformat(),
                request_end=end_date.isoformat(),
                source_url=(
                    "https://evds3.tcmb.gov.tr/"
                    "igmevdsms-dis/test"
                ),
                downloaded_at=(
                    "2026-09-16T18:00:00+00:00"
                ),
                content_type="application/json",
                body=_body(items),
            )

    client = FakeClient()
    data_root = tmp_path / "data"
    output = tmp_path / "silver.csv"

    exit_code = run(
        start_period=_parse_period("2021-01"),
        end_period=_parse_period("2021-02"),
        data_root=data_root,
        output_path=output,
        client=client,
    )

    assert exit_code == 0
    assert len(client.calls) == 3
    assert output.exists()

    assert len(
        list(
            (data_root / "bronze" / "evds").glob(
                "*/*.json"
            )
        )
    ) == 3


def test_evds_receipt_selection_uses_real_utc_time(tmp_path):
    data_root = tmp_path / "data"
    dataset_dir = data_root / "bronze" / "evds" / "tp_ktf12"
    receipts_dir = dataset_dir / "receipts"
    receipts_dir.mkdir(parents=True)

    cases = [
        ("older", "2026-10-02T10:00:00+03:00", "10"),
        ("newer", "2026-10-02T08:00:00Z", "20"),
    ]

    for name, timestamp, value in cases:
        body = _body([
            {
                "Tarih": "01-01-2021",
                "TP_KTF12": value,
            }
        ])

        raw_path = dataset_dir / f"{name}.json"
        raw_path.write_bytes(body)

        receipt = {
            "series_code": "TP.KTF12",
            "frequency": "weekly",
            "request_start": "2021-01-01",
            "request_end": "2021-02-28",
            "downloaded_at": timestamp,
            "sha256": hashlib.sha256(body).hexdigest(),
            "size_bytes": len(body),
            "raw_path": str(raw_path.relative_to(data_root)),
        }

        (receipts_dir / f"{name}.json").write_text(
            json.dumps(receipt),
            encoding="utf-8",
        )

    selected = _find_bronze_for_request(
        data_root=data_root,
        series_code="TP.KTF12",
        request_start="2021-01-01",
        request_end="2021-02-28",
    )

    assert selected == dataset_dir / "newer.json"

def _create_receipt_for_selection(
    data_root,
    name,
    timestamp,
    value="10",
):
    dataset_dir = data_root / "bronze" / "evds" / "tp_ktf12"
    receipts_dir = dataset_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    body = _body([
        {
            "Tarih": "01-01-2021",
            "TP_KTF12": value,
        }
    ])

    raw_path = dataset_dir / f"{name}.json"
    raw_path.write_bytes(body)

    receipt = {
        "series_code": "TP.KTF12",
        "frequency": "weekly",
        "request_start": "2021-01-01",
        "request_end": "2021-02-28",
        "sha256": hashlib.sha256(body).hexdigest(),
        "size_bytes": len(body),
        "raw_path": str(raw_path.relative_to(data_root)),
    }

    if timestamp != "__MISSING__":
        receipt["downloaded_at"] = timestamp

    (receipts_dir / f"{name}.json").write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    return raw_path


@pytest.mark.parametrize(
    "timestamp",
    [
        "__MISSING__",
        None,
        "",
        "invalid-date",
        "2026-10-02T08:00:00",
    ],
)
def test_evds_receipt_rejects_invalid_timestamp(
    tmp_path,
    timestamp,
):
    data_root = tmp_path / "data"

    _create_receipt_for_selection(
        data_root,
        "invalid",
        timestamp,
    )

    with pytest.raises(
        ValueError,
        match="timestamp|missing fields",
    ):
        _find_bronze_for_request(
            data_root=data_root,
            series_code="TP.KTF12",
            request_start="2021-01-01",
            request_end="2021-02-28",
        )


def test_evds_receipt_equal_utc_time_uses_filename_tiebreak(
    tmp_path,
):
    data_root = tmp_path / "data"

    _create_receipt_for_selection(
        data_root,
        "alpha",
        "2026-10-02T11:00:00+03:00",
    )

    expected = _create_receipt_for_selection(
        data_root,
        "zeta",
        "2026-10-02T08:00:00Z",
    )

    selected = _find_bronze_for_request(
        data_root=data_root,
        series_code="TP.KTF12",
        request_start="2021-01-01",
        request_end="2021-02-28",
    )

    assert selected == expected

def test_cli_reports_weekly_coverage_without_network(
    tmp_path,
    capsys,
):
    data_root, _, _, _ = _prepare_bronze(tmp_path)

    class NetworkMustNotBeUsed:
        def download_series(self, *args, **kwargs):
            raise AssertionError(
                "Network should not be used."
            )

    output = tmp_path / "silver.csv"

    exit_code = run(
        start_period=_parse_period("2021-01"),
        end_period=_parse_period("2021-02"),
        data_root=data_root,
        output_path=output,
        client=NetworkMustNotBeUsed(),
    )

    assert exit_code == 0

    # Terminale yazdırılan JSON çıktısını oku.
    cli_output = json.loads(capsys.readouterr().out)

    report_path = output.with_suffix(".coverage.json")

    # CLI doğru rapor yolunu göstermeli.
    assert cli_output["coverage_report"] == str(report_path)
    assert report_path.exists()

    # Rapor üretilen Silver CSV'ye ait olmalı.
    coverage = json.loads(
        report_path.read_text(encoding="utf-8")
    )

    assert coverage["silver_sha256"] == cli_output["sha256"]
    assert coverage["overall_status"] == "unverified"

    assert [
        month["period"] for month in coverage["months"]
    ] == ["2021-01", "2021-02"]

def test_manifest_integrates_real_bronze_and_silver(tmp_path):
    data_root, rate, cpi, kfe = _prepare_bronze(tmp_path)

    silver_path = (
        data_root
        / "silver"
        / "evds"
        / "monthly"
        / "evds_monthly_2021-01_2021-02.csv"
    )

    silver_result = build_evds_silver_from_bronze(
        housing_rate_path=rate.asset.path,
        cpi_path=cpi.asset.path,
        housing_price_path=kfe.asset.path,
        output_path=silver_path,
        start_period="2021-01",
        end_period="2021-02",
    )

    selected_raw_paths = {
        "TP.KTF12": rate.asset.path,
        "TP.TUKFIY2025.GENEL": cpi.asset.path,
        "TP.KFE.TR": kfe.asset.path,
    }

    series_metadata = {
        "TP.KTF12": {
            "silver_columns": [
                "housing_loan_interest_rate_pct",
                "weekly_observation_count",
            ],
            "unit": "percent",
            "native_frequency": "weekly",
            "target_frequency": "monthly",
            "base_year": None,
            "base_year_source": "not_applicable",
            "transformation": "mean",
        },
        "TP.TUKFIY2025.GENEL": {
            "silver_columns": ["cpi_index"],
            "unit": "index",
            "native_frequency": "monthly",
            "target_frequency": "monthly",
            "base_year": 2025,
            "base_year_source": "tcmb",
            "transformation": "level",
        },
        "TP.KFE.TR": {
            "silver_columns": ["housing_price_index"],
            "unit": "index",
            "native_frequency": "monthly",
            "target_frequency": "monthly",
            "base_year": 2023,
            "base_year_source": "tcmb",
            "transformation": "level",
        },
    }

    manifest = build_evds_manifest(
        silver_path=silver_path,
        selected_raw_paths=selected_raw_paths,
        series_metadata=series_metadata,
        request_start="2021-01-01",
        request_end="2021-02-28",
        project_root=tmp_path,
        data_root=data_root,
    )

    manifest_path = silver_path.parent / "manifest.json"

    manifest_path.write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )

    assert silver_result.row_count == 2
    assert manifest["silver"]["row_count"] == 2
    assert manifest["silver"]["sha256"] == silver_result.sha256

    series_by_code = {
        series["series_code"]: series
        for series in manifest["series"]
    }

    coverage = series_by_code["TP.KTF12"]["weekly_coverage"]

    assert coverage["overall_status"] == "unverified"
    assert len(coverage["months"]) == 2

    for series in manifest["series"]:
        bronze = series["bronze"][0]

        raw_file = tmp_path / bronze["raw_path"]
        receipt_file = tmp_path / bronze["receipt_path"]

        assert raw_file.is_file()
        assert receipt_file.is_file()

        assert hashlib.sha256(
            raw_file.read_bytes()
        ).hexdigest() == bronze["sha256"]

        assert raw_file.stat().st_size == bronze["size_bytes"]

    assert manifest_path.exists()

@pytest.mark.parametrize(
    "tamper,expected_error",
    [
        (
            "sha256",
            "Weekly coverage Silver SHA256 mismatch",
        ),
        (
            "count",
            "Weekly observation count mismatch",
        ),
        (
            "wrong_month",
            "Weekly observation belongs to another month",
        ),
        (
            "extra_field",
            "Invalid weekly coverage month fields",
        ),
    ],
)
def test_coverage_report_rejects_tampering(
    tmp_path,
    tamper,
    expected_error,
):
    data_root, rate, cpi, kfe = _prepare_bronze(tmp_path)

    silver_path = (
        data_root
        / "silver"
        / "evds"
        / "monthly"
        / "evds_monthly_2021-01_2021-02.csv"
    )

    build_evds_silver_from_bronze(
        housing_rate_path=rate.asset.path,
        cpi_path=cpi.asset.path,
        housing_price_path=kfe.asset.path,
        output_path=silver_path,
        start_period="2021-01",
        end_period="2021-02",
    )

    report_path = silver_path.with_suffix(".coverage.json")

    report = json.loads(
        report_path.read_text(encoding="utf-8")
    )

    # Her testte farklı bir bilgiyi bilerek bozuyoruz.
    if tamper == "sha256":
        report["silver_sha256"] = "0" * 64

    elif tamper == "count":
        report["months"][0]["observed_count"] = 99

    elif tamper == "wrong_month":
        report["months"][0]["observed_dates"][0] = "2021-02-01"

    elif tamper == "extra_field":
        report["months"][0]["expected_dates"] = []

    report_path.write_text(
        json.dumps(report),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=expected_error):
        build_weekly_coverage_manifest_entry(
            coverage_path=report_path,
            silver_path=silver_path,
        )

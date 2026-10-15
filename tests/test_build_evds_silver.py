import json
import hashlib

import pytest

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
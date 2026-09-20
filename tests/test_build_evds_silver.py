import json

import pytest

from app.connectors.evds import (
    EvdsRawResponse,
    store_raw_response_in_bronze,
)
from app.lakehouse.bronze import BronzeStore
from app.lakehouse.layout import LakehouseLayout
from scripts.build_evds_silver import run
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

import json

import httpx
from datetime import datetime, timezone

from app.connectors.evds import EvdsClient, EvdsRawResponse
from scripts.download_evds import (
    _parse_period,
    run,
)


class FakeEvdsClient:
    def __init__(self):
        self.calls = []

    def download_series(
        self,
        series_code,
        start_date,
        end_date,
    ):
        self.calls.append(
            (
                series_code,
                start_date,
                end_date,
            )
        )

        value_fields = {
            "TP.KTF12": (
                "01-01-2021",
                "TP_KTF12",
                "18.61",
            ),
            "TP.TUKFIY2025.GENEL": (
                "2021-1",
                "TP_TUKFIY2025_GENEL",
                "16.12",
            ),
            "TP.KFE.TR": (
                "2021-1",
                "TP_KFE_TR",
                "16.49",
            ),
        }

        tarih, value_field, value = value_fields[
            series_code
        ]

        body = json.dumps(
            {
                "totalCount": 1,
                "items": [
                    {
                        "Tarih": tarih,
                        value_field: value,
                    }
                ],
            }
        ).encode("utf-8")

        return EvdsRawResponse(
            series_code=series_code,
            frequency={
                "TP.KTF12": "weekly",
                "TP.TUKFIY2025.GENEL": "monthly",
                "TP.KFE.TR": "monthly",
            }[series_code],
            request_start=start_date.isoformat(),
            request_end=end_date.isoformat(),
            source_url=(
                "https://evds3.tcmb.gov.tr/"
                "igmevdsms-dis/test"
            ),
            downloaded_at=datetime.now(
                timezone.utc
            ).isoformat(),
            content_type="application/json",
            body=body,
        )


def test_download_evds_cli_stores_all_three_series(
    tmp_path,
):
    client = FakeEvdsClient()

    exit_code = run(
        start_period=_parse_period("2021-01"),
        end_period=_parse_period("2021-01"),
        data_root=tmp_path / "data",
        client=client,
    )

    assert exit_code == 0
    assert len(client.calls) == 3

    bronze_root = tmp_path / "data" / "bronze" / "evds"

    raw_files = list(
        bronze_root.glob("*/*.json")
    )

    receipt_files = list(
        bronze_root.glob("*/receipts/*.json")
    )

    assert len(raw_files) == 3
    assert len(receipt_files) == 3


def test_download_evds_cli_is_idempotent(
    tmp_path,
):
    client = FakeEvdsClient()

    kwargs = {
        "start_period": _parse_period("2021-01"),
        "end_period": _parse_period("2021-01"),
        "data_root": tmp_path / "data",
        "client": client,
    }

    assert run(**kwargs) == 0
    assert run(**kwargs) == 0

    bronze_root = tmp_path / "data" / "bronze" / "evds"

    assert len(
        list(bronze_root.glob("*/*.json"))
    ) == 3

    assert len(
        list(
            bronze_root.glob(
                "*/receipts/*.json"
            )
        )
    ) == 3


def test_download_evds_cli_returns_nonzero_on_failure(
    tmp_path,
):
    class BrokenClient:
        def download_series(
            self,
            series_code,
            start_date,
            end_date,
        ):
            raise RuntimeError("offline failure")

    exit_code = run(
        start_period=_parse_period("2021-01"),
        end_period=_parse_period("2021-01"),
        data_root=tmp_path / "data",
        client=BrokenClient(),
    )

    assert exit_code == 1


def test_download_cli_output_does_not_leak_api_key(
    tmp_path,
    monkeypatch,
    capsys,
):
    secret = "cli-secret-must-not-leak"
    monkeypatch.setenv("EVDS_API_KEY", secret)

    exit_code = run(
        start_period=_parse_period("2021-01"),
        end_period=_parse_period("2021-01"),
        data_root=tmp_path / "data",
        client=FakeEvdsClient(),
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert secret not in output


def test_invalid_evds_schema_returns_nonzero_without_bronze_write(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("EVDS_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"Content-Type": "application/json"},
            json={
                "items": [
                    {
                        "Tarih": "2021-1",
                        "YANLIS_ALAN": "100",
                    }
                ]
            },
        )

    client = EvdsClient(
        transport=httpx.MockTransport(handler)
    )

    data_root = tmp_path / "data"

    exit_code = run(
        start_period=_parse_period("2021-01"),
        end_period=_parse_period("2021-01"),
        data_root=data_root,
        client=client,
    )

    assert exit_code == 1

    bronze_root = (
        data_root
        / "bronze"
        / "evds"
    )

    assert list(
        bronze_root.rglob("*.json")
    ) == []

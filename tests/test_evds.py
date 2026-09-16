from datetime import date
import json

import httpx
import pytest

from app.connectors.evds import (
    EvdsClient,
    EvdsConfigurationError,
    EvdsDownloadError,
    EvdsResponseError,
)


def _json_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        request=request,
        headers={"Content-Type": "application/json; charset=utf-8"},
        json={
            "items": [
                {
                    "Tarih": "01-01-2021",
                    "VALUE": "18.61",
                }
            ]
        },
    )


def test_missing_evds_api_key_is_rejected(monkeypatch) -> None:
    monkeypatch.delenv("EVDS_API_KEY", raising=False)

    client = EvdsClient(
        transport=httpx.MockTransport(_json_response)
    )

    with pytest.raises(
        EvdsConfigurationError,
        match="EVDS_API_KEY",
    ):
        client.download_series(
            "TP.KTF12",
            date(2021, 1, 1),
            date(2021, 1, 31),
        )


def test_successful_download_uses_key_header_not_url(monkeypatch) -> None:
    secret = "super-secret-test-key"
    monkeypatch.setenv("EVDS_API_KEY", secret)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["key"] == secret
        assert secret not in str(request.url)
        assert request.url.host == "evds3.tcmb.gov.tr"
        assert request.url.path.startswith(
            "/igmevdsms-dis/series="
        )

        return _json_response(request)

    client = EvdsClient(
        transport=httpx.MockTransport(handler)
    )

    result = client.download_series(
        "TP.KTF12",
        date(2021, 1, 1),
        date(2021, 1, 31),
    )

    assert result.series_code == "TP.KTF12"
    assert result.frequency == "weekly"
    assert result.request_start == "2021-01-01"
    assert result.request_end == "2021-01-31"
    assert secret not in result.source_url
    assert result.content_type.startswith("application/json")

    payload = json.loads(result.body)
    assert len(payload["items"]) == 1


def test_api_key_does_not_leak_into_error_message(monkeypatch) -> None:
    secret = "must-never-leak"
    monkeypatch.setenv("EVDS_API_KEY", secret)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            request=request,
            json={"error": "unauthorized"},
        )

    client = EvdsClient(
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(EvdsDownloadError) as exc_info:
        client.download_series(
            "TP.KTF12",
            date(2021, 1, 1),
            date(2021, 1, 31),
        )

    assert secret not in str(exc_info.value)


def test_timeout_is_reported_without_secret(monkeypatch) -> None:
    secret = "timeout-secret"
    monkeypatch.setenv("EVDS_API_KEY", secret)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(
            "simulated timeout",
            request=request,
        )

    client = EvdsClient(
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(EvdsDownloadError) as exc_info:
        client.download_series(
            "TP.KTF12",
            date(2021, 1, 1),
            date(2021, 1, 31),
        )

    assert "timeout" in str(exc_info.value).lower()
    assert secret not in str(exc_info.value)


@pytest.mark.parametrize("status_code", [400, 404, 500, 503])
def test_http_errors_fail_closed(
    monkeypatch,
    status_code: int,
) -> None:
    monkeypatch.setenv("EVDS_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            request=request,
            text="failure",
        )

    client = EvdsClient(
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(
        EvdsDownloadError,
        match=str(status_code),
    ):
        client.download_series(
            "TP.KTF12",
            date(2021, 1, 1),
            date(2021, 1, 31),
        )


def test_empty_response_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("EVDS_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"Content-Type": "application/json"},
            content=b"",
        )

    client = EvdsClient(
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(
        EvdsResponseError,
        match="empty",
    ):
        client.download_series(
            "TP.KTF12",
            date(2021, 1, 1),
            date(2021, 1, 31),
        )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"items": []},
        {"items": "not-a-list"},
        {"items": [123]},
        {"items": [{"VALUE": "18.61"}]},
    ],
)
def test_unexpected_response_schema_is_rejected(
    monkeypatch,
    payload,
) -> None:
    monkeypatch.setenv("EVDS_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"Content-Type": "application/json"},
            json=payload,
        )

    client = EvdsClient(
        transport=httpx.MockTransport(handler)
    )

    with pytest.raises(EvdsResponseError):
        client.download_series(
            "TP.KTF12",
            date(2021, 1, 1),
            date(2021, 1, 31),
        )


def test_unknown_series_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("EVDS_API_KEY", "test-key")

    client = EvdsClient(
        transport=httpx.MockTransport(_json_response)
    )

    with pytest.raises(ValueError, match="Unsupported EVDS series"):
        client.download_series(
            "NOT.A.REAL.SERIES",
            date(2021, 1, 1),
            date(2021, 1, 31),
        )

from hashlib import sha256

from app.connectors.evds import (
    EvdsRawResponse,
    store_raw_response_in_bronze,
)
from app.lakehouse.bronze import BronzeStore
from app.lakehouse.layout import LakehouseLayout


def _sample_raw_response(
    body: bytes | None = None,
) -> EvdsRawResponse:
    if body is None:
        body = (
            b'{"items":['
            b'{"Tarih":"01-01-2021","VALUE":"18.61"}'
            b']}'
        )

    return EvdsRawResponse(
        series_code="TP.KTF12",
        frequency="weekly",
        request_start="2021-01-01",
        request_end="2021-01-31",
        source_url=(
            "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
            "series=TP.KTF12"
            "&startDate=01-01-2021"
            "&endDate=31-01-2021"
            "&type=json"
        ),
        downloaded_at="2026-09-16T13:00:00+00:00",
        content_type="application/json; charset=utf-8",
        body=body,
    )


def test_store_raw_response_in_bronze_records_hash_size_and_receipt(
    tmp_path,
) -> None:
    raw = _sample_raw_response()

    store = BronzeStore(
        LakehouseLayout(tmp_path / "data")
    )

    stored = store_raw_response_in_bronze(
        raw,
        store,
    )

    assert stored.asset.path.is_file()
    assert stored.asset.path.read_bytes() == raw.body

    expected_sha = sha256(raw.body).hexdigest()

    assert stored.asset.sha256 == expected_sha
    assert stored.asset.size_bytes == len(raw.body)

    assert stored.asset.source_url == raw.source_url
    assert stored.asset.downloaded_at == raw.downloaded_at
    assert stored.asset.content_type == raw.content_type
    assert (
        stored.asset.data_period
        == "2021-01-01/2021-01-31"
    )

    assert stored.receipt_path.is_file()

    receipt = json.loads(
        stored.receipt_path.read_text(
            encoding="utf-8"
        )
    )

    assert receipt["series_code"] == "TP.KTF12"
    assert receipt["frequency"] == "weekly"
    assert receipt["request_start"] == "2021-01-01"
    assert receipt["request_end"] == "2021-01-31"
    assert receipt["source_url"] == raw.source_url
    assert receipt["downloaded_at"] == raw.downloaded_at
    assert receipt["content_type"] == raw.content_type
    assert receipt["sha256"] == expected_sha
    assert receipt["size_bytes"] == len(raw.body)
    assert (
        receipt["data_period"]
        == "2021-01-01/2021-01-31"
    )


def test_same_evds_raw_response_is_idempotent(
    tmp_path,
) -> None:
    raw = _sample_raw_response()

    store = BronzeStore(
        LakehouseLayout(tmp_path / "data")
    )

    first = store_raw_response_in_bronze(
        raw,
        store,
    )
    second = store_raw_response_in_bronze(
        raw,
        store,
    )

    assert first.asset.path == second.asset.path
    assert first.asset.sha256 == second.asset.sha256
    assert first.receipt_path == second.receipt_path

    raw_files = list(
        first.asset.path.parent.glob("*.json")
    )
    receipt_files = list(
        first.receipt_path.parent.glob("*.json")
    )

    assert len(raw_files) == 1
    assert len(receipt_files) == 1


def test_evds_api_key_never_appears_in_bronze_receipt(
    tmp_path,
    monkeypatch,
) -> None:
    secret = "bronze-secret-must-not-leak"
    monkeypatch.setenv("EVDS_API_KEY", secret)

    raw = _sample_raw_response()

    store = BronzeStore(
        LakehouseLayout(tmp_path / "data")
    )

    stored = store_raw_response_in_bronze(
        raw,
        store,
    )

    receipt_text = stored.receipt_path.read_text(
        encoding="utf-8"
    )

    assert secret not in receipt_text
    assert secret not in str(stored.asset.path)
    assert secret not in stored.asset.source_url


def test_client_configures_connect_and_read_timeouts(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "EVDS_API_KEY",
        "timeout-test-secret",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        timeout = request.extensions["timeout"]

        assert timeout["connect"] == 2.5
        assert timeout["read"] == 7.5

        return httpx.Response(
            200,
            request=request,
            headers={
                "Content-Type": "application/json",
            },
            json={
                "items": [
                    {
                        "Tarih": "01-01-2021",
                        "TP_KTF12": "18.61",
                    }
                ]
            },
        )

    client = EvdsClient(
        connect_timeout=2.5,
        read_timeout=7.5,
        transport=httpx.MockTransport(handler),
    )

    client.download_series(
        "TP.KTF12",
        date(2021, 1, 1),
        date(2021, 1, 31),
    )

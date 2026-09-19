"""Secure acquisition of raw EVDS series responses."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from app.lakehouse.bronze import BronzeAsset, BronzeStore


EVDS_BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis"

EVDS_SERIES_FREQUENCIES = {
    "TP.KTF12": "weekly",
    "TP.TUKFIY2025.GENEL": "monthly",
    "TP.KFE.TR": "monthly",
}

EVDS_SERIES_VALUE_FIELDS = {
    "TP.KTF12": "TP_KTF12",
    "TP.TUKFIY2025.GENEL": "TP_TUKFIY2025_GENEL",
    "TP.KFE.TR": "TP_KFE_TR",
}



class EvdsError(RuntimeError):
    """Base error for EVDS acquisition."""


class EvdsConfigurationError(EvdsError):
    """Raised when required EVDS configuration is missing."""


class EvdsDownloadError(EvdsError):
    """Raised when an EVDS network request fails."""


class EvdsResponseError(EvdsError):
    """Raised when EVDS returns an unsafe or unexpected response."""


@dataclass(frozen=True)
class EvdsRawResponse:
    """Raw EVDS response plus non-secret request metadata."""

    series_code: str
    frequency: str
    request_start: str
    request_end: str
    source_url: str
    downloaded_at: str
    content_type: str
    body: bytes


def _get_api_key() -> str:
    api_key = os.getenv("EVDS_API_KEY", "").strip()

    if not api_key:
        raise EvdsConfigurationError(
            "EVDS_API_KEY environment variable is required."
        )

    return api_key


def _build_source_url(
    series_code: str,
    start_date: date,
    end_date: date,
) -> str:
    if start_date > end_date:
        raise ValueError(
            "EVDS start date must be before or equal to end date."
        )

    start = start_date.strftime("%d-%m-%Y")
    end = end_date.strftime("%d-%m-%Y")

    return (
        f"{EVDS_BASE_URL}/"
        f"series={series_code}"
        f"&startDate={start}"
        f"&endDate={end}"
        f"&type=json"
    )


def _validate_json_response(
    response: httpx.Response,
    series_code: str,
) -> None:
    if not response.content.strip():
        raise EvdsResponseError(
            "EVDS returned an empty response."
        )

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    if "json" not in content_type:
        raise EvdsResponseError(
            "EVDS returned an unexpected content type."
        )

    try:
        payload = json.loads(response.content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvdsResponseError(
            "EVDS returned malformed JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise EvdsResponseError(
            "EVDS JSON response must be an object."
        )

    items = payload.get("items")

    if not isinstance(items, list) or not items:
        raise EvdsResponseError(
            "EVDS JSON response does not contain observations."
        )

    expected_value_field = EVDS_SERIES_VALUE_FIELDS.get(
        series_code
    )

    if expected_value_field is None:
        raise EvdsResponseError(
            f"Unsupported EVDS response series: {series_code}"
        )

    for item in items:
        if not isinstance(item, dict):
            raise EvdsResponseError(
                "EVDS observation schema is invalid."
            )

        if (
            "Tarih" not in item
            or item["Tarih"] is None
            or not str(item["Tarih"]).strip()
        ):
            raise EvdsResponseError(
                "EVDS observation is missing or has empty Tarih."
            )

        if expected_value_field not in item:
            raise EvdsResponseError(
                "EVDS observation is missing expected value field "
                f"{expected_value_field} for series {series_code}."
            )


class EvdsClient:
    """Download raw EVDS series without exposing the API key."""

    def __init__(
        self,
        *,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if connect_timeout <= 0 or read_timeout <= 0:
            raise ValueError(
                "EVDS timeout values must be positive."
            )

        self.timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=read_timeout,
            pool=connect_timeout,
        )
        self.transport = transport

    def download_series(
        self,
        series_code: str,
        start_date: date,
        end_date: date,
    ) -> EvdsRawResponse:
        frequency = EVDS_SERIES_FREQUENCIES.get(
            series_code
        )

        if frequency is None:
            raise ValueError(
                f"Unsupported EVDS series: {series_code}"
            )

        api_key = _get_api_key()

        source_url = _build_source_url(
            series_code,
            start_date,
            end_date,
        )

        headers = {
            "key": api_key,
            "Accept": "application/json",
            "User-Agent": "Quad-Qore-EVDS/0.1",
        }

        try:
            with httpx.Client(
                timeout=self.timeout,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = client.get(
                    source_url,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise EvdsDownloadError(
                f"EVDS request timeout for series {series_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise EvdsDownloadError(
                f"EVDS request failed for series {series_code}."
            ) from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise EvdsDownloadError(
                "EVDS request failed with HTTP "
                f"{response.status_code} for series {series_code}."
            ) from exc

        _validate_json_response(response, series_code)

        return EvdsRawResponse(
            series_code=series_code,
            frequency=frequency,
            request_start=start_date.isoformat(),
            request_end=end_date.isoformat(),
            source_url=source_url,
            downloaded_at=datetime.now(
                timezone.utc
            ).isoformat(),
            content_type=response.headers.get(
                "Content-Type",
                "",
            ),
            body=response.content,
        )

@dataclass(frozen=True)
class StoredEvdsResponse:
    """A raw EVDS Bronze asset and its persistent provenance receipt."""

    asset: BronzeAsset
    receipt_path: Path


def _series_dataset_name(series_code: str) -> str:
    """Convert an approved EVDS series code to a safe lakehouse segment."""

    return series_code.lower().replace(".", "_")


def _ensure_api_key_not_persisted(raw: EvdsRawResponse) -> None:
    """Fail closed if the configured secret appears in persistent material."""

    api_key = os.getenv("EVDS_API_KEY", "").strip()

    if not api_key:
        return

    if api_key in raw.source_url:
        raise ValueError(
            "EVDS API key detected in Bronze source URL."
        )

    if api_key.encode("utf-8") in raw.body:
        raise ValueError(
            "EVDS API key detected in raw EVDS response."
        )


def _receipt_request_key(raw: EvdsRawResponse) -> str:
    """Build a deterministic non-secret identity for one EVDS request."""

    identity = "|".join(
        [
            raw.series_code,
            raw.frequency,
            raw.request_start,
            raw.request_end,
            raw.source_url,
        ]
    )

    return sha256(identity.encode("utf-8")).hexdigest()


def store_raw_response_in_bronze(
    raw: EvdsRawResponse,
    store: BronzeStore,
) -> StoredEvdsResponse:
    """Persist an unchanged EVDS response using the existing BronzeStore.

    The raw response body remains unchanged. A deterministic JSON receipt
    stores non-secret request provenance next to the Bronze dataset.
    """

    if raw.series_code not in EVDS_SERIES_FREQUENCIES:
        raise ValueError(
            f"Unsupported EVDS series: {raw.series_code}"
        )

    expected_frequency = EVDS_SERIES_FREQUENCIES[
        raw.series_code
    ]

    if raw.frequency != expected_frequency:
        raise ValueError(
            "EVDS response frequency does not match the series contract."
        )

    if not raw.body:
        raise ValueError(
            "Cannot store an empty EVDS response in Bronze."
        )

    _ensure_api_key_not_persisted(raw)

    digest = sha256(raw.body).hexdigest()
    dataset = _series_dataset_name(raw.series_code)

    data_period = (
        f"{raw.request_start}/{raw.request_end}"
    )

    # Content-addressed filename prevents unnecessary copies of identical
    # raw responses while preserving changed responses as new immutable assets.
    filename = f"{digest}.json"

    with TemporaryDirectory() as temp_directory:
        temporary_file = (
            Path(temp_directory) / "evds-response.json"
        )
        temporary_file.write_bytes(raw.body)

        asset = store.store_file(
            source_file=temporary_file,
            source="evds",
            dataset=dataset,
            filename=filename,
            source_url=raw.source_url,
            downloaded_at=raw.downloaded_at,
            data_period=data_period,
            content_type=raw.content_type,
        )

    request_key = _receipt_request_key(raw)

    receipts_directory = (
        asset.path.parent / "receipts"
    )
    receipts_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    receipt_path = (
        receipts_directory
        / f"{request_key[:16]}-{digest[:16]}.json"
    )

    raw_path = asset.path.relative_to(
        store.layout.root
    ).as_posix()

    receipt = {
        "series_code": raw.series_code,
        "source_url": raw.source_url,
        "request_start": raw.request_start,
        "request_end": raw.request_end,
        "frequency": raw.frequency,
        "downloaded_at": raw.downloaded_at,
        "content_type": raw.content_type,
        "sha256": asset.sha256,
        "size_bytes": asset.size_bytes,
        "data_period": data_period,
        "raw_path": raw_path,
    }

    if receipt_path.exists():
        try:
            existing = json.loads(
                receipt_path.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Existing EVDS Bronze receipt is malformed."
            ) from exc

        if not isinstance(existing, dict):
            raise ValueError(
                "Existing EVDS Bronze receipt has an invalid schema."
            )

        # downloaded_at records the first persisted copy and may naturally
        # differ on a repeated identical download. Every other field must
        # remain deterministic.
        comparable_keys = (
            "series_code",
            "source_url",
            "request_start",
            "request_end",
            "frequency",
            "content_type",
            "sha256",
            "size_bytes",
            "data_period",
            "raw_path",
        )

        for key in comparable_keys:
            if existing.get(key) != receipt[key]:
                raise FileExistsError(
                    "Existing EVDS Bronze receipt does not match "
                    "the stored raw asset."
                )

        existing_downloaded_at = existing.get(
            "downloaded_at"
        )

        if (
            not isinstance(existing_downloaded_at, str)
            or not existing_downloaded_at.strip()
        ):
            raise ValueError(
                "Existing EVDS Bronze receipt has an invalid "
                "downloaded_at value."
            )

        # Keep the persisted provenance internally consistent when the same
        # request/content is processed again at a later time.
        asset = BronzeAsset(
            path=asset.path,
            sha256=asset.sha256,
            size_bytes=asset.size_bytes,
            source_url=raw.source_url,
            downloaded_at=existing_downloaded_at,
            data_period=data_period,
            content_type=raw.content_type,
        )

        return StoredEvdsResponse(
            asset=asset,
            receipt_path=receipt_path,
        )

    receipt_text = json.dumps(
        receipt,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )

    api_key = os.getenv(
        "EVDS_API_KEY",
        "",
    ).strip()

    if api_key and api_key in receipt_text:
        raise ValueError(
            "EVDS API key detected in Bronze receipt."
        )

    temporary_receipt = receipt_path.with_name(
        receipt_path.name
        + f".{uuid4().hex}.part"
    )

    temporary_receipt.write_text(
        receipt_text,
        encoding="utf-8",
    )
    temporary_receipt.replace(receipt_path)

    return StoredEvdsResponse(
        asset=asset,
        receipt_path=receipt_path,
    )

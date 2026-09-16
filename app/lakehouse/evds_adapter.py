from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


EVDS_API_VALUE_FIELDS = {
    "TP.KTF12": "TP_KTF12",
    "TP.TUKFIY2025.GENEL": "TP_TUKFIY2025_GENEL",
    "TP.KFE.TR": "TP_KFE_TR",
}


def _normalize_api_month(value: object) -> str:
    """
    Convert the EVDS API monthly period format, such as 2021-1,
    to the strict YYYY-MM format expected by the Silver layer.
    """

    text = str(value).strip()
    parts = text.split("-")

    if (
        len(parts) != 2
        or not parts[0].isdigit()
        or not parts[1].isdigit()
        or len(parts[0]) != 4
    ):
        raise ValueError(
            f"Invalid EVDS API monthly period: {value}"
        )

    year = int(parts[0])
    month = int(parts[1])

    if month < 1 or month > 12:
        raise ValueError(
            f"Invalid EVDS API monthly period: {value}"
        )

    return f"{year:04d}-{month:02d}"


def _decode_items(
    raw_body: bytes,
    series_code: str,
) -> tuple[list[dict], str]:
    """Decode and validate the minimum EVDS API response contract."""

    if series_code not in EVDS_API_VALUE_FIELDS:
        raise ValueError(
            f"Unsupported EVDS series: {series_code}"
        )

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(
            "EVDS Bronze payload is not valid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            "EVDS Bronze payload must be a JSON object."
        )

    items = payload.get("items")

    if not isinstance(items, list) or not items:
        raise ValueError(
            "EVDS Bronze payload does not contain observations."
        )

    value_field = EVDS_API_VALUE_FIELDS[series_code]

    for item in items:
        if not isinstance(item, dict):
            raise ValueError(
                "EVDS observation must be a JSON object."
            )

        missing_fields = {
            "Tarih",
            value_field,
        }.difference(item)

        if missing_fields:
            raise ValueError(
                "EVDS observation is missing required fields: "
                f"{sorted(missing_fields)}"
            )

    return items, value_field


def adapt_evds_api_response(
    raw_body: bytes,
    series_code: str,
) -> pd.DataFrame:
    """
    Adapt a raw EVDS API response to the input shape expected by
    the existing Silver transformation functions.

    This function only adapts transport/API representation.
    Analytical transformations remain in silver.py.
    """

    items, value_field = _decode_items(
        raw_body,
        series_code,
    )

    if series_code == "TP.KTF12":
        return pd.DataFrame(
            {
                "Tarih": [
                    item["Tarih"]
                    for item in items
                ],
                "TP_KTF12": [
                    item[value_field]
                    for item in items
                ],
            }
        )

    if series_code == "TP.KFE.TR":
        return pd.DataFrame(
            {
                "Tarih": [
                    _normalize_api_month(
                        item["Tarih"]
                    )
                    for item in items
                ],
                "TP_KFE_TR": [
                    item[value_field]
                    for item in items
                ],
            }
        )

    if series_code == "TP.TUKFIY2025.GENEL":
        observations = [
            (
                _normalize_api_month(
                    item["Tarih"]
                ),
                item[value_field],
            )
            for item in items
        ]

        periods = [
            period
            for period, _ in observations
        ]

        if len(periods) != len(set(periods)):
            raise ValueError(
                "Duplicate CPI periods detected in EVDS API response."
            )

        observations.sort(
            key=lambda observation: observation[0]
        )

        row = {
            "Unnamed: 0": "Genel Endeks",
        }

        for period, value in observations:
            row[period] = value

        return pd.DataFrame([row])

    raise ValueError(
        f"Unsupported EVDS series: {series_code}"
    )


def load_evds_bronze_file(
    path: str | Path,
    series_code: str,
) -> pd.DataFrame:
    """Load an unchanged EVDS Bronze JSON file and adapt it for Silver."""

    raw_body = Path(path).read_bytes()

    return adapt_evds_api_response(
        raw_body,
        series_code,
    )

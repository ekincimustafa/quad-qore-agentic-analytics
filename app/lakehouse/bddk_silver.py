"""BDDK Silver layer transformation and validation module.

This module processes verified BDDK Bronze artifacts (monthly JSON receipts)
and transforms them into the Silver housing loan dataset.
"""

from __future__ import annotations

import datetime
import json
import math
import re
from pathlib import Path

import pandas as pd

from app.connectors.bddk import extract_housing_loan_data
from app.lakehouse.core_validators import (
    IntegrityError,
    check_missing_periods,
    deduplicate_records,
    parse_iso8601_timestamp,
    parse_period_to_date,
    resolve_secure_raw_path,
    validate_numeric_series,
    verify_file_integrity,
)

DEFAULT_START_PERIOD = "2021-01"
DEFAULT_END_PERIOD = "2026-06"
DEMO_END_PERIOD = "2025-12"


class SilverDataError(ValueError):
    """Raised when Bronze data fails integrity or schema validation during Silver build."""


def validate_bddk_monthly_silver(
    data: pd.DataFrame,
    start_period: str = DEFAULT_START_PERIOD,
    end_period: str = DEFAULT_END_PERIOD,
) -> pd.DataFrame:
    """Validates the Silver housing loan dataset against the strictly defined contract.

    Args:
        data: The Silver pandas DataFrame to validate.
        start_period: The expected starting period (YYYY-MM).
        end_period: The expected ending period (YYYY-MM).

    Returns:
        The validated DataFrame if successful.

    Raises:
        SilverDataError: If any validation rule is violated (fail-closed).
    """
    if not isinstance(data, pd.DataFrame):
        raise SilverDataError("Input data must be a pandas DataFrame.")

    try:
        start_date = parse_period_to_date(start_period)
        end_date = parse_period_to_date(end_period)
    except IntegrityError as e:
        raise SilverDataError(str(e))

    required_columns = {
        "period",
        "housing_loan_amount",
        "nominal_housing_loan_mn_try",
        "housing_loan_unit",
        "bddk_source_ref",
        "data_quality_note",
    }
    missing_cols = sorted(required_columns - set(data.columns))
    if missing_cols:
        raise SilverDataError(f"Silver data is missing required columns: {missing_cols}")

    df = data.copy()

    # 1. Period checks
    periods = df["period"].astype(str).str.strip().tolist()

    # Format and bounds
    for p in periods:
        try:
            d = parse_period_to_date(p)
            if not (start_date <= d <= end_date):
                raise SilverDataError(f"Unexpected period {p} found outside expected range [{start_period}, {end_period}].")
        except IntegrityError as e:
            raise SilverDataError(f"Invalid period found in data: {p}. {e}")

    # Duplicates
    if len(periods) != len(set(periods)):
        raise SilverDataError("Duplicate periods found in the Silver dataset.")

    # Missing gaps (using core validator)
    try:
        check_missing_periods(periods, start_period, end_period)
    except IntegrityError as e:
        raise SilverDataError(str(e))

    # 2. Value checks (using core validator)
    try:
        validate_numeric_series(df["housing_loan_amount"], "housing_loan_amount", strictly_positive=True)
    except IntegrityError as e:
        raise SilverDataError(str(e))

    # Gold compatibility column: must be numeric, finite, positive, and strictly equal to housing_loan_amount
    try:
        validate_numeric_series(df["nominal_housing_loan_mn_try"], "nominal_housing_loan_mn_try", strictly_positive=True)
    except IntegrityError as e:
        raise SilverDataError(str(e))

    if not (df["nominal_housing_loan_mn_try"] == df["housing_loan_amount"]).all():
        raise SilverDataError("nominal_housing_loan_mn_try must be strictly equal to housing_loan_amount.")

    # 3. Unit checks (Contract strictly requires 'Milyon TL')
    if df["housing_loan_unit"].isna().any():
        raise SilverDataError("housing_loan_unit contains null or missing values.")

    units = df["housing_loan_unit"].astype(str).str.strip()
    if (units == "").any() or (units.str.lower() == "none").any() or (units.str.lower() == "nan").any():
        raise SilverDataError("housing_loan_unit contains empty or invalid values.")

    invalid_units = units[units != "Milyon TL"].unique().tolist()
    if invalid_units:
        raise SilverDataError(
            f"housing_loan_unit contract violation: expected 'Milyon TL', got {invalid_units}."
        )

    # 4. Source ref checks (Fail-closed on None/empty)
    if df["bddk_source_ref"].isna().any():
        raise SilverDataError("bddk_source_ref contains null or missing values.")

    refs = df["bddk_source_ref"].astype(str).str.strip()
    if (refs == "").any() or (refs.str.lower() == "none").any() or (refs.str.lower() == "nan").any():
        raise SilverDataError("bddk_source_ref contains empty or invalid values.")

    # 5. Data quality note checks (Fail-closed on None/empty)
    if df["data_quality_note"].isna().any():
        raise SilverDataError("data_quality_note contains null or missing values.")

    notes = df["data_quality_note"].astype(str).str.strip()
    if (notes == "").any() or (notes.str.lower() == "none").any() or (notes.str.lower() == "nan").any():
        raise SilverDataError("data_quality_note contains empty or invalid values.")

    return df


def load_and_verify_bronze_receipts(
    receipts_dir: Path,
    raw_dir: Path,
    start_period: str = DEFAULT_START_PERIOD,
    end_period: str = DEFAULT_END_PERIOD,
) -> list[dict]:
    """Scans, verifies, and deduplicates BDDK Bronze monthly receipts."""
    try:
        start_date = parse_period_to_date(start_period)
        end_date = parse_period_to_date(end_period)
    except IntegrityError as e:
        raise SilverDataError(str(e))

    if not receipts_dir.is_dir():
        raise SilverDataError(f"Receipts directory not found: {receipts_dir}")

    all_receipts = []

    for receipt_path in receipts_dir.glob("*.json"):
        try:
            content = receipt_path.read_text("utf-8")
            data = json.loads(content)
        except Exception as e:
            raise SilverDataError(f"Failed to read/parse receipt {receipt_path.name}: {e}")

        if not isinstance(data, dict):
            raise SilverDataError(f"Receipt JSON root must be a dict: {receipt_path.name}")

        req_key = data.get("request_key")
        if not req_key or not isinstance(req_key, str) or not req_key.strip():
            raise SilverDataError(f"Receipt missing valid request_key: {receipt_path.name}")

        params = data.get("parameters")

        # --- Catalog vs. broken-schema distinction ---
        # A catalog receipt legitimately has NO "parameters" key at all → skip silently.
        # A receipt that HAS a "parameters" key but it is not a dict is a schema error → fail-closed.
        if "parameters" not in data:
            continue  # Catalog / non-monthly receipt — expected, skip silently.
        if not isinstance(params, dict):
            raise SilverDataError(
                f"Receipt has malformed 'parameters' field "
                f"(expected dict, got {type(params).__name__}): {receipt_path.name}"
            )

        # Filter for our target scope (tabloNo=4, TL, taraf=10001)
        if str(params.get("tabloNo")) != "4" or params.get("paraBirimi") != "TL" or params.get("taraf") != ["10001"]:
            continue

        yil = params.get("yil")
        ay = params.get("ay")

        try:
            y_int, m_int = int(yil), int(ay)
            rec_date = datetime.date(y_int, m_int, 1)
        except (ValueError, TypeError):
            raise SilverDataError(f"Invalid yil/ay in receipt {receipt_path.name}: yil={yil}, ay={ay}")

        # Check if it falls within the requested period
        if not (start_date <= rec_date <= end_date):
            continue

        # --- Validate and parse downloaded_at as a real datetime (not a raw string) ---
        # Raw string comparisons are fragile: "zzz" would silently "win" deduplication.
        try:
            downloaded_dt = parse_iso8601_timestamp(data.get("downloaded_at"), "downloaded_at")
        except IntegrityError as e:
            raise SilverDataError(f"Receipt has invalid downloaded_at in {receipt_path.name}: {e}")

        # --- HATA 2 FIX: Cross-check receipt period against validation.period ---
        # parameters.yil/ay ürettiği dönem ile receipt'in validation.period alanı
        # eşleşmeli. Eşleşmezse (örn. Ocak parametreli receipt → Şubat dosyasına işaret)
        # Şubat rakamı Ocak satırı olarak Silver'a yazılır — sessiz veri sahteciliği.
        expected_period = f"{y_int:04d}-{m_int:02d}"
        validation = data.get("validation")
        if not isinstance(validation, dict):
            raise SilverDataError(
                f"Receipt missing 'validation' block: {receipt_path.name}"
            )

        receipt_val_period = validation.get("period")
        if not receipt_val_period or not isinstance(receipt_val_period, str):
            raise SilverDataError(
                f"Receipt 'validation.period' is missing or empty: {receipt_path.name}"
            )
        if receipt_val_period.strip() != expected_period:
            raise SilverDataError(
                f"Period mismatch in {receipt_path.name}: "
                f"parameters say {expected_period!r} but validation.period is {receipt_val_period!r}. "
                f"Raw file may contain data for a different month than the request."
            )

        period_confirmation = validation.get("period_confirmation")
        if period_confirmation != "response_caption":
            raise SilverDataError(
                f"Receipt 'validation.period_confirmation' is not 'response_caption' "
                f"(got {period_confirmation!r}): {receipt_path.name}. "
                f"Period cannot be trusted without caption-level confirmation."
            )

        # Check raw file path — must stay within the expected aylik/raw subdirectory,
        # not just anywhere under the BDDK root.
        rel_path = data.get("path")
        if not rel_path or not isinstance(rel_path, str):
            raise SilverDataError(f"Receipt missing raw file path: {receipt_path.name}")
        if not rel_path.replace("\\", "/").startswith("aylik/raw/"):
            raise SilverDataError(
                f"Receipt raw path is outside expected 'aylik/raw/' subdirectory "
                f"(got {rel_path!r}): {receipt_path.name}"
            )

        try:
            raw_file_path = resolve_secure_raw_path(raw_dir.parent.parent, rel_path)
            verify_file_integrity(raw_file_path, data.get("size_bytes"), data.get("sha256"))
        except IntegrityError as e:
            raise SilverDataError(str(e))

        # Parse raw payload
        raw_bytes = raw_file_path.read_bytes()
        try:
            raw_payload = json.loads(raw_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise SilverDataError(f"Raw file is not valid JSON: {raw_file_path.name} - {e}")

        # Store for deduplication — downloaded_dt is a real datetime for correct comparison
        all_receipts.append({
            "request_key": req_key,
            "period": f"{y_int:04d}-{m_int:02d}",
            "downloaded_at": downloaded_dt,   # datetime object, NOT a raw string
            "raw_payload": raw_payload,
            "receipt_name": receipt_path.name,
            "raw_bytes_len": raw_file_path.stat().st_size,
        })

    # Deduplicate using core validator
    return deduplicate_records(all_receipts, group_key=lambda r: r["period"], sort_key=lambda r: r["downloaded_at"])


def build_bddk_monthly_silver_table(
    receipts_dir: Path,
    raw_dir: Path,
    start_period: str = DEFAULT_START_PERIOD,
    end_period: str = DEFAULT_END_PERIOD,
) -> pd.DataFrame:
    """Builds and validates the BDDK Monthly Silver dataset from Bronze.

    Args:
        receipts_dir: Path to the Bronze monthly receipts directory.
        raw_dir: Path to the Bronze monthly raw data directory.
        start_period: Target start period (YYYY-MM).
        end_period: Target end period (YYYY-MM).

    Returns:
        A validated pandas DataFrame meeting the Silver and Gold compatibility contracts.

    Raises:
        SilverDataError: If data extraction, verification, or validation fails.
    """
    valid_receipts = load_and_verify_bronze_receipts(receipts_dir, raw_dir, start_period, end_period)

    rows = []
    for rec in valid_receipts:
        try:
            parsed = extract_housing_loan_data(rec["raw_payload"])
        except ValueError as e:
            raise SilverDataError(f"Failed to extract housing loan data from {rec['receipt_name']}: {e}")

        tp = parsed.get("tp")
        yp = parsed.get("yp")
        toplam = parsed.get("toplam")

        for val, name in [(tp, "tp"), (yp, "yp"), (toplam, "toplam")]:
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                raise SilverDataError(f"Invalid housing loan {name} in {rec['receipt_name']}: {val}")

        if toplam <= 0:
            raise SilverDataError(f"Invalid housing loan total in {rec['receipt_name']}: {toplam}")

        caption = parsed.get("caption", "")
        # Official unit verification
        if "milyon tl" not in caption.lower():
            raise SilverDataError(f"Missing or unrecognized unit in caption for {rec['receipt_name']}: {caption}")

        # Cross-check period in raw payload caption if present (e.g. 'Dönem:2023/4')
        caption_match = re.search(r"Dönem:\s*(\d{4})/(\d{1,2})(?!\d)", caption, re.IGNORECASE)
        if caption_match:
            c_y, c_m = int(caption_match.group(1)), int(caption_match.group(2))
            rec_y, rec_m = map(int, rec["period"].split("-"))
            if (c_y, c_m) != (rec_y, rec_m):
                raise SilverDataError(
                    f"Raw payload caption period mismatch in {rec['receipt_name']}: "
                    f"receipt period is {rec['period']} but raw content caption indicates {c_y:04d}-{c_m:02d} ({caption!r})."
                )

        unit = "Milyon TL"

        rows.append({
            "period": rec["period"],
            "housing_loan_amount": float(toplam),
            # Compatibility bridge for existing build_housing_gold_table
            "nominal_housing_loan_mn_try": float(toplam),
            "housing_loan_unit": unit,
            "bddk_source_ref": rec["request_key"],
            "data_quality_note": f"verified:size({rec['raw_bytes_len']}),sha256,dedup,positive_finite",
        })

    df = pd.DataFrame(rows)
    if df.empty:
        # Create empty dataframe with correct schema for validation to catch the gap
        df = pd.DataFrame(columns=[
            "period", "housing_loan_amount", "nominal_housing_loan_mn_try",
            "housing_loan_unit", "bddk_source_ref", "data_quality_note"
        ])

    df = df.sort_values("period").reset_index(drop=True)
    return validate_bddk_monthly_silver(df, start_period, end_period)

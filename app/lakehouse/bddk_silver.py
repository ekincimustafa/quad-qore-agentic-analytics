"""BDDK Silver layer transformation and validation module.

This module processes verified BDDK Bronze artifacts (monthly JSON receipts)
and transforms them into the Silver housing loan dataset.
"""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

import pandas as pd

from app.connectors.bddk import extract_housing_loan_data
from app.lakehouse.core_validators import (
    IntegrityError,
    check_missing_periods,
    deduplicate_records,
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
        "housing_loan_unit",
        "bddk_source_ref",
        "data_quality_note",
    }
    missing_cols = required_columns - set(data.columns)
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

    # 3. Unit checks
    units = df["housing_loan_unit"].astype(str).str.strip()
    if (units == "").any() or (units == "nan").any():
        raise SilverDataError("housing_loan_unit contains empty values.")
    
    unique_units = units.unique()
    if len(unique_units) > 1:
        raise SilverDataError(f"housing_loan_unit is inconsistent across rows: {unique_units}")

    # 4. Source ref checks
    refs = df["bddk_source_ref"].astype(str).str.strip()
    if (refs == "").any() or (refs == "nan").any():
        raise SilverDataError("bddk_source_ref contains empty values.")

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
        if not isinstance(params, dict):
            continue  # Ignore receipts without parameters (e.g. catalogs)

        # Filter for our target scope
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

        # Check raw file path and presence
        rel_path = data.get("path")
        if not rel_path:
            raise SilverDataError(f"Receipt missing raw file path: {receipt_path.name}")
        
        try:
            raw_file_path = resolve_secure_raw_path(raw_dir.parent.parent, rel_path) # bronze base is data/bronze/bddk
            
            # Verify file presence, size, and SHA-256 via core validator
            verify_file_integrity(raw_file_path, data.get("size_bytes"), data.get("sha256"))
        except IntegrityError as e:
            raise SilverDataError(str(e))

        # Parse raw payload
        raw_bytes = raw_file_path.read_bytes()
        try:
            raw_payload = json.loads(raw_bytes.decode("utf-8"))
        except Exception as e:
            raise SilverDataError(f"Raw file is not valid JSON: {raw_file_path.name} - {e}")
            
        # Store for deduplication
        all_receipts.append({
            "request_key": req_key,
            "period": f"{y_int:04d}-{m_int:02d}",
            "downloaded_at": data.get("downloaded_at", ""),
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

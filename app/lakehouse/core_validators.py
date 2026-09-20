"""Core generic validators and utilities for the Quad-Qore Lakehouse.

This module provides reusable data integrity, path security, and structural
validation functions. These should be used across all domain-specific Silver
transformers (e.g., BDDK, Health, Education) to enforce uniform standards
without duplicating logic.
"""

import datetime
import hashlib
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd

PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

T = TypeVar("T")


class IntegrityError(ValueError):
    """Raised when data fails generic core integrity or security checks."""


def resolve_secure_raw_path(base_dir: Path, rel_path: str) -> Path:
    """Securely resolves a relative path against a base directory, preventing path traversal.

    Args:
        base_dir: The root directory that the path must not escape.
        rel_path: The untrusted relative path string.

    Returns:
        The safely resolved Path object.

    Raises:
        IntegrityError: If the path attempts to traverse outside the base directory,
                        is absolute, or contains invalid characters.
    """
    if not rel_path or not isinstance(rel_path, str) or isinstance(rel_path, bool):
        raise IntegrityError(f"Invalid path string: {rel_path}")
    if ":" in rel_path:
        raise IntegrityError(f"Path contains invalid characters (e.g. drive letter): {rel_path}")

    clean_rel = rel_path.replace("\\", "/").strip()
    if clean_rel.startswith(("/", "\\")):
        raise IntegrityError(f"Path cannot be absolute: {rel_path}")

    parts = [p for p in clean_rel.split("/") if p]
    if not parts or any(p in (".", "..") for p in parts):
        raise IntegrityError(f"Path contains traversal elements: {rel_path}")

    try:
        base_resolved = base_dir.resolve(strict=True)
        target = (base_resolved / "/".join(parts)).resolve()
        # Verify the target is safely under base_resolved by calling relative_to
        target.relative_to(base_resolved)
        return target
    except (ValueError, OSError, RuntimeError) as e:
        raise IntegrityError(f"Failed to securely resolve path {rel_path!r}: {e}")


def parse_period_to_date(period_str: str) -> datetime.date:
    """Parses a YYYY-MM string into a date representing the first of that month."""
    if not isinstance(period_str, str) or not PERIOD_PATTERN.fullmatch(period_str.strip()):
        raise IntegrityError(f"Invalid period format (must be YYYY-MM): {period_str}")
    y, m = period_str.strip().split("-")
    try:
        return datetime.date(int(y), int(m), 1)
    except ValueError as e:
        raise IntegrityError(f"Invalid calendar date for period {period_str}: {e}")


def verify_file_integrity(file_path: Path, expected_size_bytes: int, expected_sha256: str) -> None:
    """Verifies that a physical file exists, matches the expected size, and matches the expected SHA-256 hash.

    Raises:
        IntegrityError: If any of the checks fail.
    """
    if not file_path.is_file():
        raise IntegrityError(f"Physical file missing: {file_path}")

    # Strict type check: bool is a subclass of int in Python, so isinstance(True, int) == True.
    # We must use `type() is int` to reject boolean values like True/False as size_bytes.
    if type(expected_size_bytes) is not int or expected_size_bytes <= 0:
        raise IntegrityError(f"Invalid expected size: {expected_size_bytes}")

    actual_size = file_path.stat().st_size
    if actual_size != expected_size_bytes:
        raise IntegrityError(f"File size mismatch for {file_path.name}: expected {expected_size_bytes}, got {actual_size}")

    if not expected_sha256 or not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise IntegrityError(f"Invalid expected sha256 format: {expected_sha256}")

    raw_bytes = file_path.read_bytes()
    actual_sha = hashlib.sha256(raw_bytes).hexdigest()
    if actual_sha != expected_sha256.lower():
        raise IntegrityError(f"SHA-256 mismatch for {file_path.name}. File corrupted or altered.")


def parse_iso8601_timestamp(raw: object, field_name: str = "timestamp") -> datetime.datetime:
    """Parses and validates an ISO-8601 timestamp string, returning a timezone-aware datetime.

    Rejects None, empty strings, non-strings, and malformed values so they can never
    silently corrupt sort-key comparisons (e.g. deduplication by downloaded_at).

    Args:
        raw: The untrusted value to parse.
        field_name: Human-readable field name used in error messages.

    Returns:
        A timezone-aware ``datetime.datetime`` object (UTC if no timezone present).

    Raises:
        IntegrityError: If the value is missing, not a string, or not valid ISO-8601.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise IntegrityError(f"'{field_name}' is missing or empty.")
    if not isinstance(raw, str):
        raise IntegrityError(f"'{field_name}' must be a string, got {type(raw).__name__}.")

    normalised = raw.strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(normalised)
    except ValueError:
        raise IntegrityError(
            f"'{field_name}' is not a valid ISO-8601 timestamp: {raw!r}."
        )

    # Ensure timezone-aware so comparisons across receipts are always unambiguous.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def deduplicate_records(records: Iterable[T], group_key: Callable[[T], str], sort_key: Callable[[T], Any]) -> list[T]:
    """Deduplicates a list of records.

    Groups records by `group_key` and keeps the one with the maximum `sort_key` value.
    Useful for taking the latest downloaded receipt for a given period or request ID.
    """
    deduped = {}
    for r in records:
        k = group_key(r)
        s = sort_key(r)
        if k not in deduped or s > sort_key(deduped[k]):
            deduped[k] = r
    return list(deduped.values())


def check_missing_periods(actual_periods: Iterable[str], start_period: str, end_period: str) -> None:
    """Verifies that actual_periods contains every single month between start_period and end_period without gaps.

    Raises:
        IntegrityError: If any month is missing.
    """
    # Validate formats first
    start_date = parse_period_to_date(start_period)
    end_date = parse_period_to_date(end_period)

    if start_date > end_date:
        raise IntegrityError(f"start_period ({start_period}) cannot be after end_period ({end_period}).")

    expected_periods = pd.period_range(start=start_period, end=end_period, freq="M").astype(str).tolist()
    actual_set = set(actual_periods)

    missing_periods = sorted(set(expected_periods) - actual_set)
    if missing_periods:
        raise IntegrityError(f"Missing continuous periods in the dataset: gaps found at {missing_periods}")


def validate_numeric_series(series: pd.Series, series_name: str, strictly_positive: bool = False) -> None:
    """Validates that a pandas Series contains only finite, numeric values without NaNs.

    Args:
        series: The pandas Series to validate.
        series_name: The name of the series for error reporting.
        strictly_positive: If True, values <= 0 will raise an error.

    Raises:
        IntegrityError: If validation fails.
    """
    numeric = pd.to_numeric(series, errors="coerce")

    if numeric.isna().any():
        raise IntegrityError(f"Column '{series_name}' contains non-numeric or missing (NaN) values.")

    invalid_finite = numeric.isin([float("inf"), float("-inf")])
    if invalid_finite.any():
        raise IntegrityError(f"Column '{series_name}' contains infinite (Inf) values.")

    if strictly_positive and (numeric <= 0).any():
        raise IntegrityError(f"Column '{series_name}' must contain strictly positive values (> 0).")

"""EVDS manifest schema and validation logic for the housing-loan demo."""

from __future__ import annotations

from datetime import date
import hashlib
import json
import re
from pathlib import Path
from typing import Annotated, Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr


class EvdsBronzeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_path: str
    raw_path: str
    sha256: str
    size_bytes: StrictInt
    downloaded_at: str
    request_start: str
    request_end: str


class EvdsWeeklyCoverageMonth(BaseModel):
    """Observed weekly dates; no publication calendar has been verified."""

    model_config = ConfigDict(extra="forbid")

    period: StrictStr
    status: Literal["unverified"]
    observed_count: Annotated[StrictInt, Field(ge=1)]
    expected_count: None
    observed_dates: list[StrictStr]
    quality_note: StrictStr


class EvdsWeeklyCoverage(BaseModel):
    """The embedded #39 contract, not the standalone .coverage.json report."""

    model_config = ConfigDict(extra="forbid")

    overall_status: Literal["unverified"]
    calendar_verification: Literal["not_available"]
    months: list[EvdsWeeklyCoverageMonth]


class EvdsSeriesRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_code: str
    silver_columns: list[str]
    unit: str
    native_frequency: str
    target_frequency: str
    base_year: StrictInt | None
    base_year_source: str
    transformation: str
    bronze: list[EvdsBronzeReceipt]
    weekly_coverage: EvdsWeeklyCoverage | None = None


class EvdsSilverDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    size_bytes: StrictInt
    row_count: StrictInt
    start_period: str
    end_period: str
    columns: list[str]


class EvdsManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    dataset: str
    silver: EvdsSilverDataset
    series: list[EvdsSeriesRef]


SUPPORTED_SCHEMA_VERSIONS = {"1.0", "1.0.0"}
REQUIRED_EVDS_COLUMNS = (
    "period",
    "housing_loan_interest_rate_pct",
    "weekly_observation_count",
    "cpi_index",
    "housing_price_index",
)
REQUIRED_SERIES_CODES = {"TP.KTF12", "TP.TUKFIY2025.GENEL", "TP.KFE.TR"}
WEEKLY_COVERAGE_NOTE = (
    "EVDS TP.KTF12 weekly_coverage: unverified; calendar_verification: not_available. "
    "Haftalık kapsam, doğrulanmış resmî yayın takvimi olmadan teyit edilemez."
)
REQUIRED_RECEIPT_FIELDS = {
    "series_code",
    "frequency",
    "request_start",
    "request_end",
    "downloaded_at",
    "sha256",
    "size_bytes",
    "raw_path",
}
EXPECTED_SERIES_CONTRACT: dict[str, dict[str, Any]] = {
    "TP.KTF12": {
        "silver_columns": ["housing_loan_interest_rate_pct", "weekly_observation_count"],
        "unit": "percent",
        "native_frequency": "weekly",
        "target_frequency": "monthly",
        "base_year": None,
        "allowed_base_year_sources": {"not_applicable"},
        "allowed_transformations": {
            "mean",
            "monthly_arithmetic_mean",
            "monthly arithmetic mean of weekly observations",
        },
    },
    "TP.TUKFIY2025.GENEL": {
        "silver_columns": ["cpi_index"],
        "unit": "index",
        "native_frequency": "monthly",
        "target_frequency": "monthly",
        "base_year": 2025,
        "allowed_base_year_sources": {
            "tcmb",
            "evds",
            "series_definition",
            "source_metadata",
            "official_series_metadata",
        },
        "allowed_transformations": {
            "level",
            "none",
            "as_published",
            "monthly level as published",
        },
    },
    "TP.KFE.TR": {
        "silver_columns": ["housing_price_index"],
        "unit": "index",
        "native_frequency": "monthly",
        "target_frequency": "monthly",
        "base_year": 2023,
        "allowed_base_year_sources": {
            "tcmb",
            "evds",
            "series_definition",
            "source_metadata",
            "official_series_metadata",
        },
        "allowed_transformations": {
            "level",
            "none",
            "as_published",
            "monthly level as published",
        },
    },
}
_PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class ManifestValidationError(ValueError):
    """Raised when the EVDS manifest fails validation against the physical CSV or contract."""
    pass


def _parse_iso_date(value: str, field_name: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        raise ManifestValidationError(f"Invalid ISO date for {field_name}: {value!r}")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ManifestValidationError(f"Invalid calendar date for {field_name}: {value!r}") from exc


def _validate_weekly_coverage(manifest: EvdsManifest, df: pd.DataFrame) -> None:
    """Cross-check the full Silver sequence without inventing expected weeks."""
    series = next(s for s in manifest.series if s.series_code == "TP.KTF12")
    coverage = series.weekly_coverage
    if coverage is None:
        raise ManifestValidationError("TP.KTF12 weekly_coverage is required.")

    periods = df["period"].astype(str).str.strip().tolist()
    if [month.period for month in coverage.months] != periods:
        raise ManifestValidationError("weekly_coverage months must match the Silver period sequence exactly.")

    counts = pd.to_numeric(df["weekly_observation_count"], errors="coerce")
    for month, silver_count in zip(coverage.months, counts):
        prefix = f"weekly_coverage {month.period}"
        if not month.quality_note.strip():
            raise ManifestValidationError(f"{prefix} quality_note cannot be empty.")
        if month.observed_dates != sorted(set(month.observed_dates)):
            raise ManifestValidationError(f"{prefix} observed_dates must be sorted and unique.")
        for value in month.observed_dates:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ManifestValidationError(f"{prefix} observed_dates must use YYYY-MM-DD.")
            parsed = _parse_iso_date(value, f"{prefix} observed_dates")
            if parsed.isoformat()[:7] != month.period:
                raise ManifestValidationError(f"{prefix} observed_dates contains a date from another month.")
        if month.observed_count != len(month.observed_dates):
            raise ManifestValidationError(f"{prefix} observed_count does not match observed_dates length.")
        if pd.isna(silver_count) or silver_count != month.observed_count:
            raise ManifestValidationError(f"{prefix} observed_count does not match Silver weekly_observation_count.")


def load_and_validate_manifest(manifest_path: Path | str, project_root: Path | str) -> EvdsManifest:
    """Read the JSON manifest, validate its Pydantic schema, and strictly verify against contract and physical files."""
    manifest_file = Path(manifest_path)
    root_dir = Path(project_root)
    resolved_root = root_dir.resolve()

    if not manifest_file.is_file():
        raise ManifestValidationError(f"Manifest file not found: {manifest_file}")

    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest = EvdsManifest.model_validate(data)
    except Exception as exc:
        raise ManifestValidationError(f"Invalid manifest schema: {exc}") from exc

    # 1. Supported schema version
    if manifest.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ManifestValidationError(
            f"Unsupported manifest schema_version: {manifest.schema_version!r}. "
            f"Supported versions: {sorted(SUPPORTED_SCHEMA_VERSIONS)}"
        )

    # 2. Dataset declaration
    if not manifest.dataset or not manifest.dataset.strip():
        raise ManifestValidationError("Manifest dataset name cannot be empty.")

    # 3. Period declarations
    if not _PERIOD_PATTERN.match(manifest.silver.start_period):
        raise ManifestValidationError(f"Invalid manifest start_period format: {manifest.silver.start_period!r}")
    if not _PERIOD_PATTERN.match(manifest.silver.end_period):
        raise ManifestValidationError(f"Invalid manifest end_period format: {manifest.silver.end_period!r}")
    if manifest.silver.start_period > manifest.silver.end_period:
        raise ManifestValidationError(
            f"Manifest start_period ({manifest.silver.start_period}) cannot be later than end_period ({manifest.silver.end_period})"
        )

    silver_start_date = pd.Period(manifest.silver.start_period, freq="M").start_time.date()
    silver_end_date = pd.Period(manifest.silver.end_period, freq="M").end_time.date()

    # 4. Required Silver columns in manifest declaration
    missing_cols = set(REQUIRED_EVDS_COLUMNS) - set(manifest.silver.columns)
    if missing_cols:
        raise ManifestValidationError(
            f"Manifest silver columns missing required columns: {sorted(missing_cols)}"
        )
    if list(manifest.silver.columns) != list(REQUIRED_EVDS_COLUMNS):
        raise ManifestValidationError(
            f"Manifest silver columns {list(manifest.silver.columns)} do not match required order {list(REQUIRED_EVDS_COLUMNS)}"
        )

    # 5. Series validation & contract verification
    if not manifest.series:
        raise ManifestValidationError("Manifest series list cannot be empty.")

    series_codes_list = [s.series_code for s in manifest.series]
    if len(series_codes_list) != len(set(series_codes_list)):
        raise ManifestValidationError(f"Manifest contains duplicate series declarations: {series_codes_list}")

    series_codes = set(series_codes_list)
    missing_series = REQUIRED_SERIES_CODES - series_codes
    if missing_series:
        raise ManifestValidationError(
            f"Manifest missing required series: {sorted(missing_series)}"
        )
    unexpected_series = series_codes - REQUIRED_SERIES_CODES
    if unexpected_series:
        raise ManifestValidationError(
            f"Manifest contains unexpected series: {sorted(unexpected_series)}"
        )

    series_bronze_ranges: list[tuple[str, date, date]] = []

    for series in manifest.series:
        spec = EXPECTED_SERIES_CONTRACT[series.series_code]

        if not series.unit or not series.unit.strip():
            raise ManifestValidationError(f"Series {series.series_code} unit cannot be empty.")
        if series.unit.strip() != spec["unit"]:
            raise ManifestValidationError(
                f"Series {series.series_code} unit must be {spec['unit']!r}, got {series.unit!r}"
            )

        if not series.silver_columns:
            raise ManifestValidationError(f"Series {series.series_code} silver_columns cannot be empty.")
        for col in series.silver_columns:
            if col not in manifest.silver.columns:
                raise ManifestValidationError(
                    f"Series {series.series_code} column {col!r} is not declared in manifest silver columns."
                )
        if list(series.silver_columns) != spec["silver_columns"]:
            raise ManifestValidationError(
                f"Series {series.series_code} silver_columns must be {spec['silver_columns']}, got {series.silver_columns}"
            )

        if series.native_frequency != spec["native_frequency"]:
            raise ManifestValidationError(
                f"Series {series.series_code} native_frequency must be {spec['native_frequency']!r}, got {series.native_frequency!r}"
            )
        if series.target_frequency != spec["target_frequency"]:
            raise ManifestValidationError(
                f"Series {series.series_code} target_frequency must be {spec['target_frequency']!r}, got {series.target_frequency!r}"
            )

        if series.base_year != spec["base_year"] or type(series.base_year) is not type(spec["base_year"]):
            raise ManifestValidationError(
                f"Series {series.series_code} base_year must be {spec['base_year']!r}, got {series.base_year!r}"
            )

        if (
            not series.base_year_source
            or series.base_year_source.strip().lower() not in spec["allowed_base_year_sources"]
        ):
            raise ManifestValidationError(
                f"Series {series.series_code} has invalid base_year_source: {series.base_year_source!r}"
            )

        if (
            not series.transformation
            or series.transformation.strip().lower() not in spec["allowed_transformations"]
        ):
            raise ManifestValidationError(
                f"Series {series.series_code} has invalid transformation: {series.transformation!r}"
            )

        if not series.bronze:
            raise ManifestValidationError(f"Series {series.series_code} bronze receipts list cannot be empty.")

        if series.series_code == "TP.KTF12":
            if series.weekly_coverage is None:
                raise ManifestValidationError("TP.KTF12 weekly_coverage is required.")
        elif series.weekly_coverage is not None:
            raise ManifestValidationError(f"Monthly series {series.series_code} weekly_coverage must be absent or null.")

        bronze_starts: list[date] = []
        bronze_ends: list[date] = []

        for b in series.bronze:
            # Traversal & absolute path checks
            if not b.receipt_path or not b.receipt_path.strip() or ".." in b.receipt_path or b.receipt_path.startswith(("/", "\\")):
                raise ManifestValidationError(
                    f"Receipt path contains traversal or is absolute: {b.receipt_path!r}"
                )
            if not b.raw_path or not b.raw_path.strip() or ".." in b.raw_path or b.raw_path.startswith(("/", "\\")):
                raise ManifestValidationError(
                    f"Raw path contains traversal or is absolute: {b.raw_path!r}"
                )

            try:
                receipt_file = (root_dir / b.receipt_path).resolve()
                receipt_file.relative_to(resolved_root)
            except ValueError:
                raise ManifestValidationError(
                    f"Receipt path resolves outside project root: {b.receipt_path!r}"
                )

            try:
                raw_file = (root_dir / b.raw_path).resolve()
                raw_file.relative_to(resolved_root)
            except ValueError:
                raise ManifestValidationError(
                    f"Raw path resolves outside project root: {b.raw_path!r}"
                )

            # Receipt file and raw file must both physically exist
            if not receipt_file.is_file():
                raise ManifestValidationError(
                    f"Bronze receipt file declared in manifest not found: {b.receipt_path}"
                )
            if not raw_file.is_file():
                raise ManifestValidationError(
                    f"Bronze raw file declared in manifest not found: {b.raw_path}"
                )

            # Verify raw file size_bytes and SHA-256 against manifest bronze entry
            if type(b.size_bytes) is not int or b.size_bytes <= 0:
                raise ManifestValidationError(
                    f"Invalid bronze size_bytes for {b.raw_path}: {b.size_bytes!r}"
                )
            raw_bytes = raw_file.read_bytes()
            if len(raw_bytes) != b.size_bytes:
                raise ManifestValidationError(
                    f"Bronze raw file size mismatch for {b.raw_path}. "
                    f"Expected: {b.size_bytes} bytes, Actual: {len(raw_bytes)} bytes"
                )
            actual_raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
            if actual_raw_sha256.lower() != b.sha256.lower():
                raise ManifestValidationError(
                    f"Bronze raw file SHA-256 mismatch for {b.raw_path}. "
                    f"Expected: {b.sha256}, Actual: {actual_raw_sha256}"
                )

            # Read and validate receipt JSON content
            try:
                receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
            except Exception as exc:
                raise ManifestValidationError(
                    f"Invalid JSON in bronze receipt {b.receipt_path}: {exc}"
                ) from exc

            if not isinstance(receipt_data, dict):
                raise ManifestValidationError(
                    f"Bronze receipt {b.receipt_path} must be a JSON object."
                )

            missing_receipt_fields = REQUIRED_RECEIPT_FIELDS - set(receipt_data.keys())
            if missing_receipt_fields:
                raise ManifestValidationError(
                    f"Bronze receipt {b.receipt_path} is missing required fields: {sorted(missing_receipt_fields)}"
                )

            if receipt_data["series_code"] != series.series_code:
                raise ManifestValidationError(
                    f"Bronze receipt {b.receipt_path} series_code ({receipt_data['series_code']!r}) "
                    f"does not match manifest series ({series.series_code!r})."
                )
            if receipt_data["frequency"] != series.native_frequency:
                raise ManifestValidationError(
                    f"Bronze receipt {b.receipt_path} frequency ({receipt_data['frequency']!r}) "
                    f"does not match series native_frequency ({series.native_frequency!r})."
                )

            req_start = _parse_iso_date(b.request_start, "request_start")
            req_end = _parse_iso_date(b.request_end, "request_end")
            if req_start > req_end:
                raise ManifestValidationError(
                    f"Bronze request_start ({b.request_start}) cannot be after request_end ({b.request_end})."
                )
            if receipt_data["request_start"] != b.request_start or receipt_data["request_end"] != b.request_end:
                raise ManifestValidationError(
                    f"Bronze receipt {b.receipt_path} request range "
                    f"[{receipt_data['request_start']}, {receipt_data['request_end']}] "
                    f"does not match manifest [{b.request_start}, {b.request_end}]."
                )
            bronze_starts.append(req_start)
            bronze_ends.append(req_end)

            if not isinstance(b.downloaded_at, str) or not b.downloaded_at.strip():
                raise ManifestValidationError(f"Bronze downloaded_at cannot be empty for {b.receipt_path}.")
            if receipt_data["downloaded_at"] != b.downloaded_at:
                raise ManifestValidationError(
                    f"Bronze receipt {b.receipt_path} downloaded_at ({receipt_data['downloaded_at']!r}) "
                    f"does not match manifest ({b.downloaded_at!r})."
                )

            if not isinstance(receipt_data["sha256"], str) or receipt_data["sha256"].lower() != b.sha256.lower():
                raise ManifestValidationError(
                    f"Bronze receipt {b.receipt_path} sha256 ({receipt_data['sha256']!r}) "
                    f"does not match manifest sha256 ({b.sha256!r})."
                )
            if type(receipt_data["size_bytes"]) is not int or receipt_data["size_bytes"] != b.size_bytes:
                raise ManifestValidationError(
                    f"Bronze receipt {b.receipt_path} size_bytes ({receipt_data['size_bytes']!r}) "
                    f"does not match manifest size_bytes ({b.size_bytes!r})."
                )

            receipt_raw_str = receipt_data["raw_path"]
            if (
                not isinstance(receipt_raw_str, str)
                or not receipt_raw_str.strip()
                or ".." in receipt_raw_str
                or receipt_raw_str.startswith(("/", "\\"))
            ):
                raise ManifestValidationError(
                    f"Invalid raw_path in bronze receipt {b.receipt_path}: {receipt_raw_str!r}"
                )
            candidate_direct = (root_dir / receipt_raw_str).resolve()
            candidate_data = (root_dir / "data" / receipt_raw_str).resolve()
            if candidate_direct != raw_file and candidate_data != raw_file:
                raise ManifestValidationError(
                    f"Bronze receipt {b.receipt_path} raw_path ({receipt_raw_str!r}) "
                    f"does not resolve to manifest raw_path ({b.raw_path!r})."
                )

        series_bronze_ranges.append((series.series_code, min(bronze_starts), max(bronze_ends)))

    # 6. Physical CSV verification
    if ".." in manifest.silver.path or manifest.silver.path.startswith(("/", "\\")):
        raise ManifestValidationError(f"Silver CSV path contains traversal or is absolute: {manifest.silver.path!r}")

    try:
        csv_file = (root_dir / manifest.silver.path).resolve()
        csv_file.relative_to(resolved_root)
    except ValueError:
        raise ManifestValidationError(f"Silver CSV path must be within project root: {manifest.silver.path}")

    if not csv_file.is_file():
        raise ManifestValidationError(f"Silver CSV file declared in manifest not found: {csv_file}")

    # Verify SHA-256 and size_bytes
    file_bytes = csv_file.read_bytes()
    if len(file_bytes) != manifest.silver.size_bytes:
        raise ManifestValidationError(
            f"Silver CSV size mismatch. Expected: {manifest.silver.size_bytes} bytes, Actual: {len(file_bytes)} bytes"
        )
    actual_sha256 = hashlib.sha256(file_bytes).hexdigest()
    if actual_sha256.lower() != manifest.silver.sha256.lower():
        raise ManifestValidationError(
            f"Silver CSV SHA-256 mismatch. Expected: {manifest.silver.sha256}, Actual: {actual_sha256}"
        )

    # Read CSV and check row count, columns, and period range
    try:
        df = pd.read_csv(csv_file)
    except Exception as exc:
        raise ManifestValidationError(f"Could not read Silver CSV file: {exc}") from exc

    if len(df) != manifest.silver.row_count:
        raise ManifestValidationError(
            f"Silver CSV row count mismatch. Expected: {manifest.silver.row_count}, Actual: {len(df)}"
        )

    if list(df.columns) != list(manifest.silver.columns):
        raise ManifestValidationError(
            f"Silver CSV columns {list(df.columns)} do not match manifest columns {list(manifest.silver.columns)}"
        )

    if "period" not in df.columns:
        raise ManifestValidationError("Silver CSV must contain 'period' column.")

    periods = df["period"].astype(str).str.strip().tolist()
    if not periods:
        raise ManifestValidationError("Silver CSV contains no periods.")

    if periods[0] != manifest.silver.start_period or periods[-1] != manifest.silver.end_period:
        raise ManifestValidationError(
            f"Silver CSV period range [{periods[0]}, {periods[-1]}] does not match "
            f"manifest declared range [{manifest.silver.start_period}, {manifest.silver.end_period}]"
        )

    expected_periods = pd.period_range(
        start=manifest.silver.start_period,
        end=manifest.silver.end_period,
        freq="M",
    ).astype(str).tolist()
    if periods != expected_periods:
        raise ManifestValidationError(
            f"Silver CSV periods do not match expected chronological monthly sequence from "
            f"{manifest.silver.start_period} to {manifest.silver.end_period}."
        )

    for series_code, min_start, max_end in series_bronze_ranges:
        if min_start > silver_start_date or max_end < silver_end_date:
            raise ManifestValidationError(
                f"Series {series_code} bronze request range "
                f"[{min_start}, {max_end}] does not cover manifest silver period "
                f"[{silver_start_date}, {silver_end_date}]."
            )

    _validate_weekly_coverage(manifest, df)

    return manifest


def append_evds_source_refs(df: pd.DataFrame, manifest: EvdsManifest) -> pd.DataFrame:
    """Append the 'evds_source_refs' column to the DataFrame based on the manifest.

    The refs are created by joining the receipt paths of all bronze inputs
    across all series declared in the manifest.
    """
    receipts = []
    for series in manifest.series:
        for bronze in series.bronze:
            if bronze.receipt_path and bronze.receipt_path.strip():
                receipts.append(bronze.receipt_path.strip())

    # Deduplicate while preserving order
    unique_receipts = list(dict.fromkeys(receipts))
    if not unique_receipts:
        raise ManifestValidationError(
            "No valid bronze receipts found in manifest series; cannot attach empty provenance."
        )

    joined_refs = "; ".join(unique_receipts)

    result = df.copy()
    result["evds_source_refs"] = joined_refs
    return result

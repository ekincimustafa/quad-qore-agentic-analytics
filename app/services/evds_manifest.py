"""EVDS manifest schema and validation logic for the housing-loan demo."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class EvdsBronzeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_path: str
    raw_path: str
    sha256: str
    size_bytes: int
    downloaded_at: str
    request_start: str
    request_end: str


class EvdsSeriesRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series_code: str
    silver_columns: list[str]
    unit: str
    native_frequency: str
    target_frequency: str
    base_year: int | None
    base_year_source: str
    transformation: str
    bronze: list[EvdsBronzeReceipt]


class EvdsSilverDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    size_bytes: int
    row_count: int
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
_PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class ManifestValidationError(ValueError):
    """Raised when the EVDS manifest fails validation against the physical CSV or contract."""
    pass


def load_and_validate_manifest(manifest_path: Path | str, project_root: Path | str) -> EvdsManifest:
    """Read the JSON manifest, validate its Pydantic schema, and strictly verify against contract and physical files."""
    manifest_file = Path(manifest_path)
    root_dir = Path(project_root)

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

    # 4. Required Silver columns in manifest declaration
    missing_cols = set(REQUIRED_EVDS_COLUMNS) - set(manifest.silver.columns)
    if missing_cols:
        raise ManifestValidationError(
            f"Manifest silver columns missing required columns: {sorted(missing_cols)}"
        )

    # 5. Series validation
    if not manifest.series:
        raise ManifestValidationError("Manifest series list cannot be empty.")

    series_codes = {s.series_code for s in manifest.series}
    missing_series = REQUIRED_SERIES_CODES - series_codes
    if missing_series:
        raise ManifestValidationError(
            f"Manifest missing required series: {sorted(missing_series)}"
        )

    for series in manifest.series:
        if not series.unit or not series.unit.strip():
            raise ManifestValidationError(f"Series {series.series_code} unit cannot be empty.")
        if not series.silver_columns:
            raise ManifestValidationError(f"Series {series.series_code} silver_columns cannot be empty.")
        for col in series.silver_columns:
            if col not in manifest.silver.columns:
                raise ManifestValidationError(
                    f"Series {series.series_code} column {col!r} is not declared in manifest silver columns."
                )

        if not series.bronze:
            raise ManifestValidationError(f"Series {series.series_code} bronze receipts list cannot be empty.")

        for b in series.bronze:
            # Traversal & absolute path checks
            if ".." in b.receipt_path or b.receipt_path.startswith(("/", "\\")):
                raise ManifestValidationError(
                    f"Receipt path contains traversal or is absolute: {b.receipt_path!r}"
                )
            if ".." in b.raw_path or b.raw_path.startswith(("/", "\\")):
                raise ManifestValidationError(
                    f"Raw path contains traversal or is absolute: {b.raw_path!r}"
                )

            try:
                receipt_file = (root_dir / b.receipt_path).resolve()
                receipt_file.relative_to(root_dir.resolve())
            except ValueError:
                raise ManifestValidationError(
                    f"Receipt path resolves outside project root: {b.receipt_path!r}"
                )

            try:
                raw_file = (root_dir / b.raw_path).resolve()
                raw_file.relative_to(root_dir.resolve())
            except ValueError:
                raise ManifestValidationError(
                    f"Raw path resolves outside project root: {b.raw_path!r}"
                )

            # Receipt file must physically exist
            if not receipt_file.is_file():
                raise ManifestValidationError(
                    f"Bronze receipt file declared in manifest not found: {b.receipt_path}"
                )

    # 6. Physical CSV verification
    try:
        csv_file = (root_dir / manifest.silver.path).resolve()
        csv_file.relative_to(root_dir.resolve())
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

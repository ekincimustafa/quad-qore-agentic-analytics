"""EVDS manifest schema and validation logic for the housing-loan demo."""

from __future__ import annotations

import hashlib
import json
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


class ManifestValidationError(ValueError):
    """Raised when the EVDS manifest fails validation against the physical CSV."""
    pass


def load_and_validate_manifest(manifest_path: Path | str, project_root: Path | str) -> EvdsManifest:
    """Read the JSON manifest, validate its Pydantic schema, and verify the physical CSV file."""
    manifest_file = Path(manifest_path)
    root_dir = Path(project_root)
    
    if not manifest_file.is_file():
        raise ManifestValidationError(f"Manifest file not found: {manifest_file}")
        
    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest = EvdsManifest.model_validate(data)
    except Exception as exc:
        raise ManifestValidationError(f"Invalid manifest schema: {exc}") from exc
        
    try:
        csv_file = (root_dir / manifest.silver.path).resolve()
        csv_file.relative_to(root_dir.resolve())
    except ValueError:
        raise ManifestValidationError(f"Silver CSV path must be within project root: {manifest.silver.path}")
        
    if not csv_file.is_file():
        raise ManifestValidationError(f"Silver CSV file declared in manifest not found: {csv_file}")
        
    # Verify SHA-256
    file_bytes = csv_file.read_bytes()
    actual_sha256 = hashlib.sha256(file_bytes).hexdigest()
    if actual_sha256.lower() != manifest.silver.sha256.lower():
        raise ManifestValidationError(
            f"Silver CSV SHA-256 mismatch. Expected: {manifest.silver.sha256}, Actual: {actual_sha256}"
        )
        
    # Verify Row Count (excluding header)
    # Read CSV without index to check row count
    try:
        df = pd.read_csv(csv_file)
    except Exception as exc:
        raise ManifestValidationError(f"Could not read Silver CSV file: {exc}") from exc
        
    if len(df) != manifest.silver.row_count:
        raise ManifestValidationError(
            f"Silver CSV row count mismatch. Expected: {manifest.silver.row_count}, Actual: {len(df)}"
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
            receipts.append(bronze.receipt_path)
            
    # Deduplicate while preserving order
    unique_receipts = list(dict.fromkeys(receipts))
    joined_refs = "; ".join(unique_receipts)
    
    result = df.copy()
    result["evds_source_refs"] = joined_refs
    return result

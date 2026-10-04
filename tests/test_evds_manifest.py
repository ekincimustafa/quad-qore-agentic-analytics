"""Tests for the EVDS manifest schema and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.services.evds_manifest import (
    ManifestValidationError,
    append_evds_source_refs,
    load_and_validate_manifest,
)


@pytest.fixture
def mock_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path
    
    # Create CSV
    csv_path = root / "data" / "silver" / "evds" / "monthly" / "evds_monthly_2021-01_2026-06.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"period": ["2021-01", "2021-02"]})
    df.to_csv(csv_path, index=False)
    
    # Calculate hash
    import hashlib
    sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    
    manifest_data = {
        "schema_version": "1.0",
        "dataset": "evds_monthly_silver",
        "silver": {
            "path": "data/silver/evds/monthly/evds_monthly_2021-01_2026-06.csv",
            "sha256": sha256,
            "size_bytes": len(csv_path.read_bytes()),
            "row_count": 2,
            "start_period": "2021-01",
            "end_period": "2021-02",
            "columns": ["period"]
        },
        "series": [
            {
                "series_code": "TP.KTF12",
                "silver_columns": ["housing_loan_interest_rate_pct"],
                "unit": "percent",
                "native_frequency": "weekly",
                "target_frequency": "monthly",
                "base_year": None,
                "base_year_source": "not_applicable",
                "transformation": "mean",
                "bronze": [
                    {
                        "receipt_path": "bronze/evds/tp_ktf12/receipts/1.json",
                        "raw_path": "bronze/evds/tp_ktf12/raw/1.json",
                        "sha256": "abcdef",
                        "size_bytes": 100,
                        "downloaded_at": "2026-09-19T10:00:00+03:00",
                        "request_start": "2021-01-01",
                        "request_end": "2026-06-30"
                    },
                    {
                        "receipt_path": "bronze/evds/tp_ktf12/receipts/2.json",
                        "raw_path": "bronze/evds/tp_ktf12/raw/2.json",
                        "sha256": "abcdef",
                        "size_bytes": 100,
                        "downloaded_at": "2026-09-19T10:00:00+03:00",
                        "request_start": "2021-01-01",
                        "request_end": "2026-06-30"
                    }
                ]
            }
        ]
    }
    
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")
    
    return root, manifest_path


def test_load_and_validate_success(mock_project):
    root, manifest_path = mock_project
    manifest = load_and_validate_manifest(manifest_path, root)
    assert manifest.schema_version == "1.0"
    assert manifest.silver.row_count == 2
    assert len(manifest.series[0].bronze) == 2


def test_missing_manifest_file(mock_project):
    root, _ = mock_project
    with pytest.raises(ManifestValidationError, match="Manifest file not found"):
        load_and_validate_manifest(root / "nonexistent.json", root)


def test_invalid_json(mock_project):
    root, manifest_path = mock_project
    manifest_path.write_text("{invalid json", encoding="utf-8")
    with pytest.raises(ManifestValidationError, match="Invalid manifest schema"):
        load_and_validate_manifest(manifest_path, root)


def test_missing_csv_file(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    (root / data["silver"]["path"]).unlink()
    with pytest.raises(ManifestValidationError, match="Silver CSV file declared in manifest not found"):
        load_and_validate_manifest(manifest_path, root)


def test_sha256_mismatch(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    # append char to alter hash
    csv_file = root / data["silver"]["path"]
    csv_file.write_text(csv_file.read_text() + "\n")
    
    with pytest.raises(ManifestValidationError, match="Silver CSV SHA-256 mismatch"):
        load_and_validate_manifest(manifest_path, root)


def test_row_count_mismatch(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["silver"]["row_count"] = 999
    manifest_path.write_text(json.dumps(data), encoding="utf-8")
    
    with pytest.raises(ManifestValidationError, match="Silver CSV row count mismatch"):
        load_and_validate_manifest(manifest_path, root)


def test_append_evds_source_refs(mock_project):
    root, manifest_path = mock_project
    manifest = load_and_validate_manifest(manifest_path, root)
    
    df = pd.DataFrame({"dummy": [1, 2]})
    result = append_evds_source_refs(df, manifest)
    
    assert "evds_source_refs" in result.columns
    # It should deduplicate the receipts if they are identical? 
    # Wait, in the mock data, receipt paths are "1.json" and "2.json" so they are distinct
    expected_refs = "bronze/evds/tp_ktf12/receipts/1.json; bronze/evds/tp_ktf12/receipts/2.json"
    assert result["evds_source_refs"].iloc[0] == expected_refs
    assert result["evds_source_refs"].iloc[1] == expected_refs
    
    # Original DF shouldn't be mutated
    assert "evds_source_refs" not in df.columns

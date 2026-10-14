"""Tests for the EVDS manifest schema and validation."""

from __future__ import annotations

import hashlib
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

    # Create CSV with required columns
    csv_path = root / "data" / "silver" / "evds" / "monthly" / "evds_monthly_2021-01_2026-06.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "period": ["2021-01", "2021-02"],
        "housing_loan_interest_rate_pct": [15.0, 14.5],
        "weekly_observation_count": [4, 4],
        "cpi_index": [100.0, 102.0],
        "housing_price_index": [100.0, 101.5],
    })
    df.to_csv(csv_path, index=False)

    # Create receipt files physically on disk
    receipt1 = root / "bronze" / "evds" / "tp_ktf12" / "receipts" / "1.json"
    receipt2 = root / "bronze" / "evds" / "tp_ktf12" / "receipts" / "2.json"
    receipt_cpi = root / "bronze" / "evds" / "cpi" / "receipts" / "cpi.json"
    receipt_kfe = root / "bronze" / "evds" / "kfe" / "receipts" / "kfe.json"

    for r in (receipt1, receipt2, receipt_cpi, receipt_kfe):
        r.parent.mkdir(parents=True, exist_ok=True)
        r.write_text("{}", encoding="utf-8")

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
            "columns": list(df.columns),
        },
        "series": [
            {
                "series_code": "TP.KTF12",
                "silver_columns": ["housing_loan_interest_rate_pct", "weekly_observation_count"],
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
            },
            {
                "series_code": "TP.TUKFIY2025.GENEL",
                "silver_columns": ["cpi_index"],
                "unit": "index",
                "native_frequency": "monthly",
                "target_frequency": "monthly",
                "base_year": 2025,
                "base_year_source": "tcmb",
                "transformation": "level",
                "bronze": [
                    {
                        "receipt_path": "bronze/evds/cpi/receipts/cpi.json",
                        "raw_path": "bronze/evds/cpi/raw/cpi.json",
                        "sha256": "cpi123",
                        "size_bytes": 200,
                        "downloaded_at": "2026-09-19T10:00:00+03:00",
                        "request_start": "2021-01-01",
                        "request_end": "2026-06-30"
                    }
                ]
            },
            {
                "series_code": "TP.KFE.TR",
                "silver_columns": ["housing_price_index"],
                "unit": "index",
                "native_frequency": "monthly",
                "target_frequency": "monthly",
                "base_year": 2017,
                "base_year_source": "tcmb",
                "transformation": "level",
                "bronze": [
                    {
                        "receipt_path": "bronze/evds/kfe/receipts/kfe.json",
                        "raw_path": "bronze/evds/kfe/raw/kfe.json",
                        "sha256": "kfe123",
                        "size_bytes": 200,
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
    assert len(manifest.series) == 3


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
    data["silver"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Silver CSV SHA-256 mismatch"):
        load_and_validate_manifest(manifest_path, root)


def test_row_count_mismatch(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["silver"]["row_count"] = 999
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Silver CSV row count mismatch"):
        load_and_validate_manifest(manifest_path, root)


def test_unsupported_schema_version(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["schema_version"] = "2.0"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Unsupported manifest schema_version"):
        load_and_validate_manifest(manifest_path, root)


def test_empty_series(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["series"] = []
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Manifest series list cannot be empty"):
        load_and_validate_manifest(manifest_path, root)


def test_missing_required_series(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["series"] = [s for s in data["series"] if s["series_code"] != "TP.KTF12"]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Manifest missing required series"):
        load_and_validate_manifest(manifest_path, root)


def test_missing_receipt_file(mock_project):
    root, manifest_path = mock_project
    (root / "bronze" / "evds" / "tp_ktf12" / "receipts" / "1.json").unlink()

    with pytest.raises(ManifestValidationError, match="Bronze receipt file declared in manifest not found"):
        load_and_validate_manifest(manifest_path, root)


def test_receipt_path_traversal(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["series"][0]["bronze"][0]["receipt_path"] = "../secret.json"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Receipt path contains traversal"):
        load_and_validate_manifest(manifest_path, root)


def test_period_mismatch(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["silver"]["start_period"] = "2020-01"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Silver CSV period range .* does not match"):
        load_and_validate_manifest(manifest_path, root)


def test_column_mismatch(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["silver"]["columns"].pop()
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError):
        load_and_validate_manifest(manifest_path, root)


def test_size_bytes_mismatch(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["silver"]["size_bytes"] = 999999
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Silver CSV size mismatch"):
        load_and_validate_manifest(manifest_path, root)


def test_non_chronological_periods(mock_project):
    root, manifest_path = mock_project
    csv_file = root / "data" / "silver" / "evds" / "monthly" / "evds_monthly_2021-01_2026-06.csv"
    # Overwrite CSV with disordered periods
    df = pd.DataFrame({
        "period": ["2021-02", "2021-01"],
        "housing_loan_interest_rate_pct": [14.5, 15.0],
        "weekly_observation_count": [4, 4],
        "cpi_index": [102.0, 100.0],
        "housing_price_index": [101.5, 100.0],
    })
    df.to_csv(csv_file, index=False)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["silver"]["sha256"] = hashlib.sha256(csv_file.read_bytes()).hexdigest()
    data["silver"]["size_bytes"] = len(csv_file.read_bytes())
    data["silver"]["start_period"] = "2021-02"
    data["silver"]["end_period"] = "2021-01"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError):
        load_and_validate_manifest(manifest_path, root)


def test_append_evds_source_refs(mock_project):
    root, manifest_path = mock_project
    manifest = load_and_validate_manifest(manifest_path, root)

    df = pd.DataFrame({"dummy": [1, 2]})
    result = append_evds_source_refs(df, manifest)

    assert "evds_source_refs" in result.columns
    expected_refs = (
        "bronze/evds/tp_ktf12/receipts/1.json; "
        "bronze/evds/tp_ktf12/receipts/2.json; "
        "bronze/evds/cpi/receipts/cpi.json; "
        "bronze/evds/kfe/receipts/kfe.json"
    )
    assert result["evds_source_refs"].iloc[0] == expected_refs
    assert result["evds_source_refs"].iloc[1] == expected_refs
    assert "evds_source_refs" not in df.columns

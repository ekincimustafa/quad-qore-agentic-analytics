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

    def _create_bronze_pair(
        series_code: str,
        frequency: str,
        receipt_rel: str,
        raw_rel: str,
        payload_tag: str,
        request_start: str = "2021-01-01",
        request_end: str = "2026-06-30",
        downloaded_at: str = "2026-09-19T10:00:00+03:00",
    ) -> dict[str, object]:
        raw_file = root / raw_rel
        raw_file.parent.mkdir(parents=True, exist_ok=True)
        raw_payload = json.dumps(
            {
                "series_code": series_code,
                "tag": payload_tag,
                "items": [{"Tarih": "01-2021", "value": "100.0"}],
            }
        ).encode("utf-8")
        raw_file.write_bytes(raw_payload)
        raw_sha256 = hashlib.sha256(raw_payload).hexdigest()
        raw_size = len(raw_payload)

        receipt_file = root / receipt_rel
        receipt_file.parent.mkdir(parents=True, exist_ok=True)
        receipt_obj = {
            "series_code": series_code,
            "frequency": frequency,
            "request_start": request_start,
            "request_end": request_end,
            "downloaded_at": downloaded_at,
            "sha256": raw_sha256,
            "size_bytes": raw_size,
            "raw_path": raw_rel,
        }
        receipt_file.write_text(json.dumps(receipt_obj, indent=2), encoding="utf-8")

        return {
            "receipt_path": receipt_rel,
            "raw_path": raw_rel,
            "sha256": raw_sha256,
            "size_bytes": raw_size,
            "downloaded_at": downloaded_at,
            "request_start": request_start,
            "request_end": request_end,
        }

    b_ktf_1 = _create_bronze_pair(
        "TP.KTF12",
        "weekly",
        "bronze/evds/tp_ktf12/receipts/1.json",
        "bronze/evds/tp_ktf12/raw/1.json",
        "ktf12_part1",
    )
    b_ktf_2 = _create_bronze_pair(
        "TP.KTF12",
        "weekly",
        "bronze/evds/tp_ktf12/receipts/2.json",
        "bronze/evds/tp_ktf12/raw/2.json",
        "ktf12_part2",
    )
    b_cpi = _create_bronze_pair(
        "TP.TUKFIY2025.GENEL",
        "monthly",
        "bronze/evds/cpi/receipts/cpi.json",
        "bronze/evds/cpi/raw/cpi.json",
        "cpi_main",
    )
    b_kfe = _create_bronze_pair(
        "TP.KFE.TR",
        "monthly",
        "bronze/evds/kfe/receipts/kfe.json",
        "bronze/evds/kfe/raw/kfe.json",
        "kfe_main",
    )

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
                "bronze": [b_ktf_1, b_ktf_2],
                "weekly_coverage": {
                    "overall_status": "unverified",
                    "calendar_verification": "not_available",
                    "months": [
                        {
                            "period": period,
                            "status": "unverified",
                            "observed_count": 4,
                            "expected_count": None,
                            "observed_dates": [f"{period}-{day}" for day in ("01", "08", "15", "22")],
                            "quality_note": "No verified source publication calendar.",
                        }
                        for period in df["period"]
                    ],
                },
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
                "bronze": [b_cpi],
            },
            {
                "series_code": "TP.KFE.TR",
                "silver_columns": ["housing_price_index"],
                "unit": "index",
                "native_frequency": "monthly",
                "target_frequency": "monthly",
                "base_year": 2023,
                "base_year_source": "tcmb",
                "transformation": "level",
                "bronze": [b_kfe],
            },
        ],
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


def test_missing_raw_file(mock_project):
    root, manifest_path = mock_project
    (root / "bronze" / "evds" / "tp_ktf12" / "raw" / "1.json").unlink()

    with pytest.raises(ManifestValidationError, match="Bronze raw file declared in manifest not found"):
        load_and_validate_manifest(manifest_path, root)


def test_modified_raw_file_size(mock_project):
    root, manifest_path = mock_project
    raw_file = root / "bronze" / "evds" / "tp_ktf12" / "raw" / "1.json"
    raw_file.write_text('{"tampered": true}', encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Bronze raw file size mismatch"):
        load_and_validate_manifest(manifest_path, root)


def test_modified_raw_file_sha256_same_size(mock_project):
    root, manifest_path = mock_project
    raw_file = root / "bronze" / "evds" / "tp_ktf12" / "raw" / "1.json"
    original = raw_file.read_bytes()
    mutated = bytearray(original)
    mutated[-2] = ord("X") if mutated[-2] != ord("X") else ord("Y")
    raw_file.write_bytes(bytes(mutated))

    with pytest.raises(ManifestValidationError, match="Bronze raw file SHA-256 mismatch"):
        load_and_validate_manifest(manifest_path, root)


def test_invalid_receipt_json(mock_project):
    root, manifest_path = mock_project
    receipt_file = root / "bronze" / "evds" / "tp_ktf12" / "receipts" / "1.json"
    receipt_file.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Invalid JSON in bronze receipt"):
        load_and_validate_manifest(manifest_path, root)


def test_receipt_missing_required_fields(mock_project):
    root, manifest_path = mock_project
    receipt_file = root / "bronze" / "evds" / "tp_ktf12" / "receipts" / "1.json"
    receipt_file.write_text("{}", encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="missing required fields"):
        load_and_validate_manifest(manifest_path, root)


def test_receipt_sha256_mismatch(mock_project):
    root, manifest_path = mock_project
    receipt_file = root / "bronze" / "evds" / "tp_ktf12" / "receipts" / "1.json"
    receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    receipt_data["sha256"] = "f" * 64
    receipt_file.write_text(json.dumps(receipt_data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="sha256 .* does not match manifest sha256"):
        load_and_validate_manifest(manifest_path, root)


def test_receipt_size_bytes_mismatch(mock_project):
    root, manifest_path = mock_project
    receipt_file = root / "bronze" / "evds" / "tp_ktf12" / "receipts" / "1.json"
    receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    receipt_data["size_bytes"] = 99999
    receipt_file.write_text(json.dumps(receipt_data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="size_bytes .* does not match manifest size_bytes"):
        load_and_validate_manifest(manifest_path, root)


def test_receipt_series_code_mismatch(mock_project):
    root, manifest_path = mock_project
    receipt_file = root / "bronze" / "evds" / "tp_ktf12" / "receipts" / "1.json"
    receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    receipt_data["series_code"] = "TP.KFE.TR"
    receipt_file.write_text(json.dumps(receipt_data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="series_code .* does not match manifest series"):
        load_and_validate_manifest(manifest_path, root)


def test_receipt_frequency_mismatch(mock_project):
    root, manifest_path = mock_project
    receipt_file = root / "bronze" / "evds" / "tp_ktf12" / "receipts" / "1.json"
    receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    receipt_data["frequency"] = "monthly"
    receipt_file.write_text(json.dumps(receipt_data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="frequency .* does not match series native_frequency"):
        load_and_validate_manifest(manifest_path, root)


def test_receipt_request_range_mismatch(mock_project):
    root, manifest_path = mock_project
    receipt_file = root / "bronze" / "evds" / "tp_ktf12" / "receipts" / "1.json"
    receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    receipt_data["request_start"] = "2022-01-01"
    receipt_file.write_text(json.dumps(receipt_data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="request range .* does not match manifest"):
        load_and_validate_manifest(manifest_path, root)


def test_receipt_raw_path_mismatch(mock_project):
    root, manifest_path = mock_project
    receipt_file = root / "bronze" / "evds" / "tp_ktf12" / "receipts" / "1.json"
    receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    receipt_data["raw_path"] = "bronze/evds/tp_ktf12/raw/other.json"
    receipt_file.write_text(json.dumps(receipt_data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="raw_path .* does not resolve to manifest raw_path"):
        load_and_validate_manifest(manifest_path, root)


def test_duplicate_series_rejected(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["series"].append(dict(data["series"][0]))
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="duplicate series declarations"):
        load_and_validate_manifest(manifest_path, root)


def test_cpi_wrong_base_year_rejected(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for s in data["series"]:
        if s["series_code"] == "TP.TUKFIY2025.GENEL":
            s["base_year"] = 2020
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Series TP.TUKFIY2025.GENEL base_year must be 2025"):
        load_and_validate_manifest(manifest_path, root)


def test_kfe_wrong_base_year_rejected(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for s in data["series"]:
        if s["series_code"] == "TP.KFE.TR":
            s["base_year"] = 2017
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Series TP.KFE.TR base_year must be 2023"):
        load_and_validate_manifest(manifest_path, root)


def test_interest_rate_wrong_unit_rejected(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["series"][0]["unit"] = "USD"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Series TP.KTF12 unit must be 'percent'"):
        load_and_validate_manifest(manifest_path, root)


def test_wrong_target_frequency_rejected(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["series"][0]["target_frequency"] = "yearly"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Series TP.KTF12 target_frequency must be 'monthly'"):
        load_and_validate_manifest(manifest_path, root)


def test_wrong_native_frequency_rejected(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["series"][0]["native_frequency"] = "monthly"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Series TP.KTF12 native_frequency must be 'weekly'"):
        load_and_validate_manifest(manifest_path, root)


def test_interest_rate_wrong_transformation_rejected(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["series"][0]["transformation"] = "sum"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Series TP.KTF12 has invalid transformation"):
        load_and_validate_manifest(manifest_path, root)


def test_wrong_silver_column_mapping_rejected(mock_project):
    root, manifest_path = mock_project
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["series"][0]["silver_columns"] = ["housing_price_index"]
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ManifestValidationError, match="Series TP.KTF12 silver_columns must be"):
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

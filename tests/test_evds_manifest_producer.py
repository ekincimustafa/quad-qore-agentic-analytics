import hashlib
import json
from pathlib import Path

import pytest

from app.lakehouse.evds_manifest_producer import (
    build_bronze_manifest_entry,
    build_evds_manifest,
    build_silver_manifest_entry,
    build_weekly_coverage_manifest_entry,
    normalize_receipt_raw_path,
    repo_relative_data_path,
)


def test_manifest_paths_are_relative_to_repository(tmp_path):
    project_root = tmp_path / "project"
    data_root = project_root / "data"

    bronze_dir = data_root / "bronze" / "evds" / "tp_ktf12"
    receipts_dir = bronze_dir / "receipts"

    receipts_dir.mkdir(parents=True)

    raw = bronze_dir / "raw.json"
    receipt = receipts_dir / "receipt.json"

    raw.write_text("{}", encoding="utf-8")
    receipt.write_text("{}", encoding="utf-8")

    assert repo_relative_data_path(
        raw,
        project_root=project_root,
        data_root=data_root,
    ) == "data/bronze/evds/tp_ktf12/raw.json"

    assert repo_relative_data_path(
        receipt,
        project_root=project_root,
        data_root=data_root,
    ) == "data/bronze/evds/tp_ktf12/receipts/receipt.json"


def test_manifest_rejects_path_outside_data_root(tmp_path):
    project_root = tmp_path / "project"
    data_root = project_root / "data"

    data_root.mkdir(parents=True)

    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        repo_relative_data_path(
            outside,
            project_root=project_root,
            data_root=data_root,
        )

def test_receipt_raw_path_is_normalized(tmp_path):
    project_root = tmp_path / "project"
    data_root = project_root / "data"

    raw_dir = data_root / "bronze" / "evds" / "tp_ktf12"
    raw_dir.mkdir(parents=True)

    raw_file = raw_dir / "raw.json"
    raw_file.write_text("{}", encoding="utf-8")

    result = normalize_receipt_raw_path(
        "bronze/evds/tp_ktf12/raw.json",
        project_root=project_root,
        data_root=data_root,
    )

    assert result == "data/bronze/evds/tp_ktf12/raw.json"


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside.json",
        "/tmp/outside.json",
        "data/bronze/evds/raw.json",
        "bronze/../outside.json",
    ],
)
def test_receipt_raw_path_rejects_unsafe_paths(
    tmp_path,
    unsafe_path,
):
    project_root = tmp_path / "project"
    data_root = project_root / "data"
    data_root.mkdir(parents=True)

    with pytest.raises(ValueError):
        normalize_receipt_raw_path(
            unsafe_path,
            project_root=project_root,
            data_root=data_root,
        )

def test_manifest_receipt_matches_selected_raw(tmp_path):
    project_root = tmp_path / "project"
    data_root = project_root / "data"

    bronze_dir = (
        data_root / "bronze" / "evds" / "tp_ktf12"
    )
    receipts_dir = bronze_dir / "receipts"
    receipts_dir.mkdir(parents=True)

    raw_file = bronze_dir / "raw.json"
    raw_bytes = b'{"items": []}'
    raw_file.write_bytes(raw_bytes)

    digest = hashlib.sha256(raw_bytes).hexdigest()

    receipt_file = receipts_dir / "receipt.json"

    receipt = {
        "series_code": "TP.KTF12",
        "frequency": "weekly",
        "request_start": "2021-01-01",
        "request_end": "2021-02-28",
        "downloaded_at": "2026-09-16T18:00:00+00:00",
        "raw_path": "bronze/evds/tp_ktf12/raw.json",
        "sha256": digest,
        "size_bytes": len(raw_bytes),
    }

    receipt_file.write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    result = build_bronze_manifest_entry(
        selected_raw_path=raw_file,
        series_code="TP.KTF12",
        request_start="2021-01-01",
        request_end="2021-02-28",
        project_root=project_root,
        data_root=data_root,
    )

    assert result == {
        "receipt_path": (
            "data/bronze/evds/tp_ktf12/receipts/receipt.json"
        ),
        "raw_path": "data/bronze/evds/tp_ktf12/raw.json",
        "sha256": digest,
        "size_bytes": len(raw_bytes),
        "downloaded_at": "2026-09-16T18:00:00+00:00",
        "request_start": "2021-01-01",
        "request_end": "2021-02-28",
    }


@pytest.mark.parametrize(
    "field,bad_value,expected_error",
    [
        (
            "sha256",
            "0" * 64,
            "EVDS Bronze integrity mismatch",
        ),
        (
            "size_bytes",
            999,
            "EVDS Bronze integrity mismatch",
        ),
        (
            "downloaded_at",
            "2026-09-16T18:00:00",
            "Invalid receipt timestamp",
        ),
    ],
)
def test_manifest_rejects_invalid_bronze_receipt(
    tmp_path,
    field,
    bad_value,
    expected_error,
):
    project_root = tmp_path / "project"
    data_root = project_root / "data"

    bronze_dir = (
        data_root / "bronze" / "evds" / "tp_ktf12"
    )
    receipts_dir = bronze_dir / "receipts"
    receipts_dir.mkdir(parents=True)

    raw_file = bronze_dir / "raw.json"
    raw_bytes = b'{"items": []}'
    raw_file.write_bytes(raw_bytes)

    receipt = {
        "series_code": "TP.KTF12",
        "frequency": "weekly",
        "request_start": "2021-01-01",
        "request_end": "2021-02-28",
        "downloaded_at": "2026-09-16T18:00:00+00:00",
        "raw_path": "bronze/evds/tp_ktf12/raw.json",
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "size_bytes": len(raw_bytes),
    }

    # Test edilen alanı bilerek bozuyoruz.
    receipt[field] = bad_value

    receipt_file = receipts_dir / "receipt.json"
    receipt_file.write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=expected_error):
        build_bronze_manifest_entry(
            selected_raw_path=raw_file,
            series_code="TP.KTF12",
            request_start="2021-01-01",
            request_end="2021-02-28",
            project_root=project_root,
            data_root=data_root,
        )

def test_manifest_selects_latest_receipt_by_utc_time(tmp_path):
    project_root = tmp_path / "project"
    data_root = project_root / "data"

    bronze_dir = data_root / "bronze" / "evds" / "tp_ktf12"
    receipts_dir = bronze_dir / "receipts"
    receipts_dir.mkdir(parents=True)

    old_raw = bronze_dir / "old.json"
    new_raw = bronze_dir / "new.json"

    old_raw.write_bytes(b'{"items": [1]}')
    new_raw.write_bytes(b'{"items": [2]}')

    def create_receipt(raw_file, filename, downloaded_at):
        receipt = {
            "series_code": "TP.KTF12",
            "frequency": "weekly",
            "request_start": "2021-01-01",
            "request_end": "2021-02-28",
            "downloaded_at": downloaded_at,
            "raw_path": (
                f"bronze/evds/tp_ktf12/{raw_file.name}"
            ),
            "sha256": hashlib.sha256(
                raw_file.read_bytes()
            ).hexdigest(),
            "size_bytes": raw_file.stat().st_size,
        }

        (receipts_dir / filename).write_text(
            json.dumps(receipt),
            encoding="utf-8",
        )

    # UTC 07:00 - daha eski
    create_receipt(
        old_raw,
        "z-old.json",
        "2026-10-02T10:00:00+03:00",
    )

    # UTC 08:00 - daha yeni
    create_receipt(
        new_raw,
        "a-new.json",
        "2026-10-02T08:00:00Z",
    )

    result = build_bronze_manifest_entry(
        selected_raw_path=new_raw,
        series_code="TP.KTF12",
        request_start="2021-01-01",
        request_end="2021-02-28",
        project_root=project_root,
        data_root=data_root,
    )

    assert result["receipt_path"].endswith(
        "/receipts/a-new.json"
    )
    assert result["raw_path"].endswith("/new.json")

    # Eski dosya yanlışlıkla seçilirse reddedilmeli.
    with pytest.raises(
        ValueError,
        match="does not match the latest",
    ):
        build_bronze_manifest_entry(
            selected_raw_path=old_raw,
            series_code="TP.KTF12",
            request_start="2021-01-01",
            request_end="2021-02-28",
            project_root=project_root,
            data_root=data_root,
        )

def test_silver_manifest_entry_matches_actual_csv(tmp_path):
    project_root = tmp_path / "project"
    data_root = project_root / "data"

    silver_dir = data_root / "silver" / "evds" / "monthly"
    silver_dir.mkdir(parents=True)

    silver_file = silver_dir / "evds_monthly.csv"

    silver_file.write_text(
        "period,housing_loan_interest_rate_pct,"
        "weekly_observation_count,cpi_index,"
        "housing_price_index\n"
        "2021-01,15.0,2,100.0,200.0\n"
        "2021-02,16.0,2,101.0,201.0\n",
        encoding="utf-8",
    )

    result = build_silver_manifest_entry(
        silver_path=silver_file,
        project_root=project_root,
        data_root=data_root,
    )

    assert result == {
        "path": "data/silver/evds/monthly/evds_monthly.csv",
        "sha256": hashlib.sha256(
            silver_file.read_bytes()
        ).hexdigest(),
        "size_bytes": silver_file.stat().st_size,
        "row_count": 2,
        "start_period": "2021-01",
        "end_period": "2021-02",
        "columns": [
            "period",
            "housing_loan_interest_rate_pct",
            "weekly_observation_count",
            "cpi_index",
            "housing_price_index",
        ],
    }

def test_full_manifest_combines_three_evds_series(tmp_path):
    project_root = tmp_path / "project"
    data_root = project_root / "data"

    silver_dir = data_root / "silver" / "evds" / "monthly"
    silver_dir.mkdir(parents=True)

    silver_file = silver_dir / "evds_monthly.csv"
    silver_file.write_text(
        "period,housing_loan_interest_rate_pct,"
        "weekly_observation_count,cpi_index,"
        "housing_price_index\n"
        "2021-01,15.0,2,100.0,200.0\n",
        encoding="utf-8",
    )
    coverage_file = silver_file.with_suffix(".coverage.json")

    coverage_report = {
        "schema_version": "1.0",
        "silver_sha256": hashlib.sha256(
            silver_file.read_bytes()
        ).hexdigest(),
        "overall_status": "unverified",
        "calendar_verification": "not_available",
        "months": [
            {
                "period": "2021-01",
                "status": "unverified",
                "observed_count": 2,
                "expected_count": None,
                "observed_dates": [
                    "2021-01-01",
                    "2021-01-15",
                ],
                "quality_note": (
                    "Weekly coverage cannot be confirmed "
                    "without a verified source publication calendar."
                ),
            }
        ],
    }

    coverage_file.write_text(
        json.dumps(coverage_report),
        encoding="utf-8",
    )


    series_config = {
        "TP.KTF12": (
            "tp_ktf12",
            "weekly",
            ["housing_loan_interest_rate_pct",
             "weekly_observation_count"],
        ),
        "TP.TUKFIY2025.GENEL": (
            "tp_tukfiy2025_genel",
            "monthly",
            ["cpi_index"],
        ),
        "TP.KFE.TR": (
            "tp_kfe_tr",
            "monthly",
            ["housing_price_index"],
        ),
    }

    selected_raw_paths = {}
    series_metadata = {}

    for code, (dataset, frequency, columns) in series_config.items():
        bronze_dir = data_root / "bronze" / "evds" / dataset
        receipts_dir = bronze_dir / "receipts"
        receipts_dir.mkdir(parents=True)

        raw_file = bronze_dir / "raw.json"
        raw_file.write_bytes(b'{"items": []}')

        receipt = {
            "series_code": code,
            "frequency": frequency,
            "request_start": "2021-01-01",
            "request_end": "2021-01-31",
            "downloaded_at": "2026-09-16T18:00:00Z",
            "raw_path": f"bronze/evds/{dataset}/raw.json",
            "sha256": hashlib.sha256(
                raw_file.read_bytes()
            ).hexdigest(),
            "size_bytes": raw_file.stat().st_size,
        }

        (receipts_dir / "receipt.json").write_text(
            json.dumps(receipt),
            encoding="utf-8",
        )

        selected_raw_paths[code] = raw_file

        series_metadata[code] = {
            "silver_columns": columns,
            "unit": (
                "percent" if code == "TP.KTF12" else "index"
            ),
            "native_frequency": frequency,
            "target_frequency": "monthly",
            "base_year": {
                "TP.KTF12": None,
                "TP.TUKFIY2025.GENEL": 2025,
                "TP.KFE.TR": 2023,
            }[code],
            "base_year_source": (
                "not_applicable"
                if code == "TP.KTF12"
                else "tcmb"
            ),
            "transformation": (
                "mean" if code == "TP.KTF12" else "level"
            ),
        }

    manifest = build_evds_manifest(
        silver_path=silver_file,
        selected_raw_paths=selected_raw_paths,
        series_metadata=series_metadata,
        request_start="2021-01-01",
        request_end="2021-01-31",
        project_root=project_root,
        data_root=data_root,
    )

    assert manifest["schema_version"] == "1.0"
    assert manifest["silver"]["row_count"] == 1
    assert len(manifest["series"]) == 3

    assert {
        item["series_code"] for item in manifest["series"]
    } == set(series_config)

    for item in manifest["series"]:
        assert len(item["bronze"]) == 1

        bronze = item["bronze"][0]

        assert bronze["receipt_path"].startswith("data/bronze/")
        assert bronze["raw_path"].startswith("data/bronze/")
        assert bronze["request_start"] == "2021-01-01"

    series_by_code = {
        item["series_code"]: item
        for item in manifest["series"]
    }

    rate_series = series_by_code["TP.KTF12"]

    assert "weekly_coverage" in rate_series

    coverage = rate_series["weekly_coverage"]

    assert coverage["overall_status"] == "unverified"
    assert coverage["calendar_verification"] == "not_available"
    assert len(coverage["months"]) == 1
    assert coverage["months"][0]["observed_count"] == 2

    assert "silver_sha256" not in coverage
    assert "schema_version" not in coverage

    assert "weekly_coverage" not in series_by_code[
        "TP.TUKFIY2025.GENEL"
    ]
    assert "weekly_coverage" not in series_by_code[
        "TP.KFE.TR"
    ]

def test_weekly_coverage_manifest_excludes_report_metadata(tmp_path):
    silver_file = tmp_path / "silver.csv"

    silver_file.write_text(
        "period,housing_loan_interest_rate_pct,"
        "weekly_observation_count,cpi_index,"
        "housing_price_index\n"
        "2021-01,15.0,2,100.0,200.0\n"
        "2021-02,16.0,2,101.0,201.0\n",
        encoding="utf-8",
    )

    note = (
        "Weekly coverage cannot be confirmed without "
        "a verified source publication calendar."
    )

    months = [
        {
            "period": "2021-01",
            "status": "unverified",
            "observed_count": 2,
            "expected_count": None,
            "observed_dates": [
                "2021-01-01",
                "2021-01-15",
            ],
            "quality_note": note,
        },
        {
            "period": "2021-02",
            "status": "unverified",
            "observed_count": 2,
            "expected_count": None,
            "observed_dates": [
                "2021-02-05",
                "2021-02-19",
            ],
            "quality_note": note,
        },
    ]

    report = {
        "schema_version": "1.0",
        "silver_sha256": hashlib.sha256(
            silver_file.read_bytes()
        ).hexdigest(),
        "overall_status": "unverified",
        "calendar_verification": "not_available",
        "months": months,
    }

    report_file = tmp_path / "silver.coverage.json"

    report_file.write_text(
        json.dumps(report),
        encoding="utf-8",
    )

    result = build_weekly_coverage_manifest_entry(
        coverage_path=report_file,
        silver_path=silver_file,
    )

    assert set(result) == {
        "overall_status",
        "calendar_verification",
        "months",
    }

    assert result["overall_status"] == "unverified"
    assert result["calendar_verification"] == "not_available"
    assert result["months"] == months

def test_shared_fixture_has_valid_physical_provenance():
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "evds_manifest_v1"
    )

    data_root = fixture_root / "data"

    manifest_path = (
        data_root
        / "silver"
        / "evds"
        / "monthly"
        / "manifest.json"
    )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    assert manifest["schema_version"] == "1.0"
    assert manifest["dataset"] == "evds_monthly_silver"

    # Silver dosyasını gerçek içerikle karşılaştır.
    silver = manifest["silver"]
    silver_path = fixture_root / silver["path"]

    verified_silver = build_silver_manifest_entry(
        silver_path=silver_path,
        project_root=fixture_root,
        data_root=data_root,
    )

    assert silver == verified_silver
    assert silver["row_count"] == 2
    assert silver["start_period"] == "2021-01"
    assert silver["end_period"] == "2021-02"

    # Üç seri bulunmalı.
    series_by_code = {
        item["series_code"]: item
        for item in manifest["series"]
    }

    assert set(series_by_code) == {
        "TP.KTF12",
        "TP.TUKFIY2025.GENEL",
        "TP.KFE.TR",
    }

    # Bronze makbuzları ve ham dosyalar doğrulanmalı.
    for series_code, series in series_by_code.items():
        assert len(series["bronze"]) == 1

        bronze = series["bronze"][0]

        verified_bronze = build_bronze_manifest_entry(
            selected_raw_path=fixture_root / bronze["raw_path"],
            series_code=series_code,
            request_start=bronze["request_start"],
            request_end=bronze["request_end"],
            project_root=fixture_root,
            data_root=data_root,
        )

        assert bronze == verified_bronze

    # Haftalık kapsam yalnızca TP.KTF12 altında olmalı.
    rate = series_by_code["TP.KTF12"]

    verified_coverage = build_weekly_coverage_manifest_entry(
        coverage_path=silver_path.with_suffix(".coverage.json"),
        silver_path=silver_path,
    )

    assert rate["weekly_coverage"] == verified_coverage

    assert "weekly_coverage" not in series_by_code[
        "TP.TUKFIY2025.GENEL"
    ]
    assert "weekly_coverage" not in series_by_code[
        "TP.KFE.TR"
    ]

@pytest.mark.parametrize(
    "series_code,field,bad_value,expected_error",
    [
        (
            "TP.TUKFIY2025.GENEL",
            "unit",
            "USD",
            "Invalid unit",
        ),
        (
            "TP.TUKFIY2025.GENEL",
            "base_year",
            2020,
            "Invalid base year",
        ),
        (
            "TP.KFE.TR",
            "base_year",
            2025,
            "Invalid base year",
        ),
        (
            "TP.KTF12",
            "base_year",
            2020,
            "Invalid base year",
        ),
        (
            "TP.KTF12",
            "transformation",
            "sum",
            "Invalid transformation",
        ),
        (
            "TP.KFE.TR",
            "base_year_source",
            "unknown",
            "Invalid base year source",
        ),
    ],
)
def test_manifest_rejects_invalid_series_metadata(
    series_code,
    field,
    bad_value,
    expected_error,
):
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "evds_manifest_v1"
    )
    data_root = fixture_root / "data"

    manifest_path = (
        data_root
        / "silver"
        / "evds"
        / "monthly"
        / "manifest.json"
    )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    silver_path = fixture_root / manifest["silver"]["path"]

    metadata_fields = (
        "silver_columns",
        "unit",
        "native_frequency",
        "target_frequency",
        "base_year",
        "base_year_source",
        "transformation",
    )

    series_metadata = {
        item["series_code"]: {
            key: item[key] for key in metadata_fields
        }
        for item in manifest["series"]
    }

    selected_raw_paths = {
        item["series_code"]: (
            fixture_root / item["bronze"][0]["raw_path"]
        )
        for item in manifest["series"]
    }

    # Testte yalnızca tek bir metadata alanını boz.
    series_metadata[series_code][field] = bad_value

    receipt = manifest["series"][0]["bronze"][0]

    with pytest.raises(ValueError, match=expected_error):
        build_evds_manifest(
            silver_path=silver_path,
            selected_raw_paths=selected_raw_paths,
            series_metadata=series_metadata,
            request_start=receipt["request_start"],
            request_end=receipt["request_end"],
            project_root=fixture_root,
            data_root=data_root,
        )

def test_manifest_resolves_relative_silver_path_from_project_root(
    tmp_path,
    monkeypatch,
):
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "evds_manifest_v1"
    )

    manifest_path = (
        fixture_root
        / "data/silver/evds/monthly/manifest.json"
    )

    expected = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    metadata_fields = (
        "silver_columns",
        "unit",
        "native_frequency",
        "target_frequency",
        "base_year",
        "base_year_source",
        "transformation",
    )

    series_metadata = {
        series["series_code"]: {
            field: series[field]
            for field in metadata_fields
        }
        for series in expected["series"]
    }

    selected_raw_paths = {
        series["series_code"]: (
            fixture_root / series["bronze"][0]["raw_path"]
        )
        for series in expected["series"]
    }

    receipt = expected["series"][0]["bronze"][0]

    relative_silver = expected["silver"]["path"]
    absolute_silver = fixture_root / relative_silver

    # Terminalin proje klasörü dışında olduğunu taklit et.
    monkeypatch.chdir(tmp_path)

    def generate_manifest(silver_path):
        return build_evds_manifest(
            silver_path=silver_path,
            selected_raw_paths=selected_raw_paths,
            series_metadata=series_metadata,
            request_start=receipt["request_start"],
            request_end=receipt["request_end"],
            project_root=fixture_root,
            data_root=fixture_root / "data",
        )

    relative_result = generate_manifest(relative_silver)
    absolute_result = generate_manifest(absolute_silver)

    # Göreli ve mutlak yollar aynı sonucu vermeli.
    assert relative_result == absolute_result

    # Fiziksel CSV ve kapsam bilgileri doğru kalmalı.
    assert relative_result["silver"] == expected["silver"]

    rate_series = next(
        series
        for series in relative_result["series"]
        if series["series_code"] == "TP.KTF12"
    )

    assert len(rate_series["weekly_coverage"]["months"]) == 2
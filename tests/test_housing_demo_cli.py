"""E2E tests for the offline housing demo CLI."""

import json
from pathlib import Path

import pandas as pd
import pytest

from app.lakehouse.gold import build_housing_gold_table, find_rate_down_real_credit_not_up
from scripts.run_housing_demo import main


@pytest.fixture
def synthetic_66_months(tmp_path: Path) -> tuple[Path, Path, Path]:
    bddk_path = tmp_path / "bddk.parquet"
    evds_path = tmp_path / "evds.csv"
    manifest_path = tmp_path / "manifest.json"

    periods = pd.period_range(start="2021-01", end="2026-06", freq="M").astype(str).tolist()

    # BDDK
    bddk_df = pd.DataFrame({
        "period": periods,
        "housing_loan_amount": [100.0 + i for i in range(66)],
        "housing_loan_unit": ["Milyon TL" for _ in range(66)],
        "nominal_housing_loan_mn_try": [100.0 + i for i in range(66)],
        "bddk_source_ref": [f"req_{i}" for i in range(66)],
        "data_quality_note": ["ok" for _ in range(66)]
    })
    bddk_df.to_parquet(bddk_path, index=False)

    # EVDS
    evds_df = pd.DataFrame({
        "period": periods,
        "housing_loan_interest_rate_pct": [10.0 - (i % 2) for i in range(66)], # oscillates to trigger condition sometimes
        "weekly_observation_count": [4 for _ in range(66)],
        "cpi_index": [100.0 + (i*2) for i in range(66)], # monotonically increasing CPI
        "housing_price_index": [100.0 + i for i in range(66)]
    })
    evds_df.to_csv(evds_path, index=False)

    # Physical receipt files
    r1 = tmp_path / "bronze" / "1.json"
    r2 = tmp_path / "bronze" / "2.json"
    r3 = tmp_path / "bronze" / "3.json"
    for r in (r1, r2, r3):
        r.parent.mkdir(parents=True, exist_ok=True)
        r.write_text("{}", encoding="utf-8")

    # Manifest
    import hashlib
    sha256 = hashlib.sha256(evds_path.read_bytes()).hexdigest()
    manifest_data = {
        "schema_version": "1.0",
        "dataset": "evds_monthly_silver",
        "silver": {
            "path": evds_path.name, # Assuming script will resolve relative to cwd, so we run from tmp_path
            "sha256": sha256,
            "size_bytes": len(evds_path.read_bytes()),
            "row_count": 66,
            "start_period": "2021-01",
            "end_period": "2026-06",
            "columns": list(evds_df.columns)
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
                        "receipt_path": "bronze/1.json",
                        "raw_path": "bronze/raw_1.json",
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
                        "receipt_path": "bronze/2.json",
                        "raw_path": "bronze/raw_2.json",
                        "sha256": "abcdef",
                        "size_bytes": 100,
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
                        "receipt_path": "bronze/3.json",
                        "raw_path": "bronze/raw_3.json",
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
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    return bddk_path, evds_path, manifest_path


def test_cli_e2e_success_and_66_to_60_slice(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    monkeypatch.chdir(tmp_path)

    argv = [
        "--bddk-silver", str(bddk),
        "--evds-silver", str(evds),
        "--evds-manifest", str(manifest),
        "--start-period", "2021-01",
        "--end-period", "2025-12",
        "--output-dir", str(out_dir)
    ]

    assert main(argv) == 0

    assert out_dir.is_dir()
    evidence = json.loads((out_dir / "evidence.json").read_text(encoding="utf-8"))

    assert evidence["observed_month_count"] == 60
    assert evidence["period_start"] == "2021-01"
    assert evidence["period_end"] == "2025-12"

    # Validate mathematical equivalence directly with gold
    bddk_df = pd.read_parquet(bddk)
    evds_df = pd.read_csv(evds)
    gold = build_housing_gold_table(
        bddk_df, evds_df,
        start_period="2021-01", end_period="2025-12",
        evds_source_refs="bronze/1.json"
    )
    matches = find_rate_down_real_credit_not_up(gold)

    assert evidence["matched_month_count"] == len(matches)


def test_cli_determinism(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out1 = tmp_path / "out1"
    out2 = tmp_path / "out2"

    monkeypatch.chdir(tmp_path)

    argv1 = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest),
        "--start-period", "2021-01", "--end-period", "2025-12",
        "--output-dir", str(out1)
    ]
    assert main(argv1) == 0

    argv2 = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest),
        "--start-period", "2021-01", "--end-period", "2025-12",
        "--output-dir", str(out2)
    ]
    assert main(argv2) == 0

    for fname in ["evidence.json", "chart.json", "run_summary.json"]:
        assert (out1 / fname).read_bytes() == (out2 / fname).read_bytes()


def test_cli_error_missing_args(synthetic_66_months):
    bddk, evds, manifest = synthetic_66_months
    # Missing required --output-dir and --evds-manifest
    argv = ["--bddk-silver", str(bddk)]
    assert main(argv) == 2


def test_cli_error_invalid_silver(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    # Corrupt BDDK
    bddk.write_text("not a parquet")

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest),
        "--output-dir", str(out_dir)
    ]
    assert main(argv) == 1
    assert not out_dir.exists() # atomic failure


import socket

@pytest.fixture(autouse=True)
def disable_network():
    def guard(*args, **kwargs):
        raise RuntimeError("Network access disabled during tests")
    original_socket = socket.socket
    socket.socket = guard
    yield
    socket.socket = original_socket


def test_cli_error_missing_bddk_month(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    # Remove one month from BDDK
    df = pd.read_parquet(bddk)
    df = df[df["period"] != "2021-02"]
    df.to_parquet(bddk, index=False)

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir)
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_duplicate_bddk_month(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    # Duplicate one month in BDDK
    df = pd.read_parquet(bddk)
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
    df.to_parquet(bddk, index=False)

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir)
    ]
    assert main(argv) == 1
    assert not out_dir.exists()

def test_cli_error_missing_evds_month(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    # Remove one month from EVDS (this will cause row count mismatch first)
    df = pd.read_csv(evds)
    df = df[df["period"] != "2021-02"]
    df.to_csv(evds, index=False)

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir)
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_missing_files(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    bddk.unlink() # dosya yok

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir)
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_invalid_manifest_json(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    manifest.write_text("{invalid json", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir)
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_hash_mismatch(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    # Modify CSV to change hash but keep row count
    df = pd.read_csv(evds)
    df.loc[0, "cpi_index"] += 1.0
    df.to_csv(evds, index=False)

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir)
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_bddk_unit_mismatch(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    df = pd.read_parquet(bddk)
    df.loc[0, "housing_loan_unit"] = "Bin TL"
    df.to_parquet(bddk, index=False)

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir)
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_bddk_ref_missing(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    df = pd.read_parquet(bddk)
    df.loc[0, "bddk_source_ref"] = "None"
    df.to_parquet(bddk, index=False)

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir)
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_reverse_period(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest),
        "--start-period", "2025-12", "--end-period", "2021-01", # reversed
        "--output-dir", str(out_dir)
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_out_of_bounds_period(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest),
        "--start-period", "2020-01", # not in dataset
        "--end-period", "2025-12",
        "--output-dir", str(out_dir)
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_evds_silver_path_mismatch_with_manifest(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    # Create another CSV file and pass it as --evds-silver
    other_evds = tmp_path / "other_evds.csv"
    other_evds.write_text(evds.read_text(), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk),
        "--evds-silver", str(other_evds),  # does not match manifest declared path
        "--evds-manifest", str(manifest),
        "--output-dir", str(out_dir),
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_preserves_existing_output_byte_for_byte_on_publish_error(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir),
    ]

    # 1. Run successfully once
    assert main(argv) == 0
    assert out_dir.exists()

    # Record byte contents of the successful run
    initial_files = {p.name: p.read_bytes() for p in out_dir.iterdir()}
    assert "evidence.json" in initial_files
    assert "chart.json" in initial_files
    assert "run_summary.json" in initial_files

    # 2. Inject failure into staging_dir.rename when renaming to out_dir
    original_rename = Path.rename
    staging_name = out_dir.name + ".part"

    def fail_rename_on_staging(self, target):
        if str(self).endswith(staging_name) and str(target).endswith(out_dir.name):
            raise OSError("Simulated atomic publish failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_rename_on_staging)

    # 3. Re-run CLI with the injected failure
    assert main(argv) == 1

    # 4. Verify existing output directory is preserved byte-for-byte!
    assert out_dir.exists()
    current_files = {p.name: p.read_bytes() for p in out_dir.iterdir()}
    assert current_files == initial_files


def test_cli_catches_readback_content_tampering(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    # Intercept write_text on evidence.json to corrupt the written content
    original_write_text = Path.write_text

    def tamper_evidence_write(self, data, encoding="utf-8", errors=None):
        if self.name == "evidence.json":
            # Tamper with observation count: change 60 to 999
            tampered = data.replace('"observed_month_count": 60', '"observed_month_count": 999')
            return original_write_text(self, tampered, encoding=encoding, errors=errors)
        return original_write_text(self, data, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "write_text", tamper_evidence_write)

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir),
    ]
    # Must fail because read-back content does not equal in-memory evidence!
    assert main(argv) == 1
    assert not out_dir.exists()

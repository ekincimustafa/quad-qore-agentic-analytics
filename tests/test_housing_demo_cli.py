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

    # Physical raw files and receipt files
    import hashlib

    def _make_bronze_entry(
        series_code: str,
        frequency: str,
        receipt_rel: str,
        raw_rel: str,
    ) -> dict[str, object]:
        raw_path = tmp_path / raw_rel
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_bytes = json.dumps(
            {
                "series_code": series_code,
                "items": [{"Tarih": "01-2021", "value": "100.0"}],
            }
        ).encode("utf-8")
        raw_path.write_bytes(raw_bytes)
        raw_sha = hashlib.sha256(raw_bytes).hexdigest()
        raw_size = len(raw_bytes)

        receipt_path = tmp_path / receipt_rel
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_payload = {
            "series_code": series_code,
            "frequency": frequency,
            "request_start": "2021-01-01",
            "request_end": "2026-06-30",
            "downloaded_at": "2026-09-19T10:00:00+03:00",
            "sha256": raw_sha,
            "size_bytes": raw_size,
            "raw_path": raw_rel,
        }
        receipt_path.write_text(json.dumps(receipt_payload, indent=2), encoding="utf-8")

        return {
            "receipt_path": receipt_rel,
            "raw_path": raw_rel,
            "sha256": raw_sha,
            "size_bytes": raw_size,
            "downloaded_at": "2026-09-19T10:00:00+03:00",
            "request_start": "2021-01-01",
            "request_end": "2026-06-30",
        }

    b1 = _make_bronze_entry("TP.KTF12", "weekly", "bronze/1.json", "bronze/raw_1.json")
    b2 = _make_bronze_entry("TP.TUKFIY2025.GENEL", "monthly", "bronze/2.json", "bronze/raw_2.json")
    b3 = _make_bronze_entry("TP.KFE.TR", "monthly", "bronze/3.json", "bronze/raw_3.json")

    # Manifest
    sha256 = hashlib.sha256(evds_path.read_bytes()).hexdigest()
    manifest_data = {
        "schema_version": "1.0",
        "dataset": "evds_monthly_silver",
        "silver": {
            "path": evds_path.name,  # Assuming script will resolve relative to cwd, so we run from tmp_path
            "sha256": sha256,
            "size_bytes": len(evds_path.read_bytes()),
            "row_count": 66,
            "start_period": "2021-01",
            "end_period": "2026-06",
            "columns": list(evds_df.columns),
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
                "bronze": [b1],
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
                "bronze": [b2],
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
                "bronze": [b3],
            },
        ],
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


def test_cli_recovers_interrupted_backup_byte_for_byte_on_publish_error(
    synthetic_66_months, tmp_path, monkeypatch
):
    """If only output.backup exists from an interrupted run and staging->output fails, recover output byte-for-byte."""
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"
    backup_dir = tmp_path / "output.backup"

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir),
    ]

    # 1. Run successfully once to produce a valid output package
    assert main(argv) == 0
    assert out_dir.exists()
    initial_files = {p.name: p.read_bytes() for p in out_dir.iterdir()}

    # 2. Simulate an interrupted previous run where output was moved to output.backup and output is missing
    out_dir.rename(backup_dir)
    assert not out_dir.exists()
    assert backup_dir.exists()

    # 3. Inject failure into staging_dir.rename when renaming to out_dir
    original_rename = Path.rename
    staging_name = out_dir.name + ".part"

    def fail_rename_on_staging(self, target):
        if str(self).endswith(staging_name) and str(target).endswith(out_dir.name):
            raise OSError("Simulated atomic publish failure with existing backup")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_rename_on_staging)

    # 4. Re-run CLI with the injected failure
    assert main(argv) == 1

    # 5. Verify the surviving backup was NOT deleted and was recovered byte-for-byte!
    assert out_dir.exists()
    assert not backup_dir.exists()
    recovered_files = {p.name: p.read_bytes() for p in out_dir.iterdir()}
    assert recovered_files == initial_files


def test_cli_preserves_both_when_output_and_backup_both_exist(
    synthetic_66_months, tmp_path, monkeypatch
):
    """If both output and output.backup exist simultaneously, refuse to delete either and abort safely."""
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"
    backup_dir = tmp_path / "output.backup"

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir),
    ]

    assert main(argv) == 0
    initial_out_files = {p.name: p.read_bytes() for p in out_dir.iterdir()}

    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "sentinel.txt").write_bytes(b"precious-backup")

    assert main(argv) == 1
    assert out_dir.exists()
    assert {p.name: p.read_bytes() for p in out_dir.iterdir()} == initial_out_files
    assert backup_dir.exists()
    assert (backup_dir / "sentinel.txt").read_bytes() == b"precious-backup"


def test_cli_error_when_bronze_raw_deleted(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"
    (tmp_path / "bronze" / "raw_1.json").unlink()

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir),
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_when_bronze_raw_modified(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"
    raw_file = tmp_path / "bronze" / "raw_1.json"
    raw_file.write_text('{"corrupted": true}', encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir),
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_when_bronze_receipt_invalid_json(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"
    (tmp_path / "bronze" / "1.json").write_text("{broken json", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir),
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_cli_error_when_bronze_receipt_hash_mismatch(synthetic_66_months, tmp_path, monkeypatch):
    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"
    receipt_file = tmp_path / "bronze" / "1.json"
    receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    receipt_data["sha256"] = "0" * 64
    receipt_file.write_text(json.dumps(receipt_data), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir),
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "shorten_y",
        "mutate_x_period",
        "mutate_matched_y_to_999",
        "mutate_unmatched_y_to_999",
        "rename_marker_trace",
    ],
)
def test_cli_rejects_corrupted_chart_traces(
    synthetic_66_months, tmp_path, monkeypatch, mutation
):
    """Verify that validate_chart in run_housing_demo rejects all 4 chart corruption scenarios."""
    import app.services.housing_analysis as analysis_mod
    from app.tools.housing_chart import build_housing_chart as real_build_chart

    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output"

    def tampered_build_chart(evidence):
        chart = real_build_chart(evidence)
        dumped = json.loads(json.dumps(chart))
        if mutation == "shorten_y":
            dumped["data"][0]["y"] = dumped["data"][0]["y"][:-1]
        elif mutation == "mutate_x_period":
            dumped["data"][0]["x"][0] = "1999-01-01"
        elif mutation == "mutate_matched_y_to_999":
            for t in dumped["data"]:
                if t.get("name") == "Koşula uyan ay":
                    t["y"] = [999.0 for _ in t["y"]]
        elif mutation == "mutate_unmatched_y_to_999":
            dumped["data"][0]["y"][0] = 999.0
        elif mutation == "rename_marker_trace":
            for t in dumped["data"]:
                if t.get("name") == "Koşula uyan ay":
                    t["name"] = "Başka İsim"
        return dumped

    monkeypatch.setattr(analysis_mod, "build_housing_chart", tampered_build_chart)
    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk), "--evds-silver", str(evds),
        "--evds-manifest", str(manifest), "--output-dir", str(out_dir),
    ]
    assert main(argv) == 1
    assert not out_dir.exists()


def test_validate_chart_direct_unit_checks(synthetic_66_months):
    """Test validate_chart directly with both (chart, evidence) and legacy (chart, matched_periods, count) signatures."""
    from app.services.housing_demo import HousingDemoPaths, run_file_backed_housing_demo
    from scripts.run_housing_demo import validate_chart

    bddk, evds, _ = synthetic_66_months
    run = run_file_backed_housing_demo(
        start_period="2021-01",
        end_period="2025-12",
        paths=HousingDemoPaths(bddk_silver=bddk, evds_silver=evds),
    )

    # Valid chart passes both signatures
    validate_chart(run.chart, run.evidence)
    validate_chart(
        run.chart,
        run.evidence.matched_periods,
        run.evidence.observed_month_count,
        evidence=run.evidence,
    )
    validate_chart(
        run.chart,
        run.evidence.matched_periods,
        run.evidence.observed_month_count,
    )

    # 1. Shortened y array
    c1 = json.loads(json.dumps(run.chart))
    c1["data"][0]["y"] = c1["data"][0]["y"][:-1]
    with pytest.raises(RuntimeError, match="x/y length mismatch"):
        validate_chart(c1, run.evidence)
    with pytest.raises(RuntimeError, match="x/y length mismatch"):
        validate_chart(c1, run.evidence.matched_periods, run.evidence.observed_month_count)

    # 2. Mutated x period to 1999-01-01
    c2 = json.loads(json.dumps(run.chart))
    c2["data"][0]["x"][0] = "1999-01-01"
    with pytest.raises(RuntimeError):
        validate_chart(c2, run.evidence)
    with pytest.raises(RuntimeError):
        validate_chart(c2, run.evidence.matched_periods, run.evidence.observed_month_count)

    # 3. Matched months' y values changed to 999
    c3 = json.loads(json.dumps(run.chart))
    for t in c3["data"]:
        if t["name"] == "Koşula uyan ay":
            t["y"] = [999.0 for _ in t["y"]]
    with pytest.raises(RuntimeError):
        validate_chart(c3, run.evidence)
    with pytest.raises(RuntimeError):
        validate_chart(c3, run.evidence.matched_periods, run.evidence.observed_month_count)

    # 4. Marker trace renamed
    c4 = json.loads(json.dumps(run.chart))
    for t in c4["data"]:
        if t["name"] == "Koşula uyan ay":
            t["name"] = "Başka İsim"
    with pytest.raises(RuntimeError, match="6 unique expected traces"):
        validate_chart(c4, run.evidence)
    with pytest.raises(RuntimeError, match="6 unique expected traces"):
        validate_chart(c4, run.evidence.matched_periods, run.evidence.observed_month_count)

    # 5. Both marker trace AND interest rate trace mutated to 999 at matched period (caught via evidence.results)
    c5 = json.loads(json.dumps(run.chart))
    matched_date = f"{run.evidence.matched_periods[0]}-01"
    for t in c5["data"]:
        if t["name"] in ("Koşula uyan ay", "Konut kredisi faizi"):
            idx = t["x"].index(matched_date)
            t["y"][idx] = 999.0
    with pytest.raises(RuntimeError, match="does not match evidence"):
        validate_chart(c5, run.evidence)


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _create_dir_link(link_path: Path, target_dir: Path) -> None:
    try:
        link_path.symlink_to(target_dir, target_is_directory=True)
    except OSError:
        import _winapi
        _winapi.CreateJunction(str(target_dir.resolve()), str(link_path))


@pytest.mark.parametrize(
    "layout",
    [
        "output_dir_is_input_dir",
        "output_dir_is_dot_cwd",
        "inputs_in_staging_part",
        "inputs_in_backup_dir",
    ],
)
def test_cli_rejects_output_staging_backup_overlapping_inputs_and_preserves_bytes(
    synthetic_66_months, tmp_path, monkeypatch, layout
):
    """[P1] All collision layouts (output, '.', .part, .backup) must exit 1 and preserve every input file byte-for-byte."""
    import shutil

    bddk_src, evds_src, manifest_src = synthetic_66_months
    work_root = tmp_path / "isolated_run"
    work_root.mkdir(parents=True, exist_ok=True)

    out_dir = work_root / "target_out"
    if layout in ("output_dir_is_input_dir", "output_dir_is_dot_cwd"):
        input_dir = out_dir
    elif layout == "inputs_in_staging_part":
        input_dir = work_root / "target_out.part"
    else:
        input_dir = work_root / "target_out.backup"

    input_dir.mkdir(parents=True, exist_ok=True)
    bddk = input_dir / bddk_src.name
    evds = input_dir / evds_src.name
    manifest = input_dir / manifest_src.name
    shutil.copy2(bddk_src, bddk)
    shutil.copy2(evds_src, evds)
    shutil.copy2(manifest_src, manifest)
    shutil.copytree(tmp_path / "bronze", input_dir / "bronze")

    before_bytes = _snapshot_tree(input_dir)
    assert len(before_bytes) == 9  # bddk, evds, manifest + 3 receipts + 3 raw files

    monkeypatch.chdir(input_dir)
    out_arg = "." if layout == "output_dir_is_dot_cwd" else str(out_dir)
    argv = [
        "--bddk-silver", str(bddk),
        "--evds-silver", str(evds),
        "--evds-manifest", str(manifest),
        "--output-dir", out_arg,
    ]
    assert main(argv) == 1
    assert input_dir.is_dir()
    after_bytes = _snapshot_tree(input_dir)
    assert after_bytes == before_bytes


@pytest.mark.parametrize("target_kind", ["out", "part", "backup"])
def test_cli_rejects_when_only_bronze_files_reside_in_output_staging_or_backup(
    synthetic_66_months, tmp_path, monkeypatch, target_kind
):
    """[P1] Even if BDDK, EVDS, and manifest are outside, having Bronze raw/receipt files inside output/.part/.backup must exit 1 and preserve bytes."""
    import hashlib
    import shutil

    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "demo_out"
    if target_kind == "out":
        hazard_dir = out_dir
    elif target_kind == "part":
        hazard_dir = tmp_path / "demo_out.part"
    else:
        hazard_dir = tmp_path / "demo_out.backup"

    bronze_dest = hazard_dir / "bronze"
    bronze_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(tmp_path / "bronze", bronze_dest)

    rel_prefix = f"{hazard_dir.name}/bronze"
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    for s_entry in manifest_data["series"]:
        for b_entry in s_entry["bronze"]:
            old_rec_name = Path(b_entry["receipt_path"]).name
            old_raw_name = Path(b_entry["raw_path"]).name
            new_rec_rel = f"{rel_prefix}/{old_rec_name}"
            new_raw_rel = f"{rel_prefix}/{old_raw_name}"
            rec_file = tmp_path / new_rec_rel
            rec_payload = json.loads(rec_file.read_text(encoding="utf-8"))
            rec_payload["raw_path"] = new_raw_rel
            rec_file.write_text(json.dumps(rec_payload, indent=2), encoding="utf-8")
            b_entry["receipt_path"] = new_rec_rel
            b_entry["raw_path"] = new_raw_rel

    manifest.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    before_hazard = _snapshot_tree(hazard_dir)
    before_bddk = bddk.read_bytes()
    before_evds = evds.read_bytes()
    before_manifest = manifest.read_bytes()

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk),
        "--evds-silver", str(evds),
        "--evds-manifest", str(manifest),
        "--output-dir", str(out_dir),
    ]
    assert main(argv) == 1
    assert _snapshot_tree(hazard_dir) == before_hazard
    assert bddk.read_bytes() == before_bddk
    assert evds.read_bytes() == before_evds
    assert manifest.read_bytes() == before_manifest


@pytest.mark.parametrize("link_mode", ["output_link_to_inputs", "staging_link_to_inputs", "backup_link_to_inputs"])
def test_cli_rejects_symlink_aliased_output_staging_backup_paths(
    synthetic_66_months, tmp_path, monkeypatch, link_mode
):
    """[P1] Symlink/junction paths resolving to the same location as inputs must exit 1 and preserve all inputs byte-for-byte."""
    bddk, evds, manifest = synthetic_66_months
    before_bytes = {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in sorted(tmp_path.rglob("*"))
        if p.is_file()
    }

    links_dir = tmp_path.parent / f"{tmp_path.name}_links_{link_mode}"
    links_dir.mkdir(parents=True, exist_ok=True)
    out_dir = links_dir / "out"

    if link_mode == "output_link_to_inputs":
        _create_dir_link(out_dir, tmp_path)
    elif link_mode == "staging_link_to_inputs":
        _create_dir_link(links_dir / "out.part", tmp_path)
    else:
        _create_dir_link(links_dir / "out.backup", tmp_path)

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk),
        "--evds-silver", str(evds),
        "--evds-manifest", str(manifest),
        "--output-dir", str(out_dir),
    ]
    assert main(argv) == 1
    after_bytes = {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in sorted(tmp_path.rglob("*"))
        if p.is_file()
    }
    assert after_bytes == before_bytes


def test_cli_html_flag_renders_and_publishes_verified_offline_report(
    synthetic_66_months, tmp_path, monkeypatch
):
    """[P2] --html generates report.html alongside the three JSON files using render_housing_report."""
    from html import unescape
    from tests.test_housing_report import _Page

    bddk, evds, manifest = synthetic_66_months
    out_dir = tmp_path / "output_html"

    monkeypatch.chdir(tmp_path)
    argv = [
        "--bddk-silver", str(bddk),
        "--evds-silver", str(evds),
        "--evds-manifest", str(manifest),
        "--start-period", "2021-01",
        "--end-period", "2025-12",
        "--output-dir", str(out_dir),
        "--html",
    ]
    assert main(argv) == 0

    for fname in ("evidence.json", "chart.json", "run_summary.json", "report.html"):
        assert (out_dir / fname).is_file(), f"Missing expected output file: {fname}"

    html = (out_dir / "report.html").read_text(encoding="utf-8")
    summary_text = (out_dir / "run_summary.json").read_text(encoding="utf-8")
    evidence_data = json.loads((out_dir / "evidence.json").read_text(encoding="utf-8"))

    page = _Page()
    page.feed(html)
    assert page.external_resources == []
    assert "Plotly.newPlot" in html
    assert "YEREL VERİ" in html
    assert "nedensellik kanıtlamaz" in html
    assert "İlk ayın önceki ay değişimleri null" in html
    assert "bronze/1.json" in html
    assert summary_text in unescape(html)
    for matched_period in evidence_data["matched_periods"]:
        assert f"<td>{matched_period}</td>" in html


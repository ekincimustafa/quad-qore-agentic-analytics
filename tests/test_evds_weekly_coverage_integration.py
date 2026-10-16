"""Shared #39 producer fixture through the #43 consumer and actual CLI.

The fixture files are copied verbatim from PR #58 commit 7515949. Invalid
variants are created only in temporary copies, never in the shared fixture.
"""
from __future__ import annotations

import hashlib
from html import unescape
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd
import pytest

from app.services.evds_manifest import (
    EvdsWeeklyCoverage,
    ManifestValidationError,
    load_and_validate_manifest,
)
from scripts.run_housing_demo import main


FIXTURE = Path(__file__).parent / "fixtures" / "evds_manifest_v1"
MANIFEST_REL = Path("data/silver/evds/monthly/manifest.json")


@pytest.fixture
def shared_project(tmp_path, monkeypatch):
    root = tmp_path / "project"
    shutil.copytree(FIXTURE, root)
    manifest_path = root / MANIFEST_REL
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    bddk = root / "bddk.parquet"
    pd.DataFrame({
        "period": ["2021-01", "2021-02"],
        "housing_loan_amount": [100.0, 101.0],
        "housing_loan_unit": ["Milyon TL", "Milyon TL"],
        "nominal_housing_loan_mn_try": [100.0, 101.0],
        "bddk_source_ref": ["synthetic_bddk_2021_01", "synthetic_bddk_2021_02"],
        "data_quality_note": ["synthetic fixture", "synthetic fixture"],
    }).to_parquet(bddk, index=False)
    monkeypatch.chdir(root)
    return root, manifest_path, payload


def cli_args(root, payload, output="output"):
    return [
        "--bddk-silver", str(root / "bddk.parquet"),
        "--evds-silver", str(root / payload["silver"]["path"]),
        "--evds-manifest", str(root / MANIFEST_REL),
        "--start-period", "2021-01", "--end-period", "2021-02",
        "--output-dir", str(root / output), "--html",
    ]


def source_bytes(root):
    return {p.relative_to(root): p.read_bytes() for p in (root / "data").rglob("*") if p.is_file()}


@pytest.mark.parametrize("monthly_null", [False, True], ids=["producer-omits-monthly", "monthly-null"])
def test_shared_fixture_consumer_and_real_cli(shared_project, monthly_null):
    root, manifest_path, payload = shared_project
    coverage = payload["series"][0]["weekly_coverage"]
    if monthly_null:
        for series in payload["series"][1:]:
            series["weekly_coverage"] = None
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    else:
        # The positive producer fixture remains byte-for-byte unchanged.
        assert source_bytes(root) == source_bytes(FIXTURE)

    before = source_bytes(root)
    manifest = load_and_validate_manifest(manifest_path, root)
    assert isinstance(manifest.series[0].weekly_coverage, EvdsWeeklyCoverage)
    assert manifest.series[0].weekly_coverage.model_dump() == coverage
    assert all(s.weekly_coverage is None for s in manifest.series[1:])

    # Exercise the real module entry point with physical inputs and --html.
    environment = dict(os.environ, PYTHONPATH=str(FIXTURE.parents[2]))
    completed = subprocess.run(
        [sys.executable, "-m", "scripts.run_housing_demo", *cli_args(root, payload)],
        cwd=root, env=environment, capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    output = root / "output"
    assert {p.name for p in output.iterdir()} == {"evidence.json", "chart.json", "run_summary.json", "report.html"}
    summary = json.loads((output / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["manifest"]["weekly_coverage"] == coverage
    assert summary["observed_month_count"] == 2
    evidence = json.loads((output / "evidence.json").read_text(encoding="utf-8"))
    assert any("weekly_coverage: unverified" in note for note in evidence["data_quality_notes"])
    for name, digest in summary["outputs"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    assert json.dumps(summary, ensure_ascii=False, indent=2) in unescape((output / "report.html").read_text(encoding="utf-8"))
    assert "Haftalık kapsam, doğrulanmış resmî yayın takvimi olmadan teyit edilemez." in (output / "report.html").read_text(encoding="utf-8")
    assert source_bytes(root) == before
    assert not (root / "output.part").exists()
    assert not (root / "output.backup").exists()


# A single invalid fixture matrix is shared by the loader and CLI checks.
INVALID_COVERAGE = [
    ("overall_status", "complete", "overall_status"),
    ("calendar_verification", "verified", "calendar_verification"),
    ("months", [], "Silver period sequence"),
    ("months", "reverse", "Silver period sequence"),
    ("months", "duplicate", "Silver period sequence"),
    ("months.0.period", "2021-03", "Silver period sequence"),
    ("months.0.period", "2021-1", "Silver period sequence"),
    ("months.0.status", "complete", "status"),
    ("months.0.expected_count", 4, "expected_count"),
    ("months.0.expected_count", False, "expected_count"),
    ("months.0.observed_count", 3, "observed_dates length"),
    ("months.0.observed_count", 0, "observed_count"),
    ("months.0.observed_count", -1, "observed_count"),
    ("months.0.observed_count", True, "observed_count"),
    ("months.0.observed_count", "2", "observed_count"),
    ("months.0.observed_count", 2.0, "observed_count"),
    ("months.0.observed_dates", [], "observed_dates length"),
    ("months.0.observed_dates", ["2021-01-15", "2021-01-01"], "sorted and unique"),
    ("months.0.observed_dates", ["2021-01-01", "2021-01-01"], "sorted and unique"),
    ("months.0.observed_dates", ["2021-01-01", "2021-02-05"], "another month"),
    ("months.0.observed_dates", ["2021-01-01", "2021-01-32"], "Invalid calendar date"),
    ("months.0.observed_dates", ["2021-01-01", "2021-1-15"], "YYYY-MM-DD"),
    ("months.0.observed_dates", ["2021-01-01", "2021-01-15T00:00:00"], "YYYY-MM-DD"),
    ("months.0.observed_dates", ["2021-01-01", "2021-01-15 "], "YYYY-MM-DD"),
    ("months.0.observed_dates", ["2021-01-01", None], "observed_dates"),
    ("months.0.quality_note", "   ", "quality_note cannot be empty"),
    ("months.0.quality_note", None, "quality_note"),
    ("months.0.expected_dates", [], "extra_forbidden"),
    ("months.0.missing_dates", [], "extra_forbidden"),
    ("silver_sha256", "0" * 64, "extra_forbidden"),
    ("schema_version", "1.0", "extra_forbidden"),
]


def mutate_coverage(payload, path, value):
    coverage = payload["series"][0]["weekly_coverage"]
    if path == "months" and value == "reverse":
        coverage["months"].reverse()
        return
    if path == "months" and value == "duplicate":
        coverage["months"].append(coverage["months"][0].copy())
        return
    target = coverage
    parts = path.split(".")
    for part in parts[:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    target[parts[-1]] = value


def assert_rejected_by_consumer_and_cli(root, manifest_path, payload, message, capsys):
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    before = source_bytes(root)
    # Existing output is also preserved when coverage validation fails.
    output = root / "output"
    output.mkdir()
    (output / "previous.txt").write_text("previous verified report", encoding="utf-8")
    with pytest.raises(ManifestValidationError, match=message):
        load_and_validate_manifest(manifest_path, root)
    assert main(cli_args(root, payload)) == 1
    captured = capsys.readouterr()
    assert message in captured.err + captured.out
    assert {p.name for p in output.iterdir()} == {"previous.txt"}
    assert (output / "previous.txt").read_text(encoding="utf-8") == "previous verified report"
    assert source_bytes(root) == before
    assert not (root / "output.part").exists()
    assert not (root / "output.backup").exists()


@pytest.mark.parametrize("path,value,message", INVALID_COVERAGE, ids=[case[0] + "-" + str(i) for i, case in enumerate(INVALID_COVERAGE)])
def test_shared_fixture_invalid_coverage_blocks_both_consumers(shared_project, path, value, message, capsys):
    root, manifest_path, payload = shared_project
    mutate_coverage(payload, path, value)
    assert_rejected_by_consumer_and_cli(root, manifest_path, payload, message, capsys)


@pytest.mark.parametrize("placement", ["missing-weekly", "null-weekly", "cpi", "kfe", "root", "silver"])
def test_coverage_placement_policy(shared_project, placement, capsys):
    root, manifest_path, payload = shared_project
    coverage = payload["series"][0]["weekly_coverage"]
    message = "weekly_coverage"
    if placement == "missing-weekly":
        del payload["series"][0]["weekly_coverage"]
    elif placement == "null-weekly":
        payload["series"][0]["weekly_coverage"] = None
    elif placement in ("cpi", "kfe"):
        payload["series"][1 if placement == "cpi" else 2]["weekly_coverage"] = coverage
    else:
        target = payload if placement == "root" else payload["silver"]
        target["weekly_coverage"] = coverage
    assert_rejected_by_consumer_and_cli(root, manifest_path, payload, message, capsys)


@pytest.mark.parametrize("count", ["3", "2.5", "", "NaN", "inf", "True", "-2"])
def test_coverage_count_must_match_physical_silver(shared_project, count, capsys):
    root, manifest_path, payload = shared_project
    silver = root / payload["silver"]["path"]
    content = silver.read_text(encoding="utf-8").replace("2021-01,15.0,2,", f"2021-01,15.0,{count},")
    silver.write_bytes(content.encode("utf-8"))
    payload["silver"]["sha256"] = hashlib.sha256(silver.read_bytes()).hexdigest()
    payload["silver"]["size_bytes"] = silver.stat().st_size
    assert_rejected_by_consumer_and_cli(root, manifest_path, payload, "Silver weekly_observation_count", capsys)

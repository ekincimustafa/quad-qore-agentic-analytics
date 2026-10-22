"""Focused offline tests for scripts/check_local_setup.py."""

from __future__ import annotations

from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import socket

import httpx
import pandas as pd
import pytest

from app.connectors import llm_client
from app.services import economic_question as econ_core
from app.services import housing_analysis as housing_service
from app.services import inflation_analysis as inflation_service
from app.services import inflation_comparison as comparison_service
from scripts import check_local_setup as diag
from tests.housing_test_support import write_bddk


def _forbidden(*args, **kwargs):
    raise AssertionError("Network, live provider, or analysis execution is forbidden in setup diagnostics.")


@pytest.fixture(autouse=True)
def block_network_and_clean_env(monkeypatch):
    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _forbidden)
    monkeypatch.setattr(llm_client, "ask_llm", _forbidden)
    monkeypatch.setattr(llm_client, "create_llm_client", _forbidden)
    monkeypatch.setattr(housing_service, "run_housing_analysis", _forbidden)
    monkeypatch.setattr(inflation_service, "build_inflation_evidence", _forbidden)
    monkeypatch.setattr(comparison_service, "compare_inflation_years", _forbidden)
    monkeypatch.setattr(econ_core, "run_economic_question", _forbidden)

    for var in (
        "ANALYTICS_DATA_ROOT",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_CHAT_MODEL",
        "LLM_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(var, raising=False)


def _snapshot_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _build_synthetic_package(target_dir: Path, bddk_periods: list[str] | None = None) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir = Path(__file__).parent / "fixtures" / "evds_manifest_v1"
    shutil.copytree(fixture_dir, target_dir, dirs_exist_ok=True)
    write_bddk(target_dir, bddk_periods or ["2021-01", "2021-02", "2021-03"])
    return target_dir


def test_valid_package_with_spaces_succeeds_key_free_and_preserves_inputs(tmp_path, capsys):
    repo_dir = tmp_path / "repo_without_dotenv"
    repo_dir.mkdir()
    spaced_root = tmp_path / "klasör adı boşluklu" / "verified inputs"
    _build_synthetic_package(spaced_root)
    before = _snapshot_bytes(spaced_root)

    exit_code = diag.main(
        ["--data-root", str(spaced_root), "--json"],
        repo_root=repo_dir,
    )
    out = capsys.readouterr().out
    payload = json.loads(out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["exit_code"] == 0
    assert payload["preview_ready"] is True
    assert payload["normal_mode_configured"] is False
    assert payload["normal_mode_ready"] is False
    assert payload["live_model_access_verified"] is False
    assert payload["error_codes"] == []
    assert payload["warning_codes"] == ["llm_not_configured"]

    assert payload["checks"]["data_root"]["source"] == "cli"
    assert payload["checks"]["data_root"]["exists"] is True

    pkg = payload["checks"]["data_package"]
    assert pkg["status"] == "ok"
    assert pkg["verified"] is True
    assert pkg["bddk"] == {"row_count": 3, "start_period": "2021-01", "end_period": "2021-03"}
    assert pkg["cpi"] == {"row_count": 2, "start_period": "2021-01", "end_period": "2021-02"}
    assert pkg["housing_coverage"] == {"row_count": 2, "start_period": "2021-01", "end_period": "2021-02"}

    assert _snapshot_bytes(spaced_root) == before


def test_dynamic_snapshot_counts_are_derived_not_hardcoded(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    pkg_dir = _build_synthetic_package(
        tmp_path / "pkg_four_months",
        bddk_periods=["2021-01", "2021-02", "2021-03", "2021-04"],
    )
    report = diag.run_diagnostics(cli_data_root=pkg_dir, repo_root=repo_dir)
    assert report["exit_code"] == 0
    assert report["checks"]["data_package"]["bddk"] == {
        "row_count": 4,
        "start_period": "2021-01",
        "end_period": "2021-04",
    }
    assert report["checks"]["data_package"]["cpi"] == {
        "row_count": 2,
        "start_period": "2021-01",
        "end_period": "2021-02",
    }
    assert report["checks"]["data_package"]["housing_coverage"] == {
        "row_count": 2,
        "start_period": "2021-01",
        "end_period": "2021-02",
    }


def test_data_root_priority_cli_over_env_over_dotenv_over_repo_default(tmp_path, monkeypatch):
    cli_pkg = _build_synthetic_package(tmp_path / "from_cli", ["2021-01", "2021-02"])
    env_pkg = _build_synthetic_package(tmp_path / "from_env", ["2021-01", "2021-02", "2021-03"])
    dotenv_pkg = _build_synthetic_package(
        tmp_path / "from dotenv with spaces",
        ["2021-01", "2021-02", "2021-03", "2021-04"],
    )
    repo_pkg = _build_synthetic_package(
        tmp_path / "repo_root_pkg",
        ["2021-01", "2021-02", "2021-03", "2021-04", "2021-05"],
    )

    # Write .env inside repo_pkg pointing to dotenv_pkg
    (repo_pkg / ".env").write_text(
        f"ANALYTICS_DATA_ROOT={dotenv_pkg}\n",
        encoding="utf-8",
    )

    # 1. --data-root wins over process env and .env
    monkeypatch.setenv("ANALYTICS_DATA_ROOT", str(env_pkg))
    r_cli = diag.run_diagnostics(cli_data_root=cli_pkg, repo_root=repo_pkg)
    assert r_cli["checks"]["data_root"]["source"] == "cli"
    assert r_cli["checks"]["data_package"]["bddk"]["row_count"] == 2
    assert os.environ["ANALYTICS_DATA_ROOT"] == str(env_pkg)

    # 2. Process ANALYTICS_DATA_ROOT wins over .env and does not get overwritten by .env
    r_env = diag.run_diagnostics(cli_data_root=None, repo_root=repo_pkg)
    assert r_env["checks"]["data_root"]["source"] == "env"
    assert r_env["checks"]["data_package"]["bddk"]["row_count"] == 3
    assert os.environ["ANALYTICS_DATA_ROOT"] == str(env_pkg)

    # 3. Local .env wins over repo_default when process ANALYTICS_DATA_ROOT is not set
    monkeypatch.delenv("ANALYTICS_DATA_ROOT")
    r_dotenv = diag.run_diagnostics(cli_data_root=None, repo_root=repo_pkg)
    assert r_dotenv["checks"]["data_root"]["source"] == "dotenv"
    assert r_dotenv["checks"]["data_package"]["bddk"]["row_count"] == 4
    assert "ANALYTICS_DATA_ROOT" not in os.environ

    # 4. Repo root is used when .env has no ANALYTICS_DATA_ROOT
    (repo_pkg / ".env").unlink()
    r_repo = diag.run_diagnostics(cli_data_root=None, repo_root=repo_pkg)
    assert r_repo["checks"]["data_root"]["source"] == "repo_default"
    assert r_repo["checks"]["data_package"]["bddk"]["row_count"] == 5


@pytest.mark.parametrize(
    ("fault", "expected_code"),
    [
        ("missing_root", "data_root_missing"),
        ("blank_cli_root", "data_root_missing"),
        ("empty_dir", "data_files_missing"),
        ("outer_delivery_dir", "data_files_missing"),
        ("missing_manifest", "data_files_missing"),
        ("missing_bddk_silver", "data_files_missing"),
        ("missing_evds_csv", "data_files_missing"),
        ("missing_evds_bronze_raw", "data_files_missing"),
        ("corrupt_evds_bronze_raw_hash", "data_integrity_failed"),
        ("corrupt_evds_bronze_receipt", "data_integrity_failed"),
        ("corrupt_evds_csv_hash", "data_integrity_failed"),
        ("corrupt_bddk_bronze_raw_hash", "data_integrity_failed"),
        ("corrupt_bddk_silver_mismatch", "data_integrity_failed"),
        ("corrupt_manifest_contract", "data_integrity_failed"),
    ],
)
def test_missing_or_corrupted_data_package_fails_safely_without_leaking_secrets(
    tmp_path, capsys, fault, expected_code,
):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    pkg_dir = _build_synthetic_package(tmp_path / "pkg")
    manifest_path = pkg_dir / "data/silver/evds/monthly/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    cli_arg: str = str(pkg_dir)
    if fault == "missing_root":
        cli_arg = str(tmp_path / "private-nonexistent-root")
    elif fault == "blank_cli_root":
        cli_arg = "   "
    elif fault == "empty_dir":
        empty = tmp_path / "empty_folder"
        empty.mkdir()
        cli_arg = str(empty)
    elif fault == "outer_delivery_dir":
        outer = tmp_path / "outer_zip_dir"
        _build_synthetic_package(outer / "inputs")
        cli_arg = str(outer)
    elif fault == "missing_manifest":
        manifest_path.unlink()
    elif fault == "missing_bddk_silver":
        (pkg_dir / "data/silver/bddk/housing_loans.parquet").unlink()
    elif fault == "missing_evds_csv":
        (pkg_dir / manifest["silver"]["path"]).unlink()
    elif fault == "missing_evds_bronze_raw":
        (pkg_dir / manifest["series"][0]["bronze"][0]["raw_path"]).unlink()
    elif fault == "corrupt_evds_bronze_raw_hash":
        # Silver CSV is still readable, but Bronze raw hash is broken -> must fail!
        raw_target = pkg_dir / manifest["series"][0]["bronze"][0]["raw_path"]
        raw_target.write_bytes(raw_target.read_bytes() + b" broken-secret-payload")
    elif fault == "corrupt_evds_bronze_receipt":
        rec_target = pkg_dir / manifest["series"][0]["bronze"][0]["receipt_path"]
        rec_target.write_bytes(b"{broken-secret-payload")
    elif fault == "corrupt_evds_csv_hash":
        csv_target = pkg_dir / manifest["silver"]["path"]
        csv_target.write_bytes(csv_target.read_bytes() + b"\nbroken-secret-payload\n")
    elif fault == "corrupt_bddk_bronze_raw_hash":
        bddk_raw = pkg_dir / "data/bronze/bddk/aylik/raw/2021-01.json"
        bddk_raw.write_bytes(bddk_raw.read_bytes() + b" broken-secret-payload")
    elif fault == "corrupt_bddk_silver_mismatch":
        parquet_path = pkg_dir / "data/silver/bddk/housing_loans.parquet"
        frame = pd.read_parquet(parquet_path)
        frame.loc[0, ["housing_loan_amount", "nominal_housing_loan_mn_try"]] = 999999.0
        frame.to_parquet(parquet_path, index=False)
    elif fault == "corrupt_manifest_contract":
        manifest["series"][1]["base_year"] = 1999
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    exit_code = diag.main(["--data-root", cli_arg, "--json"], repo_root=repo_dir)
    out = capsys.readouterr().out
    payload = json.loads(out)

    assert exit_code == 1
    assert payload["status"] == "error"
    assert payload["preview_ready"] is False
    assert payload["normal_mode_ready"] is False
    assert payload["checks"]["data_package"]["status"] == "error"
    assert payload["checks"]["data_package"]["code"] == expected_code
    assert payload["checks"]["data_package"]["verified"] is False
    assert expected_code in payload["error_codes"]
    assert "broken-secret-payload" not in out
    assert "private-nonexistent-root" not in out
    if fault == "outer_delivery_dir":
        assert "inputs" in payload["checks"]["data_package"]["message"]


def test_python_version_and_dependency_checks(tmp_path, monkeypatch, capsys):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    pkg_dir = _build_synthetic_package(tmp_path / "pkg")

    # 1. Incompatible Python version (e.g. 3.11.9)
    monkeypatch.setattr(diag.sys, "version_info", (3, 11, 9, "final", 0))
    assert diag.main(["--data-root", str(pkg_dir), "--json"], repo_root=repo_dir) == 1
    py_err = json.loads(capsys.readouterr().out)
    assert py_err["preview_ready"] is False
    assert py_err["checks"]["python"]["code"] == "python_version_mismatch"
    assert "3.11.9" in py_err["checks"]["python"]["message"]
    assert py_err["checks"]["python"]["recommendation"]

    # Restore Python 3.12 and simulate missing runtime package
    monkeypatch.setattr(diag.sys, "version_info", (3, 12, 4, "final", 0))
    original_version = metadata.version

    def fake_version(name: str) -> str:
        if name in {"plotly", "pyarrow"}:
            raise metadata.PackageNotFoundError(name)
        return original_version(name)

    monkeypatch.setattr(diag.metadata, "version", fake_version)
    assert diag.main(["--data-root", str(pkg_dir), "--json"], repo_root=repo_dir) == 1
    dep_err = json.loads(capsys.readouterr().out)
    assert dep_err["preview_ready"] is False
    assert dep_err["checks"]["dependencies"]["code"] == "missing_dependencies"
    assert dep_err["checks"]["dependencies"]["missing_packages"] == ["pyarrow", "plotly"]
    assert "requirements.txt" in dep_err["checks"]["dependencies"]["recommendation"]


@pytest.mark.parametrize(
    ("env_vars", "expected_code", "expected_configured"),
    [
        ({}, "llm_not_configured", False),
        (
            {
                "LLM_API_KEY": "super-secret-api-key",
                "LLM_BASE_URL": "http://insecure.invalid/v1",
                "LLM_CHAT_MODEL": "secret-model",
            },
            "llm_config_invalid",
            False,
        ),
        (
            {
                "LLM_API_KEY": "super-secret-api-key",
                "LLM_BASE_URL": "https://user:super-secret-pass@llm.invalid/v1",
                "LLM_CHAT_MODEL": "secret-model",
            },
            "llm_config_invalid",
            False,
        ),
        (
            {
                "LLM_API_KEY": "super-secret-api-key",
                "LLM_BASE_URL": "https://llm.invalid/v1",
                "LLM_CHAT_MODEL": "secret-model",
                "LLM_TIMEOUT_SECONDS": "999",
            },
            "llm_config_invalid",
            False,
        ),
        (
            {
                "LLM_API_KEY": "super-secret-api-key",
                "LLM_BASE_URL": "https://llm.invalid/v1",
                "LLM_CHAT_MODEL": "secret-model",
                "LLM_TIMEOUT_SECONDS": "45",
            },
            "llm_configured_untested",
            True,
        ),
    ],
)
def test_llm_config_variants_preserve_offline_exit_zero_and_never_leak_secrets(
    tmp_path, monkeypatch, capsys, env_vars, expected_code, expected_configured,
):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".env").write_text("RAW_DOTENV_SECRET=never-print-this-dotenv-line\n", encoding="utf-8")
    pkg_dir = _build_synthetic_package(tmp_path / "pkg")

    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)

    # JSON output check
    exit_code_json = diag.main(["--data-root", str(pkg_dir), "--json"], repo_root=repo_dir)
    json_out = capsys.readouterr().out
    payload = json.loads(json_out)

    assert exit_code_json == 0
    assert payload["preview_ready"] is True
    assert payload["normal_mode_configured"] is expected_configured
    assert payload["normal_mode_ready"] is expected_configured
    assert payload["live_model_access_verified"] is False
    assert payload["checks"]["llm_config"]["code"] == expected_code
    assert payload["checks"]["llm_config"]["provider_access_tested"] is False
    assert payload["checks"]["llm_config"]["live_access_verified"] is False

    # Human output check
    exit_code_text = diag.main(["--data-root", str(pkg_dir)], repo_root=repo_dir)
    text_out = capsys.readouterr().out
    assert exit_code_text == 0
    assert "Yerel Kurulum ve Veri Paketi Teşhisi" in text_out
    if expected_configured:
        assert "Ayar mevcut; sağlayıcı erişimi denenmedi" in text_out

    combined_output = json_out + "\n" + text_out
    for secret in (
        "super-secret-api-key",
        "super-secret-pass",
        "secret-model",
        "never-print-this-dotenv-line",
    ):
        assert secret not in combined_output

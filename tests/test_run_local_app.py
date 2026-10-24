"""Focused offline and local-loopback tests for scripts/run_local_app.py."""

from __future__ import annotations

from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib import request as urllib_request
import venv
import webbrowser

import httpx
import pytest

from app.api import economic_question as econ_api
from app.api import main as api_main
from app.connectors import llm_client
from app.services import economic_question as econ_core
from app.services import housing_analysis as housing_service
from app.services import inflation_analysis as inflation_service
from app.services import inflation_comparison as comparison_service
from scripts import check_local_setup as diag
from scripts import preview_question_ui
from scripts import run_local_app as launcher
from tests.housing_test_support import write_bddk


def _forbidden(*args, **kwargs):
    raise AssertionError(
        "External network, browser launch, live provider, or analysis execution is forbidden."
    )


@pytest.fixture(autouse=True)
def block_external_calls_and_clean_env(monkeypatch):
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _forbidden)
    monkeypatch.setattr(webbrowser, "open", _forbidden)
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


def _find_free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.mark.parametrize(
    "bad_argv",
    [
        ["--mode", "invalid"],
        ["--mode", "prod"],
        ["--port", "0"],
        ["--port", "-1"],
        ["--port", "65536"],
        ["--port", "abc"],
        ["--port", "²"],
        ["--port", "8000.5"],
        ["--host", "0.0.0.0"],
        ["--reload"],
        ["--unknown-flag"],
    ],
)
def test_invalid_cli_arguments_return_exit_2_without_running_checks_or_server(
    tmp_path, monkeypatch, bad_argv,
):
    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(launcher, "run_diagnostics", _forbidden)
    monkeypatch.setattr(launcher, "_run_uvicorn_server", _forbidden)

    exit_code = launcher.main(bad_argv, repo_root=tmp_path)
    assert exit_code == 2


def test_check_only_preview_and_model_modes_never_touch_socket_or_server(
    tmp_path, monkeypatch, capsys,
):
    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(launcher, "_run_uvicorn_server", _forbidden)
    monkeypatch.setattr(launcher, "_create_mode_app", _forbidden)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    pkg_dir = _build_synthetic_package(tmp_path / "klasör adı boşluklu" / "türkçe veri girişi")
    before = _snapshot_bytes(pkg_dir)

    # 1. Preview --check-only succeeds without LLM key
    code_preview = launcher.main(
        ["--mode", "preview", "--data-root", str(pkg_dir), "--port", "8010", "--check-only"],
        repo_root=repo_dir,
    )
    out_preview = capsys.readouterr().out
    assert code_preview == 0
    assert "http://127.0.0.1:8010/" in out_preview
    assert "Seçilen çalışma modu: preview" in out_preview
    assert "üç sabit örnek" in out_preview
    assert "--check-only" in out_preview

    # 2. Preview --check-only still succeeds when LLM config is invalid (warning only)
    monkeypatch.setenv("LLM_API_KEY", "secret-key-val")
    monkeypatch.setenv("LLM_BASE_URL", "http://insecure.invalid/v1")
    monkeypatch.setenv("LLM_CHAT_MODEL", "secret-model-val")
    code_preview_invalid_llm = launcher.main(
        ["--mode", "preview", "--data-root", str(pkg_dir), "--check-only"],
        repo_root=repo_dir,
    )
    out_preview_invalid = capsys.readouterr().out
    assert code_preview_invalid_llm == 0
    assert "secret-key-val" not in out_preview_invalid
    assert "secret-model-val" not in out_preview_invalid

    # 3. Model --check-only fails (exit 1) when LLM config is invalid
    code_model_invalid = launcher.main(
        ["--mode", "model", "--data-root", str(pkg_dir), "--check-only"],
        repo_root=repo_dir,
    )
    out_model_invalid = capsys.readouterr().out
    assert code_model_invalid == 1
    assert "llm_config_invalid" in out_model_invalid
    assert "secret-key-val" not in out_model_invalid

    # 4. Model --check-only fails (exit 1) when LLM config is missing
    for var in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_CHAT_MODEL"):
        monkeypatch.delenv(var, raising=False)
    code_model_missing = launcher.main(
        ["--mode", "model", "--data-root", str(pkg_dir), "--check-only"],
        repo_root=repo_dir,
    )
    out_model_missing = capsys.readouterr().out
    assert code_model_missing == 1
    assert "llm_not_configured" in out_model_missing

    # 5. Model --check-only succeeds (exit 0) when local LLM settings are valid
    monkeypatch.setenv("LLM_API_KEY", "secret-key-val")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.invalid/v1")
    monkeypatch.setenv("LLM_CHAT_MODEL", "secret-model-val")
    code_model_ok = launcher.main(
        ["--mode", "model", "--data-root", str(pkg_dir), "--port", "8001", "--check-only"],
        repo_root=repo_dir,
    )
    out_model_ok = capsys.readouterr().out
    assert code_model_ok == 0
    assert "http://127.0.0.1:8001/" in out_model_ok
    assert "Seçilen çalışma modu: model" in out_model_ok
    assert "Ayar mevcut; sağlayıcı erişimi denenmedi" in out_model_ok
    assert "secret-key-val" not in out_model_ok
    assert "secret-model-val" not in out_model_ok
    assert _snapshot_bytes(pkg_dir) == before


def test_preview_and_model_launch_use_correct_factories_host_port_and_restore_env(
    tmp_path, monkeypatch, capsys,
):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    pkg_dir = _build_synthetic_package(tmp_path / "veri paketi" / "inputs")
    free_port = _find_free_local_port()

    calls: list[dict[str, object]] = []

    def fake_run_uvicorn(app, *, host: str, port: int) -> None:
        resolved_server_paths = econ_api.get_verified_economic_paths()
        calls.append(
            {
                "app": app,
                "host": host,
                "port": port,
                "env_data_root": os.environ.get("ANALYTICS_DATA_ROOT"),
                "server_project_root": resolved_server_paths.project_root.resolve(),
                "offline_preview": getattr(app.state, "offline_preview", False),
                "overrides": dict(app.dependency_overrides),
            }
        )

    monkeypatch.setattr(launcher, "_run_uvicorn_server", fake_run_uvicorn)

    # 1. Default mode is preview, default port is 8000 (or custom port), key-free success
    monkeypatch.setenv("ANALYTICS_DATA_ROOT", "prior-process-root")
    exit_preview = launcher.main(
        ["--data-root", str(pkg_dir), "--port", str(free_port)],
        repo_root=repo_dir,
    )
    out_preview = capsys.readouterr().out
    assert exit_preview == 0
    assert len(calls) == 1
    c_prev = calls[0]
    assert c_prev["host"] == "127.0.0.1"
    assert c_prev["port"] == free_port
    assert c_prev["env_data_root"] == str(pkg_dir.resolve())
    assert c_prev["server_project_root"] == pkg_dir.resolve()
    assert c_prev["offline_preview"] is True
    override_fn = c_prev["overrides"][econ_api.get_economic_question_model]
    assert override_fn() is preview_question_ui.fixed_plan
    assert f"http://127.0.0.1:{free_port}/" in out_preview
    assert "üç sabit örnek" in out_preview
    # Prior ANALYTICS_DATA_ROOT is restored after exit
    assert os.environ.get("ANALYTICS_DATA_ROOT") == "prior-process-root"

    # 2. Model mode stops before creating app or starting server when LLM config is missing
    calls.clear()
    monkeypatch.delenv("ANALYTICS_DATA_ROOT", raising=False)
    exit_model_blocked = launcher.main(
        ["--mode", "model", "--data-root", str(pkg_dir), "--port", str(free_port)],
        repo_root=repo_dir,
    )
    out_blocked = capsys.readouterr().out
    assert exit_model_blocked == 1
    assert calls == []
    assert "llm_not_configured" in out_blocked
    assert "ANALYTICS_DATA_ROOT" not in os.environ

    # 3. Model mode with valid LLM config uses create_app(), preserves normal dependency, makes 0 LLM calls
    monkeypatch.setenv("LLM_API_KEY", "super-secret-llm-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.invalid/v1")
    monkeypatch.setenv("LLM_CHAT_MODEL", "super-secret-model")
    exit_model_ok = launcher.main(
        ["--mode", "model", "--data-root", str(pkg_dir), "--port", str(free_port)],
        repo_root=repo_dir,
    )
    out_model = capsys.readouterr().out
    assert exit_model_ok == 0
    assert len(calls) == 1
    c_mod = calls[0]
    assert c_mod["host"] == "127.0.0.1"
    assert c_mod["port"] == free_port
    assert c_mod["env_data_root"] == str(pkg_dir.resolve())
    assert c_mod["server_project_root"] == pkg_dir.resolve()
    assert c_mod["offline_preview"] is False
    assert econ_api.get_economic_question_model not in c_mod["overrides"]
    assert c_mod["overrides"] == {}
    assert f"http://127.0.0.1:{free_port}/" in out_model
    assert "Ayar mevcut; sağlayıcı erişimi denenmedi" in out_model
    assert "super-secret-llm-key" not in out_model
    assert "super-secret-model" not in out_model
    assert "ANALYTICS_DATA_ROOT" not in os.environ
    assert os.environ["LLM_API_KEY"] == "super-secret-llm-key"


def test_direct_uvicorn_run_monkeypatch_and_in_memory_files_endpoint_with_selected_root(
    tmp_path, monkeypatch,
):
    from fastapi.testclient import TestClient
    import uvicorn

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    pkg_dir = _build_synthetic_package(
        tmp_path / "doğrulanmış paket" / "inputs",
        bddk_periods=["2021-01", "2021-02", "2021-03", "2021-04"],
    )
    free_port = _find_free_local_port()
    uvicorn_calls: list[tuple[str, int, int, str]] = []

    def fake_uvicorn_run(app, *, host: str, port: int, **kwargs) -> None:
        with TestClient(app) as client:
            r_health = client.get("/health")
            assert r_health.status_code == 200
            r_files = client.post(
                "/analysis/economic/question/files",
                json={"question": "serbest netleştirme sorusu"},
            )
            assert r_files.status_code == 200
            body = r_files.json()
            assert body["status"] == "clarification_required"
            assert body["available_periods"]["housing"]["end_period"] == "2021-02"
            uvicorn_calls.append((host, port, r_files.status_code, os.environ["ANALYTICS_DATA_ROOT"]))

    monkeypatch.setattr(uvicorn, "run", fake_uvicorn_run)

    exit_code = launcher.main(
        ["--mode", "preview", "--data-root", str(pkg_dir), "--port", str(free_port)],
        repo_root=repo_dir,
    )
    assert exit_code == 0
    assert uvicorn_calls == [("127.0.0.1", free_port, 200, str(pkg_dir.resolve()))]
    assert "ANALYTICS_DATA_ROOT" not in os.environ


def test_data_root_priority_and_relative_turkish_paths_propagate_to_server_and_restore_env(
    tmp_path, monkeypatch,
):
    cli_pkg = _build_synthetic_package(tmp_path / "cli klasörü" / "giriş", ["2021-01", "2021-02"])
    env_pkg = _build_synthetic_package(tmp_path / "env klasörü" / "giriş", ["2021-01", "2021-02", "2021-03"])
    dotenv_pkg = _build_synthetic_package(
        tmp_path / "dotenv klasörü" / "giriş",
        ["2021-01", "2021-02", "2021-03", "2021-04"],
    )
    repo_pkg = _build_synthetic_package(
        tmp_path / "repo_root_pkg",
        ["2021-01", "2021-02", "2021-03", "2021-04", "2021-05"],
    )
    dotenv_file = repo_pkg / ".env"
    dotenv_file.write_text(f"ANALYTICS_DATA_ROOT={dotenv_pkg}\n", encoding="utf-8")
    dotenv_bytes_before = dotenv_file.read_bytes()

    free_port = _find_free_local_port()
    observed_roots: list[Path] = []

    def capture_server(app, *, host: str, port: int) -> None:
        observed_roots.append(econ_api.get_verified_economic_paths().project_root.resolve())

    monkeypatch.setattr(launcher, "_run_uvicorn_server", capture_server)

    # 1. --data-root (relative path with Turkish chars and spaces) > process env > .env > repo_root
    rel_cli = os.path.relpath(cli_pkg, Path.cwd())
    monkeypatch.setenv("ANALYTICS_DATA_ROOT", str(env_pkg))
    assert launcher.main(["--data-root", rel_cli, "--port", str(free_port)], repo_root=repo_pkg) == 0
    assert observed_roots[-1] == cli_pkg.resolve()
    assert os.environ["ANALYTICS_DATA_ROOT"] == str(env_pkg)

    # 2. Process ANALYTICS_DATA_ROOT > .env > repo_root
    assert launcher.main(["--port", str(free_port)], repo_root=repo_pkg) == 0
    assert observed_roots[-1] == env_pkg.resolve()
    assert os.environ["ANALYTICS_DATA_ROOT"] == str(env_pkg)

    # 3. Local .env > repo_root
    monkeypatch.delenv("ANALYTICS_DATA_ROOT", raising=False)
    assert launcher.main(["--port", str(free_port)], repo_root=repo_pkg) == 0
    assert observed_roots[-1] == dotenv_pkg.resolve()
    assert "ANALYTICS_DATA_ROOT" not in os.environ
    assert dotenv_file.read_bytes() == dotenv_bytes_before

    # 4. Repo root default when .env is removed
    dotenv_file.unlink()
    assert launcher.main(["--port", str(free_port)], repo_root=repo_pkg) == 0
    assert observed_roots[-1] == repo_pkg.resolve()
    assert "ANALYTICS_DATA_ROOT" not in os.environ


def test_occupied_port_and_ctrl_c_and_errors_restore_environment_cleanly(
    tmp_path, monkeypatch, capsys,
):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    pkg_dir = _build_synthetic_package(tmp_path / "pkg")

    # 1. Occupied port: bind a real listener on 127.0.0.1, verify launcher exits 1 without starting server
    orig_create_mode_app = launcher._create_mode_app
    monkeypatch.setenv("ANALYTICS_DATA_ROOT", "keep-this-value")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied_sock:
        occupied_sock.bind(("127.0.0.1", 0))
        occupied_sock.listen(1)
        busy_port = int(occupied_sock.getsockname()[1])

        monkeypatch.setattr(launcher, "_create_mode_app", _forbidden)
        monkeypatch.setattr(launcher, "_run_uvicorn_server", _forbidden)

        exit_busy = launcher.main(
            ["--mode", "preview", "--data-root", str(pkg_dir), "--port", str(busy_port)],
            repo_root=repo_dir,
        )
        out_busy = capsys.readouterr().out
        assert exit_busy == 1
        assert "port_in_use" in out_busy
        assert f"127.0.0.1:{busy_port}" in out_busy
        assert os.environ["ANALYTICS_DATA_ROOT"] == "keep-this-value"
        # Listener socket is still alive
        assert occupied_sock.fileno() != -1

    # 2. Ctrl+C (KeyboardInterrupt) during server execution -> clean exit 0 & environment restored
    free_port = _find_free_local_port()
    monkeypatch.setattr(launcher, "_create_mode_app", orig_create_mode_app)

    def raise_ctrl_c(app, *, host: str, port: int) -> None:
        assert os.environ["ANALYTICS_DATA_ROOT"] == str(pkg_dir.resolve())
        raise KeyboardInterrupt

    monkeypatch.setattr(launcher, "_run_uvicorn_server", raise_ctrl_c)
    exit_ctrl_c = launcher.main(
        ["--mode", "preview", "--data-root", str(pkg_dir), "--port", str(free_port)],
        repo_root=repo_dir,
    )
    out_ctrl_c = capsys.readouterr().out
    assert exit_ctrl_c == 0
    assert "Ctrl+C" in out_ctrl_c
    assert os.environ["ANALYTICS_DATA_ROOT"] == "keep-this-value"

    # 3. Unexpected OSError inside uvicorn.run -> exit 1 & environment restored
    monkeypatch.delenv("ANALYTICS_DATA_ROOT", raising=False)

    def raise_os_error(app, *, host: str, port: int) -> None:
        assert os.environ["ANALYTICS_DATA_ROOT"] == str(pkg_dir.resolve())
        raise OSError("Simulated bind failure")

    monkeypatch.setattr(launcher, "_run_uvicorn_server", raise_os_error)
    exit_os_err = launcher.main(
        ["--mode", "preview", "--data-root", str(pkg_dir), "--port", str(free_port)],
        repo_root=repo_dir,
    )
    out_os_err = capsys.readouterr().out
    assert exit_os_err == 1
    assert "Simulated bind failure" not in out_os_err
    assert "ANALYTICS_DATA_ROOT" not in os.environ


def test_corrupt_data_and_incompatible_env_stop_before_server_and_empty_venv_subprocess_is_clean(
    tmp_path, monkeypatch, capsys,
):
    monkeypatch.setattr(launcher, "_create_mode_app", _forbidden)
    monkeypatch.setattr(launcher, "_run_uvicorn_server", _forbidden)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    pkg_dir = _build_synthetic_package(tmp_path / "pkg")

    # 1. Corrupt Bronze raw hash while Silver is readable -> exit 1, 0 server starts
    bddk_raw = pkg_dir / "data/bronze/bddk/aylik/raw/2021-01.json"
    bddk_raw.write_bytes(bddk_raw.read_bytes() + b" corrupt-secret")
    assert launcher.main(["--data-root", str(pkg_dir)], repo_root=repo_dir) == 1
    out_corrupt = capsys.readouterr().out
    assert "data_integrity_failed" in out_corrupt
    assert "corrupt-secret" not in out_corrupt

    # 2. Wrong Python version -> exit 1, 0 server starts
    monkeypatch.setattr(diag.sys, "version_info", (3, 11, 8, "final", 0))
    assert launcher.main(["--data-root", str(pkg_dir)], repo_root=repo_dir) == 1
    assert "python_version_mismatch" in capsys.readouterr().out

    # 3. Incompatible package version -> exit 1, 0 server starts
    monkeypatch.setattr(diag.sys, "version_info", (3, 12, 4, "final", 0))
    orig_version = metadata.version
    monkeypatch.setattr(
        diag.metadata,
        "version",
        lambda name: "1.10.0" if name == "pydantic" else orig_version(name),
    )
    assert launcher.main(["--data-root", str(pkg_dir)], repo_root=repo_dir) == 1
    assert "incompatible_dependencies" in capsys.readouterr().out
    monkeypatch.setattr(diag.metadata, "version", orig_version)

    # 4. Import-time stdlib-only check and empty venv (--without-pip) subprocess check
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    proc_import = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            (
                "import json, sys; "
                "import scripts.run_local_app; "
                "forbidden = [m for m in ('uvicorn', 'dotenv', 'pydantic', 'pandas', 'pyarrow', 'openai', 'fastapi', 'app') "
                "if m in sys.modules or any(k.startswith(m + '.') for k in sys.modules)]; "
                "print(json.dumps(forbidden))"
            ),
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc_import.returncode == 0
    assert json.loads(proc_import.stdout.strip()) == []

    empty_venv_dir = tmp_path / "empty_venv"
    venv.EnvBuilder(with_pip=False).create(empty_venv_dir)
    venv_python = (
        empty_venv_dir / "Scripts" / "python.exe"
        if os.name == "nt"
        else empty_venv_dir / "bin" / "python"
    )
    proc_venv = subprocess.run(
        [str(venv_python), "-m", "scripts.run_local_app", "--mode", "preview"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert proc_venv.returncode == 1
    assert proc_venv.stderr == ""
    assert "Traceback" not in proc_venv.stdout
    assert "ModuleNotFoundError" not in proc_venv.stdout
    assert "[missing_dependencies]" in proc_venv.stdout
    assert "skipped/not_run" in proc_venv.stdout


def test_local_loopback_subprocess_smoke_preview_health_and_ui(tmp_path):
    """Short local-loopback smoke test: GET /health and GET / return HTTP 200 with 0 provider calls."""
    repo_root = Path(__file__).resolve().parents[1]
    pkg_dir = _build_synthetic_package(tmp_path / "loopback smoke" / "inputs")
    port = _find_free_local_port()

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    for var in ("ANALYTICS_DATA_ROOT", "LLM_API_KEY", "LLM_BASE_URL", "LLM_CHAT_MODEL"):
        env.pop(var, None)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "scripts.run_local_app",
            "--mode",
            "preview",
            "--data-root",
            str(pkg_dir),
            "--port",
            str(port),
        ],
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        health_url = f"http://127.0.0.1:{port}/health"
        ui_url = f"http://127.0.0.1:{port}/"
        opener = urllib_request.build_opener(urllib_request.ProxyHandler({}))

        health_payload = None
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                stdout_text, stderr_text = proc.communicate(timeout=5)
                pytest.fail(
                    f"Preview server exited early with {proc.returncode}:\n{stdout_text}\n{stderr_text}"
                )
            try:
                with opener.open(health_url, timeout=1.0) as resp:
                    if resp.status == 200:
                        health_payload = json.loads(resp.read().decode("utf-8"))
                        break
            except Exception:
                time.sleep(0.15)

        assert health_payload is not None
        assert health_payload["status"] == "ok"

        with opener.open(ui_url, timeout=2.0) as ui_resp:
            assert ui_resp.status == 200
            html_body = ui_resp.read().decode("utf-8")
            assert "<!DOCTYPE html>" in html_body or "<html" in html_body
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        assert proc.poll() is not None
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()

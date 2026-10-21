"""Run the repository's offline verification steps in a single command."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_ROOT = ROOT / "out" / "verification"


@dataclass(frozen=True)
class Step:
    name: str
    command: tuple[str, ...]
    log_name: str


def _run_name() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def build_steps(run_dir: Path) -> tuple[Step, ...]:
    return (
        Step("pytest", (sys.executable, "-m", "pytest", "-q", "tests"), "pytest.log"),
        Step(
            "housing-offline-eval",
            (
                sys.executable,
                "-m",
                "scripts.evaluate_housing_questions",
                "--output",
                str(run_dir / "housing-question-eval.json"),
            ),
            "housing-offline-eval.log",
        ),
        Step(
            "economic-offline-eval",
            (
                sys.executable,
                "-m",
                "scripts.evaluate_economic_questions",
                "--output",
                str(run_dir / "economic-question-eval.json"),
            ),
            "economic-offline-eval.log",
        ),
        Step("diff-check", ("git", "diff", "--check"), "diff-check.log"),
    )


def _read_tail(path: Path, max_bytes: int = 8192, max_lines: int = 40) -> str:
    try:
        with path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - max_bytes))
            text = stream.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(text.splitlines()[-max_lines:])


def _execute_step(
    step: Step,
    repo_root: Path,
    log_path: Path,
    runner: Callable[..., object],
) -> int | None:
    try:
        with log_path.open("w", encoding="utf-8") as log:
            completed = runner(
                step.command,
                cwd=repo_root,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
    except OSError as exc:
        log_path.write_text(f"Adım başlatılamadı: {exc}\n", encoding="utf-8")
        return None
    return int(getattr(completed, "returncode", 1))


def _report_failure(
    step: Step,
    log_path: Path,
    reason: str,
    echo: Callable[[str], None],
) -> None:
    echo(f"[HATA] {step.name}: {reason}")
    echo(f"Günlük: {log_path}")
    tail = _read_tail(log_path)
    if tail:
        echo("--- son çıktı ---")
        echo(tail)
        echo("--- son çıktı sonu ---")


def run_verification(
    repo_root: Path = ROOT,
    output_root: Path | None = None,
    runner: Callable[..., object] | None = None,
    run_name: str | None = None,
    echo: Callable[[str], None] = print,
) -> int:
    repo_root = Path(repo_root).resolve()
    output_root = Path(output_root) if output_root is not None else VERIFICATION_ROOT
    run_dir = output_root / (run_name or _run_name())
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        echo(f"[HATA] Çıktı dizini oluşturulamadı: {run_dir}: {exc}")
        return 1
    steps = build_steps(run_dir)
    execute = runner or subprocess.run

    echo(f"Çevrimdışı doğrulama: {len(steps)} adım; çıktı dizini: {run_dir}")
    for index, step in enumerate(steps, start=1):
        echo(f"[{index}/{len(steps)}] {step.name} çalışıyor...")
        log_path = run_dir / step.log_name
        returncode = _execute_step(step, repo_root, log_path, execute)
        if returncode is None:
            _report_failure(step, log_path, "komut başlatılamadı", echo)
            return 1
        if returncode != 0:
            _report_failure(step, log_path, f"çıkış kodu {returncode}", echo)
            return 1
        echo(f"[{index}/{len(steps)}] {step.name}: başarılı")

    echo(f"Doğrulama başarılı: {len(steps)}/{len(steps)} adım.")
    echo(f"Ayrıntılı günlükler: {run_dir}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Depoyu çevrimdışı doğrula: testler, sahte değerlendirmeler ve diff kontrolü."
    )
    parser.parse_args(argv)
    return run_verification()


if __name__ == "__main__":
    raise SystemExit(main())

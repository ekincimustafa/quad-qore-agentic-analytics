"""Key-free comparison sample CLI: years, safety, atomic output and provenance."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

import scripts.render_inflation_comparison_sample as cli


@pytest.fixture
def output_root(monkeypatch, tmp_path):
    out = tmp_path / "out"
    monkeypatch.setattr(cli, "OUTPUT_ROOT", out)
    return out


def test_cli_produces_offline_html_and_never_changes_fixture(output_root):
    initial = cli.FIXTURE_PATH.read_bytes()
    destination = output_root / "inflation-comparison/sample.html"
    assert cli.main(["--first-year", "2023", "--second-year", "2024", "--output", str(destination)]) == 0
    html = destination.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "SENTETİK DEMO" in html
    assert "İstenen sıra: 2023 → 2024" in html
    assert "Plotly.newPlot" in html
    assert "synthetic://comparison" in html
    assert len(re.findall(r'<tr data-period="20\d\d-(?:0[1-9]|1[0-2])"', html)) == 24
    assert cli.FIXTURE_PATH.read_bytes() == initial
    assert list(destination.parent.glob("*.tmp")) == []


def test_cli_reverse_order_and_signed_pp(output_root):
    target = output_root / "reverse.html"
    assert cli.main(["--first-year", "2024", "--second-year", "2023", "--output", str(target)]) == 0
    html = target.read_text(encoding="utf-8")
    assert "İstenen sıra: 2024 → 2023" in html
    assert ">-5 yüzde puan<" in html
    assert html.index('data-period="2024-01"') < html.index('data-period="2023-01"')


@pytest.mark.parametrize("years", [
    ("2023", "2023"), ("2022", "2024"), ("2023", "2025"),
    ("0", "2024"), ("10000", "2024"),
])
def test_cli_rejects_invalid_or_unavailable_years_without_output(output_root, years):
    dest = output_root / "bad.html"
    assert cli.main(["--first-year", years[0], "--second-year", years[1], "--output", str(dest)]) == 1
    assert not dest.exists()


def test_cli_refuses_to_replace_existing_report_without_overwrite(output_root):
    target = output_root / "existing.html"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"old report")
    assert cli.main(["--output", str(target)]) == 1
    assert target.read_bytes() == b"old report"
    assert cli.main(["--output", str(target), "--overwrite"]) == 0
    assert target.read_bytes().startswith(b"<!doctype html>")


@pytest.mark.parametrize("relative", [
    "outside.html", "docs/economic-question-comparison-example.json",
])
def test_cli_refuses_targets_outside_out(monkeypatch, output_root, tmp_path, relative):
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"original")
    assert cli.main(["--output", str(target)]) == 1
    assert target.read_bytes() == b"original"


def test_cli_rejects_output_non_html_and_symlink_to_outside(output_root, tmp_path):
    data = tmp_path / "protected.txt"
    data.write_bytes(b"fixture bytes")
    output_root.mkdir()
    malicious_link = output_root / "report.html"
    malicious_link.symlink_to(data)
    assert cli.main(["--output", str(malicious_link), "--overwrite"]) == 1
    assert data.read_bytes() == b"fixture bytes"
    assert cli.main(["--output", str(output_root / "not-html.json")]) == 1


def test_cli_rejects_symlink_in_parent_directories(output_root, tmp_path):
    output_root.mkdir()
    outside = tmp_path / "external"
    outside.mkdir()
    (output_root / "alias").symlink_to(outside, target_is_directory=True)
    assert cli.main(["--output", str(output_root / "alias/escape.html")]) == 1
    assert not (outside / "escape.html").exists()


def test_failed_atomic_replace_preserves_original_and_cleans_temp(output_root, monkeypatch):
    target = output_root / "old.html"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"unchanged")
    def failed_replace(*args):
        raise OSError("simulated atomic failure")
    monkeypatch.setattr(cli.os, "replace", failed_replace)
    assert cli.main(["--output", str(target), "--overwrite"]) == 1
    assert target.read_bytes() == b"unchanged"
    assert not list(output_root.glob("*.tmp"))


def test_failed_exclusive_publication_leaves_no_partial_report(output_root, monkeypatch):
    target = output_root / "new.html"
    def failed_link(*args):
        raise OSError("simulated link failure")
    monkeypatch.setattr(cli.os, "link", failed_link)
    assert cli.main(["--output", str(target)]) == 1
    assert not target.exists()
    assert not list(output_root.glob("*.tmp"))


def test_cli_calls_core_comparison_once(output_root, monkeypatch):
    original = cli.compare_inflation_years
    calls = []
    def counting(frame, **kwargs):
        calls.append((frame.copy(deep=True), kwargs))
        return original(frame, **kwargs)
    monkeypatch.setattr(cli, "compare_inflation_years", counting)
    assert cli.main(["--output", str(output_root / "one.html")]) == 0
    assert len(calls) == 1
    assert calls[0][1] == {
        "first_year": 2023,
        "second_year": 2024,
        "source_ref": "synthetic://comparison",
    }


def test_fixture_bytes_remain_unchanged_after_failure(output_root):
    initial = hashlib.sha256(cli.FIXTURE_PATH.read_bytes()).digest()
    assert cli.main(["--first-year", "2025", "--output", str(output_root / "invalid.html")]) == 1
    assert hashlib.sha256(cli.FIXTURE_PATH.read_bytes()).digest() == initial

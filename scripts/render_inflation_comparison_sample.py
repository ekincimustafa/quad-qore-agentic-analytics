"""Render a key-free, offline two-year CPI comparison from the existing fixture.

All calculations belong to compare_inflation_years; this CLI only validates
its local inputs, creates the report and atomically publishes it under out/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

from app.services.inflation_comparison import compare_inflation_years
from app.tools.inflation_comparison_report import render_inflation_comparison_report

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "out"
FIXTURE_PATH = PROJECT_ROOT / "docs/economic-question-comparison-example.json"


class ComparisonSampleError(ValueError):
    """Unsafe output target or unusable synthetic comparison input."""


def _load_fixture() -> tuple[pd.DataFrame, str]:
    """Read the existing fixture, never rewrite it or download any data."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("inflation"), dict):
        raise ComparisonSampleError("Sentetik karşılaştırma fixture yapısı geçersiz.")
    inflation = data["inflation"]
    rows, source_ref = inflation.get("cpi_monthly"), inflation.get("source_ref")
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
        raise ComparisonSampleError("Sentetik aylık TÜFE kayıtları bulunamadı.")
    if not isinstance(source_ref, str) or not source_ref.startswith("synthetic://"):
        raise ComparisonSampleError("Sentetik kaynak referansı geçersiz.")
    return pd.DataFrame(rows), source_ref


def _require_fixture_years(frame: pd.DataFrame, first: int, second: int) -> None:
    """Check only date coverage, not any CPI values or economic calculations."""
    if not (1 <= first <= 9999 and 1 <= second <= 9999) or first == second:
        raise ComparisonSampleError("İki farklı geçerli yıl seçilmelidir.")
    periods = set(frame["period"])
    for year in (first, second):
        if any(f"{year:04d}-{month:02d}" not in periods for month in range(1, 13)):
            raise ComparisonSampleError(
                f"{year}: sentetik fixture bu yılın 12 ayını içermiyor."
            )


def _safe_output(value: Path) -> Path:
    """Only a normal .html file inside this repository's out/ is writable.

    Reject all symlink components, including an existing output symlink, to
    prevent redirects to fixture/source files or paths outside the repo.
    """
    if OUTPUT_ROOT.is_symlink():
        raise ComparisonSampleError("out klasörü sembolik bağlantı olamaz.")
    output_root = OUTPUT_ROOT.resolve()
    path = Path(os.path.abspath(os.fspath(value)))
    if path == output_root or not path.is_relative_to(output_root):
        raise ComparisonSampleError("Çıktı yalnız bu deponun out/ klasörüne yazılabilir.")
    if path.suffix.lower() != ".html":
        raise ComparisonSampleError("Çıktı uzantısı .html olmalıdır.")
    part = path
    while part != output_root:
        if part.is_symlink():
            raise ComparisonSampleError("Çıktı yolunda sembolik bağlantı kullanılamaz.")
        part = part.parent
    return path


def _write_report(path: Path, html: str, *, overwrite: bool) -> None:
    """Write a complete temporary HTML before atomically publishing it.

    Default publication is an exclusive hard link, so an existing output can
    never be silently overwritten, even in an existence-check race. Explicit
    --overwrite uses atomic os.replace. On failure the existing file survives.
    """
    if path.exists() and not overwrite:
        raise ComparisonSampleError(
            "Çıktı dosyası zaten var; değiştirmek için açıkça --overwrite kullanın."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    _safe_output(path)  # Recheck after creating parent directories.
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".inflation-comparison-", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(html)
            handle.flush()
            os.fsync(handle.fileno())
        _safe_output(path)
        if overwrite:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
    except FileExistsError as exc:
        raise ComparisonSampleError(
            "Çıktı dosyası zaten var; --overwrite olmadan değiştirilmedi."
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="İki yıl TÜFE karşılaştırması: anahtarsız sentetik offline HTML."
    )
    parser.add_argument("--first-year", type=int, default=2023)
    parser.add_argument("--second-year", type=int, default=2024)
    parser.add_argument(
        "--output", type=Path,
        default=OUTPUT_ROOT / "inflation-comparison/sample.html",
        help="Yalnızca depo out/ klasörü altındaki .html yolu.",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Var olan güvenli out/ hedefini atomik olarak değiştir.",
    )
    args = parser.parse_args(argv)

    try:
        target = _safe_output(args.output)
        if target.exists() and not args.overwrite:
            raise ComparisonSampleError(
                "Çıktı zaten var; değiştirmek için --overwrite gerekir."
            )
        frame, source_ref = _load_fixture()
        _require_fixture_years(frame, args.first_year, args.second_year)
        comparison = compare_inflation_years(
            frame,
            first_year=args.first_year,
            second_year=args.second_year,
            source_ref=source_ref,
        )
        html = render_inflation_comparison_report(
            comparison, dataset_kind="synthetic"
        )
        _write_report(target, html, overwrite=args.overwrite)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Sentetik TÜFE karşılaştırma raporu oluşturulamadı: {exc}", file=sys.stderr)
        return 1

    print(f"Sentetik offline karşılaştırma raporu hazır: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

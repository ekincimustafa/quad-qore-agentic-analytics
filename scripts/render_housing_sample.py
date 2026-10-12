"""Generate an explicitly synthetic housing report without network access."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd

from app.services.housing_analysis import HousingAnalysisRun, run_housing_analysis
from app.tools.housing_report import render_housing_report


def build_sample_run() -> HousingAnalysisRun:
    """Exercise the existing service using 60 artificial monthly observations."""
    periods = pd.period_range("2021-01", "2025-12", freq="M").astype(str).tolist()
    bddk = pd.DataFrame({
        "period": periods,
        "nominal_housing_loan_mn_try": [1000.0 + index * 8 for index in range(60)],
    })
    evds = pd.DataFrame({
        "period": periods,
        "housing_loan_interest_rate_pct": [20.0 - (index % 12) * 0.25 for index in range(60)],
        "weekly_observation_count": [4] * 60,
        "cpi_index": [100.0 + index * 1.2 for index in range(60)],
        "housing_price_index": [100.0 + index * 1.5 for index in range(60)],
    })
    return run_housing_analysis(
        bddk, evds, start_period="2021-01", end_period="2025-12",
        bddk_source_ref="synthetic://housing/bddk",
        evds_source_refs="synthetic://housing/interest; synthetic://housing/cpi; synthetic://housing/hpi",
        narrator=None,
    )


def _write_html(path: Path, html: str) -> None:
    """Replace only the report file after the full temporary write succeeds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(html)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sentetik, offline Housing HTML raporu")
    parser.add_argument("--output", type=Path, default=Path("out/housing-sample.html"))
    args = parser.parse_args(argv)
    try:
        run = build_sample_run()
        html = render_housing_report(run, dataset_kind="synthetic")
        _write_html(args.output, html)
    except (OSError, ValueError) as exc:
        print(f"Rapor üretilemedi: {exc}", file=sys.stderr)
        return 1
    print(f"Sentetik rapor hazır: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
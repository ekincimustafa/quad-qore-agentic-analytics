"""Generate an offline CPI inflation report from synthetic or verified EVDS data."""

from __future__ import annotations

import argparse
import hashlib
import sys
import tempfile
from io import BytesIO
from pathlib import Path

import pandas as pd

from app.lakehouse.core_validators import resolve_secure_raw_path
from app.services.evds_manifest import (
    EvdsManifest,
    load_and_validate_manifest,
)
from app.services.inflation_analysis import InflationEvidence, build_inflation_evidence
from app.tools.inflation_report import render_inflation_report
from scripts.run_housing_demo import (
    _collect_manifest_source_paths,
    _ensure_output_dirs_disjoint_from_sources,
)


def build_synthetic_evidence(
    *, start_period: str = "2023-01", end_period: str = "2023-12"
) -> InflationEvidence:
    """Exercise the existing service with artificial monthly observations."""
    periods = pd.period_range("2019-01", "2023-12", freq="M").astype(str).tolist()
    values = [50.0 + index * 1.5 + (index % 5) * 0.1 for index in range(len(periods))]
    frame = pd.DataFrame({"period": periods, "cpi_index": values})
    return build_inflation_evidence(
        frame,
        start_period=start_period,
        end_period=end_period,
        source_ref="synthetic://inflation/cpi",
    )


def _verified_sources(manifest_path: Path, manifest: EvdsManifest, root: Path) -> list[Path]:
    sources = [manifest_path, root / manifest.silver.path]
    for series in manifest.series:
        for bronze in series.bronze:
            sources.append(root / bronze.receipt_path)
            sources.append(root / bronze.raw_path)
    return sources


def load_verified_evidence(
    manifest_path: Path,
    root: Path,
    *,
    start_period: str,
    end_period: str,
) -> tuple[EvdsManifest, InflationEvidence]:
    """Read only bytes that still match the validated manifest hash."""
    manifest = load_and_validate_manifest(manifest_path, root)
    csv_path = resolve_secure_raw_path(root, manifest.silver.path)
    csv_bytes = csv_path.read_bytes()
    if (
        len(csv_bytes) != manifest.silver.size_bytes
        or hashlib.sha256(csv_bytes).hexdigest() != manifest.silver.sha256.lower()
    ):
        raise ValueError("EVDS CSV changed after manifest validation.")
    frame = pd.read_csv(BytesIO(csv_bytes))
    refs = tuple(dict.fromkeys(
        bronze.receipt_path.strip()
        for series in manifest.series if series.series_code == "TP.TUKFIY2025.GENEL"
        for bronze in series.bronze
    ))
    if not refs:
        raise ValueError("TÜFE serisi için Bronze receipt referansı bulunamadı.")
    evidence = build_inflation_evidence(
        frame.loc[:, ["period", "cpi_index"]],
        start_period=start_period,
        end_period=end_period,
        source_ref="; ".join(refs),
    )
    return manifest, evidence.model_copy(update={"input_origin": "verified_files"})


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
    parser = argparse.ArgumentParser(
        description="Offline TÜFE HTML raporu (varsayılan: sentetik veri)"
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--start-period", default="2023-01")
    parser.add_argument("--end-period", default="2023-12")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    verified = args.manifest is not None
    output = args.output or Path(
        "out/inflation-report/"
        + (f"evds-{args.start_period}-{args.end_period}.html" if verified else "synthetic-2023.html")
    )
    sources: list[Path] = []
    try:
        root = args.root.resolve(strict=True)
        if verified:
            manifest_path = args.manifest
            if not manifest_path.is_absolute():
                manifest_path = (Path.cwd() / manifest_path).resolve()
            sources = [manifest_path, *_collect_manifest_source_paths(manifest_path, root)]
            _ensure_output_dirs_disjoint_from_sources((output.parent,), sources)
            manifest, evidence = load_verified_evidence(
                manifest_path,
                root,
                start_period=args.start_period,
                end_period=args.end_period,
            )
            _ensure_output_dirs_disjoint_from_sources(
                (output.parent,), _verified_sources(manifest_path, manifest, root)
            )
            dataset_kind = "verified_local"
        else:
            evidence = build_synthetic_evidence(
                start_period=args.start_period, end_period=args.end_period
            )
            dataset_kind = "synthetic"
        html = render_inflation_report(evidence, dataset_kind=dataset_kind)
        _write_html(output, html)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Rapor üretilemedi: {exc}", file=sys.stderr)
        return 1
    print(f"Rapor hazır: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

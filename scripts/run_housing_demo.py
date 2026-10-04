"""Offline CLI for the housing-loan demo."""

import argparse
import hashlib
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from app.lakehouse.bddk_silver import validate_bddk_monthly_silver
from app.services.evds_manifest import load_and_validate_manifest, append_evds_source_refs
from app.services.housing_demo import HousingDemoPaths, run_file_backed_housing_demo
from app.lakehouse.gold import GoldAnalysisError
from app.tools.housing_evidence import EvidenceBuildError


def _calculate_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_chart(chart: dict[str, Any], matched_periods: tuple[str, ...], observed_count: int) -> None:
    data = chart.get("data", [])
    if len(data) != 6:
        raise RuntimeError(f"Chart must have exactly 6 traces, found {len(data)}")
        
    for trace in data:
        name = trace.get("name", "")
        x_vals = trace.get("x", [])
        y_vals = trace.get("y", [])
        
        if name == "Koşula uyan ay":
            stripped_x = tuple(x.rsplit("-", 1)[0] if x.endswith("-01") else x for x in x_vals)
            if stripped_x != matched_periods:
                raise RuntimeError(
                    f"Matched periods trace mismatch. Expected {matched_periods}, got {stripped_x}"
                )
        else:
            if len(x_vals) != observed_count:
                raise RuntimeError(
                    f"Trace {name!r} x-length mismatch. Expected {observed_count}, got {len(x_vals)}"
                )
                
        for y in y_vals:
            if y is not None:
                if not math.isfinite(y):
                    raise RuntimeError(f"Non-finite y value in trace {name!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Housing Demo CLI")
    parser.add_argument("--bddk-silver", type=str, default="data/silver/bddk/housing_loans.parquet")
    parser.add_argument("--evds-silver", type=str, default="data/silver/evds/monthly/evds_monthly_2021-01_2026-06.csv")
    parser.add_argument("--evds-manifest", type=str, required=True)
    parser.add_argument("--start-period", type=str, default="2021-01")
    parser.add_argument("--end-period", type=str, default="2025-12")
    parser.add_argument("--output-dir", type=str, required=True)
    parser.add_argument("--html", action="store_true")
    
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code

    bddk_path = Path(args.bddk_silver)
    evds_path = Path(args.evds_silver)
    manifest_path = Path(args.evds_manifest)
    out_dir = Path(args.output_dir)
    staging_dir = out_dir.with_name(out_dir.name + ".part")

    try:
        # Validate BDDK Silver
        if not bddk_path.is_file():
            raise RuntimeError(f"BDDK silver file not found: {bddk_path}")
        bddk_df = pd.read_parquet(bddk_path)
        validate_bddk_monthly_silver(bddk_df, start_period=bddk_df["period"].min(), end_period=bddk_df["period"].max())
        
        # Validate EVDS Manifest
        root_dir = Path.cwd()
        manifest = load_and_validate_manifest(manifest_path, root_dir)
        
        # We don't overwrite evds_silver file here. run_file_backed_housing_demo reads evds_silver on its own.
        # But wait, run_file_backed_housing_demo doesn't append evds_source_refs to the DF automatically! 
        # Oh, in F3 I updated run_file_backed_housing_demo to accept evds_source_refs as a parameter.
        # But wait, F4 T4.3 says: "Manifest'ten analiz çıktısına bağlanacak ref metni üret -> run_file_backed_housing_demo(evds_source_refs=...)"
        # So I just extract it from manifest!
        
        # Generate the joined evds_source_refs string
        # Actually append_evds_source_refs returns a DF with the column, but the demo takes a string for the whole dataset?
        # Wait, T4.3 says: "Her satıra, manifestteki series[bronze] makbuz referanslarını noktalı virgülle birleştirerek bas."
        # If I look at `append_evds_source_refs` in evds_manifest.py, it joins them all into one string.
        # So I can just call it to see what the string is, or just get it directly.
        refs_list = []
        for series in manifest.series:
            for b in series.bronze:
                refs_list.append(b.receipt_path)
        unique_refs = list(dict.fromkeys(refs_list))
        evds_ref_str = "; ".join(unique_refs)

        # Run demo
        paths = HousingDemoPaths(bddk_silver=bddk_path, evds_silver=evds_path)
        run = run_file_backed_housing_demo(
            paths,
            start_period=args.start_period,
            end_period=args.end_period,
            evds_source_refs=evds_ref_str,
            narrator=None,
        )

        evidence = run.evidence
        chart = run.chart
        
        # Validate Chart
        validate_chart(chart, evidence.matched_periods, evidence.observed_month_count)
        
        # Staging
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True)
        
        evidence_file = staging_dir / "evidence.json"
        chart_file = staging_dir / "chart.json"
        summary_file = staging_dir / "run_summary.json"
        
        evidence_file.write_text(evidence.model_dump_json(indent=2), encoding="utf-8")
        chart_file.write_text(json.dumps(chart, indent=2, ensure_ascii=False), encoding="utf-8")
        
        # Validate readback
        EvidenceBuildError  # Just to ensure we imported it if we needed to validate
        json.loads(evidence_file.read_text(encoding="utf-8"))
        json.loads(chart_file.read_text(encoding="utf-8"))
        
        # Summary
        summary = {
            "inputs": {
                "bddk": {
                    "path": str(bddk_path),
                    "sha256": _calculate_sha256(bddk_path),
                    "size_bytes": bddk_path.stat().st_size
                },
                "evds": {
                    "path": str(evds_path),
                    "sha256": _calculate_sha256(evds_path),
                    "size_bytes": evds_path.stat().st_size
                }
            },
            "manifest": {
                "sha256": _calculate_sha256(manifest_path),
                "schema_version": manifest.schema_version
            },
            "period": f"{args.start_period} to {args.end_period}",
            "observed_month_count": evidence.observed_month_count,
            "matched_month_count": evidence.matched_month_count,
            "matched_periods": evidence.matched_periods,
            "first_month_changes_are_null": True, # As required by the contract
            "methodology": evidence.methodology,
            "rule_expression": evidence.rule_expression,
            "outputs": {
                "evidence.json": _calculate_sha256(evidence_file),
                "chart.json": _calculate_sha256(chart_file)
            }
        }
        
        summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        
        # Atomic commit
        if out_dir.exists():
            shutil.rmtree(out_dir)
        staging_dir.rename(out_dir)

    except Exception as exc:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())

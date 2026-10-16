"""Offline CLI for the housing-loan demo."""

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from app.lakehouse.bddk_silver import validate_bddk_monthly_silver
from app.services.evds_manifest import load_and_validate_manifest, append_evds_source_refs
from app.services.housing_demo import HousingDemoPaths, run_file_backed_housing_demo
from app.lakehouse.gold import GoldAnalysisError, build_housing_gold_table
from app.tools.housing_evidence import EvidenceBuildError, HousingAnalysisEvidence


_CHART_SERIES = {
    "Nominal konut kredisi": "nominal_housing_loan_mn_try",
    "Reel konut kredisi (2025 fiyatları)": "real_housing_loan_2025_mn_try",
    "Konut kredisi faizi": "housing_loan_interest_rate_pct",
    "TÜFE (2025=100)": "cpi_index",
    "Konut Fiyat Endeksi (2023=100)": "housing_price_index",
}
_CHART_MARKER = "Koşula uyan ay"
_CHART_DATE_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-01$")


def _calculate_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_chart(
    chart: dict[str, Any],
    matched_periods_or_evidence: tuple[str, ...] | HousingAnalysisEvidence,
    observed_count: int | None = None,
    *,
    evidence: HousingAnalysisEvidence | None = None,
    gold_df: pd.DataFrame | None = None,
) -> None:
    if isinstance(matched_periods_or_evidence, HousingAnalysisEvidence):
        evidence = matched_periods_or_evidence
        matched_periods = evidence.matched_periods
        observed_count = evidence.observed_month_count
    else:
        matched_periods = tuple(matched_periods_or_evidence)
        if evidence is not None and observed_count is None:
            observed_count = evidence.observed_month_count

    if not isinstance(chart, dict):
        raise RuntimeError("Chart must be a dictionary.")

    data = chart.get("data", [])
    if not isinstance(data, list) or len(data) != 6:
        raise RuntimeError(
            f"Chart must have exactly 6 traces, found {len(data) if isinstance(data, list) else type(data).__name__}"
        )

    trace_names = [t.get("name") for t in data if isinstance(t, dict)]
    expected_names = set(_CHART_SERIES) | {_CHART_MARKER}
    if len(trace_names) != 6 or len(set(trace_names)) != 6 or set(trace_names) != expected_names:
        raise RuntimeError(
            f"Chart must contain the 6 unique expected traces: {sorted(expected_names)}, got {trace_names}"
        )

    expected_dates: list[str] | None = None
    if evidence is not None:
        periods = pd.period_range(evidence.period_start, evidence.period_end, freq="M")
        expected_dates = [f"{p}-01" for p in periods]
        matches = tuple(row.period for row in evidence.results)
        if (
            len(expected_dates) != evidence.observed_month_count
            or matches != evidence.matched_periods
            or matches != matched_periods
            or len(set(matches)) != len(matches)
            or len(matches) != evidence.matched_month_count
            or not set(matches).issubset(str(p) for p in periods[1:])
        ):
            raise RuntimeError("Evidence period metadata is inconsistent.")

    expected_matched_x = [f"{p}-01" for p in matched_periods]
    trace_maps: dict[str, dict[str, float]] = {}

    for trace in data:
        name = trace["name"]
        x_vals = trace.get("x", [])
        y_vals = trace.get("y", [])

        if not isinstance(x_vals, list) or not isinstance(y_vals, list):
            raise RuntimeError(f"Trace {name!r} x and y must be lists.")

        if len(x_vals) != len(y_vals):
            raise RuntimeError(
                f"Trace {name!r} x/y length mismatch: len(x)={len(x_vals)}, len(y)={len(y_vals)}"
            )

        if any(not isinstance(x, str) or not _CHART_DATE_PATTERN.fullmatch(x) for x in x_vals):
            raise RuntimeError(f"Trace {name!r} contains invalid date format in x.")

        if any(type(y) not in (int, float) or not math.isfinite(y) for y in y_vals):
            raise RuntimeError(f"Trace {name!r} contains non-numeric or non-finite y value.")

        if name == _CHART_MARKER:
            if x_vals != expected_matched_x:
                raise RuntimeError(
                    f"Matched periods trace mismatch. Expected {expected_matched_x}, got {x_vals}"
                )
        else:
            if observed_count is not None and len(x_vals) != observed_count:
                raise RuntimeError(
                    f"Trace {name!r} x-length mismatch. Expected {observed_count}, got {len(x_vals)}"
                )
            if expected_dates is not None:
                if x_vals != expected_dates:
                    raise RuntimeError(
                        f"Trace {name!r} x-dates do not match expected period range."
                    )
            elif x_vals:
                start_p = x_vals[0][:7]
                end_p = x_vals[-1][:7]
                if start_p > end_p:
                    raise RuntimeError(f"Trace {name!r} x-dates are not chronological.")
                contiguous = [
                    f"{p}-01" for p in pd.period_range(start=start_p, end=end_p, freq="M")
                ]
                if x_vals != contiguous:
                    raise RuntimeError(
                        f"Trace {name!r} x-dates do not form a contiguous monthly sequence."
                    )
                expected_dates = contiguous

        trace_maps[name] = dict(zip(x_vals, (float(y) for y in y_vals)))

    if expected_dates is not None and not set(expected_matched_x).issubset(set(expected_dates[1:])):
        raise RuntimeError(
            "Matched periods in chart are not a valid subset of the observed series periods."
        )

    # Cross-check marker trace values against the interest rate trace
    rate_map = trace_maps["Konut kredisi faizi"]
    marker_map = trace_maps[_CHART_MARKER]
    for mx, my in marker_map.items():
        if mx not in rate_map or rate_map[mx] != my:
            raise RuntimeError(
                f"Marker trace {_CHART_MARKER!r} value at {mx} ({my}) does not match "
                f"'Konut kredisi faizi' trace value ({rate_map.get(mx)})."
            )

    # Cross-check all traces against evidence results
    if evidence is not None:
        for row in evidence.results:
            date_key = f"{row.period}-01"
            for trace_name, values in trace_maps.items():
                field = (
                    "housing_loan_interest_rate_pct"
                    if trace_name == _CHART_MARKER
                    else _CHART_SERIES[trace_name]
                )
                expected_val = getattr(row, field)
                if date_key not in values or values[date_key] != expected_val:
                    raise RuntimeError(
                        f"Trace {trace_name!r} value at {row.period} ({values.get(date_key)}) "
                        f"does not match evidence ({expected_val})."
                    )

    # Cross-check all 5 series traces across all observed months against Gold table
    if gold_df is not None:
        sorted_gold = gold_df.sort_values("period").reset_index(drop=True)
        for trace_name, col_name in _CHART_SERIES.items():
            values = trace_maps[trace_name]
            for period_val, expected_val in zip(sorted_gold["period"], sorted_gold[col_name]):
                date_key = f"{period_val}-01"
                if date_key not in values or values[date_key] != float(expected_val):
                    raise RuntimeError(
                        f"Trace {trace_name!r} value at {period_val} ({values.get(date_key)}) "
                        f"does not match Gold table ({expected_val})."
                    )


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
    backup_dir = out_dir.with_name(f"{out_dir.name}.backup")

    try:
        # Validate BDDK Silver
        if not bddk_path.is_file():
            raise RuntimeError(f"BDDK silver file not found: {bddk_path}")
        bddk_df = pd.read_parquet(bddk_path)
        validate_bddk_monthly_silver(bddk_df, start_period=bddk_df["period"].min(), end_period=bddk_df["period"].max())

        # Validate EVDS Manifest
        root_dir = Path.cwd()
        manifest = load_and_validate_manifest(manifest_path, root_dir)

        # Verify --evds-silver resolves to the exact same file as declared in the manifest
        if not evds_path.is_file():
            raise RuntimeError(f"EVDS silver file not found: {evds_path}")
        manifest_csv_resolved = (root_dir / manifest.silver.path).resolve()
        if evds_path.resolve() != manifest_csv_resolved:
            raise RuntimeError(
                f"--evds-silver path ({evds_path.resolve()}) does not match manifest declared path ({manifest_csv_resolved})"
            )
        evds_sha256 = _calculate_sha256(evds_path)
        if evds_sha256.lower() != manifest.silver.sha256.lower():
            raise RuntimeError(
                f"--evds-silver hash ({evds_sha256}) does not match manifest hash ({manifest.silver.sha256})"
            )

        # Generate the joined evds_source_refs string from manifest
        refs_list = []
        for series in manifest.series:
            for b in series.bronze:
                if b.receipt_path and b.receipt_path.strip():
                    refs_list.append(b.receipt_path.strip())
        unique_refs = list(dict.fromkeys(refs_list))
        if not unique_refs:
            raise RuntimeError("Manifest contains no bronze receipt paths to establish provenance.")
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

        # Validate Chart against full evidence and Gold calculations
        evds_df = pd.read_csv(evds_path)
        gold_df = build_housing_gold_table(
            bddk_df,
            evds_df,
            start_period=args.start_period,
            end_period=args.end_period,
            evds_source_refs=evds_ref_str,
        )
        validate_chart(
            chart,
            evidence.matched_periods,
            evidence.observed_month_count,
            evidence=evidence,
            gold_df=gold_df,
        )

        # Staging
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True)

        evidence_file = staging_dir / "evidence.json"
        chart_file = staging_dir / "chart.json"
        summary_file = staging_dir / "run_summary.json"

        evidence_file.write_text(evidence.model_dump_json(indent=2), encoding="utf-8")
        chart_file.write_text(json.dumps(chart, indent=2, ensure_ascii=False), encoding="utf-8")

        # Validate readback: verify exact content equality with in-memory objects
        read_evidence_json = json.loads(evidence_file.read_text(encoding="utf-8"))
        expected_evidence_json = json.loads(evidence.model_dump_json())
        if read_evidence_json != expected_evidence_json:
            raise RuntimeError("Read-back verification failed for evidence.json: content mismatch.")

        read_chart_json = json.loads(chart_file.read_text(encoding="utf-8"))
        if read_chart_json != chart:
            raise RuntimeError("Read-back verification failed for chart.json: content mismatch.")

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
            "matched_periods": list(evidence.matched_periods),
            "first_month_changes_are_null": True, # As required by the contract
            "methodology": evidence.methodology,
            "rule_expression": evidence.rule_expression,
            "outputs": {
                "evidence.json": _calculate_sha256(evidence_file),
                "chart.json": _calculate_sha256(chart_file)
            }
        }

        summary_payload = json.dumps(summary, indent=2, ensure_ascii=False)
        summary_file.write_text(summary_payload, encoding="utf-8")
        read_summary_json = json.loads(summary_file.read_text(encoding="utf-8"))
        expected_summary_json = json.loads(summary_payload)
        if read_summary_json != expected_summary_json:
            raise RuntimeError("Read-back verification failed for run_summary.json: content mismatch.")

        # Transactional publishing: never delete an intact backup before the new output is published
        if out_dir.exists():
            if backup_dir.exists():
                raise RuntimeError(
                    f"Cannot overwrite {out_dir}: an unrecovered backup directory ({backup_dir}) already exists."
                )
            out_dir.rename(backup_dir)

        try:
            staging_dir.rename(out_dir)
        except Exception:
            if backup_dir.exists() and not out_dir.exists():
                try:
                    backup_dir.rename(out_dir)
                except Exception:
                    try:
                        os.replace(backup_dir, out_dir)
                    except Exception:
                        pass
            raise
        else:
            if backup_dir.exists():
                shutil.rmtree(backup_dir, ignore_errors=True)

    except Exception as exc:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        if backup_dir.exists() and not out_dir.exists():
            try:
                backup_dir.rename(out_dir)
            except Exception:
                try:
                    os.replace(backup_dir, out_dir)
                except Exception:
                    pass
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())

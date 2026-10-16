"""CLI script to build the BDDK Silver housing loan dataset.

Usage:
    python -m scripts.build_bddk_silver [--start-period YYYY-MM] [--end-period YYYY-MM] [--output PATH] [--demo]

Exit Code:
    0 on success.
    1 on failure (e.g., validation errors, missing data, integrity issues).
"""

import argparse
import hashlib
import sys
from pathlib import Path

from app.lakehouse.bddk_silver import (
    DEFAULT_END_PERIOD,
    DEFAULT_START_PERIOD,
    DEMO_END_PERIOD,
    SilverDataError,
    build_bddk_monthly_silver_table,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build BDDK Silver housing loan parquet table.")
    parser.add_argument("--start-period", type=str, default=DEFAULT_START_PERIOD, help="Start period (YYYY-MM)")
    parser.add_argument("--end-period", type=str, default=DEFAULT_END_PERIOD, help="End period (YYYY-MM)")
    parser.add_argument("--output", type=Path, default=Path("data/silver/bddk/housing_loans.parquet"), help="Output parquet path")
    parser.add_argument("--demo", action="store_true", help="Use demo scope (ends at 2025-12)")

    args = parser.parse_args()

    start_period = args.start_period
    end_period = DEMO_END_PERIOD if args.demo else args.end_period
    output_path: Path = args.output

    receipts_dir = Path("data/bronze/bddk/aylik/receipts")
    raw_dir = Path("data/bronze/bddk/aylik/raw")

    print("=" * 65)
    print("BDDK SILVER DATASET BUILDER")
    print("=" * 65)
    print(f"Target Scope : {start_period} to {end_period}")
    print(f"Bronze Src   : {receipts_dir}")
    print(f"Output Path  : {output_path}")
    print("-" * 65)

    try:
        df = build_bddk_monthly_silver_table(
            receipts_dir=receipts_dir,
            raw_dir=raw_dir,
            start_period=start_period,
            end_period=end_period,
        )
    except SilverDataError as e:
        print(f"\n[FAIL-CLOSED ERROR] Silver data generation failed:\n{e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}", file=sys.stderr)
        return 1

    # Ensure output directory exists
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"\n[FAIL-CLOSED ERROR] Cannot create output directory {output_path.parent}: {e}", file=sys.stderr)
        return 1

    # --- Atomic Parquet write ---
    # Pattern: write to temp .part file → read-back verify → SHA-256 → atomically replace.
    # If anything fails mid-write, the existing valid output is never touched.
    tmp_path = output_path.with_suffix(".part")
    try:
        df.to_parquet(tmp_path, index=False)

        import pandas as _pd
        import pandas.testing as pdt
        verified = _pd.read_parquet(tmp_path)
        try:
            # check_exact=True: financial values must match exactly — approximate equality not acceptable.
            pdt.assert_frame_equal(df, verified, check_dtype=True, check_exact=True)
        except AssertionError as e:
            raise RuntimeError(f"Parquet read-back content mismatch: {e}")

        # Compute SHA-256 from the temp file *before* replacing the destination.
        # This ensures the hash reflects what was actually written, not a stale read.
        try:
            sha256_hash = hashlib.sha256(tmp_path.read_bytes()).hexdigest()
        except OSError as e:
            raise RuntimeError(f"Failed to compute SHA-256 of temp file: {e}")

        # If all checks pass, atomically move temp file to final destination.
        tmp_path.replace(output_path)

    except Exception as e:
        # Clean up temp file if it exists, leave old output untouched
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        print(f"\n[FAIL-CLOSED ERROR] Parquet write/verify failed:\n{e}", file=sys.stderr)
        return 1

    print("[SUCCESS] Built Silver dataset.")
    print(f"Rows        : {len(df)}")
    print(f"Period      : {df['period'].min()} .. {df['period'].max()}")
    print(f"SHA-256     : {sha256_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write parquet
    df.to_parquet(output_path, index=False)
    
    # Calculate SHA-256 of the generated parquet
    file_bytes = output_path.read_bytes()
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    print("[SUCCESS] Built Silver dataset.")
    print(f"Rows        : {len(df)}")
    print(f"Period      : {df['period'].min()} .. {df['period'].max()}")
    print(f"SHA-256     : {sha256_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

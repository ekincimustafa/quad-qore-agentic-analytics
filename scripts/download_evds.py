"""Run with python -m scripts.download_evds --help."""

from __future__ import annotations

import argparse
import calendar
import json
from datetime import date
from pathlib import Path

from app.connectors.evds import (
    EVDS_SERIES_FREQUENCIES,
    EvdsClient,
    store_raw_response_in_bronze,
)
from app.lakehouse.bronze import BronzeStore
from app.lakehouse.layout import LakehouseLayout


def _parse_period(value: str) -> tuple[int, int]:
    parts = value.split("-")

    if (
        len(parts) != 2
        or len(parts[0]) != 4
        or len(parts[1]) != 2
        or not parts[0].isdigit()
        or not parts[1].isdigit()
    ):
        raise argparse.ArgumentTypeError(
            f"Invalid period {value!r}; expected YYYY-MM."
        )

    year = int(parts[0])
    month = int(parts[1])

    if month < 1 or month > 12:
        raise argparse.ArgumentTypeError(
            f"Invalid period {value!r}; expected YYYY-MM."
        )

    return year, month


def _period_start(period: tuple[int, int]) -> date:
    year, month = period
    return date(year, month, 1)


def _period_end(period: tuple[int, int]) -> date:
    year, month = period
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def run(
    *,
    start_period: tuple[int, int],
    end_period: tuple[int, int],
    data_root: Path,
    client: EvdsClient | None = None,
) -> int:
    start_date = _period_start(start_period)
    end_date = _period_end(end_period)

    if start_date > end_date:
        raise ValueError(
            "start-period must be less than or equal to end-period."
        )

    layout = LakehouseLayout(data_root)
    store = BronzeStore(layout)
    selected_client = client or EvdsClient()

    results = []
    failed = False

    for series_code, frequency in EVDS_SERIES_FREQUENCIES.items():
        try:
            raw = selected_client.download_series(
                series_code,
                start_date,
                end_date,
            )

            stored = store_raw_response_in_bronze(
                raw,
                store,
            )

            results.append(
                {
                    "series": series_code,
                    "frequency": frequency,
                    "status": "ok",
                    "period": (
                        f"{start_date.isoformat()}/"
                        f"{end_date.isoformat()}"
                    ),
                    "bronze_path": str(stored.asset.path),
                    "receipt_path": str(stored.receipt_path),
                    "sha256": stored.asset.sha256,
                    "size_bytes": stored.asset.size_bytes,
                }
            )

        except Exception as exc:
            failed = True

            results.append(
                {
                    "series": series_code,
                    "frequency": frequency,
                    "status": "failed",
                    "period": (
                        f"{start_date.isoformat()}/"
                        f"{end_date.isoformat()}"
                    ),
                    "error": (
                        f"{type(exc).__name__}: {exc}"
                    ),
                }
            )

    print(
        json.dumps(
            {
                "start_period": (
                    f"{start_period[0]:04d}-"
                    f"{start_period[1]:02d}"
                ),
                "end_period": (
                    f"{end_period[0]:04d}-"
                    f"{end_period[1]:02d}"
                ),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 1 if failed else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "TCMB EVDS serilerini değişmeden Bronze katmanına indir."
        )
    )

    parser.add_argument(
        "--start-period",
        type=_parse_period,
        default=_parse_period("2021-01"),
        help="Başlangıç ayı, YYYY-MM. Varsayılan: 2021-01",
    )

    parser.add_argument(
        "--end-period",
        type=_parse_period,
        default=_parse_period("2026-06"),
        help="Bitiş ayı, YYYY-MM. Varsayılan: 2026-06",
    )

    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("data"),
        help="Lakehouse kök klasörü. Varsayılan: data",
    )

    args = parser.parse_args(argv)

    try:
        return run(
            start_period=args.start_period,
            end_period=args.end_period,
            data_root=args.data_root,
        )
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

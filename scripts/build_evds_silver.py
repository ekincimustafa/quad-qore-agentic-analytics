"""Run with python -m scripts.build_evds_silver --help."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.connectors.evds import (
    EVDS_SERIES_FREQUENCIES,
    EvdsClient,
    store_raw_response_in_bronze,
)
from app.lakehouse.bronze import (
    BronzeStore,
    calculate_sha256,
)
from app.lakehouse.evds_pipeline import (
    build_evds_silver_from_bronze,
)
from app.lakehouse.layout import (
    DataLayer,
    LakehouseLayout,
)
from scripts.download_evds import (
    _parse_period,
    _period_end,
    _period_start,
)


SERIES_DATASETS = {
    "TP.KTF12": "tp_ktf12",
    "TP.TUKFIY2025.GENEL": "tp_tukfiy2025_genel",
    "TP.KFE.TR": "tp_kfe_tr",
}


def _resolve_raw_path(
    data_root: Path,
    raw_path: str,
) -> Path:
    root = data_root.resolve()
    candidate = (data_root / raw_path).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "EVDS receipt points outside the lakehouse root."
        ) from exc

    return candidate


def _find_bronze_for_request(
    *,
    data_root: Path,
    series_code: str,
    request_start: str,
    request_end: str,
) -> Path | None:
    dataset = SERIES_DATASETS[series_code]

    receipts_dir = (
        data_root
        / "bronze"
        / "evds"
        / dataset
        / "receipts"
    )

    if not receipts_dir.exists():
        return None

    expected_frequency = EVDS_SERIES_FREQUENCIES[
        series_code
    ]

    matches = []

    for receipt_path in sorted(
        receipts_dir.glob("*.json")
    ):
        try:
            receipt = json.loads(
                receipt_path.read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Invalid EVDS receipt: {receipt_path}"
            ) from exc

        if not isinstance(receipt, dict):
            raise ValueError(
                f"Invalid EVDS receipt: {receipt_path}"
            )

        required = {
            "series_code",
            "frequency",
            "request_start",
            "request_end",
            "downloaded_at",
            "sha256",
            "size_bytes",
            "raw_path",
        }

        missing = required.difference(receipt)

        if missing:
            raise ValueError(
                "EVDS receipt is missing fields "
                f"{sorted(missing)}: {receipt_path}"
            )

        if (
            receipt["series_code"] != series_code
            or receipt["frequency"]
            != expected_frequency
            or receipt["request_start"]
            != request_start
            or receipt["request_end"]
            != request_end
        ):
            continue

        raw_path = _resolve_raw_path(
            data_root,
            receipt["raw_path"],
        )

        if not raw_path.is_file():
            raise ValueError(
                "EVDS receipt points to a missing "
                f"Bronze file: {raw_path}"
            )

        actual_sha = calculate_sha256(
            raw_path
        )

        if actual_sha != receipt["sha256"]:
            raise ValueError(
                "EVDS Bronze SHA256 does not match "
                f"its receipt: {raw_path}"
            )

        actual_size = raw_path.stat().st_size

        if actual_size != receipt["size_bytes"]:
            raise ValueError(
                "EVDS Bronze size does not match "
                f"its receipt: {raw_path}"
            )

        matches.append(
            (
                str(receipt["downloaded_at"]),
                str(receipt_path),
                raw_path,
            )
        )

    if not matches:
        return None

    matches.sort()

    return matches[-1][2]


def _find_or_download(
    *,
    data_root: Path,
    store: BronzeStore,
    series_code: str,
    start_date,
    end_date,
    client: EvdsClient | None,
) -> Path:
    request_start = start_date.isoformat()
    request_end = end_date.isoformat()

    existing = _find_bronze_for_request(
        data_root=data_root,
        series_code=series_code,
        request_start=request_start,
        request_end=request_end,
    )

    if existing is not None:
        return existing

    selected_client = client or EvdsClient()

    raw = selected_client.download_series(
        series_code,
        start_date,
        end_date,
    )

    stored = store_raw_response_in_bronze(
        raw,
        store,
    )

    return stored.asset.path


def run(
    *,
    start_period: tuple[int, int],
    end_period: tuple[int, int],
    data_root: Path,
    output_path: Path | None = None,
    client: EvdsClient | None = None,
) -> int:
    start_date = _period_start(start_period)
    end_date = _period_end(end_period)

    if start_date > end_date:
        raise ValueError(
            "start-period must be less than or equal "
            "to end-period."
        )

    start_text = (
        f"{start_period[0]:04d}-"
        f"{start_period[1]:02d}"
    )

    end_text = (
        f"{end_period[0]:04d}-"
        f"{end_period[1]:02d}"
    )

    layout = LakehouseLayout(data_root)
    store = BronzeStore(layout)

    bronze_paths = {}

    for series_code in EVDS_SERIES_FREQUENCIES:
        bronze_paths[series_code] = (
            _find_or_download(
                data_root=data_root,
                store=store,
                series_code=series_code,
                start_date=start_date,
                end_date=end_date,
                client=client,
            )
        )

    if output_path is None:
        output_path = layout.asset_path(
            layer=DataLayer.SILVER,
            source="evds",
            dataset="monthly",
            filename=(
                f"evds_monthly_"
                f"{start_text}_{end_text}.csv"
            ),
        )

    result = build_evds_silver_from_bronze(
        housing_rate_path=bronze_paths[
            "TP.KTF12"
        ],
        cpi_path=bronze_paths[
            "TP.TUKFIY2025.GENEL"
        ],
        housing_price_path=bronze_paths[
            "TP.KFE.TR"
        ],
        output_path=output_path,
        start_period=start_text,
        end_period=end_text,
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "path": str(result.path),
                "rows": result.row_count,
                "start_period": result.start_period,
                "end_period": result.end_period,
                "sha256": result.sha256,
                "bronze": {
                    series: str(path)
                    for series, path
                    in bronze_paths.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "EVDS Bronze verilerinden doğrulanmış "
            "aylık Silver veri seti üret."
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

    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Silver CSV hedefi. Verilmezse lakehouse "
            "altında otomatik oluşturulur."
        ),
    )

    args = parser.parse_args(argv)

    try:
        return run(
            start_period=args.start_period,
            end_period=args.end_period,
            data_root=args.data_root,
            output_path=args.output,
        )
    except Exception as exc:
        print(
            f"{type(exc).__name__}: {exc}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

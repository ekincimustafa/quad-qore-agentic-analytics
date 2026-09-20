from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

import pandas as pd

from app.lakehouse.evds_adapter import load_evds_bronze_file
from app.lakehouse.silver import (
    merge_monthly_evds_series,
    monthly_cpi_index,
    monthly_housing_loan_interest_rate,
    monthly_housing_price_index,
    validate_monthly_evds_data,
)


@dataclass(frozen=True)
class EvdsSilverBuildResult:
    path: Path
    row_count: int
    start_period: str
    end_period: str
    sha256: str


def _parse_period(value: str) -> pd.Period:
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError(
            f"Invalid monthly period: {value}. Expected YYYY-MM."
        )

    try:
        return pd.Period(value, freq="M")
    except ValueError as exc:
        raise ValueError(
            f"Invalid monthly period: {value}."
        ) from exc


def build_evds_silver_from_bronze(
    *,
    housing_rate_path: str | Path,
    cpi_path: str | Path,
    housing_price_path: str | Path,
    output_path: str | Path,
    start_period: str = "2021-01",
    end_period: str = "2026-06",
) -> EvdsSilverBuildResult:
    """
    Build the validated monthly EVDS Silver dataset from unchanged
    Bronze API responses.

    API representation is adapted by evds_adapter.py.
    Analytical rules remain in silver.py.
    """

    start = _parse_period(start_period)
    end = _parse_period(end_period)

    if start > end:
        raise ValueError(
            "start_period must be less than or equal to end_period."
        )

    start_date = start.start_time.date().isoformat()
    end_date = end.end_time.date().isoformat()

    housing_rate_raw = load_evds_bronze_file(
        housing_rate_path,
        "TP.KTF12",
    )

    cpi_raw = load_evds_bronze_file(
        cpi_path,
        "TP.TUKFIY2025.GENEL",
    )

    housing_price_raw = load_evds_bronze_file(
        housing_price_path,
        "TP.KFE.TR",
    )

    housing_rate = monthly_housing_loan_interest_rate(
        housing_rate_raw,
        start_date=start_date,
        end_date=end_date,
    )

    cpi = monthly_cpi_index(
        cpi_raw,
        start_period=start_period,
        end_period=end_period,
    )

    housing_price = monthly_housing_price_index(
        housing_price_raw,
        start_period=start_period,
        end_period=end_period,
    )

    merged = merge_monthly_evds_series(
        housing_rate,
        cpi,
        housing_price,
    )

    validate_monthly_evds_data(
        merged,
        start_period=start_period,
        end_period=end_period,
    )

    output = Path(output_path)
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_bytes = merged.to_csv(
        index=False,
        lineterminator="\n",
    ).encode("utf-8")

    digest = sha256(csv_bytes).hexdigest()

    if not output.exists() or output.read_bytes() != csv_bytes:
        temporary = output.with_suffix(
            output.suffix + ".part"
        )

        temporary.write_bytes(csv_bytes)
        temporary.replace(output)

    return EvdsSilverBuildResult(
        path=output,
        row_count=len(merged),
        start_period=str(merged["period"].iloc[0]),
        end_period=str(merged["period"].iloc[-1]),
        sha256=digest,
    )

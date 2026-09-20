"""File-backed orchestration for the first housing-loan demo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.lakehouse.gold import DEFAULT_END_PERIOD, DEFAULT_START_PERIOD
from app.services.housing_analysis import (
    HousingAnalysisRun,
    HousingNarrator,
    run_housing_analysis,
)


DEFAULT_BDDK_SILVER_PATH = Path(
    "data/silver/bddk/housing_loans.parquet"
)
DEFAULT_EVDS_SILVER_PATH = Path(
    "data/silver/evds/monthly/evds_monthly_2021-01_2026-06.csv"
)
DEFAULT_BDDK_SOURCE_REF = (
    "BDDK monthly bulletin, Table 4, sector 10001, TL"
)
DEFAULT_EVDS_SOURCE_REFS = (
    "TP.KTF12; TP.TUKFIY2025.GENEL; TP.KFE.TR"
)


class HousingDemoDataError(RuntimeError):
    """Raised when a configured Silver artifact cannot be loaded safely."""


@dataclass(frozen=True, slots=True)
class HousingDemoPaths:
    """Server-controlled Silver inputs used by the first demo."""

    bddk_silver: Path = DEFAULT_BDDK_SILVER_PATH
    evds_silver: Path = DEFAULT_EVDS_SILVER_PATH


def _load_silver_table(path: Path, *, dataset_name: str) -> pd.DataFrame:
    """Load one supported Silver artifact without silently changing it."""

    candidate = Path(path)
    if not candidate.is_file():
        raise HousingDemoDataError(
            f"{dataset_name} Silver file was not found: {candidate}"
        )

    suffix = candidate.suffix.casefold()
    try:
        if suffix == ".parquet":
            frame = pd.read_parquet(candidate)
        elif suffix == ".csv":
            frame = pd.read_csv(candidate)
        else:
            raise HousingDemoDataError(
                f"{dataset_name} Silver file must be CSV or Parquet; "
                f"received: {candidate.name}"
            )
    except HousingDemoDataError:
        raise
    except Exception as exc:
        raise HousingDemoDataError(
            f"{dataset_name} Silver file could not be read: {candidate}"
        ) from exc

    if frame.empty:
        raise HousingDemoDataError(
            f"{dataset_name} Silver file is empty: {candidate}"
        )
    return frame


def run_file_backed_housing_demo(
    paths: HousingDemoPaths,
    *,
    start_period: str = DEFAULT_START_PERIOD,
    end_period: str = DEFAULT_END_PERIOD,
    narrator: HousingNarrator | None = None,
) -> HousingAnalysisRun:
    """Load verified Silver artifacts and execute the existing analysis service."""

    if not isinstance(paths, HousingDemoPaths):
        raise TypeError("paths must be a HousingDemoPaths instance.")

    bddk_monthly = _load_silver_table(
        paths.bddk_silver,
        dataset_name="BDDK",
    )
    evds_monthly = _load_silver_table(
        paths.evds_silver,
        dataset_name="EVDS",
    )

    return run_housing_analysis(
        bddk_monthly,
        evds_monthly,
        start_period=start_period,
        end_period=end_period,
        bddk_source_ref=DEFAULT_BDDK_SOURCE_REF,
        evds_source_refs=DEFAULT_EVDS_SOURCE_REFS,
        narrator=narrator,
    )

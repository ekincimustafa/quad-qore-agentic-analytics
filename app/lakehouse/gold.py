"""Deterministic Gold-layer calculations for the housing-loan demo."""

from __future__ import annotations

import re
from collections.abc import Iterable

import pandas as pd


DEFAULT_START_PERIOD = "2021-01"
DEFAULT_END_PERIOD = "2025-12"

BDDK_REQUIRED_COLUMNS = (
    "period",
    "nominal_housing_loan_mn_try",
)

EVDS_REQUIRED_COLUMNS = (
    "period",
    "housing_loan_interest_rate_pct",
    "weekly_observation_count",
    "cpi_index",
    "housing_price_index",
)

GOLD_COLUMNS = (
    "period",
    "nominal_housing_loan_mn_try",
    "real_housing_loan_2025_mn_try",
    "nominal_housing_loan_change_pct",
    "real_housing_loan_change_pct",
    "housing_loan_interest_rate_pct",
    "weekly_observation_count",
    "interest_rate_change_pp",
    "cpi_index",
    "housing_price_index",
    "rate_down_real_credit_not_up",
    "bddk_source_ref",
    "evds_source_refs",
    "data_quality_note",
)

_PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class GoldAnalysisError(ValueError):
    """Raised when Silver inputs cannot produce a trustworthy Gold table."""


def _validate_period(period: str, field_name: str) -> str:
    value = str(period).strip()
    if not _PERIOD_PATTERN.fullmatch(value):
        raise GoldAnalysisError(
            f"{field_name} must use YYYY-MM format; received {period!r}."
        )
    return value


def _expected_periods(start_period: str, end_period: str) -> list[str]:
    start = _validate_period(start_period, "start_period")
    end = _validate_period(end_period, "end_period")

    if start > end:
        raise GoldAnalysisError("start_period cannot be later than end_period.")

    return pd.period_range(start=start, end=end, freq="M").astype(str).tolist()


def _prepare_period_frame(
    frame: pd.DataFrame,
    *,
    frame_name: str,
    required_columns: tuple[str, ...],
    expected_periods: list[str],
) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise GoldAnalysisError(f"{frame_name} must be a pandas DataFrame.")

    missing_columns = sorted(set(required_columns).difference(frame.columns))
    if missing_columns:
        raise GoldAnalysisError(
            f"{frame_name} is missing required columns: {missing_columns}."
        )

    result = frame.loc[:, list(required_columns)].copy()
    result["period"] = result["period"].astype("string").str.strip()

    invalid_periods = result.loc[
        result["period"].isna()
        | ~result["period"].str.fullmatch(_PERIOD_PATTERN.pattern, na=False),
        "period",
    ].tolist()
    if invalid_periods:
        raise GoldAnalysisError(
            f"{frame_name} contains invalid periods: {invalid_periods[:5]}."
        )

    expected_set = set(expected_periods)
    result = result[result["period"].isin(expected_set)].copy()

    duplicate_periods = sorted(
        result.loc[result["period"].duplicated(keep=False), "period"].unique()
    )
    if duplicate_periods:
        raise GoldAnalysisError(
            f"{frame_name} contains duplicate periods: {duplicate_periods[:5]}."
        )

    actual_set = set(result["period"])
    missing_periods = [period for period in expected_periods if period not in actual_set]
    if missing_periods:
        raise GoldAnalysisError(
            f"{frame_name} is missing periods: {missing_periods[:10]}."
        )

    return result.sort_values("period").reset_index(drop=True)


def _require_numeric(
    frame: pd.DataFrame,
    columns: Iterable[str],
    *,
    frame_name: str,
    strictly_positive: Iterable[str] = (),
) -> None:
    positive_columns = set(strictly_positive)

    for column in columns:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        invalid = numeric.isna() | numeric.isin([float("inf"), float("-inf")])
        if invalid.any():
            periods = frame.loc[invalid, "period"].tolist()
            raise GoldAnalysisError(
                f"{frame_name}.{column} contains missing or non-numeric values "
                f"for periods: {periods[:5]}."
            )

        if column in positive_columns:
            invalid_range = numeric <= 0
            requirement = "greater than zero"
        else:
            invalid_range = numeric < 0
            requirement = "non-negative"

        if invalid_range.any():
            periods = frame.loc[invalid_range, "period"].tolist()
            raise GoldAnalysisError(
                f"{frame_name}.{column} must be {requirement}; invalid periods: "
                f"{periods[:5]}."
            )

        frame[column] = numeric.astype(float)


def build_housing_gold_table(
    bddk_monthly: pd.DataFrame,
    evds_monthly: pd.DataFrame,
    *,
    start_period: str = DEFAULT_START_PERIOD,
    end_period: str = DEFAULT_END_PERIOD,
    bddk_source_ref: str = "BDDK monthly bulletin, Table 4, sector 10001, TL",
    evds_source_refs: str = (
        "TP.KTF12; TP.TUKFIY2025.GENEL; TP.KFE.TR"
    ),
) -> pd.DataFrame:
    """Build the deterministic monthly Gold table defined by the demo contract.

    Missing and duplicate periods are rejected. No interpolation or silent
    imputation is performed.
    """

    expected_periods = _expected_periods(start_period, end_period)

    bddk = _prepare_period_frame(
        bddk_monthly,
        frame_name="bddk_monthly",
        required_columns=BDDK_REQUIRED_COLUMNS,
        expected_periods=expected_periods,
    )
    evds = _prepare_period_frame(
        evds_monthly,
        frame_name="evds_monthly",
        required_columns=EVDS_REQUIRED_COLUMNS,
        expected_periods=expected_periods,
    )

    _require_numeric(
        bddk,
        ["nominal_housing_loan_mn_try"],
        frame_name="bddk_monthly",
    )
    _require_numeric(
        evds,
        [
            "housing_loan_interest_rate_pct",
            "weekly_observation_count",
            "cpi_index",
            "housing_price_index",
        ],
        frame_name="evds_monthly",
        strictly_positive=(
            "weekly_observation_count",
            "cpi_index",
            "housing_price_index",
        ),
    )

    observation_counts = evds["weekly_observation_count"]
    if (observation_counts % 1 != 0).any():
        periods = evds.loc[observation_counts % 1 != 0, "period"].tolist()
        raise GoldAnalysisError(
            "evds_monthly.weekly_observation_count must contain whole numbers; "
            f"invalid periods: {periods[:5]}."
        )
    evds["weekly_observation_count"] = observation_counts.astype("int64")

    gold = bddk.merge(
        evds,
        on="period",
        how="inner",
        validate="one_to_one",
    ).sort_values("period").reset_index(drop=True)

    if gold["period"].tolist() != expected_periods:
        raise GoldAnalysisError("Merged Gold table does not match the requested period range.")

    gold["real_housing_loan_2025_mn_try"] = (
        gold["nominal_housing_loan_mn_try"] * 100.0 / gold["cpi_index"]
    )
    gold["nominal_housing_loan_change_pct"] = (
        gold["nominal_housing_loan_mn_try"].pct_change(fill_method=None) * 100.0
    )
    gold["real_housing_loan_change_pct"] = (
        gold["real_housing_loan_2025_mn_try"].pct_change(fill_method=None) * 100.0
    )
    gold["interest_rate_change_pp"] = (
        gold["housing_loan_interest_rate_pct"].diff()
    )

    condition = (
        (gold["interest_rate_change_pp"] < 0)
        & (gold["real_housing_loan_change_pct"] <= 0)
    ).astype("boolean")
    condition.iloc[0] = pd.NA
    gold["rate_down_real_credit_not_up"] = condition

    gold["bddk_source_ref"] = str(bddk_source_ref)
    gold["evds_source_refs"] = str(evds_source_refs)
    gold["data_quality_note"] = "validated: complete, unique, non-null"

    return gold.loc[:, list(GOLD_COLUMNS)]


def find_rate_down_real_credit_not_up(
    gold_table: pd.DataFrame,
) -> pd.DataFrame:
    """Return only months matching the first demo's deterministic condition."""

    required = {"period", "rate_down_real_credit_not_up"}
    missing = sorted(required.difference(gold_table.columns))
    if missing:
        raise GoldAnalysisError(
            f"gold_table is missing required columns: {missing}."
        )

    mask = gold_table["rate_down_real_credit_not_up"].fillna(False).astype(bool)
    return gold_table.loc[mask].copy().reset_index(drop=True)

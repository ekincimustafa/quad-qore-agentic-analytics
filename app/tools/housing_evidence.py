"""Verified evidence payloads for the first housing-loan demo."""

from __future__ import annotations

import math
import re
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict

from app.lakehouse.gold import DEFAULT_END_PERIOD, DEFAULT_START_PERIOD


ANALYSIS_ID = "housing_rate_down_real_credit_not_up"
RULE_EXPRESSION = (
    "interest_rate_change_pp < 0 AND real_housing_loan_change_pct <= 0"
)

REQUIRED_COLUMNS = (
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
_CHANGE_COLUMNS = (
    "nominal_housing_loan_change_pct",
    "real_housing_loan_change_pct",
    "interest_rate_change_pp",
)
_ALWAYS_NUMERIC_COLUMNS = (
    "nominal_housing_loan_mn_try",
    "real_housing_loan_2025_mn_try",
    "housing_loan_interest_rate_pct",
    "weekly_observation_count",
    "cpi_index",
    "housing_price_index",
)


class EvidenceBuildError(ValueError):
    """Raised when a Gold table cannot produce trustworthy evidence."""


class HousingMonthEvidence(BaseModel):
    """Verified values for one month matching the deterministic rule."""

    model_config = ConfigDict(frozen=True)

    period: str
    nominal_housing_loan_mn_try: float
    real_housing_loan_2025_mn_try: float
    nominal_housing_loan_change_pct: float
    real_housing_loan_change_pct: float
    housing_loan_interest_rate_pct: float
    weekly_observation_count: int
    interest_rate_change_pp: float
    cpi_index: float
    housing_price_index: float
    bddk_source_ref: str
    evds_source_refs: tuple[str, ...]
    data_quality_note: str


class HousingAnalysisEvidence(BaseModel):
    """Deterministic, JSON-safe payload that may be given to the LLM."""

    model_config = ConfigDict(frozen=True)

    analysis_id: Literal["housing_rate_down_real_credit_not_up"]
    status: Literal["ok"]
    period_start: str
    period_end: str
    observed_month_count: int
    matched_month_count: int
    matched_periods: tuple[str, ...]
    rule_expression: str
    bddk_source_refs: tuple[str, ...]
    evds_source_refs: tuple[str, ...]
    data_quality_notes: tuple[str, ...]
    methodology: tuple[str, ...]
    limitations: tuple[str, ...]
    results: tuple[HousingMonthEvidence, ...]


def _validate_requested_periods(start_period: str, end_period: str) -> list[str]:
    start = str(start_period).strip()
    end = str(end_period).strip()
    if not _PERIOD_PATTERN.fullmatch(start):
        raise EvidenceBuildError("start_period must use YYYY-MM format.")
    if not _PERIOD_PATTERN.fullmatch(end):
        raise EvidenceBuildError("end_period must use YYYY-MM format.")
    if start > end:
        raise EvidenceBuildError("start_period cannot be later than end_period.")
    return pd.period_range(start=start, end=end, freq="M").astype(str).tolist()


def _require_non_empty_text(frame: pd.DataFrame, column: str) -> None:
    values = frame[column].astype("string").str.strip()
    invalid = values.isna() | values.eq("")
    if invalid.any():
        periods = frame.loc[invalid, "period"].tolist()
        raise EvidenceBuildError(
            f"{column} must be present for every period; invalid periods: "
            f"{periods[:5]}."
        )
    frame[column] = values


def _finite_float(value: object, *, column: str, period: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EvidenceBuildError(
            f"{column} must be numeric for period {period}."
        ) from exc
    if not math.isfinite(number):
        raise EvidenceBuildError(
            f"{column} must be finite for period {period}."
        )
    return number


def _validate_numeric_values(frame: pd.DataFrame) -> None:
    for index, row in frame.iterrows():
        period = str(row["period"])
        for column in _ALWAYS_NUMERIC_COLUMNS:
            number = _finite_float(row[column], column=column, period=period)
            if column in {
                "nominal_housing_loan_mn_try",
                "real_housing_loan_2025_mn_try",
                "housing_loan_interest_rate_pct",
            } and number < 0:
                raise EvidenceBuildError(
                    f"{column} must be non-negative for period {period}."
                )
            if column in {
                "weekly_observation_count",
                "cpi_index",
                "housing_price_index",
            } and number <= 0:
                raise EvidenceBuildError(
                    f"{column} must be greater than zero for period {period}."
                )
            frame.at[index, column] = number

        weekly_count = float(row["weekly_observation_count"])
        if not weekly_count.is_integer():
            raise EvidenceBuildError(
                "weekly_observation_count must be a whole number for period "
                f"{period}."
            )
        frame.at[index, "weekly_observation_count"] = int(weekly_count)

        for column in _CHANGE_COLUMNS:
            value = row[column]
            if index == 0 and pd.isna(value):
                continue
            frame.at[index, column] = _finite_float(
                value,
                column=column,
                period=period,
            )


def _validated_flag(value: object, *, period: str, first_row: bool) -> bool | None:
    if pd.isna(value):
        if first_row:
            return None
        raise EvidenceBuildError(
            "rate_down_real_credit_not_up may be null only for the first period; "
            f"invalid period: {period}."
        )
    if isinstance(value, bool) or type(value).__name__ == "bool_":
        return bool(value)
    raise EvidenceBuildError(
        "rate_down_real_credit_not_up must contain boolean values; "
        f"invalid period: {period}."
    )


def _split_evds_refs(value: str) -> tuple[str, ...]:
    refs = tuple(ref.strip() for ref in value.split(";") if ref.strip())
    if not refs:
        raise EvidenceBuildError("evds_source_refs must contain at least one source.")
    return refs


def build_housing_analysis_evidence(
    gold_table: pd.DataFrame,
    *,
    start_period: str = DEFAULT_START_PERIOD,
    end_period: str = DEFAULT_END_PERIOD,
) -> HousingAnalysisEvidence:
    """Validate a Gold table and create the only payload exposed to the LLM."""

    if not isinstance(gold_table, pd.DataFrame):
        raise EvidenceBuildError("gold_table must be a pandas DataFrame.")

    missing_columns = sorted(set(REQUIRED_COLUMNS).difference(gold_table.columns))
    if missing_columns:
        raise EvidenceBuildError(
            f"gold_table is missing required columns: {missing_columns}."
        )

    expected_periods = _validate_requested_periods(start_period, end_period)
    frame = gold_table.loc[:, list(REQUIRED_COLUMNS)].copy()
    frame["period"] = frame["period"].astype("string").str.strip()

    invalid_periods = frame.loc[
        frame["period"].isna()
        | ~frame["period"].str.fullmatch(_PERIOD_PATTERN.pattern, na=False),
        "period",
    ].tolist()
    if invalid_periods:
        raise EvidenceBuildError(
            f"gold_table contains invalid periods: {invalid_periods[:5]}."
        )

    duplicates = sorted(
        frame.loc[frame["period"].duplicated(keep=False), "period"].unique()
    )
    if duplicates:
        raise EvidenceBuildError(
            f"gold_table contains duplicate periods: {duplicates[:5]}."
        )

    frame = frame.sort_values("period").reset_index(drop=True)
    actual_periods = frame["period"].tolist()
    if actual_periods != expected_periods:
        missing = [period for period in expected_periods if period not in actual_periods]
        extra = [period for period in actual_periods if period not in expected_periods]
        raise EvidenceBuildError(
            "gold_table does not match the requested period range; "
            f"missing={missing[:5]}, extra={extra[:5]}."
        )

    for column in ("bddk_source_ref", "evds_source_refs", "data_quality_note"):
        _require_non_empty_text(frame, column)

    _validate_numeric_values(frame)

    flags: list[bool | None] = []
    for index, row in frame.iterrows():
        flags.append(
            _validated_flag(
                row["rate_down_real_credit_not_up"],
                period=str(row["period"]),
                first_row=index == 0,
            )
        )
    if flags[0] is not None:
        raise EvidenceBuildError(
            "rate_down_real_credit_not_up must be null for the first period."
        )

    frame["_validated_flag"] = flags
    matches = frame[frame["_validated_flag"].eq(True)].copy()

    results = tuple(
        HousingMonthEvidence(
            period=str(row.period),
            nominal_housing_loan_mn_try=float(row.nominal_housing_loan_mn_try),
            real_housing_loan_2025_mn_try=float(
                row.real_housing_loan_2025_mn_try
            ),
            nominal_housing_loan_change_pct=float(
                row.nominal_housing_loan_change_pct
            ),
            real_housing_loan_change_pct=float(row.real_housing_loan_change_pct),
            housing_loan_interest_rate_pct=float(
                row.housing_loan_interest_rate_pct
            ),
            weekly_observation_count=int(row.weekly_observation_count),
            interest_rate_change_pp=float(row.interest_rate_change_pp),
            cpi_index=float(row.cpi_index),
            housing_price_index=float(row.housing_price_index),
            bddk_source_ref=str(row.bddk_source_ref),
            evds_source_refs=_split_evds_refs(str(row.evds_source_refs)),
            data_quality_note=str(row.data_quality_note),
        )
        for row in matches.itertuples(index=False)
    )

    bddk_refs = tuple(dict.fromkeys(frame["bddk_source_ref"].tolist()))
    evds_refs = tuple(
        dict.fromkeys(
            ref
            for value in frame["evds_source_refs"].tolist()
            for ref in _split_evds_refs(str(value))
        )
    )
    quality_notes = tuple(dict.fromkeys(frame["data_quality_note"].tolist()))
    matched_periods = tuple(result.period for result in results)

    return HousingAnalysisEvidence(
        analysis_id=ANALYSIS_ID,
        status="ok",
        period_start=expected_periods[0],
        period_end=expected_periods[-1],
        observed_month_count=len(expected_periods),
        matched_month_count=len(results),
        matched_periods=matched_periods,
        rule_expression=RULE_EXPRESSION,
        bddk_source_refs=bddk_refs,
        evds_source_refs=evds_refs,
        data_quality_notes=quality_notes,
        methodology=(
            "Weekly housing-loan interest rates are aggregated by monthly arithmetic mean.",
            "Real housing-loan volume equals nominal volume multiplied by 100 and divided by CPI.",
            "Monthly changes compare each period with the immediately preceding period.",
        ),
        limitations=(
            "The result describes association and does not establish causality.",
            "The first period has no prior-month change and cannot match the rule.",
        ),
        results=results,
    )


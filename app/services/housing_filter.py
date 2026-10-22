"""Typed, deterministic metric-threshold filtering over the housing Gold table."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Annotated, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from app.lakehouse.gold import (
    DEFAULT_END_PERIOD,
    DEFAULT_START_PERIOD,
    build_housing_gold_table,
)


ANALYSIS_ID = "housing_condition_filter"

FilterMetric = Literal[
    "interest_rate_change_pp",
    "real_housing_loan_change_pct",
    "nominal_housing_loan_change_pct",
    "housing_loan_interest_rate_pct",
]
FilterOperator = Literal["lt", "lte", "gt", "gte"]
MetricUnit = Literal["percentage_point", "percent"]

_METRIC_UNITS: dict[str, MetricUnit] = {
    "interest_rate_change_pp": "percentage_point",
    "real_housing_loan_change_pct": "percent",
    "nominal_housing_loan_change_pct": "percent",
    "housing_loan_interest_rate_pct": "percent",
}


class HousingFilterValidationError(ValueError):
    """Conditions or inputs cannot produce a trustworthy filter result."""


class HousingFilterCondition(BaseModel):
    """One allowed metric/operator/threshold comparison."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    metric: FilterMetric
    operator: FilterOperator
    threshold: Annotated[float, Field(allow_inf_nan=False)]


_CONDITIONS_ADAPTER = TypeAdapter(
    Annotated[
        tuple[HousingFilterCondition, ...],
        Field(min_length=1, max_length=3),
    ]
)


class HousingFilterConditionEvidence(BaseModel):
    """Validated condition together with its documented metric unit."""

    model_config = ConfigDict(frozen=True)

    metric: FilterMetric
    operator: FilterOperator
    threshold: float
    unit: MetricUnit


class HousingFilterMonthEvidence(BaseModel):
    """Gold values for one month matching every requested condition."""

    model_config = ConfigDict(frozen=True)

    period: str
    nominal_housing_loan_mn_try: float
    real_housing_loan_2025_mn_try: float
    nominal_housing_loan_change_pct: float | None
    real_housing_loan_change_pct: float | None
    housing_loan_interest_rate_pct: float
    weekly_observation_count: int
    interest_rate_change_pp: float | None
    cpi_index: float
    housing_price_index: float
    bddk_source_ref: str
    evds_source_refs: tuple[str, ...]
    data_quality_note: str


class HousingConditionFilterEvidence(BaseModel):
    """JSON-safe evidence returned by the deterministic filter core."""

    model_config = ConfigDict(frozen=True)

    analysis_id: Literal["housing_condition_filter"]
    status: Literal["ok"]
    period_start: str
    period_end: str
    observed_month_count: int
    evaluable_month_count: int
    matched_month_count: int
    matched_periods: tuple[str, ...]
    conditions: tuple[HousingFilterConditionEvidence, ...]
    bddk_source_refs: tuple[str, ...]
    evds_source_refs: tuple[str, ...]
    data_quality_notes: tuple[str, ...]
    methodology: tuple[str, ...]
    limitations: tuple[str, ...]
    results: tuple[HousingFilterMonthEvidence, ...]


def _validated_conditions(
    conditions: Sequence[HousingFilterCondition],
) -> tuple[HousingFilterCondition, ...]:
    if isinstance(conditions, (str, bytes)) or not isinstance(
        conditions, Sequence
    ):
        raise HousingFilterValidationError(
            "conditions must be a sequence of 1-3 typed conditions."
        )
    try:
        return _CONDITIONS_ADAPTER.validate_python(list(conditions))
    except ValidationError:
        raise HousingFilterValidationError(
            "conditions must contain 1-3 allowed metric/operator/threshold "
            "objects with finite numeric thresholds and no extra fields."
        ) from None


def _condition_mask(
    values: pd.Series,
    *,
    operator: FilterOperator,
    threshold: float,
) -> pd.Series:
    if operator == "lt":
        return values < threshold
    if operator == "lte":
        return values <= threshold
    if operator == "gt":
        return values > threshold
    return values >= threshold


def _finite_float(
    value: object,
    *,
    field: str,
    period: str,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise HousingFilterValidationError(
            f"{field} must be numeric for period {period}."
        ) from exc
    if not math.isfinite(number):
        raise HousingFilterValidationError(
            f"{field} must be finite for period {period}."
        )
    return number


def _finite_optional_float(
    value: object,
    *,
    field: str,
    period: str,
) -> float | None:
    if pd.isna(value):
        return None
    return _finite_float(value, field=field, period=period)


def _text(value: object, *, field: str, period: str) -> str:
    if pd.isna(value):
        raise HousingFilterValidationError(
            f"{field} must be present for period {period}."
        )
    text = str(value).strip()
    if not text:
        raise HousingFilterValidationError(
            f"{field} must be present for period {period}."
        )
    return text


def _split_evds_refs(value: str) -> tuple[str, ...]:
    refs = tuple(ref.strip() for ref in value.split(";") if ref.strip())
    if not refs:
        raise HousingFilterValidationError(
            "evds_source_refs must contain at least one source."
        )
    return refs


def _month_evidence(row: object) -> HousingFilterMonthEvidence:
    period = str(row.period)
    return HousingFilterMonthEvidence(
        period=period,
        nominal_housing_loan_mn_try=_finite_float(
            row.nominal_housing_loan_mn_try,
            field="nominal_housing_loan_mn_try",
            period=period,
        ),
        real_housing_loan_2025_mn_try=_finite_float(
            row.real_housing_loan_2025_mn_try,
            field="real_housing_loan_2025_mn_try",
            period=period,
        ),
        nominal_housing_loan_change_pct=_finite_optional_float(
            row.nominal_housing_loan_change_pct,
            field="nominal_housing_loan_change_pct",
            period=period,
        ),
        real_housing_loan_change_pct=_finite_optional_float(
            row.real_housing_loan_change_pct,
            field="real_housing_loan_change_pct",
            period=period,
        ),
        housing_loan_interest_rate_pct=_finite_float(
            row.housing_loan_interest_rate_pct,
            field="housing_loan_interest_rate_pct",
            period=period,
        ),
        weekly_observation_count=int(row.weekly_observation_count),
        interest_rate_change_pp=_finite_optional_float(
            row.interest_rate_change_pp,
            field="interest_rate_change_pp",
            period=period,
        ),
        cpi_index=_finite_float(
            row.cpi_index,
            field="cpi_index",
            period=period,
        ),
        housing_price_index=_finite_float(
            row.housing_price_index,
            field="housing_price_index",
            period=period,
        ),
        bddk_source_ref=_text(
            row.bddk_source_ref,
            field="bddk_source_ref",
            period=period,
        ),
        evds_source_refs=_split_evds_refs(
            _text(row.evds_source_refs, field="evds_source_refs", period=period)
        ),
        data_quality_note=_text(
            row.data_quality_note,
            field="data_quality_note",
            period=period,
        ),
    )


def _build_evidence(
    gold_table: pd.DataFrame,
    *,
    start_period: str,
    end_period: str,
    conditions: tuple[HousingFilterCondition, ...],
) -> HousingConditionFilterEvidence:
    frame = gold_table.sort_values("period").reset_index(drop=True)
    observed_periods = tuple(str(period) for period in frame["period"])

    metric_values = {
        condition.metric: pd.to_numeric(
            frame[condition.metric], errors="coerce",
        ).astype(float)
        for condition in conditions
    }

    evaluable = pd.Series(True, index=frame.index)
    for values in metric_values.values():
        evaluable &= values.notna() & values.map(math.isfinite)

    matched = evaluable.copy()
    for condition in conditions:
        matched &= _condition_mask(
            metric_values[condition.metric],
            operator=condition.operator,
            threshold=condition.threshold,
        ).fillna(False)

    results = tuple(
        _month_evidence(row)
        for row in frame.loc[matched].itertuples(index=False)
    )
    matched_periods = tuple(result.period for result in results)

    bddk_refs = tuple(
        dict.fromkeys(
            _text(value, field="bddk_source_ref", period=str(period))
            for value, period in zip(
                frame["bddk_source_ref"], frame["period"], strict=True,
            )
        )
    )
    evds_refs = tuple(
        dict.fromkeys(
            ref
            for value, period in zip(
                frame["evds_source_refs"], frame["period"], strict=True,
            )
            for ref in _split_evds_refs(
                _text(
                    value,
                    field="evds_source_refs",
                    period=str(period),
                )
            )
        )
    )
    quality_notes = tuple(
        dict.fromkeys(
            _text(value, field="data_quality_note", period=str(period))
            for value, period in zip(
                frame["data_quality_note"], frame["period"], strict=True,
            )
        )
    )

    condition_evidence = tuple(
        HousingFilterConditionEvidence(
            metric=condition.metric,
            operator=condition.operator,
            threshold=condition.threshold,
            unit=_METRIC_UNITS[condition.metric],
        )
        for condition in conditions
    )

    return HousingConditionFilterEvidence(
        analysis_id=ANALYSIS_ID,
        status="ok",
        period_start=str(start_period).strip(),
        period_end=str(end_period).strip(),
        observed_month_count=len(observed_periods),
        evaluable_month_count=int(evaluable.sum()),
        matched_month_count=len(results),
        matched_periods=matched_periods,
        conditions=condition_evidence,
        bddk_source_refs=bddk_refs,
        evds_source_refs=evds_refs,
        data_quality_notes=quality_notes,
        methodology=(
            "Gold values are built once by the existing deterministic housing builder.",
            "Every observed month is evaluated against the supplied conditions; "
            "the legacy rate_down_real_credit_not_up flag is not used.",
            "Thresholds and Gold values are compared without rounding.",
        ),
        limitations=(
            "The first period has no prior-month change, so change-based "
            "conditions cannot evaluate it.",
            "Conditions are combined with AND only.",
            "The result describes association and does not establish causality.",
            "Inputs are validated at Gold level; physical files and hashes are "
            "not verified by this service.",
        ),
        results=results,
    )


def run_housing_filter(
    bddk_monthly: pd.DataFrame,
    evds_monthly: pd.DataFrame,
    *,
    start_period: str = DEFAULT_START_PERIOD,
    end_period: str = DEFAULT_END_PERIOD,
    conditions: Sequence[HousingFilterCondition],
    bddk_source_ref: str = "BDDK monthly bulletin, Table 4, sector 10001, TL",
    evds_source_refs: str = "TP.KTF12; TP.TUKFIY2025.GENEL; TP.KFE.TR",
) -> HousingConditionFilterEvidence:
    """Filter every Gold month with 1-3 typed AND conditions.

    Conditions are validated before the Gold builder runs. The builder is
    called exactly once and remains the only source of monthly calculations.
    """

    validated_conditions = _validated_conditions(conditions)
    gold_table = build_housing_gold_table(
        bddk_monthly,
        evds_monthly,
        start_period=start_period,
        end_period=end_period,
        bddk_source_ref=bddk_source_ref,
        evds_source_refs=evds_source_refs,
    )
    return _build_evidence(
        gold_table,
        start_period=start_period,
        end_period=end_period,
        conditions=validated_conditions,
    )

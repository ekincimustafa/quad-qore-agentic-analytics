"""Run an approved combination of monthly conditions without a model call."""

from __future__ import annotations

import math
import operator
from typing import Annotated, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from app.catalog.monthly_metrics import MONTHLY_METRICS, MetricId
from app.lakehouse.core_validators import parse_period_to_date
from app.lakehouse.gold import GoldAnalysisError, build_housing_gold_table
from app.services.inflation_analysis import InflationAnalysisError, build_inflation_evidence


REAL_CREDIT_CHANGE: MetricId = "real_housing_loan_change_pct"
MAX_MONTHS = 120
_OPERATORS = {"lt": operator.lt, "lte": operator.le, "gt": operator.gt, "gte": operator.ge}


class ComposableAnalysisError(ValueError):
    """A validated plan cannot run on the supplied data."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class MonthlyCondition(_StrictModel):
    metric: MetricId
    operator: Literal["lt", "lte", "gt", "gte"]
    threshold: FiniteFloat


class MonthlyFilterPlan(_StrictModel):
    """The selected metrics are the dependencies of the requested conditions."""

    start_period: Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]
    end_period: Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]
    conditions: Annotated[tuple[MonthlyCondition, ...], Field(min_length=1, max_length=3)]

    @model_validator(mode="after")
    def _bounded_period(self) -> MonthlyFilterPlan:
        start = parse_period_to_date(self.start_period)
        end = parse_period_to_date(self.end_period)
        months = (end.year - start.year) * 12 + end.month - start.month + 1
        if not 1 <= months <= MAX_MONTHS:
            raise ValueError(f"Dönem sıralı ve en fazla {MAX_MONTHS} ay olmalıdır.")
        return self


class MonthlyObservation(_StrictModel):
    period: str
    values: dict[MetricId, FiniteFloat | None]
    matched: bool | None


class MetricSource(_StrictModel):
    metric: MetricId
    unit: Literal["percent"]
    source_refs: tuple[str, ...]


class MonthlyFilterEvidence(_StrictModel):
    plan: MonthlyFilterPlan
    sources: tuple[MetricSource, ...]
    observations: tuple[MonthlyObservation, ...]
    matched_periods: tuple[str, ...]
    evaluable_month_count: int


def _source_refs(value: str | None) -> tuple[str, ...]:
    if not isinstance(value, str):
        raise ComposableAnalysisError("Kullanılan seri için kaynak referansı gereklidir.")
    refs = tuple(dict.fromkeys(
        part.strip() for part in value.split(";") if part.strip()
    ))
    if not refs or any(ref.lower() in {"none", "nan", "null"} for ref in refs):
        raise ComposableAnalysisError("Kullanılan seri için kaynak referansı gereklidir.")
    return refs


def _contains_period(frame: pd.DataFrame, period: str) -> bool:
    return frame.columns.is_unique and "period" in frame and frame["period"].eq(period).any()


def run_monthly_filter(
    plan: MonthlyFilterPlan,
    *,
    evds_monthly: pd.DataFrame,
    cpi_source_ref: str,
    bddk_monthly: pd.DataFrame | None = None,
    bddk_source_ref: str | None = None,
) -> MonthlyFilterEvidence:
    """Read only selected metric families, align by month, and evaluate AND conditions.

    Inputs are supplied in memory by the caller. Source references describe those
    inputs; this function does not verify physical files or fetch data.
    """
    if not isinstance(plan, MonthlyFilterPlan):
        raise TypeError("plan must be a validated MonthlyFilterPlan")
    if not isinstance(evds_monthly, pd.DataFrame):
        raise ComposableAnalysisError("Aylık EVDS tablosu gereklidir.")
    metrics = tuple(dict.fromkeys(condition.metric for condition in plan.conditions))
    cpi_refs = _source_refs(cpi_source_ref)
    start, end = plan.start_period, plan.end_period
    values_by_metric: dict[MetricId, dict[str, float | None]] = {}
    sources = {metric: cpi_refs for metric in metrics}

    try:
        cpi_metrics = tuple(metric for metric in metrics if metric != REAL_CREDIT_CHANGE)
        if cpi_metrics:
            cpi = build_inflation_evidence(
                evds_monthly, start_period=start, end_period=end, source_ref=cpi_source_ref,
            )
            for metric in cpi_metrics:
                values_by_metric[metric] = {
                    row.period: getattr(row, metric) for row in cpi.observations
                }

        if REAL_CREDIT_CHANGE in metrics:
            if not isinstance(bddk_monthly, pd.DataFrame):
                raise ComposableAnalysisError("Reel kredi değişimi için aylık BDDK tablosu gereklidir.")
            _source_refs(bddk_source_ref)
            previous = pd.Period(start, freq="M") - MONTHLY_METRICS[REAL_CREDIT_CHANGE].lookback_months
            prior = f"{previous.year:04d}-{previous.month:02d}"
            gold_start = prior if previous.year > 0 and (
                _contains_period(bddk_monthly, prior) and _contains_period(evds_monthly, prior)
            ) else start
            gold = build_housing_gold_table(
                bddk_monthly, evds_monthly, start_period=gold_start, end_period=end,
                bddk_source_ref=bddk_source_ref, evds_source_refs="; ".join(cpi_refs),
            )
            # Preserve the denominator month's BDDK reference as well.
            bddk_refs = _source_refs("; ".join(str(ref) for ref in gold["bddk_source_ref"]))
            sources[REAL_CREDIT_CHANGE] = tuple(dict.fromkeys((*bddk_refs, *cpi_refs)))
            values_by_metric[REAL_CREDIT_CHANGE] = {
                period: float(value) if math.isfinite(value) else None
                for period, value in zip(gold["period"], gold[REAL_CREDIT_CHANGE], strict=True)
            }
    except (InflationAnalysisError, GoldAnalysisError) as exc:
        raise ComposableAnalysisError("İstenen dönem veya seri verisi hesaplamaya uygun değil.") from exc

    observations = []
    for month in pd.period_range(start=start, end=end, freq="M"):
        period = str(month)
        values = {metric: values_by_metric[metric][period] for metric in metrics}
        matched = None if any(value is None for value in values.values()) else all(
            _OPERATORS[condition.operator](values[condition.metric], condition.threshold)
            for condition in plan.conditions
        )
        observations.append(MonthlyObservation(period=period, values=values, matched=matched))

    return MonthlyFilterEvidence(
        plan=plan,
        sources=tuple(
            MetricSource(metric=metric, unit=MONTHLY_METRICS[metric].unit, source_refs=sources[metric])
            for metric in metrics
        ),
        observations=tuple(observations),
        matched_periods=tuple(row.period for row in observations if row.matched is True),
        evaluable_month_count=sum(row.matched is not None for row in observations),
    )

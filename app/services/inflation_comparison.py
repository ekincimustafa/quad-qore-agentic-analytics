"""Deterministic comparison of two calendar years of CPI evidence."""

from __future__ import annotations

import math
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, FiniteFloat

from app.services.inflation_analysis import (
    InflationAnalysisError,
    InflationEvidence,
    build_inflation_evidence,
)


class InflationComparisonError(InflationAnalysisError):
    """Invalid comparison years or a difference that cannot be represented safely."""


class InflationYearEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    year: int
    evidence: InflationEvidence


class InflationComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_id: Literal["cpi_two_year_comparison"] = "cpi_two_year_comparison"
    source_ref: str
    years: tuple[InflationYearEvidence, InflationYearEvidence]
    second_minus_first_december_annual_inflation_pp: FiniteFloat | None
    methodology: tuple[str, ...]
    limitations: tuple[str, ...]


def _year(value: object, *, position: str) -> int:
    if type(value) is not int or not 1 <= value <= 9999:
        raise InflationComparisonError(
            f"{position} yılı 1-9999 aralığında bir tam sayı olmalıdır."
        )
    return value


def _december_annual_inflation(evidence: InflationEvidence, year: int) -> float | None:
    december = f"{year:04d}-12"
    for observation in evidence.observations:
        if observation.period == december:
            return observation.annual_inflation_pct
    raise InflationComparisonError(f"Karşılaştırma yılı {year} için Aralık gözlemi bulunamadı.")


def compare_inflation_years(
    cpi_monthly: pd.DataFrame,
    *,
    first_year: int,
    second_year: int,
    source_ref: str,
) -> InflationComparison:
    """Compare two full calendar years of CPI changes in the requested order.

    The supplied series is not truncated to the selected years: earlier months,
    including the previous December, remain available to the existing annual
    calculation. No fetching, filling or model calls.
    """
    first = _year(first_year, position="Birinci")
    second = _year(second_year, position="İkinci")
    if first == second:
        raise InflationComparisonError("Karşılaştırma yılları farklı olmalıdır.")

    first_evidence = build_inflation_evidence(
        cpi_monthly,
        start_period=f"{first:04d}-01",
        end_period=f"{first:04d}-12",
        source_ref=source_ref,
    )
    second_evidence = build_inflation_evidence(
        cpi_monthly,
        start_period=f"{second:04d}-01",
        end_period=f"{second:04d}-12",
        source_ref=source_ref,
    )

    first_december = _december_annual_inflation(first_evidence, first)
    second_december = _december_annual_inflation(second_evidence, second)
    difference = None if first_december is None or second_december is None else second_december - first_december
    if difference is not None and not math.isfinite(difference):
        raise InflationComparisonError("Karşılaştırma farkı sonlu olmalıdır.")

    return InflationComparison(
        source_ref=first_evidence.source_ref,
        years=(
            InflationYearEvidence(year=first, evidence=first_evidence),
            InflationYearEvidence(year=second, evidence=second_evidence),
        ),
        second_minus_first_december_annual_inflation_pp=difference,
        methodology=(
            "Her yıl için Ocak–Aralık aylık ve Aralık yıllık TÜFE değişimleri mevcut build_inflation_evidence kurallarıyla hesaplanır.",
            "Karşılaştırma farkı (yüzde puan) = ikinci yılın Aralık yıllık enflasyonu - birinci yılın Aralık yıllık enflasyonu.",
            "Ocak–Aralık endeks değişimi ayrı bir alandır; Aralık yıllık enflasyonu veya aylık oranların toplamı değildir.",
        ),
        limitations=(
            "Aralık yıllık oranlarından biri için gerekli önceki Aralık verisi yoksa ilgili oran ve karşılaştırma farkı null olur; tahmin üretilmez.",
            "Yıllar verilen sırayla döndürülür; fark her zaman ikinci yıl eksi birinci yıldır ve sıra ters verilirse işaret değişir.",
            "Bu karşılaştırma enflasyonun nedenini veya gelecekteki değerini açıklamaz.",
        ),
    )

"""Deterministic CPI changes over normalized monthly EVDS observations."""

from __future__ import annotations

import math
from typing import Literal

import pandas as pd
from pandas.api.types import is_bool, is_complex
from pydantic import BaseModel, ConfigDict, FiniteFloat

from app.lakehouse.core_validators import check_missing_periods, parse_period_to_date


class InflationAnalysisError(ValueError):
    """Invalid monthly input or a calculation that cannot be represented safely."""


class InflationMonth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    period: str
    cpi_index: FiniteFloat
    monthly_inflation_pct: FiniteFloat | None
    annual_inflation_pct: FiniteFloat | None


class InflationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_id: Literal["cpi_inflation_summary"] = "cpi_inflation_summary"
    series_code: Literal["TP.TUKFIY2025.GENEL"] = "TP.TUKFIY2025.GENEL"
    cpi_base_year: Literal[2025] = 2025
    input_origin: Literal["caller_supplied"] = "caller_supplied"
    source_ref: str
    period_start: str
    period_end: str
    available_period_start: str
    available_period_end: str
    observed_month_count: int
    first_cpi_index: FiniteFloat
    last_cpi_index: FiniteFloat
    first_to_last_index_change_pct: FiniteFloat
    observations: tuple[InflationMonth, ...]
    methodology: tuple[str, ...]
    limitations: tuple[str, ...]


def _period(value: object) -> str:
    if not isinstance(value, str) or value != value.strip():
        raise InflationAnalysisError("Dönem YYYY-MM biçiminde olmalıdır.")
    try:
        parsed = parse_period_to_date(value)
    except ValueError:
        raise InflationAnalysisError("Dönem geçerli bir YYYY-MM değeri olmalıdır.") from None
    if parsed.isoformat()[:7] != value:
        raise InflationAnalysisError("Dönem YYYY-MM biçiminde olmalıdır.")
    return value


def _change(current: float, previous: float) -> float:
    result = (current / previous - 1.0) * 100.0
    if not math.isfinite(result):
        raise InflationAnalysisError("Hesaplanan endeks değişimi sonlu olmalıdır.")
    return result


def validated_cpi_monthly(cpi_monthly: pd.DataFrame) -> pd.DataFrame:
    """Validate the complete supplied CPI history for coverage and calculation."""
    if not isinstance(cpi_monthly, pd.DataFrame) or cpi_monthly.empty:
        raise InflationAnalysisError("Aylık TÜFE tablosu boş olmayan bir DataFrame olmalıdır.")
    if not cpi_monthly.columns.is_unique:
        raise InflationAnalysisError("TÜFE tablosunda mükerrer kolon bulunamaz.")
    if not {"period", "cpi_index"}.issubset(cpi_monthly.columns):
        raise InflationAnalysisError("TÜFE tablosunda period ve cpi_index kolonları bulunmalıdır.")

    frame = cpi_monthly.loc[:, ["period", "cpi_index"]].copy()
    frame["period"] = frame["period"].map(_period)
    if frame["period"].duplicated().any():
        raise InflationAnalysisError("Aynı ay için birden fazla TÜFE gözlemi bulunamaz.")
    if frame["cpi_index"].map(lambda value: is_bool(value) or is_complex(value)).any():
        raise InflationAnalysisError("TÜFE endeksi gerçek sayı olmalıdır; boolean veya karmaşık sayı olamaz.")
    try:
        values = pd.to_numeric(frame["cpi_index"], errors="coerce").astype(float)
    except (TypeError, ValueError, OverflowError):
        raise InflationAnalysisError("TÜFE endeksleri pozitif ve sonlu sayı olmalıdır.") from None
    if values.isna().any() or (values <= 0).any() or not values.map(math.isfinite).all():
        raise InflationAnalysisError("TÜFE endeksleri pozitif ve sonlu sayı olmalıdır.")
    frame["cpi_index"] = values
    frame = frame.sort_values("period").reset_index(drop=True)
    available_start, available_end = frame["period"].iloc[0], frame["period"].iloc[-1]
    try:
        check_missing_periods(frame["period"], available_start, available_end)
    except ValueError:
        raise InflationAnalysisError("Verilen TÜFE serisinde eksik ay bulunamaz.") from None
    return frame


def build_inflation_evidence(
    cpi_monthly: pd.DataFrame,
    *,
    start_period: str,
    end_period: str,
    source_ref: str,
) -> InflationEvidence:
    """Compute month-over-month and same-month-last-year CPI changes.

    Earlier rows in the supplied continuous series remain available as history;
    only the requested interval is returned. No fetching, filling or model calls.
    """
    start, end = _period(start_period), _period(end_period)
    if start > end:
        raise InflationAnalysisError("Başlangıç dönemi bitiş döneminden sonra olamaz.")
    if (
        not isinstance(source_ref, str)
        or source_ref.strip().lower() in {"", "none", "nan", "<na>"}
    ):
        raise InflationAnalysisError("Kaynak referansı boş olmayan bir metin olmalıdır.")
    frame = validated_cpi_monthly(cpi_monthly)
    available_start, available_end = frame["period"].iloc[0], frame["period"].iloc[-1]
    if start < available_start or end > available_end:
        raise InflationAnalysisError("İstenen dönem, verilen TÜFE serisinin kapsamı dışında.")

    index = dict(zip(frame["period"], frame["cpi_index"]))
    observations = []
    for period in pd.period_range(start=start, end=end, freq="M"):
        text = str(period)
        current = float(index[text])
        previous, last_year = index.get(str(period - 1)), index.get(str(period - 12))
        observations.append(InflationMonth(
            period=text,
            cpi_index=current,
            monthly_inflation_pct=None if previous is None else _change(current, float(previous)),
            annual_inflation_pct=None if last_year is None else _change(current, float(last_year)),
        ))
    first, last = observations[0].cpi_index, observations[-1].cpi_index
    return InflationEvidence(
        source_ref=source_ref.strip(), period_start=start, period_end=end,
        available_period_start=available_start, available_period_end=available_end,
        observed_month_count=len(observations), first_cpi_index=first, last_cpi_index=last,
        first_to_last_index_change_pct=_change(last, first), observations=tuple(observations),
        methodology=(
            "Aylık enflasyon (%) = (TÜFE[t] / TÜFE[t-1] - 1) × 100.",
            "Yıllık enflasyon (%) = (TÜFE[t] / TÜFE[t-12] - 1) × 100; yıllıklandırma veya 12 aylık ortalama değildir.",
            "İlk-son endeks değişimi (%) = (seçilen son ay / seçilen ilk ay - 1) × 100; aylık oranlar toplanmaz.",
            "Seçimden önce sağlanan geçmiş aylar hesapta kullanılır; eksik karşılaştırma geçmişi null olur.",
        ),
        limitations=(
            "Girdiler çağıran tarafından sağlanır; kaynak referansı fiziksel Bronze/manifest doğrulaması değildir.",
            "Sözleşme TP.TUKFIY2025.GENEL, 2025=100 aylık genel TÜFE endeksini varsayar; yeniden bazlama veya mevsim düzeltmesi yapılmaz.",
            "Tek ay seçiminde ilk-son değişimi sıfırdır; bu, o ayın aylık enflasyonunun sıfır olduğu anlamına gelmez.",
            "Bu hesaplar enflasyonun nedenini veya gelecekteki değerini açıklamaz.",
        ),
    )

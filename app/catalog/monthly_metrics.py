"""Approved monthly metrics for the composable analysis core."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal


MetricId = Literal[
    "annual_inflation_pct",
    "monthly_inflation_pct",
    "real_housing_loan_change_pct",
]


@dataclass(frozen=True)
class MonthlyMetric:
    label: str
    aliases: tuple[str, ...]
    series: tuple[str, ...]
    unit: Literal["percent"]
    frequency: Literal["monthly"]
    lookback_months: int


MONTHLY_METRICS = MappingProxyType({
    "annual_inflation_pct": MonthlyMetric(
        "Yıllık TÜFE değişimi", ("yıllık enflasyon", "geçen yılın aynı ayına göre TÜFE"),
        ("TP.TUKFIY2025.GENEL",), "percent", "monthly", 12,
    ),
    "monthly_inflation_pct": MonthlyMetric(
        "Aylık TÜFE değişimi", ("aylık enflasyon", "önceki aya göre TÜFE"),
        ("TP.TUKFIY2025.GENEL",), "percent", "monthly", 1,
    ),
    "real_housing_loan_change_pct": MonthlyMetric(
        "Reel konut kredisi stokunun aylık değişimi",
        ("reel konut kredisi değişimi", "enflasyondan arındırılmış konut kredisi bakiyesi değişimi"),
        ("BDDK monthly bulletin Table 4", "TP.TUKFIY2025.GENEL"),
        "percent", "monthly", 1,
    ),
})

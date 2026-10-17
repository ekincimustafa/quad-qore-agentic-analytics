"""Application service for the first end-to-end housing analysis."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.lakehouse.gold import build_housing_gold_table
from app.tools.housing_chart import build_housing_chart
from app.tools.housing_evidence import (
    HousingAnalysisEvidence,
    build_housing_analysis_evidence,
)


HousingNarrator = Callable[[HousingAnalysisEvidence], str]


class HousingNarrationError(RuntimeError):
    """Raised when the external narration boundary cannot return a response."""


@dataclass(frozen=True)
class HousingAnalysisRun:
    """Validated result returned by the application service."""

    evidence: HousingAnalysisEvidence
    chart: dict[str, Any]
    narration: str | None


def run_housing_analysis(
    bddk_monthly: pd.DataFrame,
    evds_monthly: pd.DataFrame,
    *,
    start_period: str,
    end_period: str,
    bddk_source_ref: str = "BDDK monthly bulletin, Table 4, sector 10001, TL",
    evds_source_refs: Any = "TP.KTF12; TP.TUKFIY2025.GENEL; TP.KFE.TR",
    narrator: HousingNarrator | None = None,
) -> HousingAnalysisRun:
    """Build Gold data, validate evidence, and optionally request narration."""

    gold_table = build_housing_gold_table(
        bddk_monthly,
        evds_monthly,
        start_period=start_period,
        end_period=end_period,
        bddk_source_ref=bddk_source_ref,
        evds_source_refs=evds_source_refs,
    )
    evidence = build_housing_analysis_evidence(
        gold_table,
        start_period=start_period,
        end_period=end_period,
    )
    chart = build_housing_chart(gold_table)

    narration: str | None = None
    if narrator is not None:
        try:
            candidate = narrator(evidence)
        except Exception as exc:
            raise HousingNarrationError("LLM narration failed.") from exc
        if not isinstance(candidate, str) or not candidate.strip():
            raise HousingNarrationError("LLM narration returned an empty response.")
        narration = candidate.strip()

    return HousingAnalysisRun(
        evidence=evidence,
        chart=chart,
        narration=narration,
    )

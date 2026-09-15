"""Application service for the first end-to-end housing analysis."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from app.lakehouse.gold import build_housing_gold_table
from app.tools.housing_evidence import (
    HousingAnalysisEvidence,
    build_housing_analysis_evidence,
)


HousingNarrator = Callable[[HousingAnalysisEvidence], str]


class HousingNarrationError(RuntimeError):
    """Raised when the external narration boundary cannot return a response."""


@dataclass(frozen=True, slots=True)
class HousingAnalysisRun:
    """Validated result returned by the application service."""

    evidence: HousingAnalysisEvidence
    narration: str | None


def run_housing_analysis(
    bddk_monthly: pd.DataFrame,
    evds_monthly: pd.DataFrame,
    *,
    start_period: str,
    end_period: str,
    bddk_source_ref: str,
    evds_source_refs: str,
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

    narration: str | None = None
    if narrator is not None:
        try:
            candidate = narrator(evidence)
        except Exception as exc:
            raise HousingNarrationError("MIA narration failed.") from exc
        if not isinstance(candidate, str) or not candidate.strip():
            raise HousingNarrationError("MIA narration returned an empty response.")
        narration = candidate.strip()

    return HousingAnalysisRun(evidence=evidence, narration=narration)

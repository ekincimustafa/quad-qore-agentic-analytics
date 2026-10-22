"""Bounded analyses using the existing physical package verifier and cores."""

from dataclasses import replace

from app.services.economic_question import (
    EconomicQuestionRun,
    HousingQuestionData,
    InflationQuestionData,
    ModelCall,
    run_economic_question,
)
from app.services.evds_manifest import WEEKLY_COVERAGE_NOTE
from app.services.housing_analysis import HousingAnalysisRun
from app.services.housing_demo import DEFAULT_BDDK_SOURCE_REF
from app.services.housing_filter import HousingConditionFilterEvidence
from app.services.housing_question_files import (
    VerifiedHousingQuestionDataError,
    VerifiedHousingQuestionPaths,
    load_verified_question_inputs,
    with_verified_housing_notes,
)
from app.services.inflation_analysis import InflationEvidence
from app.services.inflation_comparison import (
    InflationComparison,
    InflationYearEvidence,
)

_VERIFIED_CPI_LIMITATION = (
    "TÜFE, sunucunun fiziksel manifest/raw/makbuz/hash zinciri doğrulanmış EVDS dosyasından gelir."
)
_VERIFIED_HOUSING_LIMITATION = (
    "BDDK/EVDS girdileri sunucunun fiziksel manifest/raw/makbuz/hash zinciri "
    "doğrulanmış dosyalarından gelir."
)


class VerifiedEconomicQuestionDataError(RuntimeError):
    """The server package failed verification; no paths or source bodies escape."""


def _with_verified_filter_notes(
    evidence: HousingConditionFilterEvidence,
) -> HousingConditionFilterEvidence:
    limitations = (
        _VERIFIED_HOUSING_LIMITATION,
        *(
            item
            for item in evidence.limitations
            if "physical files and hashes are not verified" not in item
        ),
    )
    return evidence.model_copy(update={
        "limitations": limitations,
        "data_quality_notes": tuple(dict.fromkeys((
            *evidence.data_quality_notes, WEEKLY_COVERAGE_NOTE,
        ))),
    })


def _with_verified_cpi_notes(evidence: InflationEvidence) -> InflationEvidence:
    # Calculations are unchanged; distinguish verified provenance from request rows.
    return evidence.model_copy(update={
        "input_origin": "verified_files",
        "limitations": (_VERIFIED_CPI_LIMITATION, *evidence.limitations[1:]),
    })


def run_verified_economic_question(
    question: str,
    paths: VerifiedHousingQuestionPaths,
    *,
    model_call: ModelCall | None = None,
) -> EconomicQuestionRun:
    """Verify once, plan once, then dispatch at most one existing Python analysis."""
    try:
        inputs = load_verified_question_inputs(paths)
    except VerifiedHousingQuestionDataError:
        raise VerifiedEconomicQuestionDataError(
            "Sunucu veri paketi eksik, okunamıyor veya bütünlük doğrulamasını geçemedi."
        ) from None
    result = run_economic_question(
        question,
        housing=HousingQuestionData(
            inputs.bddk_monthly, inputs.evds_monthly,
            DEFAULT_BDDK_SOURCE_REF, inputs.evds_source_refs,
        ),
        inflation=InflationQuestionData(
            inputs.evds_monthly.loc[:, ["period", "cpi_index"]].copy(), inputs.cpi_source_ref,
        ),
        model_call=model_call,
    )
    analysis = result.analysis
    if isinstance(analysis, HousingAnalysisRun):
        analysis = with_verified_housing_notes(analysis)
    elif isinstance(analysis, HousingConditionFilterEvidence):
        analysis = _with_verified_filter_notes(analysis)
    elif isinstance(analysis, InflationEvidence):
        analysis = _with_verified_cpi_notes(analysis)
    elif isinstance(analysis, InflationComparison):
        analysis = analysis.model_copy(update={
            "years": tuple(
                InflationYearEvidence(
                    year=item.year, evidence=_with_verified_cpi_notes(item.evidence),
                )
                for item in analysis.years
            ),
        })
    return replace(result, analysis=analysis)

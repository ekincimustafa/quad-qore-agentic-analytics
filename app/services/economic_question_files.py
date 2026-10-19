"""Two bounded analyses using the existing physical package verifier and core."""

from dataclasses import replace

from app.services.economic_question import (
    EconomicQuestionRun,
    HousingQuestionData,
    InflationQuestionData,
    ModelCall,
    run_economic_question,
)
from app.services.housing_analysis import HousingAnalysisRun
from app.services.housing_demo import DEFAULT_BDDK_SOURCE_REF
from app.services.housing_question_files import (
    VerifiedHousingQuestionDataError,
    VerifiedHousingQuestionPaths,
    load_verified_question_inputs,
    with_verified_housing_notes,
)
from app.services.inflation_analysis import InflationEvidence


class VerifiedEconomicQuestionDataError(RuntimeError):
    """The server package failed verification; no paths or source bodies escape."""


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
    elif isinstance(analysis, InflationEvidence):
        # Calculations are unchanged; distinguish verified provenance from request rows.
        analysis = analysis.model_copy(update={
            "input_origin": "verified_files",
            "limitations": (
                "TÜFE, sunucunun fiziksel manifest/raw/makbuz/hash zinciri doğrulanmış EVDS dosyasından gelir.",
                *analysis.limitations[1:],
            ),
        })
    return replace(result, analysis=analysis)

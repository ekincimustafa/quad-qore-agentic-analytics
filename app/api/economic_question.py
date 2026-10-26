"""Typed HTTP boundary for the bounded Housing/CPI question service."""

from collections.abc import Callable, Coroutine
import os
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any, Literal, NoReturn, Union

import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from starlette.requests import Request
from starlette.responses import Response

from app.api.housing import BddkMonthlyRow, EvdsMonthlyRow
from app.api.inflation import CpiMonthlyRow
from app.lakehouse.gold import GoldAnalysisError
from app.services.economic_question import (
    HOUSING_ID,
    INFLATION_ID,
    MAX_QUESTION_CHARACTERS,
    MAX_PLAN_CHARACTERS,
    EconomicClarification,
    EconomicComparisonReadyPlan,
    EconomicCoverage,
    EconomicDataUnavailable,
    EconomicHousingFilterReadyPlan,
    EconomicInputError,
    EconomicPlanningError,
    EconomicPlanValidationError,
    EconomicReadyDecision,
    EconomicQuestionRun,
    EconomicUnsupported,
    HousingQuestionData,
    InflationQuestionData,
    ModelCall,
    ask_economic_plan,
    parse_economic_model_decision,
    run_economic_question,
)
from app.services.economic_question_files import (
    VerifiedEconomicQuestionDataError,
    run_verified_economic_question,
)
from app.services.housing_question_files import VerifiedHousingQuestionPaths
from app.services.housing_analysis import HousingAnalysisRun
from app.services.housing_filter import (
    HousingConditionFilterEvidence,
    HousingFilterValidationError,
)
from app.services.inflation_analysis import InflationAnalysisError, InflationEvidence
from app.services.inflation_comparison import InflationComparison
from app.tools.housing_chart import HousingChartError
from app.tools.housing_evidence import EvidenceBuildError, HousingAnalysisEvidence
from app.tools.inflation_chart import InflationChartError, build_inflation_chart


def _invalid_input() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"code": "invalid_economic_input", "message": "Soru ve aylık veri grupları geçerli olmalıdır."},
    )


class EconomicQuestionRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            started = perf_counter()
            try:
                response = await original(request)
            except RequestValidationError:
                # Avoid echoing request content, including JSON NaN/Infinity.
                error = _invalid_input()
                error.headers = _diagnostic_headers(request, started)
                raise error from None
            except HTTPException as error:
                error.headers = {**(error.headers or {}), **_diagnostic_headers(request, started)}
                raise
            response.headers.update(_diagnostic_headers(request, started))
            return response

        return handler


def _diagnostic_headers(request: Request, started: float) -> dict[str, str]:
    """Expose timings and enum-only model decisions, never questions or raw responses."""
    timings = [f"total;dur={(perf_counter() - started) * 1000:.3f}"]
    plan_ms = getattr(request.state, "economic_plan_ms", None)
    if plan_ms is not None:
        timings.append(f"plan;dur={plan_ms:.3f}")
    headers = {"Server-Timing": ", ".join(timings)}
    decision = getattr(request.state, "economic_model_decision", None)
    if decision is not None:
        headers["X-Analytics-Model-Decision"] = decision
    return headers


router = APIRouter(prefix="/analysis", tags=["analysis"], route_class=EconomicQuestionRoute)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EconomicBddkRow(BddkMonthlyRow):
    model_config = ConfigDict(extra="forbid", strict=True)


class EconomicEvdsRow(EvdsMonthlyRow):
    model_config = ConfigDict(extra="forbid", strict=True)


def _source_ref(value: str) -> str:
    if value.strip().lower() in {"", "none", "nan", "<na>"}:
        raise ValueError("Kaynak referansı boş olamaz.")
    return value.strip()


class EconomicHousingInput(_StrictModel):
    bddk_monthly: list[EconomicBddkRow] = Field(min_length=1)
    evds_monthly: list[EconomicEvdsRow] = Field(min_length=1)
    bddk_source_ref: str = Field(min_length=1)
    evds_source_refs: str = Field(min_length=1)

    @field_validator("bddk_source_ref", "evds_source_refs")
    @classmethod
    def validate_sources(cls, value: str) -> str:
        return _source_ref(value)


class EconomicInflationInput(_StrictModel):
    cpi_monthly: list[CpiMonthlyRow] = Field(min_length=1)
    source_ref: str = Field(min_length=1)

    @field_validator("source_ref")
    @classmethod
    def validate_source(cls, value: str) -> str:
        return _source_ref(value)


class EconomicQuestionText(_StrictModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARACTERS)

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Soru boş olamaz.")
        return value.strip()


class EconomicQuestionRequest(EconomicQuestionText):
    housing: EconomicHousingInput | None = None
    inflation: EconomicInflationInput | None = None


class HousingQuestionAnalysis(_StrictModel):
    analysis_id: Literal["housing_rate_down_real_credit_not_up"] = "housing_rate_down_real_credit_not_up"
    evidence: HousingAnalysisEvidence
    chart: dict[str, Any]


class HousingFilterQuestionAnalysis(_StrictModel):
    analysis_id: Literal["housing_condition_filter"] = "housing_condition_filter"
    evidence: HousingConditionFilterEvidence


class InflationQuestionAnalysis(_StrictModel):
    analysis_id: Literal["cpi_inflation_summary"] = "cpi_inflation_summary"
    evidence: InflationEvidence
    chart: dict[str, Any]


class InflationComparisonQuestionAnalysis(_StrictModel):
    analysis_id: Literal["cpi_two_year_comparison"] = "cpi_two_year_comparison"
    evidence: InflationComparison


EconomicAnalysis = Annotated[
    Union[
        HousingQuestionAnalysis,
        HousingFilterQuestionAnalysis,
        InflationQuestionAnalysis,
        InflationComparisonQuestionAnalysis,
    ],
    Field(discriminator="analysis_id"),
]


class _CoverageResponse(_StrictModel):
    available_periods: EconomicCoverage


class EconomicQuestionSuccess(_CoverageResponse):
    status: Literal["ok"] = "ok"
    decision: EconomicReadyDecision
    analysis: EconomicAnalysis


class _NoAnalysisResponse(_CoverageResponse):
    message: str
    analysis: None = None


class EconomicQuestionClarification(_NoAnalysisResponse):
    status: Literal["clarification_required"] = "clarification_required"
    decision: EconomicClarification


class EconomicQuestionUnsupported(_NoAnalysisResponse):
    status: Literal["unsupported"] = "unsupported"
    decision: EconomicUnsupported


class EconomicQuestionUnavailable(_NoAnalysisResponse):
    status: Literal["data_unavailable"] = "data_unavailable"
    decision: EconomicDataUnavailable


EconomicQuestionResponse = Annotated[
    Union[EconomicQuestionSuccess, EconomicQuestionClarification, EconomicQuestionUnsupported, EconomicQuestionUnavailable],
    Field(discriminator="status"),
]


class EconomicErrorDetail(_StrictModel):
    code: Literal["invalid_economic_input", "question_planning_failed", "invalid_question_plan"]
    message: str


class EconomicErrorResponse(_StrictModel):
    detail: EconomicErrorDetail


class EconomicFileErrorDetail(_StrictModel):
    code: Literal["economic_data_unavailable"] = "economic_data_unavailable"
    message: str


class EconomicFileErrorResponse(_StrictModel):
    detail: EconomicFileErrorDetail


def get_verified_economic_paths() -> VerifiedHousingQuestionPaths:
    """Only the server selects a package root; request/model fields cannot override it."""
    repo_root = Path(__file__).resolve().parents[2]
    load_dotenv(repo_root / ".env", override=False)
    configured = os.getenv("ANALYTICS_DATA_ROOT", "").strip()
    return VerifiedHousingQuestionPaths(project_root=Path(configured) if configured else repo_root)


def get_economic_question_model() -> ModelCall:
    return ask_economic_plan


def _observed_question_model(
    request: Request,
    model_call: ModelCall = Depends(get_economic_question_model),
) -> ModelCall:
    def observed(prompt: str) -> str:
        started = perf_counter()
        try:
            response = model_call(prompt)
        finally:
            # Includes the whole client call, not just provider generation time.
            request.state.economic_plan_ms = (perf_counter() - started) * 1000
        if isinstance(response, str) and len(response) <= MAX_PLAN_CHARACTERS:
            try:
                decision = parse_economic_model_decision(response)
            except ValidationError:
                pass  # The service still rejects the original response unchanged.
            else:
                detail = getattr(decision, "analysis_id", None) or decision.reason
                request.state.economic_model_decision = f"{decision.status}/{detail}"
        return response

    return observed


def _error(code: str, message: str) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY, detail={"code": code, "message": message},
    ) from None


@router.post(
    "/economic/question", response_model=EconomicQuestionResponse,
    responses={422: {"model": EconomicErrorResponse}, 502: {"model": EconomicErrorResponse}},
    summary="Plan a Turkish question and run one allowed Housing or CPI analysis",
)
def analyze_economic_question(
    request: EconomicQuestionRequest,
    model_call: ModelCall = Depends(_observed_question_model),
) -> EconomicQuestionResponse:
    housing = None if request.housing is None else HousingQuestionData(
        bddk_monthly=pd.DataFrame([row.model_dump() for row in request.housing.bddk_monthly]),
        evds_monthly=pd.DataFrame([row.model_dump() for row in request.housing.evds_monthly]),
        bddk_source_ref=request.housing.bddk_source_ref,
        evds_source_refs=request.housing.evds_source_refs,
    )
    inflation = None if request.inflation is None else InflationQuestionData(
        cpi_monthly=pd.DataFrame([row.model_dump() for row in request.inflation.cpi_monthly]),
        source_ref=request.inflation.source_ref,
    )
    try:
        result = run_economic_question(request.question, housing=housing, inflation=inflation, model_call=model_call)
        return _question_response(result)
    except EconomicPlanningError:
        _error("question_planning_failed", "Modelden analiz planı alınamadı.")
    except EconomicPlanValidationError:
        _error("invalid_question_plan", "Modelin analiz planı doğrulanamadı.")
    except (
        EconomicInputError, GoldAnalysisError, InflationAnalysisError, EvidenceBuildError,
        HousingChartError, InflationChartError, HousingFilterValidationError,
    ):
        raise _invalid_input() from None



@router.post(
    "/economic/question/files", response_model=EconomicQuestionResponse,
    responses={422: {"model": EconomicErrorResponse}, 502: {"model": EconomicErrorResponse},
               503: {"model": EconomicFileErrorResponse}},
    summary="Ask a Turkish question using server-configured, physically verified BDDK/EVDS files",
)
def analyze_verified_economic_question(
    request: EconomicQuestionText,
    paths: VerifiedHousingQuestionPaths = Depends(get_verified_economic_paths),
    model_call: ModelCall = Depends(_observed_question_model),
) -> EconomicQuestionResponse:
    try:
        result = run_verified_economic_question(request.question, paths, model_call=model_call)
        return _question_response(result)
    except EconomicPlanningError:
        _error("question_planning_failed", "Modelden analiz planı alınamadı.")
    except EconomicPlanValidationError:
        _error("invalid_question_plan", "Modelin analiz planı doğrulanamadı.")
    except (
        VerifiedEconomicQuestionDataError, EconomicInputError, GoldAnalysisError,
        InflationAnalysisError, EvidenceBuildError, HousingChartError, InflationChartError,
        HousingFilterValidationError,
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "economic_data_unavailable",
                    "message": "Sunucu veri paketi eksik, okunamıyor veya bütünlük doğrulamasını geçemedi."},
        ) from None


def _question_response(result: EconomicQuestionRun) -> EconomicQuestionResponse:
    common = {"available_periods": result.coverage, "decision": result.decision}
    if isinstance(result.decision, EconomicClarification):
        messages = {
            "period_required": "İncelenecek başlangıç ve bitiş dönemini belirtir misin?",
            "metric_ambiguous": "Hangi ölçüyü incelemek istediğini netleştirir misin?",
            "question_ambiguous": "Konut koşulunu mu, TÜFE değişimlerini mi inceleyelim?",
            "outside_coverage": "İstenen dönem ilgili veri grubunun kapsamı dışında; uygun bir dönem belirtir misin?",
        }
        return EconomicQuestionClarification(**common, message=messages[result.decision.reason])
    if isinstance(result.decision, EconomicUnsupported):
        return EconomicQuestionUnsupported(
            **common,
            message=(
                "Bu sürüm tek istekte konut koşulunu, TÜFE değişimlerini veya iki tam yılın "
                "TÜFE karşılaştırmasını inceleyebilir."
            ),
        )
    if isinstance(result.decision, EconomicDataUnavailable):
        return EconomicQuestionUnavailable(**common, message="İstenen analiz için kullanılabilir veri grubu yok.")
    if isinstance(result.decision, EconomicComparisonReadyPlan):
        if not isinstance(result.analysis, InflationComparison):
            raise RuntimeError("A comparison decision must contain the comparison result.")
        analysis = InflationComparisonQuestionAnalysis(evidence=result.analysis)
    elif isinstance(result.decision, EconomicHousingFilterReadyPlan):
        if not isinstance(result.analysis, HousingConditionFilterEvidence):
            raise RuntimeError("A filter decision must contain the filter result.")
        analysis = HousingFilterQuestionAnalysis(evidence=result.analysis)
    elif result.decision.analysis_id == HOUSING_ID and isinstance(result.analysis, HousingAnalysisRun):
        analysis = HousingQuestionAnalysis(evidence=result.analysis.evidence, chart=result.analysis.chart)
    elif result.decision.analysis_id == INFLATION_ID and isinstance(result.analysis, InflationEvidence):
        analysis = InflationQuestionAnalysis(
            evidence=result.analysis, chart=build_inflation_chart(result.analysis),
        )
    else:
        raise RuntimeError("A ready decision must contain the matching analysis result.")
    return EconomicQuestionSuccess(**common, analysis=analysis)

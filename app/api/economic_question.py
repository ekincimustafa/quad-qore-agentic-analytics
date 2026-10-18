"""Typed HTTP boundary for the bounded Housing/CPI question service."""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any, Literal, NoReturn, Union

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.requests import Request
from starlette.responses import Response

from app.api.housing import BddkMonthlyRow, EvdsMonthlyRow
from app.api.inflation import CpiMonthlyRow
from app.lakehouse.gold import GoldAnalysisError
from app.services.economic_question import (
    HOUSING_ID,
    INFLATION_ID,
    MAX_QUESTION_CHARACTERS,
    EconomicClarification,
    EconomicCoverage,
    EconomicDataUnavailable,
    EconomicInputError,
    EconomicPlanningError,
    EconomicPlanValidationError,
    EconomicReadyPlan,
    EconomicUnsupported,
    HousingQuestionData,
    InflationQuestionData,
    ModelCall,
    run_economic_question,
)
from app.services.housing_analysis import HousingAnalysisRun
from app.services.inflation_analysis import InflationAnalysisError, InflationEvidence
from app.tools.housing_chart import HousingChartError
from app.tools.housing_evidence import EvidenceBuildError, HousingAnalysisEvidence


def _invalid_input() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={"code": "invalid_economic_input", "message": "Soru ve aylık veri grupları geçerli olmalıdır."},
    )


class EconomicQuestionRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError:
                # Avoid echoing request content, including JSON NaN/Infinity.
                raise _invalid_input() from None

        return handler


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


class EconomicQuestionRequest(_StrictModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARACTERS)
    housing: EconomicHousingInput | None = None
    inflation: EconomicInflationInput | None = None

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Soru boş olamaz.")
        return value.strip()


class HousingQuestionAnalysis(_StrictModel):
    analysis_id: Literal["housing_rate_down_real_credit_not_up"] = "housing_rate_down_real_credit_not_up"
    evidence: HousingAnalysisEvidence
    chart: dict[str, Any]


class InflationQuestionAnalysis(_StrictModel):
    analysis_id: Literal["cpi_inflation_summary"] = "cpi_inflation_summary"
    evidence: InflationEvidence


EconomicAnalysis = Annotated[
    Union[HousingQuestionAnalysis, InflationQuestionAnalysis], Field(discriminator="analysis_id"),
]


class _CoverageResponse(_StrictModel):
    available_periods: EconomicCoverage


class EconomicQuestionSuccess(_CoverageResponse):
    status: Literal["ok"] = "ok"
    decision: EconomicReadyPlan
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


def get_economic_question_model() -> ModelCall:
    from app.connectors.llm_client import ask_llm

    return ask_llm


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
    model_call: ModelCall = Depends(get_economic_question_model),
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
    except EconomicPlanningError:
        _error("question_planning_failed", "Modelden analiz planı alınamadı.")
    except EconomicPlanValidationError:
        _error("invalid_question_plan", "Modelin analiz planı doğrulanamadı.")
    except (EconomicInputError, GoldAnalysisError, InflationAnalysisError, EvidenceBuildError, HousingChartError):
        raise _invalid_input() from None

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
            **common, message="Bu sürüm tek istekte konut koşulunu veya TÜFE değişimlerini inceleyebilir.",
        )
    if isinstance(result.decision, EconomicDataUnavailable):
        return EconomicQuestionUnavailable(**common, message="İstenen analiz için kullanılabilir veri grubu yok.")
    if result.decision.analysis_id == HOUSING_ID and isinstance(result.analysis, HousingAnalysisRun):
        analysis = HousingQuestionAnalysis(evidence=result.analysis.evidence, chart=result.analysis.chart)
    elif result.decision.analysis_id == INFLATION_ID and isinstance(result.analysis, InflationEvidence):
        analysis = InflationQuestionAnalysis(evidence=result.analysis)
    else:
        raise RuntimeError("A ready decision must contain the matching analysis result.")
    return EconomicQuestionSuccess(**common, analysis=analysis)

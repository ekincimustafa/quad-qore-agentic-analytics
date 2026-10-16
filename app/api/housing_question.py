"""Question API over caller-supplied normalized rows; no file paths accepted."""

from __future__ import annotations

from typing import Annotated, Any, Literal, NoReturn, Union

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.housing import BddkMonthlyRow, EvdsMonthlyRow, get_housing_narrator
from app.lakehouse.core_validators import check_missing_periods, parse_period_to_date
from app.lakehouse.gold import GoldAnalysisError
from app.services.housing_analysis import HousingNarrationError, HousingNarrator
from app.services.housing_question import (
    MAX_QUESTION_CHARACTERS,
    HousingClarification,
    HousingDataCoverage,
    HousingPlanningError,
    HousingPlanValidationError,
    HousingReadyPlan,
    HousingUnsupported,
    ModelCall,
    run_housing_question,
)
from app.tools.housing_chart import HousingChartError
from app.tools.housing_evidence import EvidenceBuildError, HousingAnalysisEvidence


router = APIRouter(prefix="/analysis", tags=["analysis"])


class HousingQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(strict=True, min_length=1, max_length=MAX_QUESTION_CHARACTERS)
    bddk_monthly: list[BddkMonthlyRow] = Field(min_length=1)
    evds_monthly: list[EvdsMonthlyRow] = Field(min_length=1)
    bddk_source_ref: str = Field(strict=True, min_length=1)
    evds_source_refs: str = Field(strict=True, min_length=1)
    include_narration: bool = Field(default=False, strict=True)

    @field_validator("question", "bddk_source_ref", "evds_source_refs")
    @classmethod
    def require_non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Metin alanı boş bırakılamaz.")
        return value.strip()


class _QuestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available_period: HousingDataCoverage


class HousingQuestionSuccess(_QuestionResponse):
    status: Literal["ok"] = "ok"
    decision: HousingReadyPlan
    evidence: HousingAnalysisEvidence
    chart: dict[str, Any]
    narration: str | None


class _NoAnalysisResponse(_QuestionResponse):
    message: str
    evidence: None = None
    chart: None = None
    narration: None = None


class HousingQuestionClarification(_NoAnalysisResponse):
    status: Literal["clarification_required"] = "clarification_required"
    decision: HousingClarification


class HousingQuestionUnsupported(_NoAnalysisResponse):
    status: Literal["unsupported"] = "unsupported"
    decision: HousingUnsupported


HousingQuestionResponse = Annotated[
    Union[HousingQuestionSuccess, HousingQuestionClarification, HousingQuestionUnsupported],
    Field(discriminator="status"),
]


def get_housing_question_model() -> ModelCall:
    """Return the configured client without reading settings until it is called."""
    from app.connectors.llm_client import ask_llm

    return ask_llm


def _question_inputs(
    request: HousingQuestionRequest,
) -> tuple[pd.DataFrame, pd.DataFrame, HousingDataCoverage]:
    """Derive shared coverage from validated rows, never from a model plan."""
    period_sets = []
    for rows in (request.bddk_monthly, request.evds_monthly):
        periods = [row.period for row in rows]
        for period in periods:
            # Reject year zero and non-canonical strings before an LLM request.
            if parse_period_to_date(period).isoformat()[:7] != period:
                raise ValueError("Dönem YYYY-MM biçiminde olmalıdır.")
        if len(periods) != len(set(periods)):
            raise ValueError("Mükerrer dönem kabul edilmez.")
        period_sets.append(set(periods))
    shared = period_sets[0] & period_sets[1]
    if not shared:
        raise ValueError("İki veri kümesinde ortak dönem yok.")
    coverage = HousingDataCoverage(start_period=min(shared), end_period=max(shared))
    check_missing_periods(shared, coverage.start_period, coverage.end_period)
    return (
        pd.DataFrame([row.model_dump() for row in request.bddk_monthly]),
        pd.DataFrame([row.model_dump() for row in request.evds_monthly]),
        coverage,
    )


def _error(http_status: int, code: str, message: str) -> NoReturn:
    raise HTTPException(
        status_code=http_status, detail={"code": code, "message": message},
    ) from None


@router.post(
    "/housing/question",
    response_model=HousingQuestionResponse,
    summary="Plan a Turkish question and run the allowed Housing analysis",
)
def analyze_housing_question(
    request: HousingQuestionRequest,
    model_call: ModelCall = Depends(get_housing_question_model),
    narrator: HousingNarrator = Depends(get_housing_narrator),
) -> HousingQuestionResponse:
    try:
        bddk, evds, coverage = _question_inputs(request)
    except ValueError:
        _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_analysis_input",
            "Veriler geçerli ve tekil aylardan oluşmalı; ortak dönem kesintisiz olmalıdır.",
        )
    try:
        result = run_housing_question(
            request.question, bddk, evds, coverage=coverage,
            bddk_source_ref=request.bddk_source_ref,
            evds_source_refs=request.evds_source_refs,
            model_call=model_call,
            narrator=narrator if request.include_narration else None,
        )
    except HousingPlanningError:
        _error(
            status.HTTP_502_BAD_GATEWAY, "question_planning_failed",
            "Modelden analiz planı alınamadı.",
        )
    except HousingPlanValidationError:
        _error(
            status.HTTP_502_BAD_GATEWAY, "invalid_question_plan",
            "Modelin analiz planı doğrulanamadı.",
        )
    except (GoldAnalysisError, EvidenceBuildError, HousingChartError):
        _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid_analysis_input",
            "Veriler doğrulanmış konut analizi için uygun değil.",
        )
    except HousingNarrationError:
        _error(
            status.HTTP_502_BAD_GATEWAY, "narration_failed",
            "Analiz anlatımı doğrulanamadı.",
        )

    decision = result.decision
    if isinstance(decision, HousingClarification):
        messages = {
            "period_required": "İncelenecek başlangıç ve bitiş dönemini belirtir misin?",
            "metric_ambiguous": "Konut kredisi stokunu nominal mi, enflasyondan arındırılmış reel olarak mı kastediyorsun?",
            "question_ambiguous": "Hangi konut kredisi koşulunu incelememi istediğini netleştirir misin?",
            "outside_coverage": (
                f"Bu girdilerde ortak dönem {coverage.start_period}–{coverage.end_period}. "
                "Bu kapsamda bir analiz dönemi belirtir misin?"
            ),
        }
        return HousingQuestionClarification(
            available_period=coverage, decision=decision, message=messages[decision.reason],
        )
    if isinstance(decision, HousingUnsupported):
        return HousingQuestionUnsupported(
            available_period=coverage, decision=decision,
            message=(
                "Bu sürüm, faiz düşerken reel konut kredisi stokunun artmadığı "
                "ayları bulma analizini destekliyor. İstenen diğer analiz henüz desteklenmiyor."
            ),
        )
    if result.analysis is None:
        raise RuntimeError("A ready decision must contain an analysis result.")
    return HousingQuestionSuccess(
        available_period=coverage, decision=decision,
        evidence=result.analysis.evidence, chart=result.analysis.chart,
        narration=result.analysis.narration,
    )

"""FastAPI contracts for verified housing-loan analysis."""

from __future__ import annotations

from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from app.lakehouse.gold import (
    DEFAULT_END_PERIOD,
    DEFAULT_START_PERIOD,
    GoldAnalysisError,
)
from app.services.housing_analysis import (
    HousingNarrationError,
    HousingNarrator,
    run_housing_analysis,
)
from app.services.housing_demo import (
    HousingDemoDataError,
    HousingDemoPaths,
    run_file_backed_housing_demo,
)
from app.tools.housing_chart import HousingChartError
from app.tools.housing_evidence import EvidenceBuildError, HousingAnalysisEvidence
from app.tools.housing_narrator import narrate_housing_evidence_with_mia


PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0)]
PositiveFiniteFloat = Annotated[FiniteFloat, Field(gt=0)]
PositiveStrictInt = Annotated[int, Field(strict=True, gt=0)]

router = APIRouter(prefix="/analysis", tags=["analysis"])


class BddkMonthlyRow(BaseModel):
    """Normalized monthly BDDK input required by the Gold layer."""

    model_config = ConfigDict(extra="forbid")

    period: str = Field(pattern=PERIOD_PATTERN)
    nominal_housing_loan_mn_try: NonNegativeFiniteFloat


class EvdsMonthlyRow(BaseModel):
    """Normalized monthly EVDS input required by the Gold layer."""

    model_config = ConfigDict(extra="forbid")

    period: str = Field(pattern=PERIOD_PATTERN)
    housing_loan_interest_rate_pct: NonNegativeFiniteFloat
    weekly_observation_count: PositiveStrictInt
    cpi_index: PositiveFiniteFloat
    housing_price_index: PositiveFiniteFloat


class HousingAnalysisRequest(BaseModel):
    """Controlled input contract for the first housing analysis."""

    model_config = ConfigDict(extra="forbid")

    bddk_monthly: list[BddkMonthlyRow] = Field(min_length=1)
    evds_monthly: list[EvdsMonthlyRow] = Field(min_length=1)
    start_period: str = Field(default=DEFAULT_START_PERIOD, pattern=PERIOD_PATTERN)
    end_period: str = Field(default=DEFAULT_END_PERIOD, pattern=PERIOD_PATTERN)
    bddk_source_ref: str = Field(
        default="BDDK monthly bulletin, Table 4, sector 10001, TL",
        min_length=1,
    )
    evds_source_refs: str = Field(
        default="TP.KTF12; TP.TUKFIY2025.GENEL; TP.KFE.TR",
        min_length=1,
    )
    include_narration: bool = False


class HousingDemoRequest(BaseModel):
    """Small request contract for the server-side Silver demo."""

    model_config = ConfigDict(extra="forbid")

    start_period: str = Field(default=DEFAULT_START_PERIOD, pattern=PERIOD_PATTERN)
    end_period: str = Field(default=DEFAULT_END_PERIOD, pattern=PERIOD_PATTERN)
    include_narration: bool = False


class HousingAnalysisResponse(BaseModel):
    """Evidence-first API response; narration is present only when requested."""

    status: Literal["ok"] = "ok"
    evidence: HousingAnalysisEvidence
    chart: dict[str, Any]
    narration: str | None


def get_housing_narrator() -> HousingNarrator:
    """Provide the configured MIA narrator; replaceable in offline tests."""

    return narrate_housing_evidence_with_mia


def get_housing_demo_paths() -> HousingDemoPaths:
    """Provide server-controlled demo inputs; replaceable in offline tests."""

    return HousingDemoPaths()


def _analysis_response(result: Any) -> HousingAnalysisResponse:
    return HousingAnalysisResponse(
        evidence=result.evidence,
        chart=result.chart,
        narration=result.narration,
    )


def _raise_invalid_input(exc: Exception) -> None:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "code": "invalid_analysis_input",
            "message": str(exc),
        },
    ) from exc


def _raise_narration_error(exc: HousingNarrationError) -> None:
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={
            "code": "narration_failed",
            "message": str(exc),
        },
    ) from exc


@router.post(
    "/housing",
    response_model=HousingAnalysisResponse,
    summary="Run the verified housing-loan analysis",
)
def analyze_housing(
    request: HousingAnalysisRequest,
    narrator: HousingNarrator = Depends(get_housing_narrator),
) -> HousingAnalysisResponse:
    """Run deterministic calculations before optionally crossing the LLM boundary."""

    bddk_monthly = pd.DataFrame(
        [row.model_dump() for row in request.bddk_monthly]
    )
    evds_monthly = pd.DataFrame(
        [row.model_dump() for row in request.evds_monthly]
    )

    selected_narrator = narrator if request.include_narration else None
    try:
        result = run_housing_analysis(
            bddk_monthly,
            evds_monthly,
            start_period=request.start_period,
            end_period=request.end_period,
            bddk_source_ref=request.bddk_source_ref,
            evds_source_refs=request.evds_source_refs,
            narrator=selected_narrator,
        )
    except (GoldAnalysisError, EvidenceBuildError, HousingChartError) as exc:
        _raise_invalid_input(exc)
    except HousingNarrationError as exc:
        _raise_narration_error(exc)

    return _analysis_response(result)


@router.post(
    "/housing/demo",
    response_model=HousingAnalysisResponse,
    summary="Run the first demo from server-side Silver artifacts",
)
def analyze_file_backed_housing_demo(
    request: HousingDemoRequest,
    paths: HousingDemoPaths = Depends(get_housing_demo_paths),
    narrator: HousingNarrator = Depends(get_housing_narrator),
) -> HousingAnalysisResponse:
    """Run the demo without accepting analytical rows from the caller."""

    selected_narrator = narrator if request.include_narration else None
    try:
        result = run_file_backed_housing_demo(
            paths,
            start_period=request.start_period,
            end_period=request.end_period,
            narrator=selected_narrator,
        )
    except HousingDemoDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "demo_data_unavailable",
                "message": str(exc),
            },
        ) from exc
    except (GoldAnalysisError, EvidenceBuildError, HousingChartError) as exc:
        _raise_invalid_input(exc)
    except HousingNarrationError as exc:
        _raise_narration_error(exc)

    return _analysis_response(result)

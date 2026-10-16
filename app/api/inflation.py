"""Key-free CPI analysis over caller-supplied normalized monthly observations."""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator
from starlette.requests import Request
from starlette.responses import Response

from app.services.inflation_analysis import (
    InflationAnalysisError,
    InflationEvidence,
    build_inflation_evidence,
)


Month = Annotated[str, Field(strict=True, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]


def _invalid_input() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "code": "invalid_inflation_input",
            "message": "TÜFE girdileri tekil, pozitif ve kesintisiz aylardan oluşmalı; analiz dönemi bu kapsamda olmalıdır.",
        },
    )


class InflationRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError:
                # The default handler echoes input, including unencodable NaN/Inf.
                raise _invalid_input() from None

        return handler


router = APIRouter(prefix="/analysis", tags=["analysis"], route_class=InflationRoute)


class CpiMonthlyRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: Month
    cpi_index: Annotated[FiniteFloat, Field(strict=True, gt=0)]


class InflationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpi_monthly: list[CpiMonthlyRow] = Field(min_length=1)
    start_period: Month
    end_period: Month
    source_ref: str = Field(strict=True, min_length=1)

    @field_validator("source_ref")
    @classmethod
    def require_source_ref(cls, value: str) -> str:
        if value.strip().lower() in {"", "none", "nan", "<na>"}:
            raise ValueError("Kaynak referansı boş olamaz.")
        return value.strip()


class InflationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    evidence: InflationEvidence


class InflationErrorDetail(BaseModel):
    code: Literal["invalid_inflation_input"]
    message: str


class InflationErrorResponse(BaseModel):
    detail: InflationErrorDetail


@router.post(
    "/inflation", response_model=InflationResponse,
    responses={422: {"model": InflationErrorResponse}},
    summary="Calculate monthly and annual CPI changes without a model call",
)
def analyze_inflation(request: InflationRequest) -> InflationResponse:
    try:
        evidence = build_inflation_evidence(
            pd.DataFrame([row.model_dump() for row in request.cpi_monthly]),
            start_period=request.start_period, end_period=request.end_period,
            source_ref=request.source_ref,
        )
    except InflationAnalysisError:
        raise _invalid_input() from None
    return InflationResponse(evidence=evidence)

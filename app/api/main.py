from fastapi import FastAPI
from pydantic import BaseModel

from app.api.housing import router as housing_router


APP_VERSION = "0.1.0"


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


def create_app() -> FastAPI:
    application = FastAPI(
        title="Quad-Qore Agentic Analytics API",
        description=(
            "Harness-first agentic analytics platform "
            "developed for KKB Hackathon 2026."
        ),
        version=APP_VERSION,
    )
    application.include_router(housing_router)

    @application.get(
        "/health",
        response_model=HealthResponse,
        tags=["system"],
        summary="Check API health",
    )
    def health_check() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="quad-qore-api",
            version=APP_VERSION,
        )

    return application


app = create_app()

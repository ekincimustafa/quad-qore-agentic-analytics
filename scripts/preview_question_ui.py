"""Explicit offline UI preview: fixed plans, real verified local files, no live model."""

import json

import uvicorn

from app.api.economic_question import get_economic_question_model
from app.api.main import create_app


def fixed_plan(prompt: str) -> str:
    question = json.loads(prompt.split("İSTEK_VERİSİ:\n", 1)[1])["question"]
    if question == "2021-2025 faiz düşerken reel konut kredisi stokunun artmadığı aylar hangileri?":
        plan = {"status": "ready", "analysis_id": "housing_rate_down_real_credit_not_up", "start_period": "2021-01", "end_period": "2025-12"}
    elif question == "2023 Ocak-Aralık TÜFE aylık ve yıllık değişimlerini özetle.":
        plan = {"status": "ready", "analysis_id": "cpi_inflation_summary", "start_period": "2023-01", "end_period": "2023-12"}
    elif question == "2023 ve 2024 TÜFE değişimlerini karşılaştır.":
        plan = {"status": "ready", "analysis_id": "cpi_two_year_comparison", "first_year": 2023, "second_year": 2024}
    else:
        plan = {"status": "clarification_required", "reason": "question_ambiguous"}
    return json.dumps(plan)


def create_preview_app():
    app = create_app()
    app.state.offline_preview = True
    app.dependency_overrides[get_economic_question_model] = lambda: fixed_plan
    return app


if __name__ == "__main__":
    uvicorn.run(create_preview_app(), host="127.0.0.1", port=8000)

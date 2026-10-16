"""Exercise question planning and real deterministic execution without a network."""

import json
import socket
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from app.connectors import llm_client
from app.lakehouse.gold import GoldAnalysisError
from app.services import housing_question as service
from app.services.housing_analysis import HousingNarrationError, run_housing_analysis


QUESTION = (
    "2021 Ocak-Mart arasında konut kredisi faizi düşerken "
    "reel konut kredisi stokunun artmadığı ayları bul."
)


@pytest.fixture(autouse=True)
def no_network_or_unconfigured_model(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("A real network/model call is forbidden in offline tests")
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(llm_client, "ask_llm", forbidden)


@pytest.fixture
def coverage():
    return service.HousingDataCoverage(start_period="2021-01", end_period="2021-03")


@pytest.fixture
def inputs():
    path = Path(__file__).resolve().parents[1] / "docs/housing-api-example.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return (
        pd.DataFrame(payload["bddk_monthly"]),
        pd.DataFrame(payload["evds_monthly"]),
        {
            "bddk_source_ref": payload["bddk_source_ref"],
            "evds_source_refs": payload["evds_source_refs"],
        },
    )


def ready(**changes):
    return {
        "status": "ready", "analysis_id": service.ANALYSIS_ID,
        "start_period": "2021-01", "end_period": "2021-03", **changes,
    }


def test_question_runs_existing_service_with_identical_numeric_results(coverage, inputs):
    bddk, evds, refs = inputs
    prompts = []

    def model(prompt):
        prompts.append(prompt)
        return json.dumps(ready())

    result = service.run_housing_question(
        QUESTION, bddk, evds, coverage=coverage, model_call=model, **refs,
    )
    direct = run_housing_analysis(
        bddk, evds, start_period="2021-01", end_period="2021-03", **refs,
    )
    assert isinstance(result.decision, service.HousingReadyPlan)
    assert result.analysis.evidence.model_dump() == direct.evidence.model_dump()
    assert result.analysis.chart == direct.chart
    assert result.analysis.evidence.observed_month_count == 3
    assert result.analysis.evidence.matched_periods == ("2021-02",)
    assert result.analysis.narration is None
    assert len(prompts) == 1
    assert QUESTION in prompts[0]


def test_trusted_plan_period_is_forwarded_once_without_recalculating(monkeypatch, coverage, inputs):
    bddk, evds, refs = inputs
    original = service.run_housing_analysis
    calls = []

    def tool(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "run_housing_analysis", tool)
    result = service.run_housing_question(
        "2021 Şubat-Mart için reel kredi koşulunu incele.", bddk, evds,
        coverage=coverage, model_call=lambda _: json.dumps(ready(start_period="2021-02")),
        **refs,
    )
    assert len(calls) == 1
    assert calls[0][0][0] is bddk and calls[0][0][1] is evds
    assert calls[0][1]["start_period"] == "2021-02"
    assert calls[0][1]["end_period"] == "2021-03"
    assert result.analysis.evidence.observed_month_count == 2
    # Existing Gold semantics are preserved: the first selected month has no delta.
    assert result.analysis.evidence.matched_periods == ()


@pytest.mark.parametrize("question,decision", [
    ("Faiz düşerken reel konut kredisinin artmadığı ayları bul.",
     {"status": "clarification_required", "reason": "period_required"}),
    ("2021 Ocak-Mart faiz düşerken kredinin artmadığı ayları bul.",
     {"status": "clarification_required", "reason": "metric_ambiguous"}),
    ("2021 Ocak-Mart enflasyonun seyrini özetle.",
     {"status": "unsupported", "reason": "unsupported_analysis"}),
    ("2020 Aralık-2021 Mart faiz düşerken reel kredinin artmadığı ayları bul.",
     ready(start_period="2020-12")),
    ("2021 Ocak-Nisan faiz düşerken reel kredinin artmadığı ayları bul.",
     ready(end_period="2021-04")),
])
def test_non_executable_decision_never_calls_analysis_or_narration(
    monkeypatch, coverage, inputs, question, decision,
):
    def forbidden(*args, **kwargs):
        raise AssertionError("No analysis/narration may run")

    monkeypatch.setattr(service, "run_housing_analysis", forbidden)
    bddk, evds, refs = inputs

    def model(prompt):
        assert question in prompt
        return json.dumps(decision)

    result = service.run_housing_question(
        question, bddk, evds, coverage=coverage,
        model_call=model, narrator=forbidden, **refs,
    )
    assert result.analysis is None
    if decision["status"] == "ready":
        assert result.decision.reason == "outside_coverage"
    else:
        assert result.decision.model_dump() == decision


@pytest.mark.parametrize("response", [
    "", "   ", None, 123, "not JSON", "[]",
    "```json\n" + json.dumps(ready()) + "\n```",
    json.dumps(ready(analysis_id="web_search")),
    json.dumps(ready(analysis_id="inflation_summary")),
    json.dumps(ready(sql="SELECT * FROM secrets")),
    json.dumps(ready(path="../../.env")),
    json.dumps(ready(coverage={"start_period": "1900-01", "end_period": "9999-12"})),
    json.dumps(ready(status="execute")),
    json.dumps(ready(start_period="0000-01")),
    json.dumps(ready(start_period="2021-13")),
    json.dumps(ready(start_period="2021-04", end_period="2021-01")),
    json.dumps(ready(start_period=202101)),
    json.dumps(ready(start_period="2021-01\n")),
    json.dumps({"status": "unsupported", "reason": "unsupported_analysis", "analysis_id": service.ANALYSIS_ID}),
    "x" * (service.MAX_PLAN_CHARACTERS + 1),
])
def test_invalid_plan_stops_before_any_tool_call(monkeypatch, coverage, inputs, response):
    def forbidden(*args, **kwargs):
        raise AssertionError("An invalid plan must not reach the tool")

    monkeypatch.setattr(service, "run_housing_analysis", forbidden)
    bddk, evds, refs = inputs
    with pytest.raises(service.HousingPlanValidationError):
        service.run_housing_question(
            QUESTION, bddk, evds, coverage=coverage,
            model_call=lambda _: response, **refs,
        )


@pytest.mark.parametrize("question", [None, 123, "", "  ", "x" * 2_001])
def test_invalid_question_never_calls_model(coverage, question):
    def forbidden(_):
        raise AssertionError("Invalid input must not reach the model")

    with pytest.raises(ValueError):
        service.plan_housing_question(question, coverage, model_call=forbidden)


@pytest.mark.parametrize("start,end", [
    ("2021-04", "2021-01"), ("0000-01", "2021-03"), ("2021-13", "2021-03"),
])
def test_invalid_server_coverage_is_rejected(start, end):
    with pytest.raises(ValidationError):
        service.HousingDataCoverage(start_period=start, end_period=end)


def test_plan_and_coverage_are_immutable(coverage):
    plan = service.validate_housing_question_plan(json.dumps(ready()), coverage)
    with pytest.raises(ValidationError):
        plan.analysis_id = "web_search"
    with pytest.raises(ValidationError):
        coverage.start_period = "1900-01"


def test_model_failure_is_safe_and_not_retried(monkeypatch, coverage, inputs):
    calls = []

    def fail(prompt):
        calls.append(prompt)
        raise RuntimeError("private-key secret-provider-body")

    bddk, evds, refs = inputs
    with pytest.raises(service.HousingPlanningError) as error:
        service.run_housing_question(
            QUESTION, bddk, evds, coverage=coverage, model_call=fail, **refs,
        )
    assert len(calls) == 1
    assert "private-key" not in str(error.value)
    assert "secret-provider-body" not in str(error.value)
    assert error.value.__suppress_context__


def test_default_planner_uses_configured_llm_client(monkeypatch, coverage):
    calls = []

    def model(prompt):
        calls.append(prompt)
        return json.dumps(ready())

    monkeypatch.setattr(llm_client, "ask_llm", model)
    result = service.plan_housing_question(QUESTION, coverage)
    assert result.analysis_id == service.ANALYSIS_ID
    assert len(calls) == 1


def test_missing_data_keeps_existing_fail_closed_behavior(coverage, inputs):
    bddk, evds, refs = inputs
    with pytest.raises(GoldAnalysisError, match="missing periods"):
        service.run_housing_question(
            QUESTION, bddk, evds.iloc[:-1].copy(), coverage=coverage,
            model_call=lambda _: json.dumps(ready()), **refs,
        )


def test_explicit_narrator_receives_actual_evidence(coverage, inputs):
    bddk, evds, refs = inputs
    evidence_calls = []

    def narrator(evidence):
        evidence_calls.append(evidence)
        return "test narration"

    result = service.run_housing_question(
        QUESTION, bddk, evds, coverage=coverage,
        model_call=lambda _: json.dumps(ready()), narrator=narrator, **refs,
    )
    assert evidence_calls == [result.analysis.evidence]
    assert result.analysis.narration == "test narration"


def test_narrator_failure_does_not_return_partial_success(coverage, inputs):
    bddk, evds, refs = inputs

    def fail(_):
        raise RuntimeError("narrator failed")

    with pytest.raises(HousingNarrationError):
        service.run_housing_question(
            QUESTION, bddk, evds, coverage=coverage,
            model_call=lambda _: json.dumps(ready()), narrator=fail, **refs,
        )

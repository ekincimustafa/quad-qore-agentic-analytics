"""Question-only HTTP behavior with physical synthetic packages and stub plans."""

from dataclasses import replace
import json
from pathlib import Path
import shutil

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api import economic_question as api
from app.api.main import create_app
from app.connectors import llm_client
from app.lakehouse.gold import GoldAnalysisError
from app.services import economic_question as core
from app.services import economic_question_files as files_service
from app.services.housing_question import HousingDataCoverage
from app.services.housing_question_files import (
    VerifiedHousingQuestionPaths,
    VerifiedQuestionInputs,
    run_verified_housing_question,
)
from app.services.inflation_analysis import InflationEvidence, build_inflation_evidence
from app.services.inflation_comparison import compare_inflation_years
from app.tools.inflation_chart import build_inflation_chart
from tests.housing_test_support import write_bddk


ENDPOINT = "/analysis/economic/question/files"
QUESTION = "2021 Ocak-Şubat faiz düşerken reel konut kredisinin artmadığı ayları bul."


def forbidden(*args, **kwargs):
    raise AssertionError("This operation must not run")


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(llm_client, "ask_llm", forbidden)
    monkeypatch.setattr(llm_client, "read_llm_settings", forbidden)


@pytest.fixture
def package(tmp_path):
    shutil.copytree(Path(__file__).parent / "fixtures/evds_manifest_v1", tmp_path, dirs_exist_ok=True)
    write_bddk(tmp_path, ["2021-01", "2021-02", "2021-03"])
    return VerifiedHousingQuestionPaths(project_root=tmp_path)


def ready(analysis_id=core.HOUSING_ID, **updates):
    return {"status": "ready", "analysis_id": analysis_id,
            "start_period": "2021-01", "end_period": "2021-02", **updates}


def client_with_model(package, model):
    app = create_app()
    app.dependency_overrides[api.get_verified_economic_paths] = lambda: package
    app.dependency_overrides[api.get_economic_question_model] = lambda: model
    return TestClient(app)


@pytest.mark.parametrize("question,plan,reason", [
    ("Ocak-Şubat TÜFE aylık ve yıllık oranlarını göster.",
     ready(core.INFLATION_ID), "period_required"),
    ("2021 Ocak-Şubat konut kredisi faizi düşerken kredi bakiyesinin artmadığı ayları göster.",
     ready(core.HOUSING_ID), "metric_ambiguous"),
    ("2021 Ocak ayından itibaren TÜFE değişimlerini göster.",
     ready(core.INFLATION_ID, end_period="2021-01"), "period_required"),
    ("2021 Ocak'tan sonraki TÜFE değişimlerini göster.",
     ready(core.INFLATION_ID, end_period="2021-01"), "period_required"),
])
def test_observed_ready_mistakes_are_blocked_after_file_verification(
    package, monkeypatch, question, plan, reason,
):
    monkeypatch.setattr(core, "run_housing_analysis", forbidden)
    monkeypatch.setattr(core, "build_inflation_evidence", forbidden)
    prompts = []

    def model(prompt):
        prompts.append(prompt)
        return json.dumps(plan)

    with client_with_model(package, model) as client:
        response = client.post(ENDPOINT, json={"question": question})
    assert response.status_code == 200 and len(prompts) == 1
    body = response.json()
    assert body["status"] == "clarification_required"
    assert body["decision"] == {"status": "clarification_required", "reason": reason}
    assert body["analysis"] is None


@pytest.mark.parametrize("analysis_id", [core.HOUSING_ID, core.INFLATION_ID])
def test_question_only_request_equals_existing_calculation(package, monkeypatch, analysis_id):
    prompts, calls = [], []
    housing, inflation = core.run_housing_analysis, core.build_inflation_evidence

    def run_housing(*args, **kwargs):
        calls.append(core.HOUSING_ID)
        return housing(*args, **kwargs)

    def run_inflation(*args, **kwargs):
        calls.append(core.INFLATION_ID)
        return inflation(*args, **kwargs)

    monkeypatch.setattr(core, "run_housing_analysis", run_housing)
    monkeypatch.setattr(core, "build_inflation_evidence", run_inflation)

    def model(prompt):
        prompts.append(prompt)
        assert str(package.project_root) not in prompt
        assert "synthetic-bddk" not in prompt and "receipts/" not in prompt
        return json.dumps(ready(analysis_id))

    with client_with_model(package, model) as client:
        response = client.post(ENDPOINT, json={"question": QUESTION})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["decision"] == ready(analysis_id)
    assert calls == [analysis_id] and len(prompts) == 1
    assert body["available_periods"] == {
        key: {"start_period": "2021-01", "end_period": "2021-02"}
        for key in ("housing", "inflation")
    }
    if analysis_id == core.HOUSING_ID:
        direct = run_verified_housing_question(QUESTION, package, model_call=lambda _: json.dumps(ready()))
        assert body["analysis"]["evidence"] == direct.analysis.evidence.model_dump(mode="json")
        assert body["analysis"]["chart"] == direct.analysis.chart
        assert direct.analysis.narration is None
    else:
        manifest = json.loads((package.project_root / package.evds_manifest).read_text(encoding="utf-8"))
        refs = next(s["bronze"] for s in manifest["series"] if s["series_code"] == "TP.TUKFIY2025.GENEL")
        source = "; ".join(r["receipt_path"] for r in refs)
        direct = build_inflation_evidence(
            pd.read_csv(package.project_root / manifest["silver"]["path"]),
            start_period="2021-01", end_period="2021-02", source_ref=source,
        )
        evidence = body["analysis"]["evidence"]
        assert {k: v for k, v in evidence.items() if k not in {"input_origin", "limitations"}} == (
            direct.model_dump(mode="json", exclude={"input_origin", "limitations"})
        )
        assert evidence["input_origin"] == "verified_files"
        assert evidence["limitations"][1:] == list(direct.limitations[1:])
        assert evidence["observations"][0]["monthly_inflation_pct"] is None
        assert evidence["observations"][1]["monthly_inflation_pct"] == pytest.approx(1)
        chart = body["analysis"]["chart"]
        assert chart == build_inflation_chart(InflationEvidence.model_validate(evidence))
        for trace, field in zip(chart["data"], ("cpi_index", "monthly_inflation_pct", "annual_inflation_pct")):
            assert trace["y"] == [row[field] for row in evidence["observations"]]


def test_cpi_history_and_coverage_are_not_clipped_to_housing(package):
    write_bddk(package.project_root, ["2021-02"])
    with client_with_model(package, lambda _: json.dumps(ready(core.INFLATION_ID, start_period="2021-02"))) as client:
        response = client.post(ENDPOINT, json={"question": "2021 Şubat TÜFE aylık değişimi nedir?"})
    body = response.json()
    assert response.status_code == 200
    assert body["available_periods"]["housing"]["start_period"] == "2021-02"
    assert body["available_periods"]["inflation"]["start_period"] == "2021-01"
    month = body["analysis"]["evidence"]["observations"][0]
    assert month["monthly_inflation_pct"] == pytest.approx(1)
    assert month["annual_inflation_pct"] is None


def test_files_comparison_matches_core_and_marks_nested_verified_provenance(
    package, monkeypatch,
):
    periods = pd.period_range("2022-12", "2024-12", freq="M").astype(str).tolist()
    cpi = pd.DataFrame({
        "period": periods,
        "cpi_index": [
            100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 112.0, 114.0, 116.0, 118.0, 119.0, 119.5,
            120.0, 123.0, 126.0, 129.0, 132.0, 135.0, 138.0, 141.0, 144.0, 146.0, 147.0, 148.5,
            150.0,
        ],
    })
    inputs = VerifiedQuestionInputs(
        bddk_monthly=pd.DataFrame({"period": periods}),
        evds_monthly=cpi,
        housing_coverage=HousingDataCoverage(start_period="2022-12", end_period="2024-12"),
        evds_source_refs="synthetic://evds",
        cpi_source_ref="verified://cpi-receipt",
    )
    monkeypatch.setattr(files_service, "load_verified_question_inputs", lambda _: inputs)
    question = "2023 ve 2024 TÜFE değişimlerini karşılaştır."
    plan = {"status": "ready", "analysis_id": core.COMPARISON_ID,
            "first_year": 2023, "second_year": 2024}
    with client_with_model(package, lambda _: json.dumps(plan)) as client:
        response = client.post(ENDPOINT, json={"question": question})
    assert response.status_code == 200
    body = response.json()
    direct = compare_inflation_years(
        cpi, first_year=2023, second_year=2024, source_ref="verified://cpi-receipt",
    )
    assert body["status"] == "ok" and body["decision"] == plan
    assert body["analysis"]["analysis_id"] == core.COMPARISON_ID
    evidence = body["analysis"]["evidence"]
    assert evidence["source_ref"] == "verified://cpi-receipt"
    assert evidence["second_minus_first_december_annual_inflation_pp"] == pytest.approx(5.0)
    for year, direct_year in zip(evidence["years"], direct.years):
        assert year["year"] == direct_year.year
        nested = year["evidence"]
        assert nested["input_origin"] == "verified_files"
        assert nested["source_ref"] == "verified://cpi-receipt"
        assert nested["limitations"][0] == files_service._VERIFIED_CPI_LIMITATION
        assert nested["limitations"][1:] == list(direct_year.evidence.limitations[1:])
        assert {key: value for key, value in nested.items() if key not in {"input_origin", "limitations"}} == (
            direct_year.evidence.model_dump(mode="json", exclude={"input_origin", "limitations"})
        )


@pytest.mark.parametrize("plan,expected_status,http_status", [
    ({"status": "clarification_required", "reason": "period_required"}, "clarification_required", 200),
    ({"status": "clarification_required", "reason": "metric_ambiguous"}, "clarification_required", 200),
    ({"status": "unsupported", "reason": "unsupported_analysis"}, "unsupported", 200),
    (ready(start_period="2020-12"), "clarification_required", 200),
    (ready(core.INFLATION_ID, end_period="2021-03"), "clarification_required", 200),
    (ready(start_period="2021-02", end_period="2021-01"), None, 502),
    (ready(analysis_id="web_search"), None, 502),
    (ready(path="../../private.env"), None, 502),
    (ready(source_ref="invented"), None, 502),
    ("not JSON private-provider-body", None, 502),
])
def test_non_ready_and_invalid_plans_never_analyze(package, monkeypatch, plan, expected_status, http_status):
    monkeypatch.setattr(core, "run_housing_analysis", forbidden)
    monkeypatch.setattr(core, "build_inflation_evidence", forbidden)
    prompts = []
    question = QUESTION
    if isinstance(plan, dict) and plan.get("start_period") == "2020-12":
        question = "2020 Aralık-2021 Şubat faiz düşerken reel konut kredisi stokunu göster."
    elif isinstance(plan, dict) and plan.get("end_period") == "2021-03":
        question = "2021 Ocak-Mart TÜFE değişimlerini göster."

    def model(prompt):
        prompts.append(prompt)
        return plan if isinstance(plan, str) else json.dumps(plan)

    with client_with_model(package, model) as client:
        response = client.post(ENDPOINT, json={"question": question})
    assert response.status_code == http_status and len(prompts) == 1
    assert "private" not in response.text
    if expected_status:
        assert response.json()["status"] == expected_status
        assert response.json()["analysis"] is None
        if plan.get("status") == "ready":
            assert response.json()["decision"]["reason"] == "outside_coverage"
    else:
        assert response.json()["detail"]["code"] == "invalid_question_plan"


@pytest.mark.parametrize("corruption", [
    "missing_root", "missing_manifest", "manifest_contract", "evds_raw", "evds_receipt",
    "evds_csv", "bddk_raw", "bddk_receipt", "bddk_value", "bddk_gap", "unreadable_silver", "outside_root",
])
def test_bad_physical_data_is_safe_503_before_any_model_or_analysis(package, monkeypatch, corruption):
    root = package.project_root
    manifest_path = root / package.evds_manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if corruption == "missing_root":
        package = replace(package, project_root=root / "private-unavailable")
    elif corruption == "missing_manifest":
        package = replace(package, evds_manifest=Path("private-missing.json"))
    elif corruption == "manifest_contract":
        manifest["series"][1]["base_year"] = 2020
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif corruption.startswith("evds_"):
        rel = manifest["silver"]["path"] if corruption == "evds_csv" else (
            manifest["series"][0]["bronze"][0]["raw_path" if corruption == "evds_raw" else "receipt_path"]
        )
        target = root / rel
        target.write_bytes(target.read_bytes() + b"broken private-file-body")
    elif corruption in {"bddk_raw", "bddk_receipt"}:
        folder = "raw" if corruption == "bddk_raw" else "receipts"
        target = root / package.bddk_bronze / "aylik" / folder / "2021-01.json"
        target.write_bytes(target.read_bytes() + b"broken private-file-body")
    elif corruption in {"bddk_value", "bddk_gap"}:
        frame = pd.read_parquet(root / package.bddk_silver)
        if corruption == "bddk_value":
            frame.loc[0, ["housing_loan_amount", "nominal_housing_loan_mn_try"]] = 2000.0
        else:
            frame = frame.drop(index=1)
        frame.to_parquet(root / package.bddk_silver, index=False)
    elif corruption == "unreadable_silver":
        (root / package.bddk_silver).write_bytes(b"private not parquet")
    else:
        package = replace(package, bddk_silver=Path("../private-outside.parquet"))
    monkeypatch.setattr(core, "run_housing_analysis", forbidden)
    monkeypatch.setattr(core, "build_inflation_evidence", forbidden)
    with client_with_model(package, forbidden) as client:
        response = client.post(ENDPOINT, json={"question": QUESTION})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "economic_data_unavailable"
    assert "private" not in response.text and str(root) not in response.text


@pytest.mark.parametrize("payload", [
    {}, {"question": " "}, {"question": 5}, {"question": "x" * 2001},
    *({"question": QUESTION, key: "private-request-marker"} for key in (
        "housing", "inflation", "project_root", "model", "api_key", "analysis_id", "start_period",
    )),
])
def test_request_cannot_select_data_paths_model_or_plan(package, monkeypatch, payload):
    monkeypatch.setattr(api, "run_verified_economic_question", forbidden)
    with client_with_model(package, forbidden) as client:
        response = client.post(ENDPOINT, json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_economic_input"
    assert "private-request-marker" not in response.text


@pytest.mark.parametrize("content", ["{", "[]", "null"])
def test_malformed_request_is_sanitized(package, content):
    with client_with_model(package, forbidden) as client:
        response = client.post(ENDPOINT, content=content, headers={"Content-Type": "application/json"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_economic_input"


def test_provider_error_has_one_attempt_no_analysis_and_no_raw_response(package, monkeypatch):
    calls = []

    def model(prompt):
        calls.append(prompt)
        raise RuntimeError("private-api-key provider-raw-response")

    monkeypatch.setattr(core, "run_housing_analysis", forbidden)
    monkeypatch.setattr(core, "build_inflation_evidence", forbidden)
    with client_with_model(package, model) as client:
        response = client.post(ENDPOINT, json={"question": QUESTION})
    assert len(calls) == 1 and response.status_code == 502
    assert response.json()["detail"]["code"] == "question_planning_failed"
    assert "private" not in response.text and "provider-raw" not in response.text


def test_analysis_failure_does_not_try_other_analysis(package, monkeypatch):
    def fail(*args, **kwargs):
        raise GoldAnalysisError("private-data-body")

    monkeypatch.setattr(core, "run_housing_analysis", fail)
    monkeypatch.setattr(core, "build_inflation_evidence", forbidden)
    with client_with_model(package, lambda _: json.dumps(ready())) as client:
        response = client.post(ENDPOINT, json={"question": QUESTION})
    assert response.status_code == 503 and "private" not in response.text


@pytest.mark.parametrize("analysis_id", [core.HOUSING_ID, core.INFLATION_ID])
def test_analysis_uses_verified_memory_after_planning(package, analysis_id):
    with client_with_model(package, lambda _: json.dumps(ready(analysis_id))) as client:
        expected = client.post(ENDPOINT, json={"question": QUESTION}).json()
    manifest = json.loads((package.project_root / package.evds_manifest).read_text(encoding="utf-8"))

    def model(_):
        (package.project_root / package.bddk_silver).write_bytes(b"changed after verification")
        (package.project_root / manifest["silver"]["path"]).write_bytes(b"changed after verification")
        return json.dumps(ready(analysis_id))

    with client_with_model(package, model) as client:
        response = client.post(ENDPOINT, json={"question": QUESTION})
    assert response.status_code == 200 and response.json() == expected


def test_server_environment_selects_root_without_request_paths(package, monkeypatch):
    monkeypatch.setenv("ANALYTICS_DATA_ROOT", str(package.project_root))
    app = create_app()
    app.dependency_overrides[api.get_economic_question_model] = lambda: lambda _: json.dumps(ready())
    with TestClient(app) as client:
        response = client.post(ENDPOINT, json={"question": QUESTION})
    assert response.status_code == 200 and response.json()["status"] == "ok"


def test_cpi_chart_failure_is_safe_503_without_retry(package, monkeypatch):
    from app.tools.inflation_chart import InflationChartError

    prompts = []

    def model(prompt):
        prompts.append(prompt)
        return json.dumps(ready(core.INFLATION_ID))

    def broken_chart(evidence):
        raise InflationChartError("private-chart-detail")

    monkeypatch.setattr(api, "build_inflation_chart", broken_chart)
    with client_with_model(package, model) as client:
        response = client.post(ENDPOINT, json={"question": "2021 Ocak-Şubat TÜFE değişimlerini göster."})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "economic_data_unavailable"
    assert "private-chart-detail" not in response.text
    assert len(prompts) == 1

"""HTTP assets and real-browser UI behavior; all plans are explicit offline stubs."""

import html
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import threading
import time

import pytest
from fastapi import Response
from fastapi.testclient import TestClient
import uvicorn

from app.api.economic_question import get_economic_question_model, get_verified_economic_paths
from app.api.main import create_app
from app.connectors import llm_client
from app.services.economic_question import run_economic_question, HousingQuestionData
from app.services.housing_question_files import VerifiedHousingQuestionPaths
from app.services.inflation_comparison import compare_inflation_years
from scripts.preview_question_ui import fixed_plan
from tests.housing_test_support import write_bddk
import pandas as pd


def no_model(*args, **kwargs):
    raise AssertionError("Live model access forbidden")


def plan_for(question: str) -> dict:
    prompt = "İSTEK_VERİSİ:\n" + json.dumps({"question": question})
    return json.loads(fixed_plan(prompt))


EXAMPLES = [
    ("2021-2025 faiz düşerken reel konut kredisi stokunun artmadığı aylar hangileri?",
     {"status": "ready", "analysis_id": "housing_rate_down_real_credit_not_up",
      "start_period": "2021-01", "end_period": "2025-12"}),
    ("2023 Ocak-Aralık TÜFE aylık ve yıllık değişimlerini özetle.",
     {"status": "ready", "analysis_id": "cpi_inflation_summary",
      "start_period": "2023-01", "end_period": "2023-12"}),
    ("2023 ve 2024 TÜFE değişimlerini karşılaştır.",
     {"status": "ready", "analysis_id": "cpi_two_year_comparison",
      "first_year": 2023, "second_year": 2024}),
]


def test_offline_preview_plans_only_the_three_examples():
    for question, expected in EXAMPLES:
        assert plan_for(question) == expected
    assert plan_for("2024 TÜFE değişimlerini özetle.") == {
        "status": "clarification_required", "reason": "question_ambiguous",
    }


def test_page_offers_three_non_submitting_examples():
    with TestClient(create_app()) as client:
        page = client.get("/")
    assert page.status_code == 200
    assert page.text.count('type="button" data-example=') == 3
    for question, _ in EXAMPLES:
        assert f'data-example="{html.escape(question)}"' in page.text
    assert "TÜFE karşılaştırması · 2023 / 2024" in page.text


def test_normal_and_offline_modes_explain_their_planning():
    with TestClient(create_app()) as client:
        normal = client.get("/").text
    app = create_app()
    app.state.offline_preview = True
    with TestClient(app) as client:
        offline = client.get("/").text
    assert "yapılandırılmış modelle planlanır" in normal
    assert "OFFLINE ÖNİZLEME" not in normal
    assert "OFFLINE ÖNİZLEME" in offline
    assert "Yalnız üç sabit örnek desteklenir" in offline
    assert "normal yapılandırılmış model modu gerekir" in offline
    assert "doğal dil anlama başarısı göstermez" in offline


def test_page_and_local_assets_do_not_read_keys_or_call_models(monkeypatch):
    monkeypatch.setattr(llm_client, "ask_llm", no_model)
    monkeypatch.setattr(llm_client, "read_llm_settings", no_model)
    monkeypatch.setenv("LLM_API_KEY", "PRIVATE-KEY-UI-SENTINEL")
    with TestClient(create_app()) as client:
        page = client.get("/")
        assert page.status_code == 200 and 'lang="tr"' in page.text
        assert "PRIVATE-KEY-UI-SENTINEL" not in page.text
        assert "script-src 'self'" in page.headers["content-security-policy"]
        for asset in ["question.js", "question.css", "plotly.js"]:
            response = client.get("/ui-assets/" + asset)
            assert response.status_code == 200
            assert "PRIVATE-KEY-UI-SENTINEL" not in response.text
        assert client.get("/ui-assets/../../.env").status_code == 404
        assert client.get("/health").status_code == 200


def browser_binary():
    candidates = [os.getenv("CHROME_BIN"), shutil.which("google-chrome"), shutil.which("chromium"),
                  shutil.which("chromium-browser"), r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    return next((str(p) for p in candidates if p and Path(p).is_file()), None)


def test_browser_question_flow_with_offline_plans(tmp_path, monkeypatch):
    chrome = browser_binary()
    if not chrome:
        if os.getenv("CI"):
            pytest.fail("CI must provide Chrome/Chromium for the UI behavior test")
        pytest.skip("Chrome/Chromium unavailable for browser behavior test")
    monkeypatch.setattr(llm_client, "ask_llm", no_model)
    monkeypatch.setattr(llm_client, "read_llm_settings", no_model)
    root = tmp_path / "package"
    shutil.copytree(Path(__file__).parent / "fixtures/evds_manifest_v1", root)
    write_bddk(root, ["2021-01", "2021-02"])
    app = create_app()
    app.dependency_overrides[get_verified_economic_paths] = lambda: VerifiedHousingQuestionPaths(root)
    model_calls = []

    def model(prompt):
        question = json.loads(prompt.split("İSTEK_VERİSİ:\n", 1)[1])["question"]
        model_calls.append(question)
        if question == "provider":
            raise RuntimeError("PRIVATE-PROVIDER-RESPONSE")
        if question == "unsupported":
            return json.dumps({"status": "unsupported", "reason": "unsupported_analysis"})
        if question.startswith("<img"):
            return json.dumps({"status": "clarification_required", "reason": "period_required"})
        if "Ocak-Şubat TÜFE" in question:
            if len(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", question)) != 1:
                return json.dumps({"status": "clarification_required", "reason": "period_required"})
            return json.dumps({"status": "ready", "analysis_id": "cpi_inflation_summary", "start_period": "2021-01", "end_period": "2021-02"})
        if "kredi bakiyesinin" in question:
            if "reel kredi bakiyesinin" in question:
                return json.dumps({"status": "ready", "analysis_id": "housing_rate_down_real_credit_not_up", "start_period": "2021-01", "end_period": "2021-02"})
            return json.dumps({"status": "clarification_required", "reason": "metric_ambiguous"})
        if "kredi stoku artmayan" in question:
            if "nominal kredi stoku artmayan" in question:
                return json.dumps({
                    "status": "ready", "analysis_id": "housing_condition_filter",
                    "start_period": "2021-01", "end_period": "2021-02",
                    "conditions": [
                        {"metric": "interest_rate_change_pp", "operator": "lt", "threshold": 0.0},
                        {"metric": "nominal_housing_loan_change_pct", "operator": "lte", "threshold": 0.0},
                    ],
                })
            return json.dumps({"status": "clarification_required", "reason": "metric_ambiguous"})
        return json.dumps({"status": "ready", "analysis_id": "cpi_inflation_summary" if "TÜFE" in question else "housing_rate_down_real_credit_not_up", "start_period": "2021-01", "end_period": "2021-02"})

    app.dependency_overrides[get_economic_question_model] = lambda: model
    payload = json.loads((Path(__file__).parents[1] / "docs/economic-question-api-example.json").read_text(encoding="utf-8"))
    housing = payload["housing"]
    run = run_economic_question("2021 Ocak-Mart faiz düşerken reel konut kredisi stoku artmayan aylar", housing=HousingQuestionData(
        pd.DataFrame(housing["bddk_monthly"]), pd.DataFrame(housing["evds_monthly"]),
        housing["bddk_source_ref"], housing["evds_source_refs"],
    ), model_call=lambda _: json.dumps({"status": "ready", "analysis_id": "housing_rate_down_real_credit_not_up", "start_period": "2021-01", "end_period": "2021-03"}))
    matched_payload = {"status": "ok", "available_periods": run.coverage.model_dump(),
                       "analysis": {"analysis_id": run.analysis.evidence.analysis_id,
                                    "evidence": run.analysis.evidence.model_dump(mode="json"), "chart": run.analysis.chart}}
    comparison_periods = pd.period_range("2022-12", "2024-12", freq="M").astype(str).tolist()
    comparison = compare_inflation_years(
        pd.DataFrame({
            "period": comparison_periods,
            "cpi_index": [
                100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 112.0, 114.0, 116.0, 118.0, 119.0, 119.5,
                120.0, 123.0, 126.0, 129.0, 132.0, 135.0, 138.0, 141.0, 144.0, 146.0, 147.0, 148.5,
                150.0,
            ],
        }),
        first_year=2023, second_year=2024, source_ref="synthetic://comparison",
    )
    comparison_payload = {
        "status": "ok",
        "available_periods": {
            "housing": None,
            "inflation": {"start_period": "2022-12", "end_period": "2024-12"},
        },
        "decision": {"status": "ready", "analysis_id": "cpi_two_year_comparison",
                     "first_year": 2023, "second_year": 2024},
        "analysis": {"analysis_id": "cpi_two_year_comparison",
                     "evidence": comparison.model_dump(mode="json")},
    }
    filter_plan = {
        "status": "ready", "analysis_id": "housing_condition_filter",
        "start_period": "2021-01", "end_period": "2021-02",
        "conditions": [
            {"metric": "interest_rate_change_pp", "operator": "lt", "threshold": 0.0},
            {"metric": "nominal_housing_loan_change_pct", "operator": "lte", "threshold": 0.0},
        ],
    }
    filter_run = run_economic_question(
        "2021 Ocak-Şubat faiz düşerken nominal konut kredisi stoku artmayan aylar",
        housing=HousingQuestionData(
            pd.DataFrame(housing["bddk_monthly"]), pd.DataFrame(housing["evds_monthly"]),
            housing["bddk_source_ref"], housing["evds_source_refs"],
        ),
        model_call=lambda _: json.dumps(filter_plan),
    )
    filter_payload = {
        "status": "ok", "available_periods": filter_run.coverage.model_dump(),
        "decision": filter_plan,
        "analysis": {
            "analysis_id": "housing_condition_filter",
            "evidence": filter_run.analysis.model_dump(mode="json"),
        },
    }
    script = (Path(__file__).parent / "ui_browser_checks.js").read_text(encoding="utf-8")
    script = script.replace("__MATCHED_PAYLOAD__", json.dumps(matched_payload))
    script = script.replace("__COMPARISON_PAYLOAD__", json.dumps(comparison_payload))
    script = script.replace("__FILTER_PAYLOAD__", json.dumps(filter_payload))

    @app.get("/__ui_test.js", include_in_schema=False)
    def checks():
        return Response(script, media_type="application/javascript")

    @app.middleware("http")
    async def inject_test(request, call_next):
        response = await call_next(request)
        if request.url.path != "/":
            return response
        body = b"".join([part async for part in response.body_iterator]).decode("utf-8")
        body = body.replace("</body>", '<script defer src="/__ui_test.js"></script></body>')
        headers = {k: v for k, v in response.headers.items() if k != "content-length"}
        return Response(body, headers=headers, media_type="text/html")

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.05)
        assert server.started
        command = [chrome, "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                   "--disable-background-networking", "--disable-extensions", "--disable-sync", "--no-proxy-server",
                   "--user-data-dir=" + str(tmp_path / "browser-profile"), "--window-size=1360,1100",
                   "--virtual-time-budget=30000", "--dump-dom", f"http://127.0.0.1:{port}/"]
        browser_env = {key: value for key, value in os.environ.items()
                       if not key.startswith(("LLM_", "MIA_", "EVDS_"))
                       and key not in {"GITHUB_TOKEN", "GH_TOKEN", "ANALYTICS_DATA_ROOT"}}
        completed = subprocess.run(command, capture_output=True, timeout=70, env=browser_env)
        dom = completed.stdout.decode("utf-8", errors="replace")
        match = re.search(r'<pre id="ui-test-result">(.*?)</pre>', dom, re.S)
        if not match:
            (tmp_path / "browser-dom.html").write_text(dom, encoding="utf-8")
            (tmp_path / "browser-stderr.txt").write_bytes(completed.stderr)
        assert match, "Browser did not finish UI checks (no result marker)."
        result = json.loads(html.unescape(match.group(1)))
        assert result["ok"], result
        assert len(model_calls) == 15
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()

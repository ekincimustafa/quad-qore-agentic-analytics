"""Offline tests using the installed SDK and an HTTP mock transport."""

import json
import logging

import httpx
import pytest
from openai import OpenAI as RealOpenAI

from app.connectors import llm_client


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_CHAT_MODEL", "LLM_TIMEOUT_SECONDS", "LLM_REASONING_EFFORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(llm_client, "load_dotenv", lambda *args, **kwargs: None)


def _response(content="  verified answer  ", finish_reason="stop"):
    return httpx.Response(200, json={
        "id": "test-completion", "object": "chat.completion", "created": 0,
        "model": "test-model", "choices": [{
            "index": 0, "message": {"role": "assistant", "content": content},
            "finish_reason": finish_reason,
        }],
    })


def _mock_provider(monkeypatch, handler):
    requests, clients, options = [], [], []
    monkeypatch.setenv("LLM_API_KEY", "private-test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.invalid/v1")
    monkeypatch.setenv("LLM_CHAT_MODEL", "test-model")

    def dispatch(request):
        requests.append(request)
        return handler(request)

    def constructor(**kwargs):
        options.append(kwargs)
        client = RealOpenAI(
            **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(dispatch)),
        )
        clients.append(client)
        return client

    monkeypatch.setattr(llm_client, "OpenAI", constructor)
    return requests, clients, options


@pytest.mark.parametrize("name", ["LLM_API_KEY", "LLM_BASE_URL", "LLM_CHAT_MODEL"])
def test_missing_setting_fails_before_client_creation(monkeypatch, name):
    requests, clients, _ = _mock_provider(monkeypatch, lambda request: _response())
    monkeypatch.setenv(name, "   ")
    with pytest.raises(llm_client.LLMConfigurationError, match=name):
        llm_client.ask_llm("test")
    assert requests == [] and clients == []


@pytest.mark.parametrize("url", [
    "http://llm.invalid/v1", "/v1", "https:///v1",
    "https://user:private-test-key@llm.invalid/v1",
    "https://llm.invalid/v1?key=private-test-key",
    "https://llm.invalid/v1#private-test-key",
    "https://llm.invalid:99999/v1", "https://llm.invalid/has space",
])
def test_invalid_url_fails_without_exposing_its_value(monkeypatch, url):
    requests, clients, _ = _mock_provider(monkeypatch, lambda request: _response())
    monkeypatch.setenv("LLM_BASE_URL", url)
    with pytest.raises(llm_client.LLMConfigurationError) as error:
        llm_client.ask_llm("test")
    assert "private-test-key" not in str(error.value)
    assert requests == [] and clients == []


@pytest.mark.parametrize("timeout", ["", "abc", "0", "-1", "121", "nan", "inf"])
def test_invalid_timeout_fails_before_client_creation(monkeypatch, timeout):
    requests, clients, _ = _mock_provider(monkeypatch, lambda request: _response())
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", timeout)
    with pytest.raises(llm_client.LLMConfigurationError, match="LLM_TIMEOUT_SECONDS"):
        llm_client.ask_llm("test")
    assert requests == [] and clients == []


def test_sdk_uses_explicit_settings_single_attempt_and_closes(monkeypatch):
    requests, clients, options = _mock_provider(monkeypatch, lambda request: _response())
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "8.5")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unintended.invalid/v1")
    assert llm_client.ask_llm("  test prompt  ") == "verified answer"
    assert len(requests) == 1
    assert str(requests[0].url) == "https://llm.invalid/v1/chat/completions"
    body = json.loads(requests[0].content)
    assert body["model"] == "test-model"
    assert body["messages"] == [{"role": "user", "content": "test prompt"}]
    assert "reasoning_effort" not in body
    assert "response_format" not in body
    assert options[0]["timeout"] == 8.5
    assert options[0]["max_retries"] == 0
    assert clients[0].is_closed()


def test_explicit_schema_is_sent_once_without_changing_the_response(monkeypatch):
    schema = {
        "type": "object", "properties": {"status": {"type": "string", "enum": ["ready"]}},
        "required": ["status"], "additionalProperties": False,
    }
    before = json.dumps(schema, sort_keys=True)
    # Even a non-compliant provider response must be returned unchanged to the
    # caller's existing validator, never stripped or repaired by the client.
    content = '```json\n{"status":"ready"}\n```'
    requests, clients, options = _mock_provider(monkeypatch, lambda request: _response(content))
    assert llm_client.ask_llm("JSON plan", response_schema=schema) == content
    body = json.loads(requests[0].content)
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "analysis_plan", "strict": True, "schema": schema},
    }
    assert len(requests) == 1 and options[0]["max_retries"] == 0
    assert clients[0].is_closed()
    assert json.dumps(schema, sort_keys=True) == before


@pytest.mark.parametrize("effort", ["minimal", "low", "medium", "high"])
def test_explicit_reasoning_effort_reaches_provider_once(monkeypatch, effort):
    requests, clients, _ = _mock_provider(monkeypatch, lambda request: _response())
    monkeypatch.setenv("LLM_REASONING_EFFORT", effort)
    assert llm_client.ask_llm("test") == "verified answer"
    assert len(requests) == 1
    assert json.loads(requests[0].content)["reasoning_effort"] == effort
    assert clients[0].is_closed()


@pytest.mark.parametrize("effort", ["none", "secret-upstream-value"])
def test_invalid_reasoning_effort_fails_before_client_creation(monkeypatch, effort):
    requests, clients, _ = _mock_provider(monkeypatch, lambda request: _response())
    monkeypatch.setenv("LLM_REASONING_EFFORT", effort)
    with pytest.raises(llm_client.LLMConfigurationError, match="LLM_REASONING_EFFORT") as error:
        llm_client.ask_llm("test")
    assert effort not in str(error.value)
    assert requests == [] and clients == []


def test_blank_reasoning_effort_preserves_provider_default(monkeypatch):
    requests, _, _ = _mock_provider(monkeypatch, lambda request: _response())
    monkeypatch.setenv("LLM_REASONING_EFFORT", "  ")
    llm_client.ask_llm("test")
    assert "reasoning_effort" not in json.loads(requests[0].content)


def test_explicit_settings_do_not_reread_or_modify_environment(monkeypatch):
    from dataclasses import replace
    import os

    requests, _, options = _mock_provider(monkeypatch, lambda request: _response())
    original = llm_client.read_llm_settings()
    temporary = replace(original, reasoning_effort="low", timeout_seconds=60)
    before = os.environ.copy()
    def forbidden():
        raise AssertionError("Explicit settings must not be reread")
    monkeypatch.setattr(llm_client, "read_llm_settings", forbidden)
    assert llm_client.ask_llm("test", settings=temporary) == "verified answer"
    assert original.reasoning_effort is None and original.timeout_seconds == 30
    assert options[0]["timeout"] == 60
    assert json.loads(requests[0].content)["reasoning_effort"] == "low"
    assert os.environ == before


@pytest.mark.parametrize(("status", "code"), [
    (400, "request_rejected"), (401, "authentication_failed"),
    (403, "access_denied"), (404, "request_rejected"),
    (429, "rate_limited"), (500, "provider_unavailable"),
    (503, "provider_unavailable"),
])
def test_provider_errors_are_safe_not_retried_and_client_closes(monkeypatch, caplog, status, code):
    caplog.set_level(logging.INFO)
    requests, clients, _ = _mock_provider(monkeypatch, lambda request: httpx.Response(
        status, json={"error": {"message": "private-test-key secret-upstream-body"}},
    ))
    with pytest.raises(llm_client.LLMRequestError) as error:
        llm_client.ask_llm("test")
    assert error.value.code == code
    assert error.value.__suppress_context__
    assert "private-test-key" not in str(error.value) + caplog.text
    assert "secret-upstream-body" not in str(error.value) + caplog.text
    assert len(requests) == 1 and clients[0].is_closed()


@pytest.mark.parametrize(("exc_type", "code"), [
    (httpx.ReadTimeout, "timeout"), (httpx.ConnectError, "connection_failed"),
])
def test_transport_failure_is_safe_and_not_retried(monkeypatch, exc_type, code):
    def fail(request):
        raise exc_type("secret-upstream-body", request=request)
    requests, clients, _ = _mock_provider(monkeypatch, fail)
    with pytest.raises(llm_client.LLMRequestError) as error:
        llm_client.ask_llm("test")
    assert error.value.code == code
    assert "secret-upstream-body" not in str(error.value)
    assert len(requests) == 1 and clients[0].is_closed()


@pytest.mark.parametrize("body", [
    {}, {"choices": []}, {"choices": None}, {"choices": [{}]},
    {"choices": [{"message": {"content": "text"}, "finish_reason": "length"}]},
    {"choices": [{"message": {"content": ""}, "finish_reason": "stop"}]},
    {"choices": [{"message": {"content": None}, "finish_reason": "stop"}]},
    {"choices": [{"message": {"content": "   "}, "finish_reason": "stop"}]},
])
def test_unexpected_or_incomplete_success_response_is_rejected(monkeypatch, body):
    requests, clients, _ = _mock_provider(monkeypatch, lambda request: httpx.Response(200, json=body))
    with pytest.raises(llm_client.LLMRequestError) as error:
        llm_client.ask_llm("test")
    assert error.value.code == "invalid_response"
    assert len(requests) == 1 and clients[0].is_closed()


@pytest.mark.parametrize("prompt", [None, "", "   ", 123])
def test_invalid_prompt_never_reads_settings(monkeypatch, prompt):
    def must_not_run():
        raise AssertionError("Settings must not be read")
    monkeypatch.setattr(llm_client, "read_llm_settings", must_not_run)
    with pytest.raises(ValueError):
        llm_client.ask_llm(prompt)


def test_dotenv_is_repo_local_and_does_not_override_process_env(monkeypatch):
    from pathlib import Path
    from dotenv import load_dotenv as real_load_dotenv
    paths = []
    monkeypatch.setenv("LLM_API_KEY", "private-test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.invalid/v1")
    monkeypatch.setenv("LLM_CHAT_MODEL", "process-model")
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")

    def record(path, *, override):
        paths.append(Path(path))
        assert override is False
        # Test precedence with in-memory content; do not read the user's .env.
        from io import StringIO
        real_load_dotenv(stream=StringIO("LLM_CHAT_MODEL=file-model\nLLM_REASONING_EFFORT=high"), override=override)

    monkeypatch.setattr(llm_client, "load_dotenv", record)
    settings = llm_client.read_llm_settings()
    assert settings.chat_model == "process-model"
    assert settings.reasoning_effort == "low"
    assert paths == [Path(llm_client.__file__).resolve().parents[2] / ".env"]
    assert "private-test-key" not in repr(settings)


@pytest.mark.parametrize(("rate", "status"), [(9.0, 200), (100.0, 502)])
def test_real_sdk_through_default_api_preserves_narration_validation(monkeypatch, rate, status):
    from fastapi.testclient import TestClient
    from app.api.main import create_app
    from tests.test_housing_analysis_api import _payload
    content = json.dumps({"results": [{
        "period": "2021-02", "housing_loan_interest_rate_pct": rate,
        "interest_rate_change_pp": -1.0, "real_housing_loan_change_pct": -9.0909,
    }]})
    requests, clients, _ = _mock_provider(monkeypatch, lambda request: _response(content))
    payload = _payload()
    payload["include_narration"] = True
    response = TestClient(create_app()).post("/analysis/housing", json=payload)
    assert response.status_code == status
    assert len(requests) == 1 and clients[0].is_closed()
    if status == 200:
        assert "konut kredisi faizi %9" in response.json()["narration"]
        assert "nedensellik kanıtlamaz" in response.json()["narration"]
    else:
        assert response.json()["detail"]["code"] == "narration_failed"


@pytest.mark.parametrize("files", [False, True])
@pytest.mark.parametrize("kind", ["valid", "fence", "extra_field", "wrong_condition"])
def test_economic_api_defaults_send_schema_and_still_validate_every_plan(
    monkeypatch, tmp_path, files, kind,
):
    import shutil
    from pathlib import Path
    from unittest.mock import patch

    from fastapi.testclient import TestClient
    from app.api import economic_question as api
    from app.api.main import create_app
    from app.services import economic_question as service
    from app.services.housing_question_files import VerifiedHousingQuestionPaths
    from tests.housing_test_support import write_bddk

    root = Path(__file__).resolve().parents[1]
    question = "2021 Ocak-Şubat faiz düşerken reel konut kredisi stoku artmayan ayları göster."
    plan = {
        "status": "ready", "analysis_id": service.HOUSING_FILTER_ID,
        "start_period": "2021-01", "end_period": "2021-02",
        "conditions": [
            {"metric": "interest_rate_change_pp", "operator": "lt", "threshold": 0.0},
            {"metric": "real_housing_loan_change_pct", "operator": "lte", "threshold": 0.0},
        ],
    }
    if kind == "extra_field":
        plan["private-test-key"] = "secret-upstream-body"
    elif kind == "wrong_condition":
        plan["conditions"][0]["operator"] = "gt"
    envelope = {key: None for key in service.EconomicModelResponse.model_fields}
    envelope.update(plan)
    content = json.dumps(envelope)
    if kind == "fence":
        content = "```json\n" + content + "\n```"
    requests, clients, _ = _mock_provider(monkeypatch, lambda request: _response(content))
    app = create_app()
    if files:
        shutil.copytree(root / "tests/fixtures/evds_manifest_v1", tmp_path, dirs_exist_ok=True)
        write_bddk(tmp_path, ["2021-01", "2021-02", "2021-03"])
        paths = VerifiedHousingQuestionPaths(project_root=tmp_path)
        app.dependency_overrides[api.get_verified_economic_paths] = lambda: paths
        endpoint = "/analysis/economic/question/files"
        payload = {"question": question}
    else:
        endpoint = "/analysis/economic/question"
        payload = json.loads((root / "docs/economic-question-api-example.json").read_text(encoding="utf-8"))
        payload["question"] = question
    # Crucially do not override get_economic_question_model: exercise production
    # wiring with the real SDK and a fake HTTP server, including physical files.
    with patch.object(service, "run_housing_filter", wraps=service.run_housing_filter) as analysis:
        with TestClient(app) as client:
            response = client.post(endpoint, json=payload)
    body = response.json()
    request_body = json.loads(requests[0].content)
    assert request_body["response_format"]["type"] == "json_schema"
    assert request_body["response_format"]["json_schema"]["schema"] == {
        **service.EconomicModelResponse.model_json_schema(),
    }
    assert len(requests) == 1 and clients[0].is_closed()
    assert analysis.call_count == (1 if kind == "valid" else 0)
    if kind == "valid":
        assert response.status_code == 200 and body["status"] == "ok"
        assert body["decision"] == plan
        # The physical manifest fixture and normalized-row example contain
        # different values; only the latter matches February's two conditions.
        assert body["analysis"]["evidence"]["matched_periods"] == ([] if files else ["2021-02"])
    elif kind == "wrong_condition":
        assert response.status_code == 200 and body["status"] == "clarification_required"
        assert body["analysis"] is None
    else:
        assert response.status_code == 502 and body["detail"]["code"] == "invalid_question_plan"
    assert "private-test-key" not in response.text and "secret-upstream-body" not in response.text

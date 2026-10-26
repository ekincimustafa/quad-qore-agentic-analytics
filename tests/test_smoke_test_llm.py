"""Exercise the live-check command with the real synthetic fixture, offline."""

import json
import os

import httpx
import pytest

from app.connectors import llm_client
from scripts import smoke_test_llm
from tests.test_llm_client import _mock_provider, _response


@pytest.mark.parametrize("rate", [9.0, 100.0])
def test_smoke_checks_housing_contract_not_just_connectivity(monkeypatch, capsys, rate):
    calls = []
    def model(prompt):
        calls.append(prompt)
        return json.dumps({"results": [{
            "period": "2021-02", "housing_loan_interest_rate_pct": rate,
            "interest_rate_change_pp": -1.0, "real_housing_loan_change_pct": -9.0909,
        }]})
    monkeypatch.setattr(llm_client, "ask_llm", model)
    if rate == 9.0:
        smoke_test_llm.main()
        output = capsys.readouterr().out
        assert "İncelenen ay: 3" in output
        assert "Eşleşen aylar: 2021-02" in output
        assert "nedensellik kanıtlamaz" in output
    else:
        with pytest.raises(SystemExit) as error:
            smoke_test_llm.main()
        assert error.value.code == 1
        assert "anlatımı doğrulanamadı" in capsys.readouterr().out
    assert len(calls) == 1


def test_smoke_reports_safe_configuration_failure(monkeypatch, capsys):
    def fail(prompt):
        raise llm_client.LLMConfigurationError("LLM_API_KEY boş bırakılamaz.")
    monkeypatch.setattr(llm_client, "ask_llm", fail)
    with pytest.raises(SystemExit) as error:
        smoke_test_llm.main()
    assert error.value.code == 1
    assert "Yapılandırma hatası: LLM_API_KEY" in capsys.readouterr().out


@pytest.fixture
def probe_provider(monkeypatch):
    monkeypatch.setattr(llm_client, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError("No real network or analysis fixture access")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(smoke_test_llm.Path, "read_text", forbidden)
    return lambda handler: _mock_provider(monkeypatch, handler)


def test_probe_uses_one_short_request_and_temporary_options(probe_provider, capsys):
    requests, clients, options = probe_provider(lambda request: _response("OK"))
    before = os.environ.copy()
    smoke_test_llm.main(["--probe", "--reasoning-effort", "low", "--timeout-seconds", "60"])
    output = capsys.readouterr().out
    assert len(requests) == 1 and clients[0].is_closed()
    assert options[0]["timeout"] == 60 and options[0]["max_retries"] == 0
    body = json.loads(requests[0].content)
    assert body == {
        "model": "test-model", "reasoning_effort": "low",
        "messages": [{"role": "user", "content": "Reply with exactly OK."}],
    }
    assert "Kısa üretim isteği doğrulandı" in output
    assert "İstemci çağrı denemesi: 1" in output
    assert "saf model süresi değil" in output
    assert "private-test-key" not in output
    assert os.environ == before


@pytest.mark.parametrize(("failure", "phase"), [
    (httpx.ConnectTimeout, "connect"), (httpx.ReadTimeout, "read"),
    (httpx.WriteTimeout, "write"), (httpx.PoolTimeout, "pool"),
])
def test_probe_identifies_timeout_phase_without_leaks_or_retry(probe_provider, capsys, failure, phase):
    def fail(request):
        raise failure("private-test-key secret-upstream-body", request=request)
    requests, clients, _ = probe_provider(fail)
    before = os.environ.copy()
    with pytest.raises(SystemExit) as error:
        smoke_test_llm.main(["--probe"])
    output = capsys.readouterr().out
    assert error.value.code == 1
    assert len(requests) == 1 and clients[0].is_closed()
    assert "LLM hatası: timeout" in output
    assert f"Timeout aşaması: {phase}" in output
    assert "İstemci çağrı denemesi: 1" in output
    assert "secret-upstream-body" not in output and "private-test-key" not in output
    assert os.environ == before


@pytest.mark.parametrize("status", [401, 429, 503])
def test_probe_provider_failure_stops_after_one_safe_attempt(probe_provider, capsys, status):
    requests, clients, _ = probe_provider(lambda request: httpx.Response(
        status, json={"error": {"message": "private-test-key secret-upstream-body"}},
    ))
    with pytest.raises(SystemExit) as error:
        smoke_test_llm.main(["--probe"])
    output = capsys.readouterr().out
    assert error.value.code == 1
    assert len(requests) == 1 and clients[0].is_closed()
    assert "private-test-key" not in output and "secret-upstream-body" not in output
    assert "İstemci çağrı denemesi: 1" in output


def test_probe_rejects_wrong_text_without_printing_it(probe_provider, capsys):
    requests, _, _ = probe_provider(lambda request: _response("secret-upstream-body"))
    with pytest.raises(SystemExit) as error:
        smoke_test_llm.main(["--probe"])
    output = capsys.readouterr().out
    assert error.value.code == 1 and len(requests) == 1
    assert "Yanıt tam OK değil" in output
    assert "secret-upstream-body" not in output


@pytest.mark.parametrize("timeout", ["0", "121", "nan"])
def test_probe_bad_temporary_timeout_makes_zero_calls(probe_provider, capsys, timeout):
    requests, clients, _ = probe_provider(lambda request: _response("OK"))
    with pytest.raises(SystemExit) as error:
        smoke_test_llm.main(["--probe", "--timeout-seconds", timeout])
    assert error.value.code == 1
    assert requests == [] and clients == []
    assert "İstemci çağrı denemesi: 0" in capsys.readouterr().out


def test_probe_missing_configuration_makes_zero_calls_and_restores_environment(monkeypatch, capsys):
    def simulate_dotenv(*args, **kwargs):
        os.environ["LLM_API_KEY"] = ""
        os.environ["LLM_BASE_URL"] = ""
        os.environ["LLM_CHAT_MODEL"] = ""
        os.environ["PROBE_TEST_SIDE_EFFECT"] = "temporary"
    monkeypatch.setattr(llm_client, "load_dotenv", simulate_dotenv)
    before = os.environ.copy()
    with pytest.raises(SystemExit):
        smoke_test_llm.main(["--probe"])
    assert os.environ == before
    assert "İstemci çağrı denemesi: 0" in capsys.readouterr().out


def test_probe_options_require_probe_and_help_makes_zero_calls(monkeypatch):
    def forbidden():
        raise AssertionError("No settings access")
    monkeypatch.setattr(llm_client, "read_llm_settings", forbidden)
    for argv, code in [(["--help"], 0), (["--reasoning-effort", "low"], 2)]:
        with pytest.raises(SystemExit) as error:
            smoke_test_llm.main(argv)
        assert error.value.code == code

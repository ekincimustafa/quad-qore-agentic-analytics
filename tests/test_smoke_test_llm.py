"""Exercise the live-check command with the real synthetic fixture, offline."""

import json

import pytest

from app.connectors import llm_client
from scripts import smoke_test_llm


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

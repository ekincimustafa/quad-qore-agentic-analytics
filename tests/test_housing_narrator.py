"""Regression tests for evidence-bound housing narration."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from app.lakehouse.gold import build_housing_gold_table
from app.tools.housing_evidence import build_housing_analysis_evidence
from app.tools.housing_narrator import (
    MAX_RESPONSE_CHARACTERS,
    NarrationValidationError,
    build_housing_narration_prompt,
    narrate_housing_evidence,
    narrate_housing_evidence_with_mia,
    validate_housing_narration,
)


def _evidence(*, nominal=None, months=3):
    periods = ["2021-01", "2021-02", "2021-03"][:months]
    bddk = pd.DataFrame({
        "period": periods,
        "nominal_housing_loan_mn_try":
            ([100.0, 100.0, 105.0] if nominal is None else nominal)[:months],
    })
    evds = pd.DataFrame({
        "period": periods,
        "housing_loan_interest_rate_pct": [20.0, 19.0, 18.0][:months],
        "weekly_observation_count": [4, 4, 5][:months],
        "cpi_index": [100.0, 102.0, 103.0][:months],
        "housing_price_index": [100.0, 101.0, 102.0][:months],
    })
    gold = build_housing_gold_table(
        bddk, evds, start_period=periods[0], end_period=periods[-1],
    )
    return build_housing_analysis_evidence(
        gold, start_period=periods[0], end_period=periods[-1],
    )


def _payload(evidence=None, *, rounded=False):
    evidence = _evidence() if evidence is None else evidence
    results = []
    for row in evidence.results:
        item = {
            "period": row.period,
            "housing_loan_interest_rate_pct": row.housing_loan_interest_rate_pct,
            "interest_rate_change_pp": row.interest_rate_change_pp,
            "real_housing_loan_change_pct": row.real_housing_loan_change_pct,
        }
        if rounded:
            for field in (
                "housing_loan_interest_rate_pct",
                "interest_rate_change_pp",
                "real_housing_loan_change_pct",
            ):
                item[field] = round(item[field], 4)
        results.append(item)
    return {"results": results}


def _json(payload=None):
    return json.dumps(_payload() if payload is None else payload)


def _legacy_text():
    return (
        "2021-02 döneminde konut kredisi faizi 19 seviyesindedir ve aylık "
        "değişim -1 yüzde puandır. Reel kredi değişimi yaklaşık -1,9608 olmuştur. "
        "Haftalık faiz aylık aritmetik ortalamayla birleştirilmiş, reel kredi "
        "TÜFE kullanılarak hesaplanmıştır. Kaynaklar BDDK ile EVDS "
        "TP.KTF12, TP.TUKFIY2025.GENEL ve TP.KFE.TR serileridir. "
        "Bu bulgu nedensellik kanıtlamaz."
    )


def test_prompt_requests_json_and_contains_evidence():
    prompt = build_housing_narration_prompt(_evidence())
    assert "YANIT_ŞEMASI" in prompt
    assert "DOĞRULANMIŞ_KANIT" in prompt
    assert '"matched_periods"' in prompt
    assert '"2021-02"' in prompt


@pytest.mark.parametrize("rounded", [False, True])
def test_valid_json_renders_verified_turkish_text(rounded):
    text = validate_housing_narration(
        _json(_payload(rounded=rounded)), _evidence(),
    )
    assert "2021-02: konut kredisi faizi %19" in text
    assert "faiz değişimi -1 yüzde puan" in text
    assert "reel kredi değişimi yaklaşık %-1,9608" in text
    assert "aylık aritmetik ortalaması" in text
    assert "nominal tutar × 100 / TÜFE" in text
    assert "nedensellik kanıtlamaz" in text
    assert "TP.KTF12" in text and "TP.KFE.TR" in text


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("housing_loan_interest_rate_pct", 100.0),
        ("interest_rate_change_pp", 19.0),
        ("real_housing_loan_change_pct", -1.0),
    ],
)
def test_rejects_number_borrowed_from_another_metric(field, wrong_value):
    payload = _payload()
    payload["results"][0][field] = wrong_value
    with pytest.raises(NarrationValidationError, match=field):
        validate_housing_narration(_json(payload), _evidence())


@pytest.mark.parametrize("wrong_value", [True, "19", None, float("nan"), float("inf")])
def test_rejects_invalid_numeric_types_and_non_finite_values(wrong_value):
    payload = _payload()
    payload["results"][0]["housing_loan_interest_rate_pct"] = wrong_value
    with pytest.raises(NarrationValidationError, match="JSON"):
        validate_housing_narration(_json(payload), _evidence())


@pytest.mark.parametrize(
    ("field", "claim"),
    [
        ("sources", ["Dünya Bankası"]),
        ("causality", "Bu bulgu nedensellik kanıtlar."),
        ("methodology", "Reel kredi için TÜFE kullanılmadı."),
        ("narration", "Faiz bu azalmanın nedenidir."),
    ],
)
def test_rejects_unverified_free_text_or_source_fields(field, claim):
    payload = _payload()
    payload[field] = claim
    with pytest.raises(NarrationValidationError, match="JSON"):
        validate_housing_narration(_json(payload), _evidence())


def test_rejects_extra_field_inside_a_month():
    payload = _payload()
    payload["results"][0]["source"] = "Dünya Bankası"
    with pytest.raises(NarrationValidationError, match="JSON"):
        validate_housing_narration(_json(payload), _evidence())


@pytest.mark.parametrize("period", ["2021-01", "2021-03"])
def test_rejects_value_assigned_to_an_unmatched_period(period):
    payload = _payload()
    payload["results"][0]["period"] = period
    with pytest.raises(NarrationValidationError, match="ayları"):
        validate_housing_narration(_json(payload), _evidence())


def test_rejects_duplicate_month():
    payload = _payload()
    payload["results"].append(payload["results"][0].copy())
    with pytest.raises(NarrationValidationError, match="mükerrer"):
        validate_housing_narration(_json(payload), _evidence())


def test_rejects_missing_matching_month():
    with pytest.raises(NarrationValidationError, match="ayları"):
        validate_housing_narration(_json({"results": []}), _evidence())


def test_no_match_and_single_month_have_safe_method_and_limitations():
    for evidence in (_evidence(nominal=[100, 150, 200]), _evidence(months=1)):
        text = validate_housing_narration(_json({"results": []}), evidence)
        assert "Koşula uyan ay bulunamadı." in text
        assert "TÜFE" in text
        assert "nedensellik kanıtlamaz" in text


def test_no_match_evidence_rejects_invented_matching_month():
    with pytest.raises(NarrationValidationError, match="ayları"):
        validate_housing_narration(
            _json(), _evidence(nominal=[100, 150, 200]),
        )


def test_multiple_months_use_their_own_values_and_evidence_order():
    evidence = _evidence(nominal=[100, 100, 100])
    payload = _payload(evidence, rounded=True)
    payload["results"].reverse()
    text = validate_housing_narration(_json(payload), evidence)
    assert "2021-02: konut kredisi faizi %19" in text
    assert "2021-03: konut kredisi faizi %18" in text
    assert "%-0,9709" in text
    assert text.index("2021-02:") < text.index("2021-03:")


def test_rejects_swapping_values_between_matching_months():
    evidence = _evidence(nominal=[100, 100, 100])
    payload = _payload(evidence)
    payload["results"][0]["housing_loan_interest_rate_pct"] = 18
    with pytest.raises(NarrationValidationError, match="housing_loan_interest_rate_pct"):
        validate_housing_narration(_json(payload), evidence)


@pytest.mark.parametrize("response", ["", " ", None, "{}", "[]", "{broken"])
def test_rejects_empty_or_invalid_json(response):
    with pytest.raises(NarrationValidationError):
        validate_housing_narration(response, _evidence())


def test_rejects_markdown_wrapping_and_oversized_output():
    fence = chr(96) * 3
    responses = (
        fence + "json\n" + _json() + "\n" + fence,
        "x" * (MAX_RESPONSE_CHARACTERS + 1),
    )
    for response in responses:
        with pytest.raises(NarrationValidationError):
            validate_housing_narration(response, _evidence())


def test_calls_model_once_and_returns_text_not_raw_json():
    calls = []
    def fake_model(prompt):
        calls.append(prompt)
        return _json()
    text = narrate_housing_evidence(_evidence(), fake_model)
    assert len(calls) == 1
    assert "2021-02: konut kredisi faizi %19" in text
    assert not text.startswith("{")


def test_mia_wrapper_uses_the_same_validation(monkeypatch):
    from app.connectors import mia_client
    monkeypatch.setattr(mia_client, "ask_mia", lambda prompt: _json())
    assert "nedensellik kanıtlamaz" in narrate_housing_evidence_with_mia(_evidence())


def test_rejects_non_callable_model():
    with pytest.raises(TypeError, match="model_call must be callable"):
        narrate_housing_evidence(_evidence(), "not-callable")


@pytest.mark.parametrize(
    "response",
    [
        _legacy_text().replace("faizi 19", "faizi 100"),
        _legacy_text() + " Bu koşula uyan bir diğer ay 2021-03'tür.",
        _legacy_text().replace("nedensellik kanıtlamaz", "nedensellik kanıtlar"),
        _legacy_text() + " Bu sonuç Dünya Bankası raporuyla da doğrulanmıştır.",
        _legacy_text().replace(
            "Haftalık faiz aylık aritmetik ortalamayla birleştirilmiş, "
            "reel kredi TÜFE kullanılarak hesaplanmıştır. ", "",
        ),
    ],
    ids=[
        "number_from_wrong_metric", "unmatched_period_claim",
        "positive_causality_claim", "unsupported_source_claim", "missing_methodology",
    ],
)
def test_rejects_semantically_unsupported_narration(response):
    with pytest.raises(NarrationValidationError):
        validate_housing_narration(response, _evidence())


def test_sixty_month_window_with_fifty_nine_matches_fits_output_limit():
    periods = pd.period_range("2021-01", "2025-12", freq="M").astype(str).tolist()
    bddk = pd.DataFrame({
        "period": periods,
        "nominal_housing_loan_mn_try": [100.0] * 60,
    })
    evds = pd.DataFrame({
        "period": periods,
        "housing_loan_interest_rate_pct": [100.0 - index for index in range(60)],
        "weekly_observation_count": [4] * 60,
        "cpi_index": [100.0 + index for index in range(60)],
        "housing_price_index": [100.0 + index for index in range(60)],
    })
    gold = build_housing_gold_table(bddk, evds)
    evidence = build_housing_analysis_evidence(gold)
    response = _json(_payload(evidence, rounded=True))
    assert evidence.matched_month_count == 59
    assert len(response) <= MAX_RESPONSE_CHARACTERS
    text = validate_housing_narration(response, evidence)
    assert "60 ay incelendi" in text
    assert "2025-12:" in text


@pytest.mark.parametrize("rate, expected_status", [(9.0, 200), (100.0, 502)])
def test_default_api_narrator_validates_model_output(monkeypatch, rate, expected_status):
    from fastapi.testclient import TestClient

    from app.api.main import create_app
    from app.connectors import mia_client
    from tests.test_housing_analysis_api import _payload as api_payload

    response = _json({
        "results": [{
            "period": "2021-02",
            "housing_loan_interest_rate_pct": rate,
            "interest_rate_change_pp": -1.0,
            "real_housing_loan_change_pct": -9.0909,
        }],
    })
    monkeypatch.setattr(mia_client, "ask_mia", lambda prompt: response)
    request = api_payload()
    request["include_narration"] = True
    result = TestClient(create_app()).post("/analysis/housing", json=request)
    assert result.status_code == expected_status
    if expected_status == 200:
        assert "konut kredisi faizi %9" in result.json()["narration"]
        assert "nedensellik kanıtlamaz" in result.json()["narration"]
    else:
        assert result.json()["detail"]["code"] == "narration_failed"
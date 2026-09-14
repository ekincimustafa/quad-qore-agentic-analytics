"""Tests for guarded housing evidence narration."""

from __future__ import annotations

import pandas as pd
import pytest

from app.lakehouse.gold import build_housing_gold_table
from app.tools.housing_evidence import build_housing_analysis_evidence
from app.tools.housing_narrator import (
    NarrationValidationError,
    build_housing_narration_prompt,
    narrate_housing_evidence,
    validate_housing_narration,
)


def _evidence(*, has_match: bool = True):
    bddk = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02", "2021-03"],
            "nominal_housing_loan_mn_try": [100.0, 100.0, 105.0],
        }
    )
    evds = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02", "2021-03"],
            "housing_loan_interest_rate_pct": [20.0, 19.0, 18.0],
            "weekly_observation_count": [4, 4, 5],
            "cpi_index": [100.0, 102.0, 103.0],
            "housing_price_index": [100.0, 101.0, 102.0],
        }
    )
    gold = build_housing_gold_table(
        bddk,
        evds,
        start_period="2021-01",
        end_period="2021-03",
    )
    if not has_match:
        gold.loc[1:, "rate_down_real_credit_not_up"] = False
    return build_housing_analysis_evidence(
        gold,
        start_period="2021-01",
        end_period="2021-03",
    )


def _valid_response() -> str:
    return (
        "2021-02 döneminde konut kredisi faizi 19 seviyesindedir ve aylık "
        "değişim -1 yüzde puandır. Reel kredi değişimi yaklaşık -1,9608 olmuştur. "
        "Haftalık faiz aylık aritmetik ortalamayla birleştirilmiş, reel kredi "
        "TÜFE kullanılarak hesaplanmıştır. Kaynaklar BDDK ile EVDS "
        "TP.KTF12, TP.TUKFIY2025.GENEL ve TP.KFE.TR serileridir. Bu bulgu "
        "nedensellik kanıtlamaz."
    )


def test_prompt_contains_verified_json_and_turkish_rules() -> None:
    prompt = build_housing_narration_prompt(_evidence())

    assert "DOĞRULANMIŞ_KANIT" in prompt
    assert '"matched_periods"' in prompt
    assert '"2021-02"' in prompt
    assert "JSON içinde bulunmayan hiçbir sayı" in prompt


def test_calls_model_once_and_accepts_supported_rounding() -> None:
    captured: list[str] = []

    def fake_model(prompt: str) -> str:
        captured.append(prompt)
        return _valid_response()

    result = narrate_housing_evidence(_evidence(), fake_model)

    assert result == _valid_response()
    assert len(captured) == 1
    assert "2021-02" in captured[0]


def test_rejects_number_not_present_in_evidence() -> None:
    response = _valid_response() + " Kanıtlanmamış değer 999 olarak verilmiştir."

    with pytest.raises(NarrationValidationError, match="bulunmayan sayılar.*999"):
        validate_housing_narration(response, _evidence())


def test_rejects_missing_matching_period() -> None:
    response = _valid_response().replace("2021-02 döneminde ", "İlgili dönemde ")

    with pytest.raises(NarrationValidationError, match="eşleşen dönemler eksik"):
        validate_housing_narration(response, _evidence())


def test_rejects_missing_series_reference() -> None:
    response = _valid_response().replace("TP.KFE.TR", "konut fiyat serisi")

    with pytest.raises(NarrationValidationError, match="seri referansları eksik"):
        validate_housing_narration(response, _evidence())


def test_rejects_missing_causality_limitation() -> None:
    response = _valid_response().replace(
        "Bu bulgu nedensellik kanıtlamaz.",
        "Bu bulgu birlikte hareketi gösterir.",
    )

    with pytest.raises(NarrationValidationError, match="nedensellik sınırlamasını"):
        validate_housing_narration(response, _evidence())


@pytest.mark.parametrize("response", ["", "   ", None])
def test_rejects_empty_or_non_text_response(response: object) -> None:
    with pytest.raises(NarrationValidationError):
        validate_housing_narration(response, _evidence())  # type: ignore[arg-type]


def test_accepts_explicit_no_match_response() -> None:
    response = (
        "Koşula uyan ay bulunamadı. Haftalık faiz aylık aritmetik ortalamayla "
        "hesaplandı ve reel kredi için TÜFE kullanıldı. Kaynaklar BDDK ile "
        "EVDS TP.KTF12, TP.TUKFIY2025.GENEL ve TP.KFE.TR serileridir. "
        "Bu değerlendirme nedensellik kanıtlamaz."
    )

    assert validate_housing_narration(response, _evidence(has_match=False)) == response


def test_rejects_non_callable_model() -> None:
    with pytest.raises(TypeError, match="model_call must be callable"):
        narrate_housing_evidence(_evidence(), "not-callable")  # type: ignore[arg-type]


"""Validate structured model output and render evidence-based Turkish text."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, ValidationError

from app.tools.housing_evidence import HousingAnalysisEvidence


ModelCall = Callable[[str], str]
MAX_RESPONSE_CHARACTERS = 16_000
NUMBER_FIELDS = (
    "housing_loan_interest_rate_pct",
    "interest_rate_change_pp",
    "real_housing_loan_change_pct",
)


class NarrationValidationError(ValueError):
    """Raised when model output cannot be verified against the evidence."""


class _NarrationMonth(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    housing_loan_interest_rate_pct: FiniteFloat
    interest_rate_change_pp: FiniteFloat
    real_housing_loan_change_pct: FiniteFloat


class _NarrationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    results: list[_NarrationMonth]


def _require_evidence(evidence: HousingAnalysisEvidence) -> None:
    if not isinstance(evidence, HousingAnalysisEvidence):
        raise TypeError("evidence must be a HousingAnalysisEvidence instance.")


def _rounded_decimal(value: float) -> Decimal:
    if not math.isfinite(value):
        raise NarrationValidationError("Kanıttaki sayılar sonlu olmalıdır.")
    number = Decimal(str(value))
    with localcontext() as context:
        context.prec = max(28, abs(number.adjusted()) + 20)
        return number.quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)


def _format_number(value: float) -> str:
    number = _rounded_decimal(value)
    if number == 0:
        return "0"
    return format(number, "f").rstrip("0").rstrip(".").replace(".", ",")


def build_housing_narration_prompt(evidence: HousingAnalysisEvidence) -> str:
    """Request a strict JSON draft instead of unverified free-form prose."""
    _require_evidence(evidence)
    schema = json.dumps(_NarrationDraft.model_json_schema(), ensure_ascii=False)
    return f"""Aşağıdaki DOĞRULANMIŞ_KANIT verisini kullanarak yalnızca JSON döndür.

Kurallar:
- Şemaya uygun tek bir JSON nesnesi üret; Markdown veya ek açıklama yazma.
- results, kanıttaki bütün eşleşen ayları tam bir kez içermeli.
- Eşleşen ay yoksa results boş liste olmalı.
- Her sayı aynı ayın aynı adlı evidence alanından alınmalı; hesaplama yapma.
- Tam değeri veya dört ondalık basamağa yuvarlanmış değerini kullan.
- Kaynak, yöntem, nedensellik iddiası veya başka bir alan ekleme.
- Türkçe anlatımı, kaynakları ve sınırlamaları uygulama oluşturacak.

YANIT_ŞEMASI:
{schema}

DOĞRULANMIŞ_KANIT:
{evidence.model_dump_json(indent=2)}
"""


def _render_narration(evidence: HousingAnalysisEvidence) -> str:
    """Render values and fixed domain statements using the trusted evidence."""
    paragraphs = [
        f"{evidence.period_start}–{evidence.period_end} arasında "
        f"{evidence.observed_month_count} ay incelendi."
    ]
    if evidence.results:
        paragraphs.append(
            "Faiz düşerken reel konut kredisi stokunun artmadığı aylar:"
        )
        for row in evidence.results:
            paragraphs.append(
                f"- {row.period}: konut kredisi faizi "
                f"%{_format_number(row.housing_loan_interest_rate_pct)}, "
                f"faiz değişimi {_format_number(row.interest_rate_change_pp)} "
                "yüzde puan, reel kredi değişimi yaklaşık "
                f"%{_format_number(row.real_housing_loan_change_pct)}."
            )
    else:
        paragraphs.append("Koşula uyan ay bulunamadı.")
    paragraphs.extend([
        "Kaynaklar: BDDK (" + "; ".join(evidence.bddk_source_refs)
        + ") ve EVDS (" + "; ".join(evidence.evds_source_refs) + ").",
        "Yöntem: Haftalık faizlerin aylık aritmetik ortalaması kullanıldı. "
        "Reel kredi, nominal tutar × 100 / TÜFE ile hesaplandı. "
        "Aylık değişimler bir önceki ayla karşılaştırıldı.",
        "Bu bulgular nedensellik kanıtlamaz. İlk ayın önceki ay değişimi "
        "bulunmadığından ilk ay koşula uyan aylar arasında değerlendirilmez.",
    ])
    return "\n\n".join(paragraphs)


def validate_housing_narration(
    response: str,
    evidence: HousingAnalysisEvidence,
) -> str:
    """Validate every draft field, then return text rendered from evidence."""
    _require_evidence(evidence)
    if not isinstance(response, str) or not response.strip():
        raise NarrationValidationError("Model yanıtı boş olmayan metin olmalıdır.")
    if len(response) > MAX_RESPONSE_CHARACTERS:
        raise NarrationValidationError("Model yanıtı izin verilen uzunluğu aşıyor.")
    try:
        draft = _NarrationDraft.model_validate_json(response)
    except ValidationError as exc:
        raise NarrationValidationError(
            "Model yanıtı beklenen JSON şemasına uymuyor."
        ) from exc

    expected = {row.period: row for row in evidence.results}
    expected_periods = tuple(row.period for row in evidence.results)
    if (
        len(expected) != len(evidence.results)
        or expected_periods != evidence.matched_periods
        or len(expected) != evidence.matched_month_count
    ):
        raise NarrationValidationError("Kanıtın eşleşen ay bilgileri tutarsız.")
    periods = [row.period for row in draft.results]
    if len(periods) != len(set(periods)):
        raise NarrationValidationError("Model yanıtında mükerrer ay var.")
    if set(periods) != set(expected):
        raise NarrationValidationError("Model yanıtının ayları kanıtla eşleşmiyor.")

    for row in draft.results:
        reference = expected[row.period]
        for field in NUMBER_FIELDS:
            original = getattr(reference, field)
            claimed = Decimal(str(getattr(row, field)))
            if claimed not in (Decimal(str(original)), _rounded_decimal(original)):
                raise NarrationValidationError(
                    f"{row.period} / {field}: değer kanıtla eşleşmiyor."
                )
    return _render_narration(evidence)


def narrate_housing_evidence(
    evidence: HousingAnalysisEvidence,
    model_call: ModelCall,
) -> str:
    if not callable(model_call):
        raise TypeError("model_call must be callable.")
    response = model_call(build_housing_narration_prompt(evidence))
    return validate_housing_narration(response, evidence)


def narrate_housing_evidence_with_mia(evidence: HousingAnalysisEvidence) -> str:
    from app.connectors.mia_client import ask_mia

    return narrate_housing_evidence(evidence, ask_mia)
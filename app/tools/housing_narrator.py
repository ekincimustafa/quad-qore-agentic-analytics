"""Guarded MIA narration for verified housing-analysis evidence."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from decimal import Decimal, InvalidOperation

from app.tools.housing_evidence import HousingAnalysisEvidence


ModelCall = Callable[[str], str]

MAX_RESPONSE_CHARACTERS = 6_000
_NUMBER_PATTERN = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)?")
_CAUSALITY_LIMIT_TERMS = (
    "nedensellik",
    "nedensel",
    "neden-sonuç",
    "sebep-sonuç",
)
_NO_MATCH_TERMS = (
    "eşleşen ay bulunamadı",
    "uygun ay bulunamadı",
    "koşula uyan ay bulunamadı",
)


class NarrationValidationError(ValueError):
    """Raised when an LLM response violates the evidence boundary."""


def build_housing_narration_prompt(evidence: HousingAnalysisEvidence) -> str:
    """Create a Turkish-only prompt containing one verified evidence payload."""

    if not isinstance(evidence, HousingAnalysisEvidence):
        raise TypeError("evidence must be a HousingAnalysisEvidence instance.")

    evidence_json = evidence.model_dump_json(indent=2)
    return f"""Sen bir finansal veri analiz anlatıcısısın.

Yalnızca aşağıdaki DOĞRULANMIŞ_KANIT JSON nesnesini kullanarak Türkçe bir yanıt üret.

Zorunlu kurallar:
- JSON içinde bulunmayan hiçbir sayı, dönem, kaynak veya sonuç ekleme.
- Hesaplama yapma ve verilen sayısal değerleri değiştirme.
- Ondalık değerleri en fazla dört basamağa yuvarlayabilirsin.
- Koşula uyan dönemleri YYYY-MM biçiminde açıkça yaz.
- BDDK ile kullanılan EVDS seri kodlarını belirt.
- Haftalık faizin aylık aritmetik ortalamaya dönüştürüldüğünü ve reel kredi hesabının TÜFE kullandığını açıkla.
- Bulguların nedensellik kanıtlamadığını açıkça belirt.
- Koşula uyan dönem yoksa bunu açıkça söyle; dönem veya değer uydurma.
- Numaralı liste kullanma; gerekiyorsa madde işaretleri kullan.
- Kısa, anlaşılır ve profesyonel yaz.

DOĞRULANMIŞ_KANIT:
{evidence_json}
"""


def _walk_numbers(value: object) -> Iterable[float]:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        yield float(value)
        return
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk_numbers(nested)
        return
    if isinstance(value, (list, tuple)):
        for nested in value:
            yield from _walk_numbers(nested)


def _to_decimal(token: str) -> Decimal:
    try:
        return Decimal(token.replace(",", "."))
    except InvalidOperation as exc:
        raise NarrationValidationError(
            f"Model yanıtındaki sayı çözümlenemedi: {token!r}."
        ) from exc


def _normalized_decimal(token: str) -> str:
    number = _to_decimal(token)
    normalized = format(number.normalize(), "f")
    return "0" if normalized in {"-0", "+0"} else normalized


def _decimal_places(token: str) -> int:
    normalized = token.replace(",", ".")
    return len(normalized.rsplit(".", 1)[1]) if "." in normalized else 0


def _number_is_supported(
    token: str,
    *,
    exact_tokens: set[str],
    evidence_numbers: tuple[float, ...],
) -> bool:
    normalized = _normalized_decimal(token)
    if normalized in exact_tokens:
        return True

    claimed = _to_decimal(token)
    places = min(_decimal_places(token), 4)
    quantum = Decimal(1).scaleb(-places)
    return any(
        Decimal(str(number)).quantize(quantum) == claimed.quantize(quantum)
        for number in evidence_numbers
    )


def validate_housing_narration(
    response: str,
    evidence: HousingAnalysisEvidence,
) -> str:
    """Reject unsupported numerical or source claims in an LLM response."""

    if not isinstance(response, str):
        raise NarrationValidationError("Model yanıtı metin olmalıdır.")

    cleaned = response.strip()
    if not cleaned:
        raise NarrationValidationError("Model boş yanıt döndürdü.")
    if len(cleaned) > MAX_RESPONSE_CHARACTERS:
        raise NarrationValidationError("Model yanıtı izin verilen uzunluğu aşıyor.")

    lower_response = cleaned.casefold()
    if "bddk" not in lower_response or "evds" not in lower_response:
        raise NarrationValidationError(
            "Model yanıtı BDDK ve EVDS kaynaklarını belirtmelidir."
        )
    missing_series = [
        ref for ref in evidence.evds_source_refs if ref.casefold() not in lower_response
    ]
    if missing_series:
        raise NarrationValidationError(
            f"Model yanıtında EVDS seri referansları eksik: {missing_series}."
        )
    if not any(term in lower_response for term in _CAUSALITY_LIMIT_TERMS):
        raise NarrationValidationError(
            "Model yanıtı nedensellik sınırlamasını açıkça belirtmelidir."
        )

    if evidence.matched_periods:
        missing_periods = [
            period for period in evidence.matched_periods if period not in cleaned
        ]
        if missing_periods:
            raise NarrationValidationError(
                f"Model yanıtında eşleşen dönemler eksik: {missing_periods}."
            )
    elif not any(term in lower_response for term in _NO_MATCH_TERMS):
        raise NarrationValidationError(
            "Model yanıtı koşula uyan ay bulunmadığını açıkça belirtmelidir."
        )

    evidence_dump = evidence.model_dump(mode="json")
    evidence_json = evidence.model_dump_json()
    exact_tokens = {
        _normalized_decimal(token) for token in _NUMBER_PATTERN.findall(evidence_json)
    }
    evidence_numbers = tuple(_walk_numbers(evidence_dump))

    unsupported = [
        token
        for token in _NUMBER_PATTERN.findall(cleaned)
        if not _number_is_supported(
            token,
            exact_tokens=exact_tokens,
            evidence_numbers=evidence_numbers,
        )
    ]
    if unsupported:
        raise NarrationValidationError(
            "Model yanıtı kanıtta bulunmayan sayılar içeriyor: "
            f"{unsupported[:5]}."
        )

    return cleaned


def narrate_housing_evidence(
    evidence: HousingAnalysisEvidence,
    model_call: ModelCall,
) -> str:
    """Call an injected text model and validate its response."""

    if not callable(model_call):
        raise TypeError("model_call must be callable.")
    prompt = build_housing_narration_prompt(evidence)
    response = model_call(prompt)
    return validate_housing_narration(response, evidence)


def narrate_housing_evidence_with_mia(
    evidence: HousingAnalysisEvidence,
) -> str:
    """Use the configured MIA connector without exposing credentials here."""

    from app.connectors.mia_client import ask_mia

    return narrate_housing_evidence(evidence, ask_mia)


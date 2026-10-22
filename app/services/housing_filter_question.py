"""Narrow natural-language checks for housing condition-filter plans."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.services.housing_filter import FilterMetric, FilterOperator, HousingFilterCondition
from app.services.question_periods import normalize_question_text

_AMOUNT_TAIL = r"(?:stok\w*|bakiy\w*|tutar\w*|hacm\w*|miktar\w*)"
_CHANGE_TAIL = r"(?:değiş\w*|artış\w*|azalış\w*|büyüme\w*|gerileme\w*)"
_CREDIT_BASE = r"(?:konut\s+)?kredi(?:si|leri|ler)?\b"
_CREDIT_NOUN = rf"{_CREDIT_BASE}(?:\s+(?:{_AMOUNT_TAIL}|{_CHANGE_TAIL}))?"
_REAL_CREDIT = re.compile(
    r"\b(?:reel(?:\s+olarak)?|enflasyondan\s+arındırılmış|"
    r"tüfe\s+ile\s+arındırılmış|enflasyona\s+göre\s+düzeltilmiş)\s+" + _CREDIT_NOUN
)
_NOMINAL_CREDIT = re.compile(r"\bnominal(?:\s+olarak)?\s+" + _CREDIT_NOUN)
_COMBINED_CREDIT = re.compile(
    r"\b(reel|nominal)\s+(?:ve|ile)\s+(reel|nominal)\s+" + _CREDIT_NOUN
)
_BARE_CREDIT = re.compile(
    rf"\b(?:{_CREDIT_BASE}(?:\s+{_AMOUNT_TAIL})?|{_AMOUNT_TAIL})"
)
_INTEREST = re.compile(r"\b(?:konut\s+kredisi\s+)?faiz\w*")

_NEGATED_METRIC = re.compile(
    r"^\s*(?:\w+\s+){0,3}(?:değil|hariç|yerine|dışında)\b"
)
_MIXED_CHOICE = re.compile(r"\b(?:veya|ya\s+da|yahut|mi)\b")
_MIXED_CREDIT = re.compile(
    r"\b(?:reel|nominal)\b[^.;]{0,40}?\b(?:veya|ya\s+da|yahut|mi)\b"
    r"[^.;]{0,40}?\b(?:reel|nominal)\b"
)

_CHANGE_CUE = re.compile(
    r"\b(?:değiş\w*|art\w*|azal\w*|düş\w*|yüksel\w*|gerile\w*|"
    r"büyü\w*|küçül\w*|sabit\s+kalan)\b"
)
_UP = re.compile(
    r"\b(?:artan|artar|artıyor|arttı|artma\w*|artış\w*|yükselen|yükselir|"
    r"yükseliyor|yükseldi|yükselme\w*|yükseliş\w*|büyüyen|büyür|büyüme\w*|pozitif)\w*"
)
_DOWN = re.compile(
    r"\b(?:azalan|azalır|azalıyor|azaldı|azalma\w*|azalış\w*|düşen|düşer|"
    r"düşüyor|düştü|düşme\w*|düşüş\w*|gerileyen|geriler\w*|gerileme\w*|"
    r"küçülen|küçülme\w*|negatif)\w*"
)
_NOT_UP = re.compile(
    r"\b(?:artmayan|artmadığı|artmadı|artmamış|artmayıp|artmıyor|"
    r"artış\w*\s+(?:olmayan|olmadığı|yok)|artış\s+göstermeyen|"
    r"yükselmeyen|yükselmediği|yükselmedi|yükselmiyor|"
    r"büyümeyen|büyümediği|büyümedi|büyümüyor)\w*"
)
_NOT_DOWN = re.compile(
    r"\b(?:azalmayan|azalmadığı|azalmadı|azalmamış|azalmıyor|"
    r"azalış\w*\s+(?:olmayan|olmadığı|yok)|azalış\s+göstermeyen|"
    r"düşmeyen|düşmediği|düşmedi|düşmüyor|gerilemeyen)\w*"
)
_LEVEL_CUE = re.compile(r"\b(?:seviye\w*|oran\w*|düzey\w*)\b")

_RELATION = re.compile(
    r"(?P<gte>\ben\s+az(?:ından)?\b|\bve\s+(?:üzeri|üstü)\w*\b|"
    r"\bveya\s+daha\s+fazla\b|\beşit\s+veya\s+büyük\b|\b(?:kadar\s+)?üzeri\b)"
    r"|(?P<lte>\ben\s+fazla\b|\ben\s+çok\b|\başmayan\b|\bgeçmeyen\b|"
    r"\bve\s+alt(?:ı|ında|ına|ındaki)\b|\bveya\s+daha\s+az\b|"
    r"\beşit\s+veya\s+küçük\b|\bkadar\b)"
    r"|(?P<gt>\başan\b|\bgeçen\b(?!\s+(?:yıl|yıla|yılı|yılda|hafta|gün|dönem|çeyrek))|"
    r"\büzerinde\b|\büstünde\b|\bfazla\b|\byüksek\b|\bbüyük\b)"
    r"|(?P<lt>\baltında\b|\baltına\b|\baltındaki\b|\bküçük\b|\bdüşük\b|\baz\b)"
)
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)*(?![\w.])")

_PREFIX_SEPARATOR = re.compile(r"\b(?:ve|veya|ya\s+da|yahut|iken|ayrıca)\b|[,;]")

_REAL_INTEREST = re.compile(
    r"\b(?:reel(?:\s+olarak)?|enflasyondan\s+arındırılmış|"
    r"tüfe\s+ile\s+arındırılmış)\s+faiz\b"
)
_OUT_OF_SCOPE = re.compile(
    r"\b(?:tahmin\w*|öngör\w*|nedensellik\w*|neden\w*|kanıtla\w*|etkisi\w*|"
    r"ortalama\w*|yıllık\w*|yıllıklandır\w*|toplam\w*)\b"
)
_TOPN = re.compile(
    r"\b(?:top[-\s]?\d+|sırala\w*|sıralı|en\s+(?:yüksek|düşük)\w*)\b"
)
_DEFLATOR = re.compile(
    r"(?:enflasyondan\s+arındırılmış|tüfe\s+ile\s+arındırılmış|"
    r"tüfe'?ye\s+göre|enflasyona\s+göre\s+düzeltilmiş|reel)"
)
_OTHER_METRIC = re.compile(
    r"\b(?:tüfe|tüketici\s+fiyat\w*|enflasyon\w*|döviz\w*|kur|borsa|altın|"
    r"işsizlik|gsyh|bütçe|kfe|konut\s+fiyat\w*)\b"
)
_OR = re.compile(r"\b(?:veya|ya\s+da|yahut)\b")
_OR_OPERATOR = re.compile(
    r"(?:eşit\s+)?veya\s+daha\s+(?:az|fazla)|eşit\s+veya\s+(?:küçük|büyük)"
)


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class _Parsed:
    metric: FilterMetric
    operator: FilterOperator
    threshold: float


def _overlaps(span: _Span, other: _Span) -> bool:
    return span.start < other.end and other.start < span.end


def _negated(text: str, span: _Span) -> bool:
    return bool(_NEGATED_METRIC.match(text[span.end:span.end + 60]))


def _metric_spans(text: str) -> list[_Span]:
    spans: list[_Span] = []

    def overlaps(candidate: _Span, kinds: set[str]) -> bool:
        return any(
            _overlaps(candidate, span) for span in spans if span.kind in kinds
        )

    for match in _COMBINED_CREDIT.finditer(text):
        candidate = _Span(match.start(), match.end(), "combined")
        if _negated(text, candidate):
            continue
        for qualifier in (match.group(1), match.group(2)):
            kind = "real_credit" if qualifier == "reel" else "nominal_credit"
            spans.append(_Span(match.start(), match.end(), kind))

    for kind, pattern in (
        ("real_credit", _REAL_CREDIT),
        ("nominal_credit", _NOMINAL_CREDIT),
        ("interest", _INTEREST),
    ):
        for match in pattern.finditer(text):
            candidate = _Span(match.start(), match.end(), kind)
            if not overlaps(candidate, {"real_credit", "nominal_credit", "interest"}):
                spans.append(candidate)

    for match in _BARE_CREDIT.finditer(text):
        candidate = _Span(match.start(), match.end(), "bare_credit")
        if not overlaps(candidate, {"real_credit", "nominal_credit", "interest"}):
            spans.append(candidate)

    spans = [span for span in spans if not _negated(text, span)]
    spans.sort(key=lambda span: (span.start, span.end))
    return spans


def _neighbours(
    text: str, span: _Span, spans: list[_Span]
) -> tuple[int, int]:
    previous = max(
        (other.end for other in spans if other.end <= span.start), default=0
    )
    following = min(
        (other.start for other in spans if other.start >= span.end),
        default=len(text),
    )
    return previous, following


def _prefix(text: str, span: _Span, previous: int) -> str:
    raw = text[max(previous, span.start - 80):span.start]
    separators = list(_PREFIX_SEPARATOR.finditer(raw))
    if separators:
        return raw[separators[-1].end():]
    return raw if previous == 0 else ""


def _relations(context: str) -> list[tuple[str, re.Match[str]]]:
    return [
        (match.lastgroup or "", match)
        for match in _RELATION.finditer(context)
    ]


def _number_value(raw: str) -> float:
    value = raw.strip()
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".")
    elif value.count(".") > 1:
        value = value.replace(".", "")
    else:
        value = value.replace(",", ".")
    return float(value)


def _percent_marker(context: str, match: re.Match[str]) -> bool:
    before = context[max(0, match.start() - 12):match.start()]
    after = context[match.end():match.end() + 8]
    return "%" in before or "%" in after or "yüzde" in before


def _point_marker(context: str, match: re.Match[str]) -> bool:
    window = context[max(0, match.start() - 16):match.end() + 24]
    return "puan" in window


def _direction(context: str) -> tuple[FilterOperator, float] | None:
    not_up = bool(_NOT_UP.search(context))
    not_down = bool(_NOT_DOWN.search(context))
    if not_up and not_down:
        return None
    if not_up:
        return "lte", 0.0
    if not_down:
        return "gte", 0.0
    categories = [
        (operator, float(threshold))
        for operator, threshold, pattern in (
            ("gt", 0.0, _UP),
            ("lt", 0.0, _DOWN),
        )
        if pattern.search(context)
    ]
    if len({operator for operator, _ in categories}) > 1:
        return None
    return categories[0] if categories else None


def _numeric_condition(
    context: str,
) -> tuple[FilterOperator, float] | None:
    relations = _relations(context)
    if not relations:
        return None
    candidates: list[tuple[float, int, FilterOperator, re.Match[str]]] = []
    for match in _NUMBER.finditer(context):
        value = _number_value(match.group())
        if (
            1900 <= value <= 2099
            and float(value).is_integer()
            and not _percent_marker(context, match)
            and not _point_marker(context, match)
        ):
            continue
        nearest = min(
            relations,
            key=lambda item: (
                min(
                    abs(match.start() - item[1].end()),
                    abs(item[1].start() - match.end()),
                ),
                0 if _percent_marker(context, match) or _point_marker(context, match) else 1,
            ),
        )
        distance = min(
            abs(match.start() - nearest[1].end()),
            abs(nearest[1].start() - match.end()),
        )
        candidates.append((distance, match.start(), nearest[0], match))
    if not candidates:
        return None
    _, _, operator, match = min(candidates, key=lambda item: (item[0], item[1]))
    if operator == "gte":
        return "gte", _number_value(match.group())
    if operator == "lte":
        return "lte", _number_value(match.group())
    if operator == "gt":
        return "gt", _number_value(match.group())
    return "lt", _number_value(match.group())


def _parse_span(
    text: str, span: _Span, spans: list[_Span]
) -> _Parsed | str | None:
    previous, following = _neighbours(text, span, spans)
    suffix = text[span.end:min(following, span.end + 220)]
    prefix = _prefix(text, span, previous)
    span_text = text[span.start:span.end]
    combined = f"{span_text} {suffix} {prefix}"

    numeric = _numeric_condition(suffix) or _numeric_condition(prefix)
    direction = _direction(combined)

    has_change = bool(
        _CHANGE_CUE.search(combined)
        or _CHANGE_CUE.search(text[span.start:span.end])
    )

    if span.kind == "interest":
        metric: FilterMetric = (
            "interest_rate_change_pp" if has_change
            else "housing_loan_interest_rate_pct"
        )
    else:
        if not has_change:
            return "unsupported"
        metric = (
            "real_housing_loan_change_pct"
            if span.kind == "real_credit"
            else "nominal_housing_loan_change_pct"
        )

    if numeric is not None:
        operator, threshold = numeric
        number_match = None
        for match in _NUMBER.finditer(combined):
            if math.isclose(_number_value(match.group()), threshold, abs_tol=1e-9):
                number_match = match
                break
        if number_match is not None:
            percent = _percent_marker(combined, number_match)
            points = _point_marker(combined, number_match)
            if metric == "interest_rate_change_pp":
                if percent and not points:
                    return "metric_ambiguous"
                if not points:
                    return "metric_ambiguous"
            elif points:
                return "metric_ambiguous"
        return _Parsed(metric=metric, operator=operator, threshold=threshold)

    if direction is not None:
        return _Parsed(metric=metric, operator=direction[0], threshold=direction[1])

    if metric == "housing_loan_interest_rate_pct" and _LEVEL_CUE.search(combined):
        return None
    return None


def guard_housing_filter_question(
    question: str, conditions: tuple[HousingFilterCondition, ...]
) -> str | None:
    """Return a safe clarification/unsupported reason, or None when grounded."""
    text = normalize_question_text(question)
    spans = _metric_spans(text)

    real = [span for span in spans if span.kind == "real_credit"]
    nominal = [span for span in spans if span.kind == "nominal_credit"]
    if _MIXED_CREDIT.search(text):
        return "metric_ambiguous"
    if real and nominal and _MIXED_CHOICE.search(text):
        return "metric_ambiguous"
    if any(span.kind == "bare_credit" for span in spans):
        return "metric_ambiguous"

    if _REAL_INTEREST.search(text):
        return "unsupported"
    if _OUT_OF_SCOPE.search(text) or _TOPN.search(text):
        return "unsupported"
    without_operators = _OR_OPERATOR.sub(" ", text)
    if _OR.search(without_operators):
        return "unsupported"
    residual = _DEFLATOR.sub(" ", text)
    if _OTHER_METRIC.search(residual):
        return "unsupported"

    parsed: list[_Parsed] = []
    for span in spans:
        item = _parse_span(text, span, spans)
        if isinstance(item, str):
            return item
        if item is not None:
            parsed.append(item)
    if not parsed:
        return "question_ambiguous"
    if len(parsed) > 3:
        return "unsupported"

    requested = Counter(
        (item.metric, item.operator, round(item.threshold, 9))
        for item in parsed
    )
    planned = Counter(
        (
            item.metric,
            item.operator,
            round(float(item.threshold), 9),
        )
        for item in conditions
    )
    return None if requested == planned else "question_ambiguous"

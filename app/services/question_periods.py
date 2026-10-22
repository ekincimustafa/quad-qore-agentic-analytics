"""Bounded resolution of the explicit Turkish periods used by question planning."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass


_MONTHS = {
    "ocak": "01", "şubat": "02", "mart": "03", "nisan": "04",
    "mayıs": "05", "haziran": "06", "temmuz": "07", "ağustos": "08",
    "eylül": "09", "ekim": "10", "kasım": "11", "aralık": "12",
}
_YEAR = r"(?:19|20)\d{2}"
_MONTH_NAME = "(?:" + "|".join(_MONTHS) + ")"
_POSSESSIVE = r"(?:['’][a-zçğıöşü]+)?"
_SPAN_SEPARATOR = (
    r"(?:\s*[-–—]\s*|\s*['’](?:tan|ten|dan|den)\s*|"
    r"\s+ay[ıi]ndan\s+|\s+ay[ıi]\s+(?:ile|ve)\s+|\s+(?:ile|ve)\s+)"
)
_QUARTER_ORDINAL = r"(?:ilk|birinci|ikinci|üçüncü|dördüncü|son|[1-4]\s*\.)"
_HALF_ORDINAL = r"(?:ilk|birinci|son|ikinci)"
_QUARTER_NOUN = r"(?:çeyre(?:k|ğ)\w*|üç\s+ay\w*)"
_HALF_NOUN = r"(?:(?:altı|6)\s+ay\w*|yar[ıi]s\w*)"

_YEAR_TOKEN = re.compile(rf"(?<!\d){_YEAR}(?!\d)")
_MONTH_TOKEN = re.compile(rf"\b{_MONTH_NAME}\b")
_DAY_MONTH_YEAR = re.compile(rf"(?<!\d)(\d{{1,2}})\s+({_MONTH_NAME})\s+({_YEAR})\b")
_DAY_DATE = re.compile(
    r"(?<!\d)(?:\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{4})(?!\d)"
)
_YEAR_SPAN = re.compile(rf"(?<!\d)({_YEAR})\s*[-–—]\s*({_YEAR})(?!\d)")
_YEAR_FIRST_SPAN = re.compile(
    rf"(?<!\d)(?P<year1>{_YEAR}){_POSSESSIVE}?\s+(?:yıl\w*\s+)?(?P<month1>{_MONTH_NAME})"
    rf"{_SPAN_SEPARATOR}(?:(?P<year2>{_YEAR}){_POSSESSIVE}?\s+)?(?P<month2>{_MONTH_NAME})\b"
)
_YEAR_LAST_SPAN = re.compile(
    rf"\b(?P<month1>{_MONTH_NAME}){_SPAN_SEPARATOR}(?P<month2>{_MONTH_NAME})"
    rf"{_POSSESSIVE}?\s+(?P<year>{_YEAR})\b"
)
_QUARTER = re.compile(
    rf"(?<!\d)(?P<year>{_YEAR}){_POSSESSIVE}?\s+(?:yıl\w*\s+)?"
    rf"(?P<ordinal>{_QUARTER_ORDINAL})\s+{_QUARTER_NOUN}\b"
)
_HALF_YEAR = re.compile(
    rf"(?<!\d)(?P<year>{_YEAR}){_POSSESSIVE}?\s+(?:yıl\w*\s+)?"
    rf"(?P<ordinal>{_HALF_ORDINAL})\s+{_HALF_NOUN}\b"
)
_QUARTER_PHRASE = re.compile(rf"\b{_QUARTER_ORDINAL}\s+{_QUARTER_NOUN}\b")
_HALF_PHRASE = re.compile(rf"\b{_HALF_ORDINAL}\s+{_HALF_NOUN}\b")
_WHOLE_YEAR = re.compile(
    rf"(?<!\d)(?P<year>{_YEAR}){_POSSESSIVE}?\s+"
    rf"(?:yılında(?:ki)?|yılı\s+boyunca|yılının\s+tamamında|yılının\s+tamamı|"
    rf"yıl\s+boyunca|yılın\s+tamamında|yılı\s+içinde|yılı\s+genelinde)\b"
    rf"(?!\s+(?:ilk|birinci|ikinci|üçüncü|dördüncü|son|[1-4]\s*\.)\s+)"
)
_ANY_NAMED_SPAN = re.compile(rf"\b{_MONTH_NAME}{_SPAN_SEPARATOR}{_MONTH_NAME}\b")
_MONTH_POINT_PATTERNS = (
    (re.compile(rf"(?<!\d)({_YEAR})-(0[1-9]|1[0-2])(?![-/\d])"), (1, 2)),
    (re.compile(rf"(?<!\d)(0?[1-9]|1[0-2])/({_YEAR})(?!\d)"), (2, 1)),
    (re.compile(rf"(?<!\d)({_YEAR})\s+({_MONTH_NAME})\b"), (1, 2)),
    (re.compile(rf"\b({_MONTH_NAME})\s+({_YEAR})\b"), (2, 1)),
)
_OPEN_ENDED_PERIOD = re.compile(
    r"\b(?:itibaren|sonra(?:ki)?|sonrası(?:nda)?|başlayarak|bu\s+yana)\b"
)
_RANGE_SUFFIX = re.compile(r"^\s+(?:ay\w*\s+)?(?:arası\w*|aralığ\w*|kadar)\b")
_LIST_SEPARATOR = re.compile(r"\bve\b")
_RANGE_BETWEEN = re.compile(r"^\s*(?:[-–—]|ile)\s*$")
_QUARTER_START = {1: 1, 2: 4, 3: 7, 4: 10}


@dataclass(frozen=True)
class _Candidate:
    start: str
    end: str
    spans: tuple[tuple[int, int], ...]
    kind: str = "specific"


@dataclass(frozen=True)
class _MonthPoint:
    period: str
    start: int
    end: int


def normalize_question_text(question: str) -> str:
    """Lowercase Turkish text without changing the user's original prompt."""
    return question.translate(str.maketrans("IİŞĞÜÖÇ", "ıişğüöç")).casefold()


def year_tokens(text: str) -> list[str]:
    return _YEAR_TOKEN.findall(text)


def _month_points(text: str) -> list[_MonthPoint]:
    points = []
    for pattern, (year_group, month_group) in _MONTH_POINT_PATTERNS:
        for match in pattern.finditer(text):
            year, month = match[year_group], match[month_group]
            points.append(_MonthPoint(
                period=f"{year}-{_MONTHS.get(month, month.zfill(2))}",
                start=match.start(), end=match.end(),
            ))
    points.sort(key=lambda point: point.start)
    return points


def month_points(text: str) -> list[tuple[int, str]]:
    """Collect supported month expressions with their positions in the text."""
    return [(point.start, point.period) for point in _month_points(text)]


def month_tokens(text: str) -> list[str]:
    return [match.group() for match in _MONTH_TOKEN.finditer(text)]


def contains_partial_period_expression(text: str) -> bool:
    """True for a day, month-range, quarter or half-year expression."""
    return bool(
        _DAY_MONTH_YEAR.search(text)
        or _DAY_DATE.search(text)
        or _ANY_NAMED_SPAN.search(text)
        or _QUARTER_PHRASE.search(text)
        or _HALF_PHRASE.search(text)
    )


def _period(year: str, month: str, end_year: str | None = None, end_month: str | None = None) -> _Candidate | None:
    start = f"{year}-{_MONTHS[month]}"
    end = f"{end_year or year}-{_MONTHS[end_month or month]}"
    return None if start > end else _Candidate(start=start, end=end, spans=())


def _day_candidate(text: str) -> _Candidate | None:
    days = list(_DAY_MONTH_YEAR.finditer(text))
    if len(days) != 2:
        return None
    first, last = days
    end_month = int(_MONTHS[last[2]])
    if int(first[1]) != 1 or int(last[1]) != calendar.monthrange(int(last[3]), end_month)[1]:
        return None
    candidate = _period(first[3], first[2], last[3], last[2])
    if candidate is None:
        return None
    return _Candidate(candidate.start, candidate.end, (
        (first.start(), first.end()), (last.start(), last.end()),
    ))


def _quarter_number(token: str) -> int:
    return {
        "ilk": 1, "birinci": 1, "1.": 1,
        "ikinci": 2, "2.": 2,
        "üçüncü": 3, "3.": 3,
        "dördüncü": 4, "son": 4, "4.": 4,
    }[token.replace(" ", "")]


def _span_is_closed(text: str, match: re.Match[str]) -> bool:
    if not _LIST_SEPARATOR.search(text[match.start():match.end()]):
        return True
    return bool(_RANGE_SUFFIX.match(text[match.end():]))


def _whole_year_kind(phrase: str) -> str:
    if phrase.endswith(("yılında", "yılındaki")):
        return "whole_year_context"
    return "whole_year_explicit"


def _month_points_form_range(text: str, first: _MonthPoint, second: _MonthPoint) -> bool:
    between = text[first.end:second.start]
    if _RANGE_BETWEEN.match(between):
        return True
    return bool(
        _LIST_SEPARATOR.search(between)
        and _RANGE_SUFFIX.match(text[second.end:])
    )


def _complete_candidates(text: str) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for match in _YEAR_SPAN.finditer(text):
        candidates.append(_Candidate(
            start=f"{match[1]}-01", end=f"{match[2]}-12",
            spans=((match.start(), match.end()),),
        ))
    for match in _YEAR_FIRST_SPAN.finditer(text):
        candidate = _period(match["year1"], match["month1"], match["year2"], match["month2"])
        if candidate is not None and _span_is_closed(text, match):
            candidates.append(_Candidate(
                candidate.start, candidate.end, ((match.start(), match.end()),),
            ))
    for match in _YEAR_LAST_SPAN.finditer(text):
        candidate = _period(match["year"], match["month1"], match["year"], match["month2"])
        if candidate is not None and _span_is_closed(text, match):
            candidates.append(_Candidate(
                candidate.start, candidate.end, ((match.start(), match.end()),),
            ))
    for match in _QUARTER.finditer(text):
        start_month = _QUARTER_START[_quarter_number(match["ordinal"])]
        candidates.append(_Candidate(
            start=f"{match['year']}-{start_month:02d}",
            end=f"{match['year']}-{start_month + 2:02d}",
            spans=((match.start(), match.end()),),
        ))
    for match in _HALF_YEAR.finditer(text):
        first = match["ordinal"].replace(" ", "") in {"ilk", "birinci"}
        candidates.append(_Candidate(
            start=f"{match['year']}-{'01' if first else '07'}",
            end=f"{match['year']}-{'06' if first else '12'}",
            spans=((match.start(), match.end()),),
        ))
    for match in _WHOLE_YEAR.finditer(text):
        candidates.append(_Candidate(
            start=f"{match['year']}-01", end=f"{match['year']}-12",
            spans=((match.start(), match.end()),),
            kind=_whole_year_kind(match.group()),
        ))
    return candidates


def _inside(position: int, spans: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= position < end for start, end in spans)


def _candidate_tokens_consistent(
    text: str, start: str, end: str, spans: tuple[tuple[int, int], ...],
) -> bool:
    allowed_years = {start[:4], end[:4]}
    if any(
        not _inside(match.start(), spans) and match.group() not in allowed_years
        for match in _YEAR_TOKEN.finditer(text)
    ):
        return False
    if any(not _inside(match.start(), spans) for match in _MONTH_TOKEN.finditer(text)):
        return False
    if any(not _inside(point.start, spans) for point in _month_points(text)):
        return False
    if any(not _inside(match.start(), spans) for match in _QUARTER_PHRASE.finditer(text)):
        return False
    if any(not _inside(match.start(), spans) for match in _HALF_PHRASE.finditer(text)):
        return False
    return True


def explicit_period(question: str) -> tuple[str, str] | None:
    """Return a single closed period only when every explicit date agrees."""
    text = normalize_question_text(question)
    if not _YEAR_TOKEN.search(text) or _OPEN_ENDED_PERIOD.search(text):
        return None
    if _DAY_DATE.search(text):
        return None

    days = list(_DAY_MONTH_YEAR.finditer(text))
    candidates: list[_Candidate] = []
    if days:
        day_candidate = _day_candidate(text)
        if day_candidate is None:
            return None
        candidates.append(day_candidate)
    candidates.extend(_complete_candidates(text))

    if candidates:
        periods = {(candidate.start, candidate.end) for candidate in candidates}
        selected = candidates
        if len(periods) != 1:
            specific = [candidate for candidate in candidates if candidate.kind == "specific"]
            specific_periods = {(candidate.start, candidate.end) for candidate in specific}
            year_context = [
                candidate for candidate in candidates if candidate.kind == "whole_year_context"
            ]
            explicit_whole_year = [
                candidate for candidate in candidates if candidate.kind == "whole_year_explicit"
            ]
            if len(specific_periods) != 1 or explicit_whole_year:
                return None
            start, end = next(iter(specific_periods))
            if not all(
                candidate.start[:4] == start[:4] and candidate.end[:4] == end[:4]
                for candidate in year_context
            ):
                return None
            selected = specific
            periods = {(start, end)}
        start, end = periods.pop()
        spans = tuple(
            span for candidate in selected
            if (candidate.start, candidate.end) == (start, end)
            for span in candidate.spans
        )
        if not _candidate_tokens_consistent(text, start, end, spans):
            return None
        return (start, end) if start <= end else None

    points = _month_points(text)
    if len(points) not in {1, 2}:
        return None
    if len(points) == 1:
        start = end = points[0].period
        spans = ((points[0].start, points[0].end),)
    else:
        if not _month_points_form_range(text, points[0], points[1]):
            return None
        start, end = points[0].period, points[1].period
        if start > end:
            return None
        spans = tuple((point.start, point.end) for point in points)

    allowed_years = {start[:4], end[:4]}
    if any(
        not _inside(match.start(), spans) and match.group() not in allowed_years
        for match in _YEAR_TOKEN.finditer(text)
    ):
        return None
    if any(not _inside(match.start(), spans) for match in _MONTH_TOKEN.finditer(text)):
        return None
    if any(not _inside(match.start(), spans) for match in _QUARTER_PHRASE.finditer(text)):
        return None
    if any(not _inside(match.start(), spans) for match in _HALF_PHRASE.finditer(text)):
        return None
    return (start, end) if start <= end else None

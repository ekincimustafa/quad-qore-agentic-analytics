"""Quality assessment for weekly EVDS observation coverage."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class MonthlyWeeklyCoverage:
    period: str
    status: Literal["unverified"]
    observed_count: int
    expected_count: int | None
    observed_dates: tuple[str, ...]
    quality_note: str


def assess_monthly_weekly_coverage(
    *,
    period: str,
    observed_dates: list[str],
) -> MonthlyWeeklyCoverage:
    """Assess coverage without assuming a fixed number of weeks per month."""

    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
        raise ValueError("Period must use YYYY-MM format.")

    if not observed_dates:
        raise ValueError("No weekly observations found.")

    for observation in observed_dates:
        if (
            not isinstance(observation, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", observation)
        ):
            raise ValueError("Invalid weekly observation date.")

        try:
            parsed = date.fromisoformat(observation)
        except ValueError as exc:
            raise ValueError("Invalid weekly observation date.") from exc

        if parsed.strftime("%Y-%m") != period:
            raise ValueError(
                "Weekly observation belongs to another month."
            )

    if len(observed_dates) != len(set(observed_dates)):
        raise ValueError("Duplicate weekly observation dates detected.")

    return MonthlyWeeklyCoverage(
        period=period,
        status="unverified",
        observed_count=len(observed_dates),
        expected_count=None,
        observed_dates=tuple(sorted(observed_dates)),
        quality_note=(
            "Weekly coverage cannot be confirmed without "
            "a verified source publication calendar."
        ),
    )
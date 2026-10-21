"""Deterministic Plotly chart for a CPI inflation evidence run."""

from __future__ import annotations

import json
import math
import re
from numbers import Real
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.services.inflation_analysis import InflationEvidence, InflationMonth

PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

_PANEL_TITLES = (
    "TÜFE endeksi (2025=100)",
    "Aylık değişim (%)",
    "Yıllık değişim (%)",
)
_EMPTY_SERIES_NOTES = {
    2: "Bu dönemde önceki ay olmadığı için aylık değişim yok.",
    3: "Önceki yılın aynı ayı olmadığı için yıllık değişim yok.",
}


class InflationChartError(ValueError):
    """Raised when a trustworthy chart cannot be built from CPI evidence."""


def _period_text(value: object) -> str:
    if not isinstance(value, str) or PERIOD_PATTERN.fullmatch(value) is None:
        raise InflationChartError("Evidence dönemi geçerli YYYY-MM metni olmalıdır.")
    return value


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _validated_observations(evidence: InflationEvidence) -> tuple[InflationMonth, ...]:
    if not isinstance(evidence, InflationEvidence):
        raise InflationChartError("Grafik için InflationEvidence gerekir.")
    observations = evidence.observations
    if not isinstance(observations, tuple) or not observations:
        raise InflationChartError("Evidence en az bir aylık gözlem içermelidir.")
    if (
        not isinstance(evidence.observed_month_count, int)
        or isinstance(evidence.observed_month_count, bool)
        or evidence.observed_month_count != len(observations)
    ):
        raise InflationChartError("Evidence ay sayısı gözlem satırlarıyla uyuşmuyor.")
    if any(not isinstance(row, InflationMonth) for row in observations):
        raise InflationChartError("Evidence yalnız aylık gözlem satırları içermelidir.")

    actual_periods = [_period_text(row.period) for row in observations]
    if evidence.period_start != actual_periods[0] or evidence.period_end != actual_periods[-1]:
        raise InflationChartError("Evidence dönem aralığı gözlem satırlarıyla uyuşmuyor.")
    try:
        expected_periods = [
            str(period)
            for period in pd.period_range(
                evidence.period_start, evidence.period_end, freq="M"
            )
        ]
    except (ValueError, OverflowError):
        raise InflationChartError("Evidence dönem aralığı geçerli değil.") from None
    if actual_periods != expected_periods:
        raise InflationChartError(
            "Evidence gözlem dönemleri eksiksiz ve artan sırada olmalıdır."
        )

    available_start = _period_text(evidence.available_period_start)
    available_end = _period_text(evidence.available_period_end)
    if available_start > actual_periods[0] or available_end < actual_periods[-1]:
        raise InflationChartError("Evidence kullanılabilir dönem kapsamı tutarsız.")

    for row in observations:
        if not _is_finite_number(row.cpi_index) or row.cpi_index <= 0:
            raise InflationChartError(
                f"{row.period}: TÜFE endeksi pozitif ve sonlu sayı olmalıdır."
            )
        if row.monthly_inflation_pct is not None and not _is_finite_number(
            row.monthly_inflation_pct
        ):
            raise InflationChartError(
                f"{row.period}: aylık değişim sonlu sayı veya null olmalıdır."
            )
        if row.annual_inflation_pct is not None and not _is_finite_number(
            row.annual_inflation_pct
        ):
            raise InflationChartError(
                f"{row.period}: yıllık değişim sonlu sayı veya null olmalıdır."
            )

    first, last = observations[0], observations[-1]
    if (
        not _is_finite_number(evidence.first_cpi_index)
        or evidence.first_cpi_index != first.cpi_index
        or not _is_finite_number(evidence.last_cpi_index)
        or evidence.last_cpi_index != last.cpi_index
        or not _is_finite_number(evidence.first_to_last_index_change_pct)
    ):
        raise InflationChartError("Evidence endeks özeti gözlem satırlarıyla uyuşmuyor.")
    return observations


def _series_values(
    observations: tuple[InflationMonth, ...], field: str
) -> list[float | None]:
    return [getattr(row, field) for row in observations]


def _empty_series_annotations(
    observations: tuple[InflationMonth, ...],
) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    series = (
        (2, "monthly_inflation_pct"),
        (3, "annual_inflation_pct"),
    )
    for panel, field in series:
        if any(getattr(row, field) is not None for row in observations):
            continue
        annotations.append(
            {
                "x": 0.5,
                "y": 0.5,
                "xref": f"x{panel} domain",
                "yref": f"y{panel} domain",
                "text": _EMPTY_SERIES_NOTES[panel],
                "showarrow": False,
                "align": "center",
                "font": {"size": 12, "color": "#526176"},
            }
        )
    return annotations


def build_inflation_chart(evidence: InflationEvidence) -> dict[str, Any]:
    """Return a JSON-safe, three-panel Plotly figure specification.

    Values are copied from the evidence in the order supplied. Null changes stay
    null so Plotly renders gaps instead of joining or inventing observations.
    """

    observations = _validated_observations(evidence)
    x_values = [f"{row.period}-01" for row in observations]

    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=_PANEL_TITLES,
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=_series_values(observations, "cpi_index"),
            mode="lines+markers",
            name="TÜFE endeksi (2025=100)",
            connectgaps=False,
            hovertemplate=(
                "%{x|%Y-%m}<br>"
                "TÜFE endeksi (2025=100): %{y:.4f}"
                "<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=_series_values(observations, "monthly_inflation_pct"),
            mode="lines+markers",
            name="Aylık değişim (%)",
            connectgaps=False,
            hovertemplate=(
                "%{x|%Y-%m}<br>"
                "Aylık değişim: %{y:.4f}%"
                "<extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=_series_values(observations, "annual_inflation_pct"),
            mode="lines+markers",
            name="Yıllık değişim (%)",
            connectgaps=False,
            hovertemplate=(
                "%{x|%Y-%m}<br>"
                "Yıllık değişim (önceki yılın aynı ayına göre): %{y:.4f}%"
                "<extra></extra>"
            ),
        ),
        row=3,
        col=1,
    )

    figure.update_yaxes(title_text="TÜFE endeksi (2025=100)", row=1, col=1)
    figure.update_yaxes(title_text="Değişim (%)", row=2, col=1)
    figure.update_yaxes(title_text="Değişim (%)", row=3, col=1)
    figure.update_xaxes(title_text="Dönem", row=3, col=1)
    figure.update_layout(
        title={"text": "TÜFE Enflasyon Analizi", "x": 0.01, "xanchor": "left"},
        height=900,
        hovermode="x unified",
        dragmode="zoom",
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.09,
            "x": 0.5,
            "xanchor": "center",
        },
        margin={"t": 120, "b": 110, "l": 70, "r": 30},
        template="plotly_white",
    )
    for annotation in _empty_series_annotations(observations):
        figure.add_annotation(**annotation)

    return json.loads(figure.to_json())

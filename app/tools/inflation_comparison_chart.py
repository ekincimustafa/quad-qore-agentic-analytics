"""Three-panel, six-trace CPI year-comparison chart from existing evidence.

Presentation only: no inflation, index-change or year-difference calculation.
"""

from __future__ import annotations

import json
import math
from numbers import Real
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.services.inflation_comparison import (
    InflationComparison,
    InflationYearEvidence,
)
from app.tools.inflation_chart import InflationChartError, _validated_observations


class InflationComparisonChartError(ValueError):
    """The comparison is unsuitable for a trustworthy chart or report."""


_MONTH_NAMES = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)
_COLORS = ("#2563eb", "#d97706")
_PANELS = (
    ("TÜFE endeksi (2025=100)", "cpi_index", "TÜFE endeksi (2025=100)"),
    ("Aylık değişim (%)", "monthly_inflation_pct", "Aylık değişim (%)"),
    (
        "Yıllık değişim (%)",
        "annual_inflation_pct",
        "Yıllık değişim (önceki yılın aynı ayına göre, %)",
    ),
)


def validated_comparison_years(
    comparison: InflationComparison,
) -> tuple[InflationYearEvidence, InflationYearEvidence]:
    """Check full years and nested evidence without changing/recalculating it.

    Also used by the HTML report, so invalid inputs cannot yield plausible
    looking charts, tables or comparison summaries.
    """
    if not isinstance(comparison, InflationComparison):
        raise InflationComparisonChartError("InflationComparison nesnesi gerekir.")
    if comparison.analysis_id != "cpi_two_year_comparison":
        raise InflationComparisonChartError("Karşılaştırma analiz kimliği geçersiz.")
    years = comparison.years
    if not isinstance(years, tuple) or len(years) != 2:
        raise InflationComparisonChartError("Tam olarak iki karşılaştırma yılı gerekir.")
    if any(not isinstance(item, InflationYearEvidence) for item in years):
        raise InflationComparisonChartError("Yıl kayıtları InflationYearEvidence olmalıdır.")
    if any(type(item.year) is not int or not 1 <= item.year <= 9999 for item in years):
        raise InflationComparisonChartError("Yıl geçerli bir tam sayı olmalıdır.")
    if years[0].year == years[1].year:
        raise InflationComparisonChartError("Karşılaştırma yılları farklı olmalıdır.")
    if not isinstance(comparison.source_ref, str) or not comparison.source_ref.strip():
        raise InflationComparisonChartError("Kaynak referansı boş olamaz.")

    for item in years:
        evidence = item.evidence
        try:
            observations = _validated_observations(evidence)
        except (InflationChartError, AttributeError, TypeError) as exc:
            raise InflationComparisonChartError(
                f"{item.year}: geçersiz aylık evidence: {exc}"
            ) from None
        expected = [f"{item.year:04d}-{month:02d}" for month in range(1, 13)]
        if len(observations) != 12 or [row.period for row in observations] != expected:
            raise InflationComparisonChartError(
                f"{item.year}: Ocak-Aralık için 12 eksiksiz ay gerekir."
            )
        if evidence.source_ref != comparison.source_ref:
            raise InflationComparisonChartError(
                f"{item.year}: kaynak referansları farklı olamaz."
            )

    difference = comparison.second_minus_first_december_annual_inflation_pp
    if difference is not None and (
        not isinstance(difference, Real)
        or isinstance(difference, bool)
        or not math.isfinite(float(difference))
    ):
        raise InflationComparisonChartError("Yıl farkı sonlu sayı veya null olmalıdır.")
    december_rates = [item.evidence.observations[-1].annual_inflation_pct for item in years]
    if any(rate is None for rate in december_rates) and difference is not None:
        raise InflationComparisonChartError("Eksik Aralık oranında yıl farkı null olmalıdır.")
    if all(rate is not None for rate in december_rates) and difference is None:
        raise InflationComparisonChartError("İki Aralık oranı varken yıl farkı eksik olamaz.")
    return years


def build_inflation_comparison_chart(
    comparison: InflationComparison,
) -> dict[str, Any]:
    """Return a JSON-safe Plotly spec with three panels and six traces.

    Input order determines trace/legend order, even when the second year is
    earlier. Values are copied unchanged from the existing typed evidence.
    A missing change remains ``None`` so Plotly leaves the corresponding gap.
    """
    years = validated_comparison_years(comparison)
    figure = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.1,
        subplot_titles=tuple(panel[0] for panel in _PANELS),
    )

    for panel_index, (_, field, hover_label) in enumerate(_PANELS, start=1):
        for year_index, item in enumerate(years):
            observations = item.evidence.observations
            figure.add_trace(
                go.Scatter(
                    x=list(range(1, 13)),
                    y=[getattr(row, field) for row in observations],
                    customdata=[row.period for row in observations],
                    mode="lines+markers",
                    name=str(item.year),
                    legendgroup=f"year-{item.year}",
                    showlegend=panel_index == 1,
                    line={"color": _COLORS[year_index]},
                    marker={"color": _COLORS[year_index]},
                    connectgaps=False,
                    hovertemplate=(
                        f"{item.year} — %{{customdata}}<br>"
                        f"{hover_label}: %{{y:.4f}}"
                        + ("%" if panel_index != 1 else "")
                        + "<extra></extra>"
                    ),
                ),
                row=panel_index, col=1,
            )

    figure.update_yaxes(title_text="TÜFE endeksi (2025=100)", row=1, col=1)
    figure.update_yaxes(title_text="Değişim (%)", row=2, col=1)
    figure.update_yaxes(title_text="Değişim (%)", row=3, col=1)
    figure.update_xaxes(
        tickmode="array", tickvals=list(range(1, 13)),
        ticktext=list(_MONTH_NAMES), row=3, col=1,
        title_text="Takvim ayı (Ocak–Aralık)",
    )
    figure.update_layout(
        title={
            "text": f"TÜFE Karşılaştırması: {years[0].year} → {years[1].year}",
            "x": 0.01, "xanchor": "left",
        },
        height=950,
        hovermode="x unified",
        dragmode="zoom",
        template="plotly_white",
        legend={"orientation": "h", "x": 0.5, "xanchor": "center", "y": -0.08},
        margin={"t": 120, "b": 120, "l": 75, "r": 30},
    )

    for panel_index, (_, field, _) in enumerate(_PANELS, start=1):
        if all(
            getattr(observation, field) is None
            for item in years for observation in item.evidence.observations
        ):
            figure.add_annotation(
                x=0.5, y=0.5,
                xref=f"x{panel_index if panel_index > 1 else ''} domain",
                yref=f"y{panel_index if panel_index > 1 else ''} domain",
                text="Önceki karşılaştırma dönemi bulunmadığı için değişim yok.",
                showarrow=False,
            )

    return json.loads(figure.to_json())

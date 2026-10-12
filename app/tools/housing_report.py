"""Offline HTML presentation of an existing housing-analysis run."""

from __future__ import annotations

import json
import math
from html import escape
from typing import Any, Literal

import pandas as pd
import plotly.io as pio

from app.services.housing_analysis import HousingAnalysisRun


class HousingReportError(ValueError):
    """Raised when the chart and evidence cannot be presented together."""


_SERIES = {
    "Nominal konut kredisi": "nominal_housing_loan_mn_try",
    "Reel konut kredisi (2025 fiyatları)": "real_housing_loan_2025_mn_try",
    "Konut kredisi faizi": "housing_loan_interest_rate_pct",
    "TÜFE (2025=100)": "cpi_index",
    "Konut Fiyat Endeksi (2023=100)": "housing_price_index",
}
_MARKER = "Koşula uyan ay"


def _validate_chart(run: HousingAnalysisRun) -> None:
    evidence = run.evidence
    periods = pd.period_range(evidence.period_start, evidence.period_end, freq="M")
    dates = [str(period) + "-01" for period in periods]
    matches = tuple(row.period for row in evidence.results)
    if (
        len(dates) != evidence.observed_month_count
        or matches != evidence.matched_periods
        or len(set(matches)) != len(matches)
        or len(matches) != evidence.matched_month_count
        or not set(matches).issubset(str(period) for period in periods[1:])
    ):
        raise HousingReportError("Evidence dönem bilgileri tutarsız.")
    traces = run.chart.get("data", [])
    if len(traces) != 6 or {t.get("name") for t in traces} != set(_SERIES) | {_MARKER}:
        raise HousingReportError("Grafikte beklenen altı seri bulunmalı.")
    for trace in traces:
        name = trace["name"]
        x, y = trace.get("x", []), trace.get("y", [])
        expected_x = [period + "-01" for period in matches] if name == _MARKER else dates
        if x != expected_x or len(y) != len(x):
            raise HousingReportError(f"{name}: grafik dönemleri evidence ile uyuşmuyor.")
        if any(type(value) not in (int, float) or not math.isfinite(value) for value in y):
            raise HousingReportError(f"{name}: grafik değerleri sonlu sayı olmalı.")
        values = dict(zip(x, y))
        field = "housing_loan_interest_rate_pct" if name == _MARKER else _SERIES[name]
        for row in evidence.results:
            if values[row.period + "-01"] != getattr(row, field):
                raise HousingReportError(f"{name}: grafik değeri evidence ile uyuşmuyor.")


def _items(values: tuple[str, ...]) -> str:
    return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>"


def _number(value: float) -> str:
    if not math.isfinite(value):
        raise HousingReportError("Tablodaki sayılar sonlu olmalı.")
    return f"{value:,.4f}".rstrip("0").rstrip(".").translate(str.maketrans(",.", ".,"))


def render_housing_report(
    run: HousingAnalysisRun,
    *,
    dataset_kind: Literal["synthetic", "local"],
    run_summary: dict[str, Any] | None = None,
) -> str:
    """Present service output without repeating the financial calculations."""
    if dataset_kind not in {"synthetic", "local"}:
        raise HousingReportError("dataset_kind synthetic veya local olmalı.")
    _validate_chart(run)
    evidence = run.evidence
    chart_html = pio.to_html(
        run.chart, full_html=False, include_plotlyjs=True, include_mathjax=False,
        div_id="housing-chart", config={"responsive": True, "displaylogo": False},
    )
    rows = []
    for row in evidence.results:
        values = (
            row.nominal_housing_loan_mn_try, row.real_housing_loan_2025_mn_try,
            row.housing_loan_interest_rate_pct, row.interest_rate_change_pp,
            row.real_housing_loan_change_pct,
        )
        rows.append("<tr><td>" + escape(row.period) + "</td>" + "".join(
            f"<td>{_number(value)}</td>" for value in values
        ) + f"<td>{row.weekly_observation_count}</td></tr>")
    if not rows:
        rows.append('<tr><td colspan="7">Koşula uyan ay bulunamadı.</td></tr>')
    label = (
        "SENTETİK DEMO — Bu değerler gerçek BDDK/EVDS verisi veya ekonomik bulgu değildir."
        if dataset_kind == "synthetic" else
        "YEREL VERİ — Bu rapor, girdinin gerçekliğini veya manifest bütünlüğünü doğrulamaz."
    )
    summary_html = ""
    if run_summary is not None:
        summary = escape(json.dumps(run_summary, ensure_ascii=False, indent=2, allow_nan=False))
        summary_html = f"<details><summary>Sağlanan çalıştırma özeti</summary><pre>{summary}</pre></details>"
    evidence_json = escape(evidence.model_dump_json(indent=2))
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Konut kredisi analiz raporu</title>
<style>
body{{margin:0;background:#eef2f6;color:#172033;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1160px;margin:auto;padding:28px 20px}}
h1,h2{{line-height:1.25}} h1{{font-size:30px}} h2{{font-size:22px}}
section{{background:white;border:1px solid #d8e1eb;border-radius:12px;padding:24px;margin:20px 0}}
.notice{{background:#fff0cd;border-left:5px solid #ad6600;padding:16px;border-radius:6px}}
.stats{{display:flex;flex-wrap:wrap;gap:18px;margin-top:20px}}
.stats div{{background:#e9f0f8;padding:12px 20px;border-radius:8px}}
.table-wrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:14px}}
th,td{{padding:10px;text-align:right;border-bottom:1px solid #d8e1eb}}
th:first-child,td:first-child{{text-align:left}} th{{background:#e9f0f8}}
li,pre{{overflow-wrap:anywhere}} pre{{white-space:pre-wrap;font-size:13px}}
summary{{cursor:pointer;font-weight:600;margin:14px 0}}
code{{overflow-wrap:anywhere}} .muted{{color:#526176}}
</style></head><body><main>
<h1>Konut kredisi analiz raporu</h1>
<p class="notice">{label}</p>
<p>Faiz düşerken reel konut kredisi stokunun artmadığı aylar.</p>
<div class="stats"><div>Dönem: <strong>{escape(evidence.period_start)} – {escape(evidence.period_end)}</strong></div>
<div>İncelenen ay: <strong>{evidence.observed_month_count}</strong></div>
<div>Koşula uyan ay: <strong>{evidence.matched_month_count}</strong></div></div>
<section><h2>Aylık seriler</h2>{chart_html}</section>
<section><h2>Koşula uyan aylar</h2>
<p><code>{escape(evidence.rule_expression)}</code></p>
<p class="muted">Tutarlar milyon TL; reel tutarlar 2025 fiyatlarıyla. Sayılar dört ondalığa yuvarlanır.</p>
<div class="table-wrap"><table><thead><tr><th>Ay</th><th>Nominal kredi</th><th>Reel kredi</th>
<th>Faiz (%)</th><th>Faiz değişimi (puan)</th><th>Reel değişim (%)</th><th>Haftalık gözlem</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
<section><h2>Kaynak referansları</h2><h3>BDDK</h3>{_items(evidence.bddk_source_refs)}
<h3>EVDS</h3>{_items(evidence.evds_source_refs)}
<p class="muted">Referanslar analiz çıktısından aktarılır; rapor yeni veri indirmez.</p></section>
<section><h2>Yöntem ve sınırlamalar</h2>
<p>Haftalık faiz aylık aritmetik ortalamayla birleştirilir. Reel kredi = nominal kredi × 100 / TÜFE.</p>
<p><strong>Bu bulgular nedensellik kanıtlamaz.</strong> İlk ayın önceki ay değişimleri null olduğundan ilk ay koşulu sağlayamaz.</p>
<details><summary>Evidence içindeki yöntem ve sınırlamalar</summary>
{_items(evidence.methodology)}{_items(evidence.limitations)}</details>
<h3>Veri kalitesi notları</h3>{_items(evidence.data_quality_notes)}</section>
<section><h2>İnceleme kaydı</h2><p>HTML içindeki grafik internet bağlantısı gerektirmez.</p>
<details><summary>Analiz evidence JSON</summary><pre>{evidence_json}</pre></details>{summary_html}</section>
</main></body></html>"""
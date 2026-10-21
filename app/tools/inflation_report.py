"""Standalone offline HTML presentation of CPI inflation evidence."""

from __future__ import annotations

import math
from html import escape
from typing import Any, Literal

import plotly.io as pio

from app.services.inflation_analysis import InflationEvidence
from app.tools.inflation_chart import build_inflation_chart

_PANELS = (
    ("TÜFE endeksi (2025=100)", "cpi_index"),
    ("Aylık değişim (%)", "monthly_inflation_pct"),
    ("Yıllık değişim (%)", "annual_inflation_pct"),
)


class InflationReportError(ValueError):
    """Raised when the chart and evidence cannot be presented together."""


def _all_null(evidence: InflationEvidence, field: str) -> bool:
    return all(getattr(row, field) is None for row in evidence.observations)


def validate_inflation_chart(
    chart: dict[str, Any], evidence: InflationEvidence
) -> None:
    """Require every chart series to copy the evidence values exactly."""
    if not isinstance(chart, dict):
        raise InflationReportError("Grafik bir JSON nesnesi olmalıdır.")
    traces = chart.get("data")
    if not isinstance(traces, list) or len(traces) != len(_PANELS):
        raise InflationReportError("Grafikte beklenen üç seri bulunmalıdır.")
    expected_x = [f"{row.period}-01" for row in evidence.observations]
    for trace, (name, field) in zip(traces, _PANELS):
        if not isinstance(trace, dict) or trace.get("name") != name:
            raise InflationReportError(f"{name}: grafik serisi bulunamadı.")
        x_values, y_values = trace.get("x"), trace.get("y")
        if x_values != expected_x or not isinstance(y_values, list):
            raise InflationReportError(f"{name}: grafik dönemleri evidence ile uyuşmuyor.")
        if len(y_values) != len(evidence.observations):
            raise InflationReportError(f"{name}: grafik uzunluğu evidence ile uyuşmuyor.")
        for row, value in zip(evidence.observations, y_values):
            expected = getattr(row, field)
            if value != expected:
                raise InflationReportError(
                    f"{name}: {row.period} grafik değeri evidence ile uyuşmuyor."
                )


def _items(values: tuple[str, ...]) -> str:
    return "<ul>" + "".join(f"<li>{escape(value)}</li>" for value in values) + "</ul>"


def _number(value: float | None) -> str:
    if value is None:
        return "—"
    if not math.isfinite(value):
        raise InflationReportError("Tablodaki sayılar sonlu olmalı.")
    return f"{value:,.4f}".rstrip("0").rstrip(".").translate(str.maketrans(",.", ".,"))


def _null_notes(evidence: InflationEvidence) -> str:
    notes = []
    if any(row.monthly_inflation_pct is None for row in evidence.observations):
        notes.append(
            "— aylık değişim: önceki takvim ayına ait gözlem yok. Değer sıfır kabul edilmez."
        )
    if _all_null(evidence, "annual_inflation_pct"):
        notes.append(
            "— yıllık değişim: önceki yılın aynı ayına ait gözlem yok. "
            "Yıllık oran 12 aylık ortalama veya yıllıklandırma değildir."
        )
    elif any(row.annual_inflation_pct is None for row in evidence.observations):
        notes.append(
            "— yıllık değişim: ilgili ay için önceki yılın aynı ayına ait gözlem yok. "
            "Yıllık oran 12 aylık ortalama veya yıllıklandırma değildir."
        )
    return "".join(f"<li>{note}</li>" for note in notes)


def render_inflation_report(
    evidence: InflationEvidence,
    *,
    dataset_kind: Literal["synthetic", "verified_local"],
) -> str:
    """Render the same evidence as chart, table, summary and provenance text."""
    if dataset_kind not in {"synthetic", "verified_local"}:
        raise InflationReportError("dataset_kind synthetic veya verified_local olmalı.")
    chart = build_inflation_chart(evidence)
    validate_inflation_chart(chart, evidence)
    chart_html = pio.to_html(
        chart,
        full_html=False,
        include_plotlyjs=True,
        include_mathjax=False,
        div_id="inflation-chart",
        config={"responsive": True, "displaylogo": False, "scrollZoom": True},
    )
    rows = []
    for row in evidence.observations:
        rows.append(
            "<tr><td>"
            + escape(row.period)
            + f"</td><td>{_number(row.cpi_index)}</td>"
            + f"<td>{_number(row.monthly_inflation_pct)}</td>"
            + f"<td>{_number(row.annual_inflation_pct)}</td></tr>"
        )
    label = (
        "SENTETİK DEMO — Bu değerler gerçek EVDS verisi veya ekonomik bulgu değildir."
        if dataset_kind == "synthetic"
        else (
            "YEREL DOĞRULANMIŞ EVDS PAKETİ — CLI manifest, raw, receipt ve Silver "
            "hash kontrollerini çalıştırdı. Bu HTML tek başına kaynak gerçekliğini kanıtlamaz."
        )
    )
    single_month = ""
    if evidence.observed_month_count == 1:
        single_month = (
            '<p class="notice">Tek ay seçildiği için ilk-son endeks değişimi tanım '
            "gereği %0'dır; bu, o ayın aylık enflasyonunun sıfır olduğu anlamına gelmez.</p>"
        )
    notes = _null_notes(evidence)
    null_section = (
        f"<h3>Eksik değerler</h3><ul>{notes}</ul>" if notes else
        "<p>Seçilen dönemde gösterilemeyen aylık veya yıllık değişim yok.</p>"
    )
    evidence_json = escape(evidence.model_dump_json(indent=2))
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TÜFE enflasyon raporu</title>
<style>
body{{margin:0;background:#eef2f6;color:#172033;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1160px;margin:auto;padding:28px 20px}}
h1,h2,h3{{line-height:1.25}} h1{{font-size:30px}} h2{{font-size:22px}} h3{{font-size:18px}}
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
@media (max-width:600px){{
main{{padding:16px 10px}} section{{padding:16px 12px;border-radius:10px}}
h1{{font-size:25px}} h2{{font-size:20px}} .stats{{gap:10px}}
.stats div{{padding:10px 14px}}
}}
</style></head><body><main>
<h1>TÜFE enflasyon raporu</h1>
<p class="notice">{escape(label)}</p>
<p>Seri <code>{escape(evidence.series_code)}</code>, baz yılı
<strong>{evidence.cpi_base_year}</strong> (2025=100). Kaynak:
<code>{escape(evidence.source_ref)}</code></p>
<div class="stats">
<div>Dönem: <strong>{escape(evidence.period_start)} – {escape(evidence.period_end)}</strong></div>
<div>Gözlenen ay: <strong>{evidence.observed_month_count}</strong></div>
<div>İlk TÜFE endeksi: <strong>{_number(evidence.first_cpi_index)}</strong></div>
<div>Son TÜFE endeksi: <strong>{_number(evidence.last_cpi_index)}</strong></div>
<div>İlk-son endeks değişimi: <strong>{_number(evidence.first_to_last_index_change_pct)}%</strong></div>
</div>
{single_month}
<p class="muted">İlk-son endeks değişimi yıllık enflasyon değildir; yalnızca seçilen
ilk ve son ayın endeks düzeyini karşılaştırır.</p>
<section><h2>TÜFE serisi</h2>{chart_html}
<p class="muted">Üç panel aynı ay eksenini kullanır: endeks düzeyi, aylık değişim ve
önceki yılın aynı ayına göre yıllık değişim. Null değerler boşluk olarak kalır.</p></section>
<section><h2>Aylık gözlemler</h2>
<p class="muted">Sayılar en fazla dört ondalıkla gösterilir; grafik ve evidence tam
hassasiyeti korur. Aylık değişim önceki takvim ayına, yıllık değişim önceki yılın
aynı ayına göredir.</p>
<div class="table-wrap"><table><thead><tr><th>Ay</th><th>TÜFE endeksi</th>
<th>Aylık değişim (%)</th><th>Yıllık değişim (%)</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>{null_section}</section>
<section><h2>Kaynak zinciri ve yöntem</h2>
<p><strong>Kaynak referansı:</strong> <code>{escape(evidence.source_ref)}</code></p>
<p class="muted">Referans analiz çıktısından aktarılır; rapor yeni veri indirmez.
Sentetik ve yerel doğrulanmış etiketleri birbirine karıştırılmaz.</p>
<h3>Evidence yöntemi</h3>{_items(evidence.methodology)}
<h3>Evidence sınırlamaları</h3>{_items(evidence.limitations)}</section>
<section><h2>İnceleme kaydı</h2>
<p>HTML içindeki Plotly.js gömülüdür; rapor CDN, sunucu veya model anahtarı
gerektirmeden internetsiz açılır.</p>
<details><summary>Analiz evidence JSON</summary><pre>{evidence_json}</pre></details></section>
</main></body></html>"""

"""Standalone offline HTML report for an existing two-year CPI comparison.

A presentation layer only: it never calculates an inflation rate, an index
change or a year-over-year percentage-point difference.
"""

from __future__ import annotations

import json
import math
from html import escape
from typing import Any, Literal

import plotly.io as pio

from app.services.inflation_comparison import InflationComparison
from app.tools.inflation_comparison_chart import (
    build_inflation_comparison_chart,
    validated_comparison_years,
)


class InflationComparisonReportError(ValueError):
    """Raised if the evidence or Plotly output is unfit for a trustworthy report."""


_SERIES = ("cpi_index", "monthly_inflation_pct", "annual_inflation_pct")


def _display_number(value: float | None) -> str:
    """Round only what the reader sees; never modify the underlying evidence."""
    if value is None:
        return "—"
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise InflationComparisonReportError("Gösterilecek değer sonlu sayı veya null olmalıdır.")
    return f"{value:,.4f}".rstrip("0").rstrip(".").translate(
        str.maketrans(",.", ".,")
    )


def _items(values: tuple[str, ...]) -> str:
    if not isinstance(values, tuple) or any(not isinstance(v, str) for v in values):
        raise InflationComparisonReportError("Açıklamalar metin dizisi olmalıdır.")
    return "<ul>" + "".join(f"<li>{escape(value, quote=True)}</li>" for value in values) + "</ul>"


def validate_inflation_comparison_chart(
    chart: dict[str, Any], comparison: InflationComparison,
) -> None:
    """Assert exact six-series equivalence to the two supplied year evidences."""
    years = validated_comparison_years(comparison)
    if not isinstance(chart, dict) or not isinstance(chart.get("data"), list):
        raise InflationComparisonReportError("Grafik bir Plotly JSON nesnesi olmalıdır.")
    traces = chart["data"]
    if len(traces) != 6:
        raise InflationComparisonReportError("Karşılaştırma grafiğinde altı seri gerekir.")
    for panel, field in enumerate(_SERIES):
        for position, item in enumerate(years):
            trace = traces[2 * panel + position]
            observations = item.evidence.observations
            if not isinstance(trace, dict) or trace.get("name") != str(item.year):
                raise InflationComparisonReportError("Grafikte yıl/seri sırası uyuşmuyor.")
            if trace.get("x") != list(range(1, 13)):
                raise InflationComparisonReportError("Grafikte 12 takvim ayı bulunmalıdır.")
            if trace.get("customdata") != [r.period for r in observations]:
                raise InflationComparisonReportError("Grafik dönemleri evidence ile uyuşmuyor.")
            if trace.get("y") != [getattr(r, field) for r in observations]:
                raise InflationComparisonReportError("Grafik değerleri evidence ile uyuşmuyor.")
            if trace.get("connectgaps") is not False:
                raise InflationComparisonReportError("Eksik gözlemler grafikte birleştirilemez.")
    try:
        json.dumps(chart, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InflationComparisonReportError("Grafik JSON olarak güvenli değil.") from exc


def _month_rows(item: Any) -> str:
    rows = []
    for observation in item.evidence.observations:
        rows.append(
            f'<tr data-period="{escape(observation.period, quote=True)}">'
            f'<td>{escape(observation.period)}</td>'
            f'<td>{_display_number(observation.cpi_index)}</td>'
            f'<td>{_display_number(observation.monthly_inflation_pct)}</td>'
            f'<td>{_display_number(observation.annual_inflation_pct)}</td></tr>'
        )
    return "".join(rows)


def _year_block(item: Any, position: int) -> str:
    evidence = item.evidence
    december_rate = evidence.observations[-1].annual_inflation_pct
    return f"""
<section aria-labelledby="year-{position}-heading" class="year-block year-{position}">
<h2 id="year-{position}-heading">{item.year} yılı — Ocak–Aralık</h2>
<div class="stats">
<div><span>Ocak–Aralık ilk-son TÜFE endeksi değişimi</span>
<strong>{_display_number(evidence.first_to_last_index_change_pct)}%</strong></div>
<div><span>Aralık yıllık enflasyonu (geçen yılın Aralık ayına göre)</span>
<strong>{_display_number(december_rate)}{'' if december_rate is None else '%'}</strong></div>
</div>
<p class="muted">İlk-son endeks değişimi Aralık yıllık enflasyonu değildir.
Gösterim dört ondalıkla sınırlıdır; evidence sayıları değiştirilmez.</p>
<div class="table-wrap"><table><caption>{item.year} TÜFE aylık gözlemleri (12 ay)</caption>
<thead><tr><th>Dönem</th><th>TÜFE endeksi (2025=100)</th>
<th>Aylık değişim (%)</th><th>Yıllık değişim (%)</th></tr></thead>
<tbody>{_month_rows(item)}</tbody></table></div>
<h3>{item.year} evidence yöntemi</h3>{_items(evidence.methodology)}
<h3>{item.year} evidence sınırlamaları</h3>{_items(evidence.limitations)}
</section>"""


def render_inflation_comparison_report(
    comparison: InflationComparison,
    *,
    dataset_kind: Literal["synthetic", "verified_local"],
    title: str = "İki Tam Yıl TÜFE Karşılaştırması",
) -> str:
    """Render one self-contained HTML from an already calculated comparison.

    ``dataset_kind`` states the origin as supplied by the caller. This renderer
    does not check manifests, physical paths, hashes or remote data sources.
    """
    if dataset_kind not in ("synthetic", "verified_local"):
        raise InflationComparisonReportError("dataset_kind synthetic veya verified_local olmalı.")
    if not isinstance(title, str):
        raise InflationComparisonReportError("Rapor başlığı metin olmalıdır.")
    years = validated_comparison_years(comparison)
    chart = build_inflation_comparison_chart(comparison)
    validate_inflation_comparison_chart(chart, comparison)
    chart_html = pio.to_html(
        chart,
        full_html=False,
        include_plotlyjs=True,
        include_mathjax=False,
        div_id="inflation-comparison-chart",
        config={"responsive": True, "displaylogo": False, "scrollZoom": True},
    )

    difference = comparison.second_minus_first_december_annual_inflation_pp
    diff_text = _display_number(difference)
    if difference is not None:
        diff_text += " yüzde puan"
    label = (
        "SENTETİK DEMO — Bu rapordaki değerler gerçek EVDS verisi veya ekonomik bulgu değildir."
        if dataset_kind == "synthetic"
        else "HARİCEN DOĞRULANDIĞI BELİRTİLEN VERİ — Raporun oluşturulması "
        "manifest, ham veri ya da dosya hash kontrolü yapmaz."
    )
    null_note = (
        "— işareti önceki ayın veya önceki yılın karşılık gelen ayının "
        "verisi olmadığı için hesaplanamayan oranı gösterir; sıfır veya "
        "tahmin değildir. Aralık yıllık oranı yoksa yüzde puan farkı da — kalır."
    )
    evidence_json = escape(comparison.model_dump_json(indent=2), quote=True)
    escaped_title = escape(title, quote=True)

    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escaped_title}</title>
<style>
:root{{color-scheme:light;--ink:#172033;--muted:#526176;--line:#d8e1eb;--blue:#2563eb;--orange:#d97706}}
*{{box-sizing:border-box}}
body{{margin:0;background:#eef2f6;color:var(--ink);font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1160px;margin:auto;padding:28px 20px}}
h1,h2,h3{{line-height:1.25}}h1{{font-size:30px}}h2{{font-size:22px}}h3{{font-size:18px}}
section{{background:white;border:1px solid var(--line);border-radius:12px;padding:24px;margin:20px 0}}
.notice{{background:#fff0cd;border-left:5px solid #ad6600;padding:16px;border-radius:6px}}
.muted{{color:var(--muted)}}.years{{font-weight:700;font-size:20px;margin:14px 0}}
.stats{{display:flex;flex-wrap:wrap;gap:14px;margin:20px 0}}
.stats>div{{flex:1 1 245px;background:#e9f0f8;border-radius:8px;padding:12px 18px}}
.stats span{{display:block;font-size:14px}}.stats strong{{display:block;font-size:20px}}
.year-0{{border-top:5px solid var(--blue)}}.year-1{{border-top:5px solid var(--orange)}}
.table-wrap{{overflow-x:auto;max-width:100%}}table{{border-collapse:collapse;width:100%;min-width:620px;font-size:14px}}
caption{{text-align:left;font-weight:600;padding:8px 0}}th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:right}}
th:first-child,td:first-child{{text-align:left;white-space:nowrap}}th{{background:#e9f0f8}}
li,pre,code{{overflow-wrap:anywhere}}pre{{white-space:pre-wrap;font-size:13px}}
summary{{cursor:pointer;font-weight:600;margin:14px 0}}
@media(max-width:600px){{main{{padding:16px 10px}}section{{padding:16px 12px;border-radius:10px}}h1{{font-size:25px}}h2{{font-size:20px}}.stats strong{{font-size:18px}}}}
</style></head><body><main>
<h1>{escaped_title}</h1>
<p class="notice">{escape(label)}</p>
<p class="years">İstenen sıra: {years[0].year} → {years[1].year}</p>
<p>Seri: <code>{escape(years[0].evidence.series_code, quote=True)}</code>;
baz yılı <strong>{years[0].evidence.cpi_base_year}</strong> (2025=100).</p>
<div class="stats"><div><span>İlk yıl</span><strong>{years[0].year}</strong></div>
<div><span>İkinci yıl</span><strong>{years[1].year}</strong></div>
<div><span>İkinci yılın Aralık yıllık enflasyonu − ilk yılın Aralık yıllık enflasyonu</span>
<strong>{diff_text}</strong></div></div>
<p class="muted">Yıl farkının birimi yüzde puandır, yüzde değil.
İki yılın sırası kronolojik olarak yeniden düzenlenmez.</p>
<section><h2>Üç panelde iki yıl</h2>{chart_html}
<p class="muted">Her panelde iki yılın 12 ayı aynı Ocak–Aralık eksenindedir.
Hover gerçek YYYY-MM dönemini ve yılı gösterir. Eksik oranlarda çizgi boş kalır.</p></section>
{_year_block(years[0], 0)}
{_year_block(years[1], 1)}
<section><h2>Kaynaklar, yöntem ve sınırlamalar</h2>
<p><strong>Kaynak referansı (karşılaştırma):</strong>
<code>{escape(comparison.source_ref, quote=True)}</code></p>
<p><strong>İlk yıl kaynak referansı:</strong>
<code>{escape(years[0].evidence.source_ref, quote=True)}</code></p>
<p><strong>İkinci yıl kaynak referansı:</strong>
<code>{escape(years[1].evidence.source_ref, quote=True)}</code></p>
<p class="muted">Kaynak bilgisi mevcut evidence'dan aktarılır.
Bu renderer veri indirmez ve fiziksel dosya/manifest/hash zincirini doğrulamaz.</p>
<h3>Karşılaştırma yöntemi</h3>{_items(comparison.methodology)}
<h3>Karşılaştırma sınırlamaları</h3>{_items(comparison.limitations)}
<h3>Eksik veri açıklaması</h3><p>{escape(null_note)}</p></section>
<section><h2>Evidence inceleme kaydı</h2>
<p>Plotly.js bu HTML içine gömülüdür. Açmak için CDN, ağ, veri sunucusu
veya LLM anahtarı gerekmez. Rapor yalnız sunum katmanıdır.</p>
<details><summary>Karşılaştırma evidence JSON</summary><pre>{evidence_json}</pre></details></section>
</main></body></html>"""

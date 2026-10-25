"""Offline report checks for the two-year CPI evidence presentation."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from html import escape
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import pytest

from app.services.inflation_comparison import compare_inflation_years
from app.tools.inflation_comparison_chart import build_inflation_comparison_chart
from app.tools.inflation_comparison_report import (
    InflationComparisonReportError,
    render_inflation_comparison_report,
    validate_inflation_comparison_chart,
)


class _Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.external_resources: list[str] = []
        self.tables = 0
        self.month_rows: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"script", "iframe", "img"} and "src" in values:
            self.external_resources.append(values["src"])
        if tag == "link" and "href" in values:
            self.external_resources.append(values["href"])
        if tag == "table":
            self.tables += 1
        if tag == "tr" and "data-period" in values:
            self.month_rows.append(values["data-period"])


def _comparison(first: int = 2023, second: int = 2024):
    fixture = Path("docs/economic-question-comparison-example.json")
    data = json.loads(fixture.read_text(encoding="utf-8"))["inflation"]
    frame = pd.DataFrame(data["cpi_monthly"])
    return compare_inflation_years(
        frame, first_year=first, second_year=second,
        source_ref=data["source_ref"],
    )


def _extract_plotly_chart(html: str) -> dict:
    marker = html.index("Plotly.newPlot(")
    start = html.index('"inflation-comparison-chart",', marker) + len(
        '"inflation-comparison-chart",'
    )
    while html[start].isspace():
        start += 1
    decoder = json.JSONDecoder()
    data, end = decoder.raw_decode(html, start)
    layout_start = html.index(",", end) + 1
    while html[layout_start].isspace():
        layout_start += 1
    layout, _ = decoder.raw_decode(html, layout_start)
    return {"data": data, "layout": layout}


def test_offline_html_contains_two_years_24_rows_and_embedded_plotly():
    comparison = _comparison()
    original = deepcopy(comparison.model_dump())
    html = render_inflation_comparison_report(
        comparison, dataset_kind="synthetic"
    )
    parser = _Assets()
    parser.feed(html)

    assert html.startswith("<!doctype html>")
    assert 'lang="tr"' in html
    assert "SENTETİK DEMO" in html
    assert "gerçek EVDS verisi" in html
    assert "İstenen sıra: 2023 → 2024" in html
    assert parser.external_resources == []
    assert parser.tables == 2
    assert parser.month_rows == (
        [f"2023-{i:02d}" for i in range(1, 13)] +
        [f"2024-{i:02d}" for i in range(1, 13)]
    )
    assert "Plotly.newPlot" in html
    assert "plotly.js" in html.lower()
    assert "@media(max-width:600px)" in html
    assert "overflow-x:auto" in html
    assert "Kaynak referansı" in html
    assert "Karşılaştırma yöntemi" in html
    assert "Karşılaştırma sınırlamaları" in html
    assert "Eksik veri açıklaması" in html
    assert "12 aylık ortalama" in html
    assert comparison.model_dump() == original

    chart = _extract_plotly_chart(html)
    validate_inflation_comparison_chart(chart, comparison)
    assert len(chart["data"]) == 6
    assert chart == build_inflation_comparison_chart(comparison)


def test_numeric_summary_reads_existing_evidence_and_pp_not_percent():
    comparison = _comparison()
    html = render_inflation_comparison_report(comparison, dataset_kind="synthetic")
    assert "17,6471%" in html  # 2023 Jan-Dec = (120 / 102 - 1) * 100
    assert "21,9512%" in html  # 2024 Jan-Dec = (150 / 123 - 1) * 100
    assert ">20%<" in html  # December annual 2023 = 120 / 100 - 1
    assert ">25%<" in html  # December annual 2024 = 150 / 120 - 1
    assert ">5 yüzde puan<" in html  # 25 - 20 = 5 percentage points
    assert "İlk-son endeks değişimi Aralık yıllık enflasyonu değildir" in html
    assert "Yıl farkının birimi yüzde puandır" in html


def test_reverse_order_keeps_years_and_negative_difference():
    comparison = _comparison(2024, 2023)
    html = render_inflation_comparison_report(comparison, dataset_kind="synthetic")
    assert "İstenen sıra: 2024 → 2023" in html
    assert ">-5 yüzde puan<" in html
    chart = _extract_plotly_chart(html)
    assert [t["name"] for t in chart["data"][:2]] == ["2024", "2023"]
    assert [m for m in _Assets_rows(html)][:12] == [
        f"2024-{month:02d}" for month in range(1, 13)
    ]


def _Assets_rows(html: str) -> list[str]:
    parser = _Assets()
    parser.feed(html)
    return parser.month_rows


def test_null_annual_rate_difference_remain_missing_in_html_and_chart():
    comparison = _comparison()
    first, second = comparison.years
    rows = tuple(
        row.model_copy(update={"annual_inflation_pct": None})
        for row in first.evidence.observations
    )
    first = first.model_copy(update={
        "evidence": first.evidence.model_copy(update={"observations": rows})
    })
    comparison = comparison.model_copy(update={
        "years": (first, second),
        "second_minus_first_december_annual_inflation_pp": None,
    })

    html = render_inflation_comparison_report(comparison, dataset_kind="synthetic")
    chart = _extract_plotly_chart(html)
    assert chart["data"][4]["y"] == [None] * 12
    assert chart["data"][4]["connectgaps"] is False
    assert "— işareti" in html
    assert "yüzde puan" in html
    assert ">—</strong>" in html
    json.dumps(chart, allow_nan=False)


def test_bad_period_incomplete_rows_and_nonfinite_inputs_cannot_render():
    original = _comparison()
    year = original.years[0]
    rows = year.evidence.observations
    faulty_evidences = [
        year.evidence.model_copy(update={"observations": rows[:8] + rows[9:], "observed_month_count": 11}),
        year.evidence.model_copy(update={"observations": (
            rows[0].model_copy(update={"period": "2023-15"}),
        ) + rows[1:]}),
        year.evidence.model_copy(update={"observations": (
            rows[0].model_copy(update={"cpi_index": float("inf")}),
        ) + rows[1:]}),
    ]
    for evidence in faulty_evidences:
        first = year.model_copy(update={"evidence": evidence})
        comparison = original.model_copy(update={"years": (first, original.years[1])})
        with pytest.raises(ValueError):
            render_inflation_comparison_report(comparison, dataset_kind="synthetic")


def test_escaped_sources_methodology_limitations_and_title():
    comparison = _comparison()
    injected = '<img src=x onerror=alert("x")>'
    comparison = comparison.model_copy(update={
        "source_ref": injected,
        "methodology": (injected,),
        "limitations": ('</script><script>alert(1)</script>',),
        "years": tuple(
            item.model_copy(update={
                "evidence": item.evidence.model_copy(update={
                    "source_ref": injected,
                    "methodology": (injected,),
                    "limitations": (injected,),
                })
            }) for item in comparison.years
        ),
    })
    html = render_inflation_comparison_report(
        comparison, dataset_kind="verified_local", title=injected,
    )
    assert escape(injected) in html
    assert "<img src=x onerror" not in html
    assert "</script><script>alert(1)</script>" not in html
    assert "&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "SENTETİK DEMO" not in html
    assert "manifest" in html
    parser = _Assets()
    parser.feed(html)
    assert parser.external_resources == []
    assert "</script><script>" not in html


def test_refuses_bad_dataset_kind_and_untrusted_chart(monkeypatch):
    comparison = _comparison()
    with pytest.raises(InflationComparisonReportError):
        render_inflation_comparison_report(comparison, dataset_kind="unknown")
    with pytest.raises(InflationComparisonReportError):
        render_inflation_comparison_report(comparison, dataset_kind="synthetic", title=3)

    import app.tools.inflation_comparison_report as module
    real = module.build_inflation_comparison_chart
    for edit in ("values", "period", "gaps", "nan", "count"):
        def tampered(source, edit=edit):
            spec = real(source)
            if edit == "values":
                spec["data"][0]["y"][0] += 1
            elif edit == "period":
                spec["data"][1]["customdata"][0] = "2020-01"
            elif edit == "gaps":
                spec["data"][2]["connectgaps"] = True
            elif edit == "nan":
                spec["layout"]["bogus"] = float("nan")
            else:
                spec["data"].pop()
            return spec
        monkeypatch.setattr(module, "build_inflation_comparison_chart", tampered)
        with pytest.raises(InflationComparisonReportError):
            render_inflation_comparison_report(comparison, dataset_kind="synthetic")

"""Verify offline presentation, evidence consistency and safe text rendering."""

from copy import deepcopy
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.tools.housing_report import HousingReportError, render_housing_report
from scripts.render_housing_sample import build_sample_run, main


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.external_resources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "img", "iframe"} and "src" in attrs:
            self.external_resources.append(attrs["src"])
        if tag == "link" and "href" in attrs:
            self.external_resources.append(attrs["href"])


def test_sample_cli_is_offline_and_needs_no_keys(monkeypatch, tmp_path):
    import socket
    from app.connectors import mia_client

    def forbidden(*args, **kwargs):
        raise AssertionError("Network or model call is forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(mia_client, "ask_mia", forbidden)
    monkeypatch.delenv("MIA_API_KEY", raising=False)
    output = tmp_path / "report.html"
    assert main(["--output", str(output)]) == 0
    html = output.read_text(encoding="utf-8")
    page = _Page()
    page.feed(html)
    assert page.external_resources == []
    assert "Plotly.newPlot" in html
    assert "SENTETİK DEMO" in html
    assert "nedensellik kanıtlamaz" in html
    assert "İlk ayın önceki ay değişimleri null" in html
    assert "<td>2021-01</td>" not in html


def test_report_displays_service_values_and_summary_without_mutating_run():
    run = build_sample_run()
    before = deepcopy(run.chart)
    html = render_housing_report(run, dataset_kind="synthetic", run_summary={"commit": "example"})
    assert run.evidence.observed_month_count == 60
    assert "<td>2021-02</td><td>1.008</td>" in html
    assert "<td>19,75</td>" in html
    assert "synthetic://housing/bddk" in html
    assert "example" in html
    assert run.chart == before


def test_untrusted_source_quality_and_summary_text_is_escaped():
    payload = '<script>alert("unsafe")</script>'
    run = build_sample_run()
    evidence = run.evidence.model_copy(update={
        "bddk_source_refs": (payload,), "data_quality_notes": (payload,),
    })
    html = render_housing_report(
        replace(run, evidence=evidence), dataset_kind="local", run_summary={"path": payload},
    )
    assert payload not in html
    assert "&lt;script&gt;" in html
    assert "YEREL VERİ" in html


@pytest.mark.parametrize("fault", ["period", "value", "length", "non_finite", "missing_trace"])
def test_report_rejects_chart_inconsistent_with_evidence(fault):
    run = build_sample_run()
    chart = deepcopy(run.chart)
    if fault == "period":
        chart["data"][0]["x"][0] = "2020-12-01"
    elif fault == "value":
        chart["data"][2]["y"][1] = 999.0
    elif fault == "length":
        chart["data"][3]["y"].pop()
    elif fault == "non_finite":
        chart["data"][0]["y"][0] = float("nan")
    else:
        chart["data"].pop()
    with pytest.raises(HousingReportError):
        render_housing_report(replace(run, chart=chart), dataset_kind="synthetic")


@pytest.mark.parametrize("month_count", [1, 3])
def test_report_handles_no_matches_and_single_month(month_count):
    import pandas as pd
    from app.services.housing_analysis import run_housing_analysis

    periods = ["2021-01", "2021-02", "2021-03"][:month_count]
    run = run_housing_analysis(
        pd.DataFrame({"period": periods, "nominal_housing_loan_mn_try": [100, 200, 300][:month_count]}),
        pd.DataFrame({
            "period": periods,
            "housing_loan_interest_rate_pct": [20, 19, 18][:month_count],
            "weekly_observation_count": [4] * month_count,
            "cpi_index": [100, 110, 120][:month_count],
            "housing_price_index": [100, 101, 102][:month_count],
        }),
        start_period=periods[0], end_period=periods[-1],
        bddk_source_ref="synthetic://test", evds_source_refs="synthetic://test", narrator=None,
    )
    assert run.evidence.matched_month_count == 0
    html = render_housing_report(run, dataset_kind="synthetic")
    assert "Koşula uyan ay bulunamadı." in html


def test_failed_file_replacement_preserves_previous_report(monkeypatch, tmp_path):
    output = tmp_path / "report.html"
    output.write_text("previous report", encoding="utf-8")

    def fail_replace(self, target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    assert main(["--output", str(output)]) == 1
    assert output.read_text(encoding="utf-8") == "previous report"
    assert list(tmp_path.iterdir()) == [output]
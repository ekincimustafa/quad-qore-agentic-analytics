"""Verify the standalone CPI report, safe rendering and verified CLI inputs."""

from __future__ import annotations

import hashlib
import json
import re
import socket
from copy import deepcopy
from html import escape
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd
import pytest

from app.services.inflation_analysis import InflationEvidence, build_inflation_evidence
from app.tools.inflation_chart import build_inflation_chart
from app.tools.inflation_report import (
    InflationReportError,
    render_inflation_report,
    validate_inflation_chart,
)
from scripts.render_inflation_report import build_synthetic_evidence, main


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.external_resources: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "img", "iframe"} and "src" in attrs:
            self.external_resources.append(attrs["src"])
        if tag == "link" and "href" in attrs:
            self.external_resources.append(attrs["href"])


def _chart_from_html(html: str) -> dict:
    marker = html.index("Plotly.newPlot(")
    start = html.index('"inflation-chart",', marker) + len('"inflation-chart",')
    while html[start].isspace():
        start += 1
    decoder = json.JSONDecoder()
    data, end = decoder.raw_decode(html, start)
    layout_start = html.index(",", end) + 1
    while html[layout_start].isspace():
        layout_start += 1
    layout, _ = decoder.raw_decode(html, layout_start)
    return {"data": data, "layout": layout}


def _tr_number(value: float) -> str:
    return f"{value:,.4f}".rstrip("0").rstrip(".").translate(str.maketrans(",.", ".,"))


def _table_rows(html: str) -> list[tuple[str, str, str, str]]:
    return re.findall(
        r"<tr><td>(\d{4}-\d{2})</td><td>([^<]*)</td><td>([^<]*)</td><td>([^<]*)</td></tr>",
        html,
    )


def _evidence(history_start: str = "2021-01", end: str = "2023-12") -> InflationEvidence:
    periods = pd.period_range(history_start, end, freq="M").astype(str).tolist()
    return build_inflation_evidence(
        pd.DataFrame(
            {"period": periods, "cpi_index": [40.0 + index * 1.25 for index in range(len(periods))]}
        ),
        start_period="2023-01",
        end_period=end,
        source_ref="synthetic://inflation/report",
    )


def _write_verified_package(tmp_path: Path) -> tuple[Path, Path]:
    periods = pd.period_range("2021-01", "2023-12", freq="M").astype(str).tolist()
    csv_path = tmp_path / "data/silver/evds/monthly/cpi.csv"
    csv_path.parent.mkdir(parents=True)
    frame = pd.DataFrame({
        "period": periods,
        "housing_loan_interest_rate_pct": [20.0] * len(periods),
        "weekly_observation_count": [4] * len(periods),
        "cpi_index": [40.0 + index * 1.25 for index in range(len(periods))],
        "housing_price_index": [100.0 + index for index in range(len(periods))],
    })
    frame.to_csv(csv_path, index=False)

    def bronze(series_code: str, frequency: str, name: str) -> dict:
        raw_path = tmp_path / "data/bronze/evds" / name / "raw.json"
        raw_path.parent.mkdir(parents=True)
        raw_bytes = json.dumps({"series_code": series_code}).encode("utf-8")
        raw_path.write_bytes(raw_bytes)
        receipt_path = tmp_path / "data/bronze/evds" / name / "receipts/receipt.json"
        receipt_path.parent.mkdir(parents=True)
        ref = f"data/bronze/evds/{name}/raw.json"
        receipt = {
            "series_code": series_code,
            "frequency": frequency,
            "request_start": "2021-01-01",
            "request_end": "2023-12-31",
            "downloaded_at": "2026-10-18T10:00:00+03:00",
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "size_bytes": len(raw_bytes),
            "raw_path": ref,
        }
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return {
            "receipt_path": f"data/bronze/evds/{name}/receipts/receipt.json",
            "raw_path": ref,
            "sha256": receipt["sha256"],
            "size_bytes": receipt["size_bytes"],
            "downloaded_at": receipt["downloaded_at"],
            "request_start": receipt["request_start"],
            "request_end": receipt["request_end"],
        }

    manifest = {
        "schema_version": "1.0",
        "dataset": "evds_monthly_silver",
        "silver": {
            "path": "data/silver/evds/monthly/cpi.csv",
            "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            "size_bytes": len(csv_path.read_bytes()),
            "row_count": len(periods),
            "start_period": "2021-01",
            "end_period": "2023-12",
            "columns": list(frame.columns),
        },
        "series": [
            {
                "series_code": "TP.KTF12",
                "silver_columns": ["housing_loan_interest_rate_pct", "weekly_observation_count"],
                "unit": "percent",
                "native_frequency": "weekly",
                "target_frequency": "monthly",
                "base_year": None,
                "base_year_source": "not_applicable",
                "transformation": "mean",
                "bronze": [bronze("TP.KTF12", "weekly", "tp_ktf12")],
                "weekly_coverage": {
                    "overall_status": "unverified",
                    "calendar_verification": "not_available",
                    "months": [
                        {
                            "period": period,
                            "status": "unverified",
                            "observed_count": 4,
                            "expected_count": None,
                            "observed_dates": [
                                f"{period}-{day}" for day in ("01", "08", "15", "22")
                            ],
                            "quality_note": "No verified source publication calendar.",
                        }
                        for period in periods
                    ],
                },
            },
            {
                "series_code": "TP.TUKFIY2025.GENEL",
                "silver_columns": ["cpi_index"],
                "unit": "index",
                "native_frequency": "monthly",
                "target_frequency": "monthly",
                "base_year": 2025,
                "base_year_source": "tcmb",
                "transformation": "level",
                "bronze": [bronze("TP.TUKFIY2025.GENEL", "monthly", "tp_tukfiy2025_genel")],
            },
            {
                "series_code": "TP.KFE.TR",
                "silver_columns": ["housing_price_index"],
                "unit": "index",
                "native_frequency": "monthly",
                "target_frequency": "monthly",
                "base_year": 2023,
                "base_year_source": "tcmb",
                "transformation": "level",
                "bronze": [bronze("TP.KFE.TR", "monthly", "tp_kfe_tr")],
            },
        ],
    }
    manifest_path = tmp_path / "data/silver/evds/monthly/manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return csv_path, manifest_path


def test_synthetic_cli_is_offline_and_chart_matches_table_and_evidence(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network or model call is forbidden")

    monkeypatch.setattr(socket, "socket", forbidden)
    output = tmp_path / "synthetic.html"
    assert main(["--output", str(output)]) == 0
    html = output.read_text(encoding="utf-8")

    page = _Page()
    page.feed(html)
    assert page.external_resources == []
    assert "Plotly.newPlot" in html
    assert "SENTETİK DEMO" in html
    assert "YEREL DOĞRULANMIŞ" not in html
    assert "İlk-son endeks değişimi yıllık enflasyon değildir" in html

    evidence = build_synthetic_evidence()
    chart = _chart_from_html(html)
    validate_inflation_chart(chart, evidence)
    assert [trace["name"] for trace in chart["data"]] == [
        "TÜFE endeksi (2025=100)",
        "Aylık değişim (%)",
        "Yıllık değişim (%)",
    ]

    rows = _table_rows(html)
    assert len(rows) == evidence.observed_month_count == 12
    for (period, index, monthly, annual), row in zip(rows, evidence.observations):
        assert period == row.period
        assert index == _tr_number(row.cpi_index)
        assert monthly == _tr_number(row.monthly_inflation_pct)
        assert annual == _tr_number(row.annual_inflation_pct)
    assert _tr_number(evidence.first_to_last_index_change_pct) in html


def test_report_shows_null_gaps_and_separates_first_last_from_annual():
    single_history = _evidence(history_start="2023-01", end="2023-03")
    html = render_inflation_report(single_history, dataset_kind="synthetic")
    rows = _table_rows(html)
    assert rows[0][2] == "—"
    assert rows[0][3] == "—"
    assert "— aylık değişim: önceki takvim ayına ait gözlem yok." in html
    assert "Yıllık oran 12 aylık ortalama veya yıllıklandırma değildir." in html
    assert "İlk-son endeks değişimi" in html

    single = _evidence(history_start="2022-12", end="2023-01")
    single_html = render_inflation_report(single, dataset_kind="synthetic")
    assert single.observations[0].monthly_inflation_pct is not None
    assert single.observations[0].annual_inflation_pct is None
    assert "Tek ay seçildiği için ilk-son endeks değişimi" in single_html
    assert "aylık enflasyonunun sıfır olduğu anlamına gelmez" in single_html
    assert _table_rows(single_html)[0][2] != "—"


def test_dynamic_evidence_text_is_escaped_and_never_script():
    payload = '<script>alert("unsafe")</script>'
    evidence = _evidence().model_copy(update={
        "source_ref": payload,
        "methodology": (payload,),
        "limitations": (payload,),
    })
    html = render_inflation_report(evidence, dataset_kind="verified_local")
    assert payload not in html
    assert escape(payload) in html
    assert "YEREL DOĞRULANMIŞ EVDS PAKETİ" in html
    assert "Bu HTML tek başına kaynak gerçekliğini kanıtlamaz." in html


@pytest.mark.parametrize("fault", ["period", "value", "length", "name", "missing"])
def test_report_rejects_chart_that_differs_from_evidence(fault):
    evidence = _evidence()
    chart = deepcopy(build_inflation_chart(evidence))
    if fault == "period":
        chart["data"][0]["x"][0] = "2022-12-01"
    elif fault == "value":
        chart["data"][2]["y"][-1] = 999.0
    elif fault == "length":
        chart["data"][1]["y"].pop()
    elif fault == "name":
        chart["data"][2]["name"] = "Başka seri"
    else:
        chart["data"].pop()
    with pytest.raises(InflationReportError):
        validate_inflation_chart(chart, evidence)


def test_verified_cli_reads_manifest_bound_csv_without_bddk(tmp_path, monkeypatch):
    csv_path, manifest_path = _write_verified_package(tmp_path)
    output = tmp_path / "out/report.html"
    assert not (tmp_path / "data/silver/bddk").exists()
    before = {path: path.read_bytes() for path in (csv_path, manifest_path)}
    assert main([
        "--root", str(tmp_path),
        "--manifest", str(manifest_path),
        "--start-period", "2023-01",
        "--end-period", "2023-12",
        "--output", str(output),
    ]) == 0
    html = output.read_text(encoding="utf-8")
    assert "YEREL DOĞRULANMIŞ EVDS PAKETİ" in html
    assert "SENTETİK DEMO" not in html
    assert "data/bronze/evds/tp_tukfiy2025_genel/receipts/receipt.json" in html
    assert len(_table_rows(html)) == 12
    assert "2023-12" in html
    assert "12 aylık ortalama" in html
    assert all(path.read_bytes() == content for path, content in before.items())

    evidence = build_inflation_evidence(
        pd.read_csv(csv_path)[["period", "cpi_index"]],
        start_period="2023-01", end_period="2023-12",
        source_ref="data/bronze/evds/tp_tukfiy2025_genel/receipts/receipt.json",
    )
    validate_inflation_chart(_chart_from_html(html), evidence)


def test_verified_cli_rejects_csv_changed_after_manifest_validation(tmp_path, monkeypatch):
    import scripts.render_inflation_report as cli

    csv_path, manifest_path = _write_verified_package(tmp_path)
    original = csv_path.read_bytes()
    real_validate = cli.load_and_validate_manifest

    def change_after_validation(path, root):
        manifest = real_validate(path, root)
        csv_path.write_bytes(original + b"\n")
        return manifest

    monkeypatch.setattr(cli, "load_and_validate_manifest", change_after_validation)
    output = tmp_path / "out/report.html"
    assert main([
        "--root", str(tmp_path),
        "--manifest", str(manifest_path),
        "--output", str(output),
    ]) == 1
    assert not output.exists()
    assert csv_path.read_bytes() == original + b"\n"


@pytest.mark.parametrize("target", ["manifest", "silver", "inside_data"])
def test_cli_rejects_output_targets_that_overlap_inputs(tmp_path, target):
    csv_path, manifest_path = _write_verified_package(tmp_path)
    csv_before = csv_path.read_bytes()
    manifest_before = manifest_path.read_bytes()
    output = {
        "manifest": manifest_path,
        "silver": csv_path,
        "inside_data": tmp_path / "data/silver/report.html",
    }[target]
    assert main([
        "--root", str(tmp_path),
        "--manifest", str(manifest_path),
        "--output", str(output),
    ]) == 1
    assert csv_path.read_bytes() == csv_before
    assert manifest_path.read_bytes() == manifest_before
    assert not (tmp_path / "data/silver/report.html").exists()


def test_failed_report_replacement_preserves_previous_output(monkeypatch, tmp_path):
    output = tmp_path / "report.html"
    output.write_text("previous report", encoding="utf-8")

    def fail_replace(self, target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    assert main(["--output", str(output)]) == 1
    assert output.read_text(encoding="utf-8") == "previous report"
    assert list(tmp_path.iterdir()) == [output]

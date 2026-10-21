from __future__ import annotations

import json

import pandas as pd
import pytest

from app.services.inflation_analysis import (
    InflationEvidence,
    InflationMonth,
    build_inflation_evidence,
)
from app.tools.inflation_chart import InflationChartError, build_inflation_chart


def _monthly_frame(start: str, end: str) -> pd.DataFrame:
    periods = pd.period_range(start, end, freq="M").astype(str)
    values = [100.0 + index * 2.345678901 for index in range(len(periods))]
    return pd.DataFrame({"period": periods, "cpi_index": values})


def _evidence(
    *, start: str = "2021-01", end: str = "2021-03", history_start: str = "2019-01"
) -> InflationEvidence:
    return build_inflation_evidence(
        _monthly_frame(history_start, end),
        start_period=start,
        end_period=end,
        source_ref="synthetic://inflation-chart",
    )


def _observed(evidence: InflationEvidence, field: str) -> list[float | None]:
    return [getattr(row, field) for row in evidence.observations]


def test_chart_copies_three_series_from_evidence_in_supplied_order():
    evidence = _evidence()
    chart = build_inflation_chart(evidence)

    assert [trace["name"] for trace in chart["data"]] == [
        "TÜFE endeksi (2025=100)",
        "Aylık değişim (%)",
        "Yıllık değişim (%)",
    ]
    expected_x = [f"{row.period}-01" for row in evidence.observations]
    assert chart["data"][0]["x"] == expected_x
    assert chart["data"][0]["y"] == _observed(evidence, "cpi_index")
    assert chart["data"][1]["y"] == _observed(evidence, "monthly_inflation_pct")
    assert chart["data"][2]["y"] == _observed(evidence, "annual_inflation_pct")
    assert chart["layout"]["yaxis"]["title"]["text"] == "TÜFE endeksi (2025=100)"
    assert chart["layout"]["yaxis2"]["title"]["text"] == "Değişim (%)"
    assert chart["layout"]["yaxis3"]["title"]["text"] == "Değişim (%)"
    assert chart["layout"]["xaxis3"]["title"]["text"] == "Dönem"
    assert "2025=100" in chart["data"][0]["hovertemplate"]
    assert "aylık" in chart["data"][1]["hovertemplate"].lower()
    assert "aynı ayına göre" in chart["data"][2]["hovertemplate"]
    json.dumps(chart, allow_nan=False)


def test_null_changes_remain_gaps_and_display_rounding_keeps_full_precision():
    evidence = _evidence(start="2021-01", end="2021-01", history_start="2019-01")
    observation = evidence.observations[0]
    chart = build_inflation_chart(evidence)

    assert observation.monthly_inflation_pct is not None
    assert observation.annual_inflation_pct is not None
    assert chart["data"][0]["y"] == [observation.cpi_index]
    assert chart["data"][0]["y"][0] == 100.0 + 24 * 2.345678901
    assert chart["data"][0]["hovertemplate"].count(":.4f") == 1
    assert chart["data"][1]["connectgaps"] is False
    assert chart["data"][2]["connectgaps"] is False

    no_history = _evidence(start="2021-01", end="2021-01", history_start="2021-01")
    no_history_chart = build_inflation_chart(no_history)
    assert no_history_chart["data"][1]["y"] == [None]
    assert no_history_chart["data"][2]["y"] == [None]
    assert json.loads(json.dumps(no_history_chart, allow_nan=False))["data"][1]["y"] == [None]


def test_single_month_has_one_point_per_panel_and_no_invented_history():
    evidence = _evidence(start="2021-01", end="2021-01", history_start="2020-02")
    chart = build_inflation_chart(evidence)

    assert evidence.observed_month_count == 1
    assert all(trace["x"] == ["2021-01-01"] for trace in chart["data"])
    assert chart["data"][0]["y"] == [evidence.first_cpi_index]
    assert chart["data"][1]["y"] == [evidence.observations[0].monthly_inflation_pct]
    assert chart["data"][2]["y"] == [None]
    assert chart["layout"]["annotations"][-1]["text"] == (
        "Önceki yılın aynı ayı olmadığı için yıllık değişim yok."
    )


def test_all_missing_annual_history_stays_empty_with_explanation():
    evidence = _evidence(start="2021-01", end="2021-12", history_start="2021-01")
    chart = build_inflation_chart(evidence)

    assert len(chart["data"][2]["x"]) == 12
    assert chart["data"][2]["y"] == [None] * 12
    annotation_texts = [
        annotation["text"] for annotation in chart["layout"]["annotations"]
    ]
    assert annotation_texts.count(
        "Önceki yılın aynı ayı olmadığı için yıllık değişim yok."
    ) == 1
    assert (
        "Bu dönemde önceki ay olmadığı için aylık değişim yok."
        not in annotation_texts
    )


def test_chart_rejects_inconsistent_period_and_row_counts():
    evidence = _evidence()
    first, second, third = evidence.observations
    faults = (
        evidence.model_copy(update={"observed_month_count": 2}),
        evidence.model_copy(update={"period_start": "2020-12"}),
        evidence.model_copy(
            update={
                "observed_month_count": 2,
                "observations": (first, third),
            }
        ),
        evidence.model_copy(
            update={
                "observed_month_count": 3,
                "observations": (first, first, third),
            }
        ),
        evidence.model_copy(
            update={
                "observed_month_count": 3,
                "observations": (third, second, first),
            }
        ),
        evidence.model_copy(update={"available_period_end": "2020-12"}),
        evidence.model_copy(update={"last_cpi_index": first.cpi_index}),
    )
    for faulty in faults:
        with pytest.raises(InflationChartError):
            build_inflation_chart(faulty)


@pytest.mark.parametrize(
    "faulty",
    [
        None,
        {},
        "evidence",
        InflationEvidence.model_construct(
            observations=(),
            observed_month_count=0,
        ),
    ],
)
def test_chart_rejects_non_evidence_or_empty_observations(faulty):
    with pytest.raises(InflationChartError):
        build_inflation_chart(faulty)


def test_chart_rejects_invalid_period_and_non_finite_values():
    evidence = _evidence()
    first = evidence.observations[0]
    bad_period = first.model_copy(update={"period": "2021-1"})
    bad_index = first.model_copy(update={"cpi_index": float("inf")})
    bad_monthly = first.model_copy(update={"monthly_inflation_pct": float("nan")})
    bad_annual = first.model_copy(update={"annual_inflation_pct": float("nan")})
    mutations = (
        {"observations": (bad_period,) + evidence.observations[1:]},
        {"observations": (bad_index,) + evidence.observations[1:]},
        {"observations": (bad_monthly,) + evidence.observations[1:]},
        {"observations": (bad_annual,) + evidence.observations[1:]},
        {"available_period_start": "not-a-period"},
    )
    for mutation in mutations:
        with pytest.raises(InflationChartError):
            build_inflation_chart(evidence.model_copy(update=mutation))


def test_chart_does_not_mutate_evidence_or_observation_order():
    evidence = _evidence()
    before = evidence.model_dump()

    build_inflation_chart(evidence)

    assert evidence.model_dump() == before
    assert [row.period for row in evidence.observations] == [
        "2021-01",
        "2021-02",
        "2021-03",
    ]
    assert isinstance(evidence.observations[0], InflationMonth)

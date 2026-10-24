"""Evidence-first tests for the three-panel CPI comparison chart."""

import json
from copy import deepcopy

import pandas as pd
import pytest

from app.services.inflation_comparison import (
    InflationComparison,
    compare_inflation_years,
)
from app.tools.inflation_comparison_chart import (
    InflationComparisonChartError,
    build_inflation_comparison_chart,
    validated_comparison_years,
)


@pytest.fixture
def comparison():
    months = pd.period_range("2022-12", "2024-12", freq="M").astype(str)
    values = [
        100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 119, 119.5, 120,
        123, 126, 129, 132, 135, 138, 141, 144, 146, 147, 148.5, 150,
    ]
    frame = pd.DataFrame({"period": months, "cpi_index": values})
    return compare_inflation_years(
        frame, first_year=2023, second_year=2024,
        source_ref="synthetic://comparison",
    )


def test_six_traces_copy_complete_nested_evidence_without_rounding(comparison):
    before = deepcopy(comparison.model_dump())
    chart = build_inflation_comparison_chart(comparison)

    assert len(chart["data"]) == 6
    assert [trace["name"] for trace in chart["data"]] == [
        "2023", "2024", "2023", "2024", "2023", "2024"
    ]
    fields = ("cpi_index", "monthly_inflation_pct", "annual_inflation_pct")
    for panel_index, field in enumerate(fields):
        for year_index, item in enumerate(comparison.years):
            trace = chart["data"][panel_index * 2 + year_index]
            assert trace["x"] == list(range(1, 13))
            assert trace["customdata"] == [row.period for row in item.evidence.observations]
            assert trace["y"] == [getattr(row, field) for row in item.evidence.observations]
            assert trace["connectgaps"] is False
            assert trace["showlegend"] is (panel_index == 0)
            assert str(item.year) in trace["hovertemplate"]
            assert "%{customdata}" in trace["hovertemplate"]
    assert chart["data"][0]["line"]["color"] == chart["data"][2]["line"]["color"]
    assert chart["data"][1]["line"]["color"] == chart["data"][5]["line"]["color"]
    assert chart["data"][0]["line"]["color"] != chart["data"][1]["line"]["color"]
    assert "2025=100" in chart["layout"]["yaxis"]["title"]["text"]
    assert chart["layout"]["xaxis3"]["ticktext"][0] == "Ocak"
    assert chart["layout"]["xaxis3"]["ticktext"][-1] == "Aralık"
    json.dumps(chart, allow_nan=False)
    assert comparison.model_dump() == before


def test_reverse_order_remains_reverse_not_chronological(comparison):
    reversed_comparison = comparison.model_copy(update={
        "years": (comparison.years[1], comparison.years[0]),
        "second_minus_first_december_annual_inflation_pp": -5.0,
    })
    chart = build_inflation_comparison_chart(reversed_comparison)
    assert [trace["name"] for trace in chart["data"][:2]] == ["2024", "2023"]
    assert "2024 → 2023" in chart["layout"]["title"]["text"]
    assert chart["data"][0]["customdata"][0] == "2024-01"
    assert chart["data"][1]["customdata"][0] == "2023-01"


def test_missing_annual_history_remains_none_not_zero(comparison):
    first, second = comparison.years
    no_history_rows = tuple(
        row.model_copy(update={"annual_inflation_pct": None})
        for row in first.evidence.observations
    )
    year_without_history = first.model_copy(update={
        "evidence": first.evidence.model_copy(update={"observations": no_history_rows})
    })
    incomplete = comparison.model_copy(update={
        "years": (year_without_history, second),
        "second_minus_first_december_annual_inflation_pp": None,
    })
    chart = build_inflation_comparison_chart(incomplete)
    assert chart["data"][4]["y"] == [None] * 12
    assert chart["data"][5]["y"] == [
        row.annual_inflation_pct for row in second.evidence.observations
    ]
    json.dumps(chart, allow_nan=False)


@pytest.mark.parametrize("mutation", [
    "missing_row", "wrong_period", "reverse_months", "wrong_year", "repeated_year",
    "wrong_source", "bad_observation_count", "bad_index", "bad_monthly", "bad_annual",
    "bad_difference", "difference_without_rate", "missing_difference",
])
def test_malformed_evidence_is_rejected(comparison, mutation):
    first, second = comparison.years
    observations = first.evidence.observations
    changes = {}
    if mutation == "missing_row":
        changes["observations"] = observations[:5] + observations[6:]
        changes["observed_month_count"] = 11
    elif mutation == "wrong_period":
        changes["observations"] = (
            observations[0].model_copy(update={"period": "2022-01"}),
        ) + observations[1:]
    elif mutation == "reverse_months":
        changes["observations"] = tuple(reversed(observations))
    elif mutation == "wrong_year":
        first = first.model_copy(update={"year": 2022})
    elif mutation == "repeated_year":
        second = second.model_copy(update={"year": 2023})
    elif mutation == "wrong_source":
        changes["source_ref"] = "synthetic://different-source"
    elif mutation == "bad_observation_count":
        changes["observed_month_count"] = 13
    elif mutation == "bad_index":
        changes["observations"] = (
            observations[0].model_copy(update={"cpi_index": float("inf")}),
        ) + observations[1:]
    elif mutation == "bad_monthly":
        changes["observations"] = (
            observations[0].model_copy(update={"monthly_inflation_pct": float("nan")}),
        ) + observations[1:]
    elif mutation == "bad_annual":
        changes["observations"] = (
            observations[0].model_copy(update={"annual_inflation_pct": float("inf")}),
        ) + observations[1:]
    if changes:
        first = first.model_copy(update={
            "evidence": first.evidence.model_copy(update=changes)
        })
    if mutation == "bad_difference":
        comparison = comparison.model_copy(update={
            "second_minus_first_december_annual_inflation_pp": float("nan")
        })
    elif mutation == "difference_without_rate":
        rows = list(first.evidence.observations)
        rows[-1] = rows[-1].model_copy(update={"annual_inflation_pct": None})
        first = first.model_copy(update={
            "evidence": first.evidence.model_copy(update={"observations": tuple(rows)})
        })
    elif mutation == "missing_difference":
        comparison = comparison.model_copy(update={
            "second_minus_first_december_annual_inflation_pp": None
        })
    comparison = comparison.model_copy(update={"years": (first, second)})
    with pytest.raises(InflationComparisonChartError):
        build_inflation_comparison_chart(comparison)


def test_rejects_wrong_kind_and_preserves_input(comparison):
    assert validated_comparison_years(comparison) == comparison.years
    for bad in (None, {}, "comparison", []):
        with pytest.raises(InflationComparisonChartError):
            build_inflation_comparison_chart(bad)
    assert comparison.years[0].evidence.observations[0].period == "2023-01"

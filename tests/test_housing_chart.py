from __future__ import annotations

import json

import pandas as pd
import pytest

from app.lakehouse.gold import build_housing_gold_table
from app.tools.housing_chart import HousingChartError, build_housing_chart


def _gold_table() -> pd.DataFrame:
    bddk = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02", "2021-03"],
            "nominal_housing_loan_mn_try": [100.0, 100.0, 100.0],
        }
    )
    evds = pd.DataFrame(
        {
            "period": ["2021-01", "2021-02", "2021-03"],
            "housing_loan_interest_rate_pct": [10.0, 9.0, 11.0],
            "weekly_observation_count": [4, 4, 5],
            "cpi_index": [100.0, 110.0, 120.0],
            "housing_price_index": [100.0, 101.0, 102.0],
        }
    )
    return build_housing_gold_table(
        bddk,
        evds,
        start_period="2021-01",
        end_period="2021-03",
    )


def test_build_housing_chart_returns_json_safe_three_panel_figure():
    chart = build_housing_chart(_gold_table())

    assert len(chart["data"]) == 6
    assert chart["layout"]["title"]["text"] == "Konut Kredisi Analizi"
    json.dumps(chart, allow_nan=False)


def test_build_housing_chart_marks_only_matching_periods():
    chart = build_housing_chart(_gold_table())
    marker_trace = next(
        trace for trace in chart["data"] if trace["name"] == "Koşula uyan ay"
    )

    assert marker_trace["x"] == ["2021-02-01"]
    assert marker_trace["y"] == [9.0]


def test_build_housing_chart_rejects_duplicate_periods():
    gold = _gold_table()
    gold = pd.concat([gold, gold.iloc[[0]]], ignore_index=True)

    with pytest.raises(HousingChartError, match="duplicate chart periods"):
        build_housing_chart(gold)


def test_build_housing_chart_rejects_invalid_numeric_values():
    gold = _gold_table()
    gold.loc[1, "cpi_index"] = float("inf")

    with pytest.raises(HousingChartError, match="invalid chart values"):
        build_housing_chart(gold)

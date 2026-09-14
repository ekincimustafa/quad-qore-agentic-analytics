"""Tests for the verified housing-analysis evidence payload."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from app.lakehouse.gold import build_housing_gold_table
from app.tools.housing_evidence import (
    EvidenceBuildError,
    build_housing_analysis_evidence,
)


def _gold() -> pd.DataFrame:
    bddk = pd.DataFrame(
        {
            "period": ["2021-03", "2021-01", "2021-02"],
            "nominal_housing_loan_mn_try": [105.0, 100.0, 100.0],
        }
    )
    evds = pd.DataFrame(
        {
            "period": ["2021-02", "2021-03", "2021-01"],
            "housing_loan_interest_rate_pct": [19.0, 18.0, 20.0],
            "weekly_observation_count": [4, 5, 4],
            "cpi_index": [102.0, 103.0, 100.0],
            "housing_price_index": [101.0, 102.0, 100.0],
        }
    )
    return build_housing_gold_table(
        bddk,
        evds,
        start_period="2021-01",
        end_period="2021-03",
    )


def _build(gold: pd.DataFrame | None = None):
    return build_housing_analysis_evidence(
        _gold() if gold is None else gold,
        start_period="2021-01",
        end_period="2021-03",
    )


def test_builds_verified_evidence_for_matching_months() -> None:
    evidence = _build()

    assert evidence.status == "ok"
    assert evidence.observed_month_count == 3
    assert evidence.matched_month_count == 1
    assert evidence.matched_periods == ("2021-02",)
    assert evidence.results[0].period == "2021-02"
    assert evidence.results[0].interest_rate_change_pp == pytest.approx(-1.0)
    assert evidence.results[0].real_housing_loan_change_pct < 0
    assert evidence.evds_source_refs == (
        "TP.KTF12",
        "TP.TUKFIY2025.GENEL",
        "TP.KFE.TR",
    )


def test_payload_is_json_safe_and_deterministic() -> None:
    first = _build().model_dump_json()
    second = _build().model_dump_json()

    assert first == second
    payload = json.loads(first)
    assert payload["matched_periods"] == ["2021-02"]
    assert payload["results"][0]["period"] == "2021-02"


def test_returns_empty_results_when_no_month_matches() -> None:
    gold = _gold()
    gold.loc[1:, "rate_down_real_credit_not_up"] = False

    evidence = _build(gold)

    assert evidence.matched_month_count == 0
    assert evidence.matched_periods == ()
    assert evidence.results == ()


def test_does_not_mutate_gold_input() -> None:
    gold = _gold()
    before = gold.copy(deep=True)

    _build(gold)

    pd.testing.assert_frame_equal(gold, before)


def test_rejects_missing_required_column() -> None:
    gold = _gold().drop(columns=["cpi_index"])

    with pytest.raises(EvidenceBuildError, match="missing required columns"):
        _build(gold)


def test_rejects_missing_period() -> None:
    gold = _gold()[lambda frame: frame["period"] != "2021-02"]

    with pytest.raises(EvidenceBuildError, match="missing=.*2021-02"):
        _build(gold)


def test_rejects_duplicate_period() -> None:
    gold = pd.concat([_gold(), _gold().iloc[[1]]], ignore_index=True)

    with pytest.raises(EvidenceBuildError, match="duplicate periods"):
        _build(gold)


@pytest.mark.parametrize(
    "column",
    ["bddk_source_ref", "evds_source_refs", "data_quality_note"],
)
def test_rejects_missing_provenance(column: str) -> None:
    gold = _gold()
    gold.loc[1, column] = ""

    with pytest.raises(EvidenceBuildError, match=column):
        _build(gold)


def test_rejects_non_finite_numeric_value() -> None:
    gold = _gold()
    gold.loc[1, "cpi_index"] = float("inf")

    with pytest.raises(EvidenceBuildError, match="cpi_index must be finite"):
        _build(gold)


def test_rejects_missing_flag_after_first_period() -> None:
    gold = _gold()
    gold.loc[1, "rate_down_real_credit_not_up"] = pd.NA

    with pytest.raises(EvidenceBuildError, match="may be null only"):
        _build(gold)


def test_rejects_non_null_flag_for_first_period() -> None:
    gold = _gold()
    gold.loc[0, "rate_down_real_credit_not_up"] = False

    with pytest.raises(EvidenceBuildError, match="must be null for the first"):
        _build(gold)


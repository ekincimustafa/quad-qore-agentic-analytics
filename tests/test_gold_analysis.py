"""Tests for the deterministic housing-loan Gold calculation."""

from __future__ import annotations

import pandas as pd
import pytest

from app.lakehouse.gold import (
    GOLD_COLUMNS,
    GoldAnalysisError,
    build_housing_gold_table,
    find_rate_down_real_credit_not_up,
)


def _bddk() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "period": ["2021-03", "2021-01", "2021-02"],
            "nominal_housing_loan_mn_try": [105.0, 100.0, 100.0],
        }
    )


def _evds() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "period": ["2021-02", "2021-03", "2021-01"],
            "housing_loan_interest_rate_pct": [19.0, 18.0, 20.0],
            "weekly_observation_count": [4, 5, 4],
            "cpi_index": [102.0, 103.0, 100.0],
            "housing_price_index": [101.0, 102.0, 100.0],
        }
    )


def _build(
    bddk: pd.DataFrame | None = None,
    evds: pd.DataFrame | None = None,
) -> pd.DataFrame:
    return build_housing_gold_table(
        _bddk() if bddk is None else bddk,
        _evds() if evds is None else evds,
        start_period="2021-01",
        end_period="2021-03",
    )


def test_builds_contract_columns_in_chronological_order() -> None:
    result = _build()

    assert result.columns.tolist() == list(GOLD_COLUMNS)
    assert result["period"].tolist() == ["2021-01", "2021-02", "2021-03"]
    assert result["weekly_observation_count"].tolist() == [4, 4, 5]


def test_computes_real_credit_changes_and_condition() -> None:
    result = _build()

    assert result.loc[0, "real_housing_loan_2025_mn_try"] == pytest.approx(100.0)
    assert result.loc[1, "real_housing_loan_2025_mn_try"] == pytest.approx(
        100.0 * 100.0 / 102.0
    )
    assert result.loc[1, "nominal_housing_loan_change_pct"] == pytest.approx(0.0)
    assert result.loc[1, "real_housing_loan_change_pct"] < 0
    assert result.loc[1, "interest_rate_change_pp"] == pytest.approx(-1.0)
    assert pd.isna(result.loc[0, "rate_down_real_credit_not_up"])
    assert bool(result.loc[1, "rate_down_real_credit_not_up"]) is True
    assert bool(result.loc[2, "rate_down_real_credit_not_up"]) is False


def test_returns_only_matching_months() -> None:
    matches = find_rate_down_real_credit_not_up(_build())

    assert matches["period"].tolist() == ["2021-02"]


def test_does_not_mutate_inputs() -> None:
    bddk = _bddk()
    evds = _evds()
    bddk_before = bddk.copy(deep=True)
    evds_before = evds.copy(deep=True)

    _build(bddk, evds)

    pd.testing.assert_frame_equal(bddk, bddk_before)
    pd.testing.assert_frame_equal(evds, evds_before)


def test_rejects_missing_period_without_interpolation() -> None:
    bddk = _bddk()[lambda frame: frame["period"] != "2021-02"]

    with pytest.raises(GoldAnalysisError, match="missing periods.*2021-02"):
        _build(bddk=bddk)


def test_rejects_duplicate_period() -> None:
    evds = pd.concat([_evds(), _evds().iloc[[0]]], ignore_index=True)

    with pytest.raises(GoldAnalysisError, match="duplicate periods.*2021-02"):
        _build(evds=evds)


@pytest.mark.parametrize(
    ("column", "invalid_value"),
    [
        ("housing_loan_interest_rate_pct", "not-a-number"),
        ("cpi_index", 0),
        ("housing_price_index", -1),
        ("weekly_observation_count", 0),
        ("weekly_observation_count", 2.5),
    ],
)
def test_rejects_invalid_evds_values(column: str, invalid_value: object) -> None:
    evds = _evds()
    evds[column] = evds[column].astype("object")
    evds.loc[0, column] = invalid_value

    with pytest.raises(GoldAnalysisError):
        _build(evds=evds)


def test_rejects_invalid_nominal_credit() -> None:
    bddk = _bddk()
    bddk.loc[0, "nominal_housing_loan_mn_try"] = -1

    with pytest.raises(GoldAnalysisError, match="must be non-negative"):
        _build(bddk=bddk)


def test_rejects_invalid_period_range() -> None:
    with pytest.raises(GoldAnalysisError, match="cannot be later"):
        build_housing_gold_table(
            _bddk(),
            _evds(),
            start_period="2021-03",
            end_period="2021-01",
        )

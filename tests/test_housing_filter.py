"""Focused tests for the typed, deterministic housing condition filter."""

from __future__ import annotations

import json

import pandas as pd
import pytest

import app.services.housing_filter as housing_filter
from app.lakehouse.gold import (
    GoldAnalysisError,
    build_housing_gold_table,
    find_rate_down_real_credit_not_up,
)
from app.services.housing_filter import (
    ANALYSIS_ID,
    HousingFilterCondition,
    HousingFilterValidationError,
    run_housing_filter,
)


DEFAULT_PERIODS = (
    "2021-01",
    "2021-02",
    "2021-03",
    "2021-04",
    "2021-05",
    "2021-06",
)


def _inputs(
    *,
    periods: tuple[str, ...] = DEFAULT_PERIODS,
    nominals: tuple[float, ...] | None = None,
    interests: tuple[float, ...] | None = None,
    cpis: tuple[float, ...] | None = None,
    housing_indices: tuple[float, ...] | None = None,
    shuffle: bool = False,
    bddk_refs: tuple[str, ...] | None = None,
    data_notes: tuple[str, ...] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if nominals is None:
        nominals = tuple(100.0 for _ in periods)
    if interests is None:
        interests = (
            (20.0, 19.0, 19.0, 20.0, 18.0, 18.5)
            if periods == DEFAULT_PERIODS
            else tuple(10.0 for _ in periods)
        )
    cpis = cpis or tuple(100.0 for _ in periods)
    housing_indices = housing_indices or tuple(100.0 for _ in periods)

    bddk = pd.DataFrame(
        {
            "period": periods,
            "nominal_housing_loan_mn_try": nominals,
        }
    )
    if bddk_refs is not None:
        bddk["bddk_source_ref"] = bddk_refs
        bddk["data_quality_note"] = data_notes

    evds = pd.DataFrame(
        {
            "period": periods,
            "housing_loan_interest_rate_pct": interests,
            "weekly_observation_count": [4] * len(periods),
            "cpi_index": cpis,
            "housing_price_index": housing_indices,
        }
    )
    if shuffle:
        bddk = bddk.sample(frac=1.0, random_state=7).reset_index(drop=True)
        evds = evds.sample(frac=1.0, random_state=11).reset_index(drop=True)
    return bddk, evds


def _condition(
    metric: str,
    operator: str,
    threshold: float | int,
) -> HousingFilterCondition:
    return HousingFilterCondition(
        metric=metric,
        operator=operator,
        threshold=threshold,
    )


def _run(
    conditions,
    *,
    inputs: tuple[pd.DataFrame, pd.DataFrame] | None = None,
    start_period: str | None = None,
    end_period: str | None = None,
    **kwargs,
):
    bddk, evds = inputs or _inputs()
    periods = sorted(bddk["period"].tolist())
    return run_housing_filter(
        bddk,
        evds,
        start_period=start_period or periods[0],
        end_period=end_period or periods[-1],
        conditions=conditions,
        **kwargs,
    )


def test_four_operators_respect_equality_at_the_threshold() -> None:
    cases = {
        "lt": ("2021-02", "2021-05"),
        "lte": ("2021-02", "2021-03", "2021-05"),
        "gt": ("2021-04", "2021-06"),
        "gte": ("2021-03", "2021-04", "2021-06"),
    }

    for operator, expected in cases.items():
        evidence = _run([_condition("interest_rate_change_pp", operator, 0)])

        assert evidence.matched_periods == expected
        assert evidence.observed_month_count == 6
        assert evidence.evaluable_month_count == 5
        assert "2021-01" not in evidence.matched_periods


def test_negative_positive_and_fractional_thresholds_are_not_rounded() -> None:
    assert _run(
        [_condition("interest_rate_change_pp", "lt", -1)]
    ).matched_periods == ("2021-05",)
    assert _run(
        [_condition("interest_rate_change_pp", "gte", -1)]
    ).matched_periods == ("2021-02", "2021-03", "2021-04", "2021-06")
    assert _run(
        [_condition("interest_rate_change_pp", "gt", 0.5)]
    ).matched_periods == ("2021-04",)
    assert _run(
        [_condition("interest_rate_change_pp", "gte", 0.5)]
    ).matched_periods == ("2021-04", "2021-06")
    assert _run(
        [_condition("interest_rate_change_pp", "gt", 0.499999)]
    ).matched_periods == ("2021-04", "2021-06")
    assert _run(
        [_condition("interest_rate_change_pp", "gt", 0.500001)]
    ).matched_periods == ("2021-04",)


def test_one_two_and_three_and_conditions_narrow_the_result() -> None:
    inputs = _inputs(
        nominals=(100.0, 110.0, 99.0, 99.0, 105.93, 105.93),
    )

    one = _run([_condition("interest_rate_change_pp", "lt", 0)], inputs=inputs)
    two = _run(
        [
            _condition("interest_rate_change_pp", "lt", 0),
            _condition("real_housing_loan_change_pct", "gte", 0),
        ],
        inputs=inputs,
    )
    three = _run(
        [
            _condition("interest_rate_change_pp", "lt", 0),
            _condition("real_housing_loan_change_pct", "gte", 0),
            _condition("housing_loan_interest_rate_pct", "lt", 18.25),
        ],
        inputs=inputs,
    )

    assert one.matched_periods == ("2021-02", "2021-05")
    assert two.matched_periods == ("2021-02", "2021-05")
    assert three.matched_periods == ("2021-05",)
    assert len(three.conditions) == 3
    assert all(condition.unit for condition in three.conditions)


def test_interest_rising_while_real_credit_rises() -> None:
    inputs = _inputs(
        periods=("2021-01", "2021-02"),
        nominals=(100.0, 110.0),
        interests=(10.0, 11.0),
        cpis=(100.0, 107.0),
    )

    evidence = _run(
        [
            _condition("interest_rate_change_pp", "gt", 0),
            _condition("real_housing_loan_change_pct", "gt", 0),
        ],
        inputs=inputs,
    )

    assert evidence.matched_periods == ("2021-02",)
    assert evidence.results[0].interest_rate_change_pp == pytest.approx(1.0)
    assert evidence.results[0].real_housing_loan_change_pct == pytest.approx(
        110.0 * 100.0 / 107.0 - 100.0,
    )
    assert [condition.unit for condition in evidence.conditions] == [
        "percentage_point",
        "percent",
    ]


def test_real_credit_above_two_percent_while_nominal_credit_falls() -> None:
    inputs = _inputs(
        periods=("2021-01", "2021-02"),
        nominals=(100.0, 90.0),
        interests=(12.0, 12.0),
        cpis=(100.0, 85.0),
    )

    evidence = _run(
        [
            _condition("real_housing_loan_change_pct", "gt", 2),
            _condition("nominal_housing_loan_change_pct", "lt", 0),
        ],
        inputs=inputs,
    )

    assert evidence.matched_periods == ("2021-02",)
    assert evidence.results[0].nominal_housing_loan_change_pct == pytest.approx(
        -10.0,
    )
    assert evidence.results[0].real_housing_loan_change_pct == pytest.approx(
        90.0 * 100.0 / 85.0 - 100.0,
    )


def test_level_filter_can_match_the_first_month_and_keeps_nulls_as_none() -> None:
    evidence = _run(
        [_condition("housing_loan_interest_rate_pct", "gte", 0)],
    )

    assert evidence.observed_month_count == 6
    assert evidence.evaluable_month_count == 6
    assert evidence.matched_periods == DEFAULT_PERIODS
    first = evidence.results[0]
    assert first.period == "2021-01"
    assert first.nominal_housing_loan_change_pct is None
    assert first.real_housing_loan_change_pct is None
    assert first.interest_rate_change_pp is None


def test_change_filter_excludes_the_first_month_without_filling_zero() -> None:
    evidence = _run(
        [_condition("nominal_housing_loan_change_pct", "gte", -100)],
    )

    assert evidence.observed_month_count == 6
    assert evidence.evaluable_month_count == 5
    assert evidence.matched_month_count == 5
    assert "2021-01" not in evidence.matched_periods


def test_single_month_periods_can_match_or_be_unevaluable() -> None:
    inputs = _inputs(
        periods=("2021-01",),
        nominals=(100.0,),
        interests=(20.0,),
    )

    level = _run(
        [_condition("housing_loan_interest_rate_pct", "gte", 20)],
        inputs=inputs,
        start_period="2021-01",
        end_period="2021-01",
    )
    change = _run(
        [_condition("interest_rate_change_pp", "lt", 1000)],
        inputs=inputs,
        start_period="2021-01",
        end_period="2021-01",
    )

    assert level.observed_month_count == 1
    assert level.matched_periods == ("2021-01",)
    assert change.observed_month_count == 1
    assert change.evaluable_month_count == 0
    assert change.matched_periods == ()
    assert change.results == ()


def test_zero_matches_is_a_successful_empty_result() -> None:
    evidence = _run(
        [_condition("housing_loan_interest_rate_pct", "gt", 1000)],
    )

    assert evidence.status == "ok"
    assert evidence.matched_month_count == 0
    assert evidence.matched_periods == ()
    assert evidence.results == ()


def test_parameterized_rule_matches_the_existing_legacy_function() -> None:
    inputs = _inputs(
        periods=("2021-01", "2021-02", "2021-03"),
        nominals=(100.0, 100.0, 105.0),
        interests=(20.0, 19.0, 18.0),
        cpis=(100.0, 102.0, 103.0),
        housing_indices=(100.0, 101.0, 102.0),
    )
    gold = build_housing_gold_table(
        *inputs,
        start_period="2021-01",
        end_period="2021-03",
    )
    legacy = find_rate_down_real_credit_not_up(gold)

    evidence = _run(
        [
            _condition("interest_rate_change_pp", "lt", 0),
            _condition("real_housing_loan_change_pct", "lte", 0),
        ],
        inputs=inputs,
        start_period="2021-01",
        end_period="2021-03",
    )

    assert evidence.matched_periods == tuple(legacy["period"])
    assert evidence.matched_periods == ("2021-02",)


def test_result_is_chronological_even_when_inputs_are_shuffled() -> None:
    evidence = _run(
        [_condition("housing_loan_interest_rate_pct", "gte", 0)],
        inputs=_inputs(shuffle=True),
    )

    assert evidence.matched_periods == DEFAULT_PERIODS
    assert [result.period for result in evidence.results] == list(DEFAULT_PERIODS)


def test_sources_quality_notes_and_inputs_are_preserved() -> None:
    inputs = _inputs(
        periods=("2021-01", "2021-02"),
        nominals=(100.0, 100.0),
        interests=(20.0, 19.0),
        bddk_refs=("source A", "source A"),
        data_notes=("note A", "note A"),
    )
    bddk_before = inputs[0].copy(deep=True)
    evds_before = inputs[1].copy(deep=True)
    conditions = [_condition("housing_loan_interest_rate_pct", "gte", 0)]
    conditions_before = [condition.model_dump() for condition in conditions]

    evidence = _run(
        conditions,
        inputs=inputs,
        start_period="2021-01",
        end_period="2021-02",
        evds_source_refs="TP.A; TP.B",
    )

    pd.testing.assert_frame_equal(inputs[0], bddk_before)
    pd.testing.assert_frame_equal(inputs[1], evds_before)
    assert [condition.model_dump() for condition in conditions] == conditions_before

    assert evidence.bddk_source_refs == ("source A",)
    assert evidence.evds_source_refs == ("TP.A", "TP.B")
    assert evidence.data_quality_notes == (
        "note A; validated: complete, unique, non-null",
    )
    assert evidence.results[0].bddk_source_ref == "source A"
    assert evidence.results[0].evds_source_refs == ("TP.A", "TP.B")
    assert evidence.results[0].data_quality_note == (
        "note A; validated: complete, unique, non-null"
    )


def test_evidence_is_json_safe_and_deterministic() -> None:
    conditions = [_condition("housing_loan_interest_rate_pct", "gte", 0)]

    first = _run(conditions)
    second = _run(conditions)

    assert first.model_dump_json() == second.model_dump_json()
    payload_text = first.model_dump_json()
    assert "NaN" not in payload_text
    assert "Infinity" not in payload_text
    payload = json.loads(payload_text)
    assert payload["analysis_id"] == ANALYSIS_ID
    assert payload["results"][0]["nominal_housing_loan_change_pct"] is None


@pytest.mark.parametrize(
    "invalid_conditions",
    [
        [],
        [
            {"metric": "interest_rate_change_pp", "operator": "lt", "threshold": 0},
            {"metric": "interest_rate_change_pp", "operator": "lt", "threshold": 1},
            {"metric": "interest_rate_change_pp", "operator": "lt", "threshold": 2},
            {"metric": "interest_rate_change_pp", "operator": "lt", "threshold": 3},
        ],
        [{"metric": "unknown_metric", "operator": "lt", "threshold": 0}],
        [{"metric": "interest_rate_change_pp", "operator": "eq", "threshold": 0}],
        [{"metric": "interest_rate_change_pp", "operator": "lt", "threshold": True}],
        [{"metric": "interest_rate_change_pp", "operator": "lt", "threshold": "0"}],
        [{"metric": "interest_rate_change_pp", "operator": "lt", "threshold": float("nan")}],
        [{"metric": "interest_rate_change_pp", "operator": "lt", "threshold": float("inf")}],
        [
            {
                "metric": "interest_rate_change_pp",
                "operator": "lt",
                "threshold": 0,
                "extra": 1,
            }
        ],
    ],
)
def test_invalid_conditions_are_rejected_before_the_gold_builder(
    monkeypatch: pytest.MonkeyPatch,
    invalid_conditions,
) -> None:
    calls = 0

    def fail_if_called(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("Gold builder must not run for invalid conditions")

    monkeypatch.setattr(housing_filter, "build_housing_gold_table", fail_if_called)

    with pytest.raises(HousingFilterValidationError):
        _run(invalid_conditions)

    assert calls == 0


def test_valid_condition_runs_the_gold_builder_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original_builder = housing_filter.build_housing_gold_table

    def counting_builder(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_builder(*args, **kwargs)

    monkeypatch.setattr(
        housing_filter,
        "build_housing_gold_table",
        counting_builder,
    )

    evidence = _run([_condition("housing_loan_interest_rate_pct", "gte", 0)])

    assert calls == 1
    assert evidence.observed_month_count == 6


@pytest.mark.parametrize(
    ("start_period", "end_period", "message"),
    [
        ("2021-03", "2021-01", "cannot be later"),
        ("2020-12", "2021-02", "missing periods"),
        ("2021-01", "2021-07", "missing periods"),
        ("2021-13", "2021-12", "YYYY-MM"),
    ],
)
def test_invalid_period_ranges_fail_through_existing_gold_checks(
    start_period: str,
    end_period: str,
    message: str,
) -> None:
    with pytest.raises(GoldAnalysisError, match=message):
        _run(
            [_condition("housing_loan_interest_rate_pct", "gte", 0)],
            start_period=start_period,
            end_period=end_period,
        )


def test_missing_month_and_corrupt_data_fail_through_existing_gold_checks() -> None:
    bddk, evds = _inputs(periods=("2021-01", "2021-02", "2021-03"))

    with pytest.raises(GoldAnalysisError, match="missing periods"):
        _run(
            [_condition("housing_loan_interest_rate_pct", "gte", 0)],
            inputs=(bddk, evds.iloc[:-1]),
            start_period="2021-01",
            end_period="2021-03",
        )

    corrupt_evds = evds.copy()
    corrupt_evds["cpi_index"] = corrupt_evds["cpi_index"].astype("object")
    corrupt_evds.loc[1, "cpi_index"] = "not-a-number"
    with pytest.raises(GoldAnalysisError, match="cpi_index"):
        _run(
            [_condition("housing_loan_interest_rate_pct", "gte", 0)],
            inputs=(bddk, corrupt_evds),
            start_period="2021-01",
            end_period="2021-03",
        )

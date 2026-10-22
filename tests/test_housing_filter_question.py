"""Narrow natural-language grounding for parameterized Housing filters."""

import pytest

from app.services.housing_filter import HousingFilterCondition
from app.services.housing_filter_question import (
    guard_housing_filter_question,
    guard_legacy_housing_question,
)


def condition(metric, operator, threshold):
    return HousingFilterCondition(metric=metric, operator=operator, threshold=threshold)


def test_legacy_guard_requires_an_explicit_credit_direction():
    assert guard_legacy_housing_question(
        "2021 Ocak-Mart faiz düşerken reel konut kredisi stokunu göster"
    ) == "question_ambiguous"
    assert guard_legacy_housing_question(
        "2021 Ocak-Mart faiz düşerken reel konut kredisi bakiyesini incele"
    ) == "question_ambiguous"
    assert guard_legacy_housing_question(
        "2021 Ocak-Mart faiz düşerken reel konut kredisi stoku artmayan aylar"
    ) is None


@pytest.mark.parametrize("question,conditions", [
    (
        "2021 Ocak-Mart faiz düşerken reel konut kredisi stoku artmayan aylar",
        (
            condition("interest_rate_change_pp", "lt", 0.0),
            condition("real_housing_loan_change_pct", "lte", 0.0),
        ),
    ),
    (
        "2021 Ocak-Mart faiz artarken nominal konut kredisi stoku azalan aylar",
        (
            condition("interest_rate_change_pp", "gt", 0.0),
            condition("nominal_housing_loan_change_pct", "lt", 0.0),
        ),
    ),
    (
        "2021 Ocak-Mart reel ve nominal konut kredisi değişimi artan aylar",
        (
            condition("real_housing_loan_change_pct", "gt", 0.0),
            condition("nominal_housing_loan_change_pct", "gt", 0.0),
        ),
    ),
    (
        "2021 Ocak-Mart faiz seviyesi %20'nin altında olan aylar",
        (condition("housing_loan_interest_rate_pct", "lt", 20.0),),
    ),
    (
        "2021 Ocak-Mart aylık faiz değişimi en az 0,5 yüzde puan olan aylar",
        (condition("interest_rate_change_pp", "gte", 0.5),),
    ),
    (
        "2021 Ocak-Mart reel konut kredisi değişimi %2'yi aşmayan aylar",
        (condition("real_housing_loan_change_pct", "lte", 2.0),),
    ),
    (
        "2021 Ocak-Mart'ta reel konut kredisi stokunun aylık artışı %2'yi aşan aylar",
        (condition("real_housing_loan_change_pct", "gt", 2.0),),
    ),
    (
        "2021 Ocak-Mart nominal konut kredisi değişimi -2'nin altında olan aylar",
        (condition("nominal_housing_loan_change_pct", "lt", -2.0),),
    ),
    (
        "2021 Ocak-Mart reel konut kredisi artmayan aylar",
        (condition("real_housing_loan_change_pct", "lte", 0.0),),
    ),
    (
        "2021 Ocak-Mart nominal konut kredisi azalan aylar",
        (condition("nominal_housing_loan_change_pct", "lt", 0.0),),
    ),
    (
        "2021 Ocak-Mart reel konut kredisi artış göstermeyen aylar",
        (condition("real_housing_loan_change_pct", "lte", 0.0),),
    ),
    (
        "2021 Ocak-Mart reel konut kredisi artışı olmayan aylar",
        (condition("real_housing_loan_change_pct", "lte", 0.0),),
    ),
    (
        "2021 Ocak-Mart reel konut kredisi artmadığı aylar",
        (condition("real_housing_loan_change_pct", "lte", 0.0),),
    ),
    (
        "2021 Ocak-Mart faiz oranı 20 ve üzerinde olan aylar",
        (condition("housing_loan_interest_rate_pct", "gte", 20.0),),
    ),
    (
        "2021 Ocak-Mart faiz oranı 20 ve altında olan aylar",
        (condition("housing_loan_interest_rate_pct", "lte", 20.0),),
    ),
    (
        "2021 Ocak-Mart faiz değişimi 2 puanı geçen aylar",
        (condition("interest_rate_change_pp", "gt", 2.0),),
    ),
    (
        "2021 ilk altı ay faiz oranı %20'nin altında olan aylar",
        (condition("housing_loan_interest_rate_pct", "lt", 20.0),),
    ),
    (
        "2021 Ocak-Mart faiz oranı %10'un üzerinde ve %20'nin altında olan aylar",
        (
            condition("housing_loan_interest_rate_pct", "gt", 10.0),
            condition("housing_loan_interest_rate_pct", "lt", 20.0),
        ),
    ),
    (
        "2021 Ocak-Mart faiz oranı %20'nin altında olmayan aylar",
        (condition("housing_loan_interest_rate_pct", "gte", 20.0),),
    ),
    (
        "2021 Ocak-Mart faiz oranı %20'nin üstünde olmayan aylar",
        (condition("housing_loan_interest_rate_pct", "lte", 20.0),),
    ),
    (
        "2021 Ocak-Mart nominal konut kredisi stokunun aylık azalışı %2'yi aşan aylar",
        (condition("nominal_housing_loan_change_pct", "lt", -2.0),),
    ),
    (
        "2021 Ocak-Mart reel konut kredisi aylık düşüşü %2'yi geçen aylar",
        (condition("real_housing_loan_change_pct", "lt", -2.0),),
    ),
    (
        "2021 Ocak-Mart nominal konut kredisi stokunun aylık artışı %2'yi aşan aylar",
        (condition("nominal_housing_loan_change_pct", "gt", 2.0),),
    ),
    (
        "2021 Ocak-Mart faiz oranı %10'un üzerinde, reel konut kredisi artan ve "
        "nominal konut kredisi artan aylar",
        (
            condition("housing_loan_interest_rate_pct", "gt", 10.0),
            condition("real_housing_loan_change_pct", "gt", 0.0),
            condition("nominal_housing_loan_change_pct", "gt", 0.0),
        ),
    ),
])
def test_grounded_conditions_pass(question, conditions):
    assert guard_housing_filter_question(question, conditions) is None


@pytest.mark.parametrize("question,conditions,reason", [
    (
        "2021 Ocak-Mart kredi stoku artmayan aylar",
        (condition("real_housing_loan_change_pct", "lte", 0.0),),
        "metric_ambiguous",
    ),
    (
        "2021 Ocak-Mart reel veya nominal konut kredisi stoku artan aylar",
        (condition("nominal_housing_loan_change_pct", "gt", 0.0),),
        "metric_ambiguous",
    ),
    (
        "2021 Ocak-Mart faiz değişimi %2'yi aşan aylar",
        (condition("interest_rate_change_pp", "gt", 2.0),),
        "metric_ambiguous",
    ),
    (
        "2021 Ocak-Mart faiz artarken reel konut kredisi stoku artan veya azalan aylar",
        (condition("interest_rate_change_pp", "gt", 0.0),),
        "unsupported",
    ),
    (
        "2021 Ocak-Mart en düşük faizli ay",
        (condition("interest_rate_change_pp", "lt", 0.0),),
        "unsupported",
    ),
    (
        "2021 Ocak-Mart reel konut kredisi stoku 100'ün üzerinde",
        (condition("real_housing_loan_change_pct", "gt", 100.0),),
        "unsupported",
    ),
    (
        "2021 Ocak-Mart faiz artışını tahmin et",
        (condition("interest_rate_change_pp", "gt", 0.0),),
        "unsupported",
    ),
    (
        "2021 Ocak-Mart TÜFE ve faiz artarken aylar",
        (condition("interest_rate_change_pp", "gt", 0.0),),
        "unsupported",
    ),
    (
        "2021 Ocak-Mart faiz artarken reel konut kredisi stoku artan aylar",
        (condition("interest_rate_change_pp", "gt", 0.0),),
        "question_ambiguous",
    ),
    (
        "2021 Ocak-Mart faiz artarken reel ve nominal konut kredisi stoku azalan aylar",
        (condition("interest_rate_change_pp", "gt", 0.0),),
        "question_ambiguous",
    ),
    (
        "2021 Ocak-Mart reel konut kredisi değişmeyen aylar",
        (condition("real_housing_loan_change_pct", "lte", 0.0),),
        "question_ambiguous",
    ),
    (
        "2021 Ocak-Mart faiz oranı %20'nin altında olmayan aylar",
        (condition("housing_loan_interest_rate_pct", "lt", 20.0),),
        "question_ambiguous",
    ),
    (
        "2021 Ocak-Mart faiz oranı %10'un üzerinde ve %20'nin altında olan aylar",
        (condition("housing_loan_interest_rate_pct", "gt", 10.0),),
        "question_ambiguous",
    ),
    (
        "2021 Ocak-Mart nominal konut kredisi stokunun aylık azalışı %2'yi aşan aylar",
        (condition("nominal_housing_loan_change_pct", "gt", 2.0),),
        "question_ambiguous",
    ),
    (
        "2021 Ocak-Mart faiz oranı %10'un üzerinde, faiz oranı %20'nin altında, "
        "reel konut kredisi artan ve nominal konut kredisi artan aylar",
        (
            condition("housing_loan_interest_rate_pct", "gt", 10.0),
            condition("housing_loan_interest_rate_pct", "lt", 20.0),
            condition("real_housing_loan_change_pct", "gt", 0.0),
        ),
        "unsupported",
    ),
])
def test_ungrounded_conditions_are_rejected(question, conditions, reason):
    assert guard_housing_filter_question(question, conditions) == reason

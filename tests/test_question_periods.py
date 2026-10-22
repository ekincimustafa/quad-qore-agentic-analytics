"""Explicit closed Turkish periods accepted by the bounded question planner."""

import pytest

from app.services.question_periods import (
    contains_partial_period_expression,
    explicit_period,
)


@pytest.mark.parametrize("question,expected", [
    ("2023 yılında TÜFE değişimlerini göster.", ("2023-01", "2023-12")),
    ("2023 yılı boyunca TÜFE değişimlerini göster.", ("2023-01", "2023-12")),
    ("2023 yılının tamamında TÜFE değişimlerini göster.", ("2023-01", "2023-12")),
    ("2023'ün ikinci çeyreğinde TÜFE değişimlerini göster.", ("2023-04", "2023-06")),
    ("2023 yılının 2. çeyreğinde TÜFE değişimlerini göster.", ("2023-04", "2023-06")),
    ("2023'ün üçüncü çeyreğinde TÜFE değişimlerini göster.", ("2023-07", "2023-09")),
    ("2023'ün dördüncü çeyreğinde TÜFE değişimlerini göster.", ("2023-10", "2023-12")),
    ("2023'ün son çeyreğinde TÜFE değişimlerini göster.", ("2023-10", "2023-12")),
    ("2023'ün ilk altı ayında TÜFE değişimlerini göster.", ("2023-01", "2023-06")),
    ("2023 yılının son altı ayında TÜFE değişimlerini göster.", ("2023-07", "2023-12")),
    ("2023'ün ilk 6 ayında TÜFE değişimlerini göster.", ("2023-01", "2023-06")),
    ("2023'ün ilk yarısında TÜFE değişimlerini göster.", ("2023-01", "2023-06")),
    ("2023 Ocak ile Mart arasında TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023 Ocak ile 2023 Mart arasında TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023 Ocak'tan Mart'a kadar TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023 Ocak ayı ile Mart ayı arasında TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023 Ocak ayından Mart ayına kadar TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023 Ocak-Mart TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("Ocak-Mart 2023 TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023'ün ilk çeyreğinde TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023 yılının ilk çeyreğinde TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023'ün ilk üç ayında TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023 yılında ilk altı ay TÜFE değişimlerini göster.", ("2023-01", "2023-06")),
    ("2023 yılında Ocak-Mart TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023 Ocak ve Mart arasında TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023 Ocak\tve\tMart arasında TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023  Ocak   ve   Mart  arasında TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("Ocak 2023 ve Mart 2023 arasında TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023-01 ile 2023-03 TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("01/2023 ile 03/2023 TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("1 Ocak 2023-31 Mart 2023 TÜFE değişimlerini göster.", ("2023-01", "2023-03")),
    ("2023 Şubat TÜFE değişimlerini göster.", ("2023-02", "2023-02")),
    ("2023-2025 TÜFE değişimlerini göster.", ("2023-01", "2025-12")),
])
def test_supported_explicit_periods_resolve_to_closed_months(question, expected):
    assert explicit_period(question) == expected


@pytest.mark.parametrize("question", [
    "Ocak-Mart TÜFE aylık ve yıllık oranlarını göster.",
    "2023 Ocak'tan itibaren TÜFE değişimlerini göster.",
    "2023 yılından itibaren TÜFE değişimlerini göster.",
    "Son altı ayın TÜFE değişimlerini göster.",
    "Geçen yıl TÜFE değişimlerini göster.",
    "2023 Mart ile Ocak arasında TÜFE değişimlerini göster.",
    "2023 Ocak-Mart ve 2023 Nisan-Haziran TÜFE değişimlerini göster.",
    "2023'ün ikinci çeyreği ile üçüncü çeyreğinde TÜFE değişimlerini göster.",
    "1 Ocak 2023-15 Mart 2023 TÜFE değişimlerini göster.",
    "2023 yılında ve 2024 Ocak-Mart TÜFE değişimlerini göster.",
    "2023 yılının tamamında ve 2023 Ocak-Mart TÜFE değişimlerini göster.",
    "2023 Ocak, Şubat ve Mart TÜFE değişimlerini göster.",
    "2023 Ocak ve Mart TÜFE değişimlerini göster.",
    "2023 Ocak ve 2023 Mart TÜFE değişimlerini göster.",
    "Ocak 2023 ve Mart 2023 TÜFE değişimlerini göster.",
    "2023 Ocak\tve\tMart TÜFE değişimlerini göster.",
    "2023  Ocak  ve  2023  Mart TÜFE değişimlerini göster.",
    "2023 yılı boyunca 2023-02-15 ile 2023-03-15 arasındaki TÜFE değişimini göster.",
    "15.02.2023 ile 15.03.2023 arasındaki TÜFE değişimini göster.",
    "2025-2023 TÜFE değişimlerini göster.",
])
def test_ambiguous_or_incomplete_dates_do_not_invent_a_period(question):
    assert explicit_period(question) is None


@pytest.mark.parametrize("question", [
    "2023-02-15 ile 2024-03-15 TÜFE değişimlerini karşılaştır.",
    "15.02.2023 ile 15.03.2024 TÜFE değişimlerini karşılaştır.",
])
def test_comparison_day_dates_are_partial_periods(question):
    assert contains_partial_period_expression(question) is True

"""Tests for due-date parsing (taskpluck.dates)."""

from datetime import date

import pytest

from taskpluck.dates import parse_due_date, week_start

# All cases use Wednesday 2026-11-25 as the reference date.
BASE = date(2026, 11, 25)


def due(text: str, base: date = BASE):
    parsed, _ = parse_due_date(text, base)
    return parsed


def test_iso_date():
    assert due("send it by 2026-12-01") == date(2026, 12, 1)
    assert due("due 2026/12/04") == date(2026, 12, 4)


def test_iso_date_invalid_falls_through():
    # 30 February is not a date -- and there is no other date in the line.
    assert due("send it by 2026-02-30") is None


def test_month_name_with_year():
    assert due("review by Dec 2, 2026") == date(2026, 12, 2)
    assert due("ship on 5 December 2026") == date(2026, 12, 5)


def test_month_name_without_year():
    # Still ahead this year.
    assert due("review by Dec 2") == date(2026, 12, 2)
    # Already passed this year -> must mean next year.
    assert due("review by Jan 10") == date(2027, 1, 10)
    assert due("due 2nd Dec") == date(2026, 12, 2)


def test_bare_weekday_is_next_occurrence():
    # Base is Wednesday 25 Nov: Friday is two days away.
    assert due("send it by Friday") == date(2026, 11, 27)
    # Wednesday itself means next Wednesday, not today.
    assert due("send it by Wednesday") == date(2026, 12, 2)


def test_next_weekday_skips_this_week():
    assert due("send it next Friday") == date(2026, 12, 4)
    assert due("send it next Monday") == date(2026, 11, 30)


def test_relative_words():
    assert due("send it tomorrow") == date(2026, 11, 26)
    assert due("send it today") == date(2026, 11, 25)
    assert due("send it EOD") == date(2026, 11, 25)
    assert due("send it by end of day") == date(2026, 11, 25)
    # EOW from a Wednesday is that Friday.
    assert due("send it EOW") == date(2026, 11, 27)


def test_in_n_days_weeks_months():
    assert due("send it in 3 days") == date(2026, 11, 28)
    assert due("send it in 2 weeks") == date(2026, 12, 9)
    assert due("send it in a week") == date(2026, 12, 2)
    assert due("send it in 1 month") == date(2026, 12, 25)


def test_next_week_is_next_monday():
    assert due("send it next week") == date(2026, 11, 30)


def test_no_date_returns_none():
    assert due("just a normal sentence") is None
    assert due("send it soon") is None


def test_span_covers_the_date_phrase():
    parsed, span = parse_due_date("send the report by Friday", BASE)
    assert parsed == date(2026, 11, 27)
    assert span is not None
    assert "Friday" in "send the report by Friday"[span[0]:span[1]]


def test_week_start_is_monday():
    assert week_start(date(2026, 11, 25)) == date(2026, 11, 23)  # Wednesday
    assert week_start(date(2026, 11, 30)) == date(2026, 11, 30)  # Monday
    assert week_start(date(2026, 11, 29)) == date(2026, 11, 23)  # Sunday

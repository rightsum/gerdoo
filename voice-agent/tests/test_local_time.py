from datetime import datetime, timedelta, timezone

import pytest

import local_time


@pytest.mark.parametrize("greg,jal", [
    ((2024, 3, 20), (1403, 1, 1)),    # Nowruz
    ((2025, 3, 21), (1404, 1, 1)),    # Nowruz
    ((1979, 2, 11), (1357, 11, 22)),
    ((2000, 1, 1), (1378, 10, 11)),
    ((2026, 9, 2), (1405, 6, 11)),
])
def test_known_jalali_dates(greg, jal):
    assert local_time.gregorian_to_jalali(*greg) == jal


def test_nowruz_is_the_first_of_farvardin():
    jy, jm, jd = local_time.gregorian_to_jalali(2024, 3, 20)
    assert (jm, jd) == (1, 1)
    assert local_time.JALALI_MONTHS[jm - 1] == "Farvardin"


def test_day_before_nowruz_is_the_last_of_esfand():
    jy, jm, jd = local_time.gregorian_to_jalali(2024, 3, 19)
    assert jm == 12
    assert local_time.JALALI_MONTHS[jm - 1] == "Esfand"


def test_month_index_is_always_in_range():
    d = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for _ in range(400):
        _, jm, _ = local_time.gregorian_to_jalali(d.year, d.month, d.day)
        assert 1 <= jm <= 12
        d += timedelta(days=1)


def test_describe_contains_time_weekday_and_persian_date():
    now = datetime(2026, 9, 2, 14, 30, tzinfo=timezone.utc)
    out = local_time.describe("today", now)
    assert "14:30" in out
    assert "Wednesday" in out
    assert "Shahrivar" in out
    assert "1405" in out


def test_describe_defaults_to_today_and_now():
    out = local_time.describe()
    assert "Current time:" in out
    assert "Jalali" in out


@pytest.mark.parametrize("text,days", [
    ("today", 0), ("Today", 0), ("  TODAY  ", 0),
    ("yesterday", -1), ("last night", -1),
    ("tomorrow", 1),
    ("last week", -7), ("next week", 7),
    ("3 days ago", -3), ("10 days ago", -10),
    ("2 weeks ago", -14), ("1 month ago", -30),
    ("in 2 weeks", 14), ("in 5 days", 5),
    ("", 0), ("something unparseable", 0),
])
def test_resolve_offset(text, days):
    assert local_time.resolve_offset(text) == days


def test_format_day_gives_both_calendars():
    out = local_time.format_day(datetime(2024, 3, 20, tzinfo=timezone.utc))
    assert "20 March 2024" in out and "Gregorian" in out
    assert "1 Farvardin 1403" in out and "Jalali" in out


def test_describe_today_omits_the_relative_line():
    out = local_time.describe("today", datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc))
    assert "Today:" in out
    assert "days):" not in out


def test_describe_yesterday_resolves_a_real_date():
    out = local_time.describe("yesterday", datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc))
    assert "Tuesday 1 September 2026" in out
    assert "10 Shahrivar 1405" in out


def test_describe_always_includes_both_calendars():
    out = local_time.describe("today", datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc))
    assert "Gregorian" in out and "Jalali" in out

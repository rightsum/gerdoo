"""
The current time and date, for a robot that is asked in two languages.

Includes the Persian (Jalali) date, because "today is the 11th of Shahrivar"
is what someone speaking Farsi actually wants to hear. No dependency for it —
jdatetime is not installed and the conversion is short and well established.
"""

import re
from datetime import datetime, timedelta

# Jalali month names, transliterated. The agent speaks these aloud, so they are
# given in Latin script for the TTS to pronounce sensibly in either language.
JALALI_MONTHS = [
    "Farvardin", "Ordibehesht", "Khordad", "Tir", "Mordad", "Shahrivar",
    "Mehr", "Aban", "Azar", "Dey", "Bahman", "Esfand",
]

_G_DAYS_IN_MONTH = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """
    Convert a Gregorian date to the Persian (Jalali) calendar.

    Verified against known dates: 2024-03-20 and 2025-03-21 are Nowruz
    (1403-01-01, 1404-01-01), 1979-02-11 is 1357-11-22, 2000-01-01 is
    1378-10-11.
    """
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) \
        + ((gy2 + 399) // 400) - 80 + gd + _G_DAYS_IN_MONTH[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


# Relative expressions the agent may be handed. Resolving these to a real date
# is the point of the tool: "what happened yesterday" is only searchable once
# yesterday has an actual date attached.
_RELATIVE = {
    "today": 0, "now": 0, "tonight": 0, "this morning": 0, "this evening": 0,
    "yesterday": -1, "last night": -1,
    "tomorrow": 1,
    "day before yesterday": -2, "two days ago": -2,
    "last week": -7, "a week ago": -7,
    "next week": 7,
    "last month": -30, "a month ago": -30,
    "next month": 30,
    "last year": -365, "a year ago": -365,
}

_AGO = re.compile(r"(\d+)\s*(day|week|month|year)s?\s*ago", re.I)
_IN = re.compile(r"in\s*(\d+)\s*(day|week|month|year)s?", re.I)
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def resolve_offset(when: str) -> int:
    """Days from today for a relative expression. Unknown text means today."""
    if not when:
        return 0
    text = " ".join(when.lower().split())
    if text in _RELATIVE:
        return _RELATIVE[text]
    m = _AGO.search(text)
    if m:
        return -int(m.group(1)) * _UNIT_DAYS[m.group(2).lower()]
    m = _IN.search(text)
    if m:
        return int(m.group(1)) * _UNIT_DAYS[m.group(2).lower()]
    return 0


def format_day(d: datetime) -> str:
    """Both calendars for one day, since the household uses both."""
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return (f"{d:%A} {d.day} {d:%B} {d.year} (Gregorian) "
            f"= {jd} {JALALI_MONTHS[jm - 1]} {jy} (Persian/Jalali)")


def describe(when: str = "today", now: datetime | None = None) -> str:
    """
    The time now, plus the date of whatever day was asked about.

    Always gives both calendars. The agent decides which to say aloud, but it
    cannot say one it was never given.
    """
    now = now or datetime.now().astimezone()
    offset = resolve_offset(when)
    target = now + timedelta(days=offset)

    lines = [f"Current time: {now:%H:%M} {now:%Z}.",
             f"Today: {format_day(now)}."]
    if offset:
        label = " ".join(when.split()) or "that day"
        lines.append(f"{label.capitalize()} ({offset:+d} days): {format_day(target)}.")
    return " ".join(lines)

"""Due-date parsing for taskpluck.

Turns the loose ways people write dates in meeting notes -- "by Friday",
"Dec 5", "in 3 days", "EOD" -- into real dates. Everything is relative to
a base date so tests (and --base-date) stay deterministic.

Only the standard library is used. If a line has no recognisable date,
parse_due_date returns None instead of guessing.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

__all__ = ["parse_due_date", "week_start"]

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_MONTH_NAME = r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_WEEKDAY_NAME = (
    r"(Monday|Mon|Tuesday|Tue(?:s)?|Wednesday|Wed|Thursday|Thu(?:rs?)?"
    r"|Friday|Fri|Saturday|Sat|Sunday|Sun)"
)
# Words that can introduce a due date: "by Friday", "due Dec 5", "before Monday".
_LEAD_IN = r"(?:\b(?:by|due|before|until|on)\s+)?"

_ISO_RE = re.compile(
    r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b"
)
_MONTH_DAY_RE = re.compile(
    _LEAD_IN + _MONTH_NAME + r"\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:\s*,?\s*(\d{4}))?",
    re.IGNORECASE,
)
_DAY_MONTH_RE = re.compile(
    _LEAD_IN + r"(\d{1,2})(?:st|nd|rd|th)?\b\s+of\s+" + _MONTH_NAME
    + r"(?:\s*,?\s*(\d{4}))?",
    re.IGNORECASE,
)
# "5 Dec" without the "of" -- kept separate so "5 December 2026" still works.
_DAY_MONTH_BARE_RE = re.compile(
    _LEAD_IN + r"(\d{1,2})(?:st|nd|rd|th)?\b\s+" + _MONTH_NAME
    + r"(?:\s*,?\s*(\d{4}))?",
    re.IGNORECASE,
)
_RELATIVE_RE = re.compile(
    r"\b(?:in\s+)?(a|an|\d+)\s+(day|days|week|weeks|month|months)\b",
    re.IGNORECASE,
)
_NEXT_WEEKDAY_RE = re.compile(
    r"\bnext\s+" + _WEEKDAY_NAME + r"\b", re.IGNORECASE
)
_WEEKDAY_RE = re.compile(_LEAD_IN + _WEEKDAY_NAME + r"\b", re.IGNORECASE)
_TOMORROW_RE = re.compile(r"\btomorrow\b", re.IGNORECASE)
_TODAY_RE = re.compile(r"\btoday\b", re.IGNORECASE)
_EOD_RE = re.compile(r"\b(?:eod|end of (?:the )?day)\b", re.IGNORECASE)
_EOW_RE = re.compile(r"\b(?:eow|end of (?:the )?week)\b", re.IGNORECASE)
_NEXT_WEEK_RE = re.compile(r"\bnext week\b", re.IGNORECASE)


def _clamp_day(year: int, month: int, day: int) -> date:
    """Build a date, pulling the day back to the last day of the month."""
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _add_months(base: date, months: int) -> date:
    total = (base.year * 12 + (base.month - 1)) + months
    return _clamp_day(total // 12, total % 12 + 1, base.day)


def _month_day(
    month_name: str, day: int, year: int | None, base: date
) -> date | None:
    month = _MONTHS[month_name.lower()]
    if year is not None:
        try:
            return date(year, month, day)
        except ValueError:
            return None
    candidate = _clamp_day(base.year, month, day)
    # No year given and the date already passed: it must mean next year.
    if candidate < base:
        candidate = _clamp_day(base.year + 1, month, day)
    return candidate


def _next_weekday(base: date, target: int, skip_this_week: bool) -> date:
    """Next occurrence of weekday ``target`` (0 = Monday).

    Bare weekdays mean the next occurrence (today's weekday means next
    week). "Next <weekday>" means that weekday in the following week,
    counted from the Monday of next week -- so "next Monday" from a
    Wednesday is five days away, not twelve.
    """
    if skip_this_week:
        return base + timedelta(days=(7 - base.weekday()) + target)
    delta = (target - base.weekday()) % 7
    if delta == 0:
        delta = 7
    return base + timedelta(days=delta)


def week_start(d: date) -> date:
    """Monday of the ISO week containing ``d``."""
    return d - timedelta(days=d.weekday())


def parse_due_date(text: str, base: date) -> tuple[date | None, tuple[int, int] | None]:
    """Find a due date in ``text``.

    Returns ``(parsed_date, span)`` where ``span`` is the (start, end)
    character range of the matched date phrase, so callers can strip it
    from the task text. Returns ``(None, None)`` when nothing matches.
    """
    match = _ISO_RE.search(text)
    if match:
        year, month, day = (int(g) for g in match.groups())
        try:
            return date(year, month, day), match.span()
        except ValueError:
            pass  # "2026-02-30" is not a date; fall through to other patterns.

    match = _MONTH_DAY_RE.search(text)
    if match:
        parsed = _month_day(
            match.group(1),
            int(match.group(2)),
            int(match.group(3)) if match.group(3) else None,
            base,
        )
        if parsed is not None:
            return parsed, match.span()

    match = _DAY_MONTH_RE.search(text) or _DAY_MONTH_BARE_RE.search(text)
    if match:
        parsed = _month_day(
            match.group(2),
            int(match.group(1)),
            int(match.group(3)) if match.group(3) else None,
            base,
        )
        if parsed is not None:
            return parsed, match.span()

    match = _NEXT_WEEKDAY_RE.search(text)
    if match:
        target = _WEEKDAYS[match.group(1).lower()]
        return _next_weekday(base, target, skip_this_week=True), match.span()

    match = _WEEKDAY_RE.search(text)
    if match:
        target = _WEEKDAYS[match.group(1).lower()]
        return _next_weekday(base, target, skip_this_week=False), match.span()

    match = _RELATIVE_RE.search(text)
    if match:
        amount = 1 if match.group(1).lower() in ("a", "an") else int(match.group(1))
        unit = match.group(2).lower()
        if unit.startswith("day"):
            return base + timedelta(days=amount), match.span()
        if unit.startswith("week"):
            return base + timedelta(weeks=amount), match.span()
        return _add_months(base, amount), match.span()

    match = _NEXT_WEEK_RE.search(text)
    if match:
        return _next_weekday(base, 0, skip_this_week=True), match.span()

    if _TOMORROW_RE.search(text):
        match = _TOMORROW_RE.search(text)
        assert match is not None
        return base + timedelta(days=1), match.span()

    if _TODAY_RE.search(text) or _EOD_RE.search(text):
        match = _TODAY_RE.search(text) or _EOD_RE.search(text)
        assert match is not None
        return base, match.span()

    if _EOW_RE.search(text):
        match = _EOW_RE.search(text)
        assert match is not None
        # Friday of this week; on a weekend, next Friday.
        return _next_weekday(base, 4, skip_this_week=base.weekday() >= 5), match.span()

    return None, None

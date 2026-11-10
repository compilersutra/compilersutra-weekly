# SPDX-License-Identifier: Apache-2.0
"""Saturday→Friday editorial windows; publish on Saturday (Asia/Kolkata).

Canonical boundaries use Asia/Kolkata so week edges match the editorial
calendar in India. Commit timestamps are converted into this zone before
window membership checks.

Period (inclusive calendar days): Saturday → Friday
Exclusive datetime range: [Sat 00:00, next Sat 00:00)
Publish day: the Saturday at the exclusive end.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from csweekly.models import Window

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc
EDITORIAL_TZ_NAME = "Asia/Kolkata"


def _as_midnight(d: date, tz: ZoneInfo = IST) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=tz)


def _today(tz: ZoneInfo = IST) -> date:
    return datetime.now(tz).date()


def saturday_of_week(on: date) -> date:
    """Saturday that opens the editorial week containing ``on``."""
    # Mon=0 … Sat=5 Sun=6 → days since Saturday
    days_since_saturday = (on.weekday() + 2) % 7
    return on - timedelta(days=days_since_saturday)


def collecting_window(*, as_of: date | None = None) -> Window:
    """Week currently being accumulated (Sat→Fri / next Sat exclusive)."""
    day = as_of or _today()
    start_sat = saturday_of_week(day)
    end_sat = start_sat + timedelta(days=7)
    return Window(
        start=_as_midnight(start_sat),
        end=_as_midnight(end_sat),
        timezone=EDITORIAL_TZ_NAME,
    )


def publishable_window(*, as_of: date | None = None) -> Window:
    """Closed week ready to publish (or last completed week).

    On Saturday (publish day), returns the week that just ended:
    ``[this Saturday − 7d, this Saturday)``.

    Mid-week, returns the previous completed week (the one before the
    currently collecting week). For Friday freeze / process of the
    *upcoming* Saturday issue, use ``collecting_window`` instead.
    """
    day = as_of or _today()
    if day.weekday() == 5:  # Saturday = publish day
        start = day - timedelta(days=7)
        return Window(
            start=_as_midnight(start),
            end=_as_midnight(day),
            timezone=EDITORIAL_TZ_NAME,
        )
    collecting = collecting_window(as_of=day)
    prev_start = collecting.start.date() - timedelta(days=7)
    return Window(
        start=_as_midnight(prev_start),
        end=collecting.start,
        timezone=EDITORIAL_TZ_NAME,
    )


def friday_friday_window(*, as_of: date | None = None) -> Window:
    """Backward-compatible alias for the week used by collect/report demos.

    Mid-week → collecting week (so fixture/demo commits land in-range).
    On Saturday → the week that just closed (publishable).
    """
    day = as_of or _today()
    if day.weekday() == 5:
        return publishable_window(as_of=day)
    return collecting_window(as_of=day)


def publish_saturday(window: Window) -> date:
    """Issues ship on the Saturday at the exclusive end of the window."""
    return window.end.date()


def in_window(when: datetime, window: Window) -> bool:
    """True if ``when`` falls in [start, end). Converts into editorial TZ."""
    tz = ZoneInfo(window.timezone) if window.timezone else IST
    local = when.astimezone(tz)
    return window.start <= local < window.end


def git_since_until(window: Window) -> tuple[str, str]:
    """Args for ``git log --since --until`` (ISO-8601 with offset)."""
    return (
        window.start.isoformat(),
        window.end.isoformat(),
    )


def previous_friday(on: date | None = None) -> date:
    day = on or _today(UTC)
    delta = (day.weekday() - 4) % 7
    return day - timedelta(days=delta)

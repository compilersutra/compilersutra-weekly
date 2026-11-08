# SPDX-License-Identifier: Apache-2.0
"""Friday→Friday UTC reporting windows; publish on Saturday."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from csweekly.models import Window

UTC = timezone.utc


def _as_utc_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def previous_friday(on: date | None = None) -> date:
    """Most recent Friday on or before ``on`` (UTC date)."""
    day = on or datetime.now(UTC).date()
    # Friday = 4
    delta = (day.weekday() - 4) % 7
    return day - timedelta(days=delta)


def friday_friday_window(*, as_of: date | None = None) -> Window:
    """Window closed by the Friday on/before ``as_of``.

    Example: as_of Saturday 8 Nov → end Friday 7 Nov 00:00,
    start previous Friday 31 Oct 00:00.
    """
    end_friday = previous_friday(as_of)
    start_friday = end_friday - timedelta(days=7)
    return Window(
        start=_as_utc_midnight(start_friday),
        end=_as_utc_midnight(end_friday),
        timezone="UTC",
    )


def publish_saturday(window: Window) -> date:
    """Issues ship the Saturday after the window's end Friday."""
    return window.end.date() + timedelta(days=1)


def git_since_until(window: Window) -> tuple[str, str]:
    """Args for ``git log --since --until`` (ISO-8601 UTC)."""
    return (
        window.start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        window.end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

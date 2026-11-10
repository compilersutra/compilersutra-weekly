# SPDX-License-Identifier: Apache-2.0
from datetime import date, datetime
from zoneinfo import ZoneInfo

from csweekly.window import (
    collecting_window,
    friday_friday_window,
    in_window,
    previous_friday,
    publish_saturday,
    publishable_window,
    saturday_of_week,
)


def test_calendar_nov_2026():
    # Ground truth for this repo's first issues.
    assert date(2026, 11, 7).strftime("%A") == "Saturday"
    assert date(2026, 11, 8).strftime("%A") == "Sunday"
    assert date(2026, 10, 31).strftime("%A") == "Saturday"


def test_saturday_of_week():
    assert saturday_of_week(date(2026, 11, 5)) == date(2026, 10, 31)
    assert saturday_of_week(date(2026, 11, 7)) == date(2026, 11, 7)
    assert saturday_of_week(date(2026, 11, 8)) == date(2026, 11, 7)


def test_collecting_midweek():
    w = collecting_window(as_of=date(2026, 11, 5))
    assert w.start.date() == date(2026, 10, 31)
    assert w.end.date() == date(2026, 11, 7)
    assert w.timezone == "Asia/Kolkata"
    assert publish_saturday(w) == date(2026, 11, 7)


def test_publishable_on_saturday_ship_day():
    w = publishable_window(as_of=date(2026, 11, 7))
    assert w.start.date() == date(2026, 10, 31)
    assert w.end.date() == date(2026, 11, 7)
    assert publish_saturday(w) == date(2026, 11, 7)


def test_publishable_midweek_is_previous_completed():
    w = publishable_window(as_of=date(2026, 11, 5))
    assert w.start.date() == date(2026, 10, 24)
    assert w.end.date() == date(2026, 10, 31)


def test_friday_friday_alias_midweek_is_collecting():
    w = friday_friday_window(as_of=date(2026, 11, 5))
    assert w.start.date() == date(2026, 10, 31)
    assert publish_saturday(w) == date(2026, 11, 7)


def test_friday_friday_alias_on_saturday_is_publishable():
    w = friday_friday_window(as_of=date(2026, 11, 7))
    assert publish_saturday(w) == date(2026, 11, 7)
    assert w.start.date() == date(2026, 10, 31)


def test_previous_friday_on_sunday():
    assert date(2026, 11, 8).weekday() == 6
    assert previous_friday(date(2026, 11, 8)) == date(2026, 11, 6)


def test_in_window_converts_to_editorial_tz():
    w = collecting_window(as_of=date(2026, 11, 5))
    # Friday evening IST still inside [Sat, next Sat)
    fri = datetime(2026, 11, 6, 23, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert in_window(fri, w)
    sat_publish = datetime(2026, 11, 7, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert not in_window(sat_publish, w)

# SPDX-License-Identifier: Apache-2.0
from datetime import date

from csweekly.window import friday_friday_window, previous_friday, publish_saturday


def test_previous_friday_on_sunday():
    # 2026-11-08 is Sunday → previous Friday is 2026-11-06
    assert date(2026, 11, 8).weekday() == 6
    assert previous_friday(date(2026, 11, 8)) == date(2026, 11, 6)


def test_friday_friday_window():
    w = friday_friday_window(as_of=date(2026, 11, 8))
    assert w.start.date() == date(2026, 10, 30)
    assert w.end.date() == date(2026, 11, 6)
    assert publish_saturday(w) == date(2026, 11, 7)


def test_as_of_saturday_closes_that_friday():
    # Saturday publish day itself
    w = friday_friday_window(as_of=date(2026, 11, 7))
    assert w.end.date() == date(2026, 11, 6)
    assert publish_saturday(w) == date(2026, 11, 7)

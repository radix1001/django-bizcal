from __future__ import annotations

from datetime import date, timedelta

from django_bizcal import WorkingCalendar


def test_business_interval_duration_reflects_dst_gap() -> None:
    calendar = WorkingCalendar(
        tz="America/New_York",
        weekly_schedule={6: [("01:30", "03:30")]},
    )
    windows = calendar.business_windows_for_day(date(2026, 3, 8))
    assert len(windows) == 1
    assert windows[0].duration() == timedelta(hours=1)


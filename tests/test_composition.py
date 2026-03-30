from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django_bizcal import (
    DifferenceCalendar,
    IntersectionCalendar,
    OverrideCalendar,
    UnionCalendar,
    WorkingCalendar,
)


def test_union_calendar_merges_child_windows() -> None:
    left = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("09:00", "12:00")]},
    )
    right = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("11:00", "15:00")]},
    )
    union = UnionCalendar([left, right], tz="UTC")
    windows = union.business_windows_for_day(date(2026, 3, 2))
    assert len(windows) == 1
    assert windows[0].start == datetime(2026, 3, 2, 9, 0, tzinfo=ZoneInfo("UTC"))
    assert windows[0].end == datetime(2026, 3, 2, 15, 0, tzinfo=ZoneInfo("UTC"))


def test_intersection_calendar_keeps_only_shared_time() -> None:
    left = WorkingCalendar(tz="UTC", weekly_schedule={0: [("09:00", "13:00")]})
    right = WorkingCalendar(tz="UTC", weekly_schedule={0: [("11:00", "15:00")]})
    calendar = IntersectionCalendar([left, right], tz="UTC")
    windows = calendar.business_windows_for_day(date(2026, 3, 2))
    assert len(windows) == 1
    assert windows[0].start.hour == 11
    assert windows[0].end.hour == 13


def test_difference_calendar_subtracts_blocked_windows() -> None:
    base = WorkingCalendar(tz="UTC", weekly_schedule={0: [("09:00", "18:00")]})
    blocker = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("12:00", "13:00"), ("15:00", "16:00")]},
    )
    calendar = DifferenceCalendar(base, blocker, tz="UTC")
    windows = calendar.business_windows_for_day(date(2026, 3, 2))
    assert [(window.start.hour, window.end.hour) for window in windows] == [
        (9, 12),
        (13, 15),
        (16, 18),
    ]


def test_override_calendar_replaces_specific_dates() -> None:
    base = WorkingCalendar(
        tz="America/Santiago",
        weekly_schedule={0: [("09:00", "18:00")]},
    )
    calendar = OverrideCalendar(
        base,
        overrides={
            "2026-03-02": [("10:00", "12:00")],
            "2026-03-09": None,
        },
    )
    first = calendar.business_windows_for_day(date(2026, 3, 2))
    second = calendar.business_windows_for_day(date(2026, 3, 9))
    assert len(first) == 1
    assert first[0].start.hour == 10
    assert second == ()


def test_union_calendar_projects_children_across_timezones() -> None:
    cl = WorkingCalendar(
        tz="America/Santiago",
        weekly_schedule={0: [("09:00", "10:00")]},
    )
    mx = WorkingCalendar(
        tz="America/Mexico_City",
        weekly_schedule={0: [("09:00", "10:00")]},
    )
    union = UnionCalendar([cl, mx], tz="UTC")
    windows = union.business_windows_for_day(date(2026, 1, 5), tz="UTC")
    assert len(windows) == 2
    assert {window.start.hour for window in windows} == {12, 15}


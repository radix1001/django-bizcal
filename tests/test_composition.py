from __future__ import annotations

from datetime import date, datetime, timedelta
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



def test_union_of_a_day_shift_and_a_night_shift_covers_both_sides_of_midnight() -> None:
    day_shift = WorkingCalendar(tz="UTC", weekly_schedule={1: [("09:00", "18:00")]})
    night_shift = WorkingCalendar(tz="UTC", weekly_schedule={0: [("22:00", "06:00", 1)]})
    union = UnionCalendar([day_shift, night_shift], tz="UTC")

    monday = union.business_windows_for_day(date(2026, 3, 2))
    tuesday = union.business_windows_for_day(date(2026, 3, 3))

    assert [(window.start.hour, window.end.hour) for window in monday] == [(22, 0)]
    assert [(window.start.hour, window.end.hour) for window in tuesday] == [(0, 6), (9, 18)]
    assert union.business_time_between(
        datetime(2026, 3, 2, 22, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2026, 3, 3, 18, 0, tzinfo=ZoneInfo("UTC")),
    ) == timedelta(hours=17)


def test_intersection_and_difference_work_across_the_midnight_boundary() -> None:
    night_shift = WorkingCalendar(tz="UTC", weekly_schedule={0: [("22:00", "06:00", 1)]})
    early_hours = WorkingCalendar(tz="UTC", weekly_schedule={1: [("00:00", "03:00")]})

    intersection = IntersectionCalendar([night_shift, early_hours], tz="UTC")
    difference = DifferenceCalendar(night_shift, early_hours, tz="UTC")

    assert [
        (window.start, window.end)
        for window in intersection.business_windows_for_day(date(2026, 3, 3))
    ] == [
        (
            datetime(2026, 3, 3, 0, 0, tzinfo=ZoneInfo("UTC")),
            datetime(2026, 3, 3, 3, 0, tzinfo=ZoneInfo("UTC")),
        )
    ]
    assert intersection.business_windows_for_day(date(2026, 3, 2)) == ()
    assert [
        (window.start, window.end)
        for window in difference.business_windows_for_day(date(2026, 3, 3))
    ] == [
        (
            datetime(2026, 3, 3, 3, 0, tzinfo=ZoneInfo("UTC")),
            datetime(2026, 3, 3, 6, 0, tzinfo=ZoneInfo("UTC")),
        )
    ]


def test_override_calendar_materializes_an_overnight_override() -> None:
    base = WorkingCalendar(tz="UTC", weekly_schedule={0: [("09:00", "18:00")]})
    calendar = OverrideCalendar(base, overrides={"2026-03-02": [("22:00", "06:00", 1)]})

    monday = calendar.business_windows_for_day(date(2026, 3, 2))
    tuesday = calendar.business_windows_for_day(date(2026, 3, 3))

    assert [(window.start.hour, window.end.hour) for window in monday] == [(22, 0)]
    assert [(window.start.hour, window.end.hour) for window in tuesday] == [(0, 6)]

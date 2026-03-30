from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from django_bizcal import WorkingCalendar
from django_bizcal.exceptions import CalendarRangeError


def test_is_business_day_and_time(support_calendar: WorkingCalendar) -> None:
    tz = ZoneInfo("America/Santiago")
    assert support_calendar.is_business_day(date(2026, 3, 2)) is True
    assert support_calendar.is_business_day(date(2026, 3, 7)) is False
    assert (
        support_calendar.is_business_time(datetime(2026, 3, 2, 10, 30, tzinfo=tz)) is True
    )
    assert support_calendar.is_business_time(datetime(2026, 3, 2, 13, 30, tzinfo=tz)) is False


def test_day_overrides_replace_normal_schedule(support_calendar: WorkingCalendar) -> None:
    tz = ZoneInfo("America/Santiago")
    windows = support_calendar.business_windows_for_day(date(2026, 12, 24))
    assert len(windows) == 1
    assert windows[0].start == datetime(2026, 12, 24, 9, 0, tzinfo=tz)
    assert windows[0].end == datetime(2026, 12, 24, 12, 0, tzinfo=tz)
    assert support_calendar.is_business_day(date(2026, 12, 31)) is False


def test_add_business_hours_crosses_gaps_and_days(support_calendar: WorkingCalendar) -> None:
    tz = ZoneInfo("America/Santiago")
    start = datetime(2026, 3, 2, 12, 30, tzinfo=tz)
    assert support_calendar.add_business_hours(start, 2) == datetime(
        2026,
        3,
        2,
        15,
        30,
        tzinfo=tz,
    )

    friday = datetime(2026, 3, 6, 16, 30, tzinfo=tz)
    assert support_calendar.add_business_hours(friday, 2) == datetime(
        2026,
        3,
        9,
        10,
        30,
        tzinfo=tz,
    )


def test_add_business_time_supports_negative_deltas(support_calendar: WorkingCalendar) -> None:
    tz = ZoneInfo("America/Santiago")
    start = datetime(2026, 3, 2, 15, 0, tzinfo=tz)
    assert support_calendar.add_business_time(start, timedelta(hours=-2)) == datetime(
        2026,
        3,
        2,
        12,
        0,
        tzinfo=tz,
    )


def test_business_time_between_counts_only_open_windows(support_calendar: WorkingCalendar) -> None:
    tz = ZoneInfo("America/Santiago")
    start = datetime(2026, 3, 2, 12, 0, tzinfo=tz)
    end = datetime(2026, 3, 2, 15, 0, tzinfo=tz)
    assert support_calendar.business_time_between(start, end) == timedelta(hours=2)
    assert support_calendar.business_hours_between(end, start) == -2.0


def test_navigation_helpers_snap_to_open_time_and_boundary(
    support_calendar: WorkingCalendar,
) -> None:
    tz = ZoneInfo("America/Santiago")
    current = datetime(2026, 3, 2, 10, 30, tzinfo=tz)
    assert support_calendar.next_business_datetime(current) == current
    assert support_calendar.previous_business_datetime(current) == current
    assert support_calendar.next_business_datetime(
        datetime(2026, 3, 2, 13, 30, tzinfo=tz)
    ) == datetime(2026, 3, 2, 14, 0, tzinfo=tz)
    assert support_calendar.previous_business_datetime(
        datetime(2026, 3, 2, 13, 30, tzinfo=tz)
    ) == datetime(2026, 3, 2, 13, 0, tzinfo=tz)


def test_day_level_helpers_cover_iteration_count_and_navigation(
    support_calendar: WorkingCalendar,
) -> None:
    assert list(support_calendar.iter_business_days("2026-03-02", "2026-03-06")) == [
        date(2026, 3, 2),
        date(2026, 3, 3),
        date(2026, 3, 4),
        date(2026, 3, 5),
        date(2026, 3, 6),
    ]
    assert support_calendar.list_business_days("2026-03-05", "2026-03-08") == [
        date(2026, 3, 5),
        date(2026, 3, 6),
    ]
    assert support_calendar.count_business_days("2026-03-05", "2026-03-08") == 2
    assert support_calendar.count_business_days(
        "2026-03-05",
        "2026-03-06",
        inclusive=False,
    ) == 1
    assert support_calendar.next_business_day("2026-03-07") == date(2026, 3, 9)
    assert support_calendar.previous_business_day("2026-03-07") == date(2026, 3, 6)


def test_opening_and_closing_helpers_expose_day_boundaries(
    support_calendar: WorkingCalendar,
) -> None:
    tz = ZoneInfo("America/Santiago")
    assert support_calendar.opening_for_day("2026-03-02") == datetime(
        2026,
        3,
        2,
        9,
        0,
        tzinfo=tz,
    )
    assert support_calendar.closing_for_day("2026-03-02") == datetime(
        2026,
        3,
        2,
        18,
        0,
        tzinfo=tz,
    )
    assert support_calendar.opening_for_day("2026-03-07") is None
    assert support_calendar.closing_for_day("2026-03-07") is None
    assert support_calendar.next_opening_datetime(
        datetime(2026, 3, 2, 13, 30, tzinfo=tz)
    ) == datetime(2026, 3, 2, 14, 0, tzinfo=tz)
    assert support_calendar.previous_closing_datetime(
        datetime(2026, 3, 2, 13, 30, tzinfo=tz)
    ) == datetime(2026, 3, 2, 13, 0, tzinfo=tz)


def test_from_country_uses_official_holidays() -> None:
    calendar = WorkingCalendar.from_country(
        country="CL",
        years=[2026],
        tz="America/Santiago",
        weekly_schedule={
            0: [("09:00", "18:00")],
            1: [("09:00", "18:00")],
            2: [("09:00", "18:00")],
            3: [("09:00", "18:00")],
            4: [("09:00", "18:00")],
        },
    )
    assert calendar.is_business_day(date(2026, 1, 1)) is False


def test_holiday_provider_raises_outside_configured_years() -> None:
    calendar = WorkingCalendar.from_country(
        country="CL",
        years=[2026],
        tz="America/Santiago",
        weekly_schedule={0: [("09:00", "18:00")]},
    )
    with pytest.raises(CalendarRangeError):
        calendar.is_business_day(date(2027, 1, 1))

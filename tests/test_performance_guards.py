from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django_bizcal.calendars.base import (
    _LOCAL_DAY_WINDOW_CACHE_SIZE,
    BusinessCalendar,
)
from django_bizcal.intervals import BusinessInterval


class CountingCalendar(BusinessCalendar):
    def __init__(self) -> None:
        super().__init__("UTC")
        self.calls_by_day: dict[date, int] = {}

    def _business_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
        self.calls_by_day[day] = self.calls_by_day.get(day, 0) + 1
        if day.weekday() >= 5:
            return ()
        return (
            BusinessInterval(
                start=datetime.combine(day, time(9, 0), tzinfo=self.tz),
                end=datetime.combine(day, time(18, 0), tzinfo=self.tz),
            ),
        )


def test_business_windows_for_day_reuses_cached_local_day_results() -> None:
    calendar = CountingCalendar()
    day = date(2026, 3, 2)

    first = calendar.business_windows_for_day(day)
    second = calendar.business_windows_for_day(day)

    assert first is second
    assert calendar.calls_by_day == {day: 1}


def test_business_windows_for_range_reuses_cached_local_day_results() -> None:
    calendar = CountingCalendar()
    start = datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("UTC"))
    end = datetime(2026, 3, 4, 17, 0, tzinfo=ZoneInfo("UTC"))

    first = calendar.business_windows_for_range(start, end)
    second = calendar.business_windows_for_range(start, end)

    assert first == second
    assert all(count == 1 for count in calendar.calls_by_day.values())
    assert set(calendar.calls_by_day) == {
        date(2026, 3, 1),
        date(2026, 3, 2),
        date(2026, 3, 3),
        date(2026, 3, 4),
        date(2026, 3, 5),
    }


def test_local_day_window_cache_is_bounded_per_calendar_instance() -> None:
    calendar = CountingCalendar()
    start_day = date(2026, 1, 1)

    for offset in range(_LOCAL_DAY_WINDOW_CACHE_SIZE + 5):
        calendar.business_windows_for_day(start_day + timedelta(days=offset))

    assert len(calendar._local_day_window_cache) == _LOCAL_DAY_WINDOW_CACHE_SIZE
    assert calendar.calls_by_day[start_day] == 1

    calendar.business_windows_for_day(start_day)

    assert calendar.calls_by_day[start_day] == 2

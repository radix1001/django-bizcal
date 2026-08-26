from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from django_bizcal import WorkingCalendar

UTC = ZoneInfo("UTC")


def test_business_interval_duration_reflects_dst_gap() -> None:
    calendar = WorkingCalendar(
        tz="America/New_York",
        weekly_schedule={6: [("01:30", "03:30")]},
    )
    windows = calendar.business_windows_for_day(date(2026, 3, 8))
    assert len(windows) == 1
    assert windows[0].duration() == timedelta(hours=1)



def test_overnight_block_absorbs_the_spring_forward_gap() -> None:
    santiago = ZoneInfo("America/Santiago")
    calendar = WorkingCalendar(
        tz=santiago,
        weekly_schedule={5: [("22:00", "06:00", 1)]},
    )
    saturday = date(2026, 9, 5)
    sunday = date(2026, 9, 6)

    blocks = calendar.business_blocks_for_day(saturday)
    saturday_windows = calendar.business_windows_for_day(saturday)
    sunday_windows = calendar.business_windows_for_day(sunday)

    assert blocks[0].duration() == timedelta(hours=7)
    assert saturday_windows[-1].end == sunday_windows[0].start
    assert (
        saturday_windows[0].duration() + sunday_windows[0].duration()
    ) == timedelta(hours=7)
    assert calendar.business_time_between(
        datetime(2026, 9, 5, 22, 0, tzinfo=santiago),
        datetime(2026, 9, 6, 6, 0, tzinfo=santiago),
    ) == timedelta(hours=7)
    for window in (*saturday_windows, *sunday_windows):
        assert window.start == window.start.astimezone(UTC).astimezone(santiago)
        assert window.end == window.end.astimezone(UTC).astimezone(santiago)
    assert sunday_windows[0].start.hour == 1


def test_overnight_block_absorbs_the_fall_back_repeated_hour() -> None:
    santiago = ZoneInfo("America/Santiago")
    calendar = WorkingCalendar(
        tz=santiago,
        weekly_schedule={5: [("22:00", "06:00", 1)]},
    )
    saturday = date(2026, 4, 4)
    sunday = date(2026, 4, 5)

    blocks = calendar.business_blocks_for_day(saturday)
    saturday_windows = calendar.business_windows_for_day(saturday)
    sunday_windows = calendar.business_windows_for_day(sunday)

    assert blocks[0].duration() == timedelta(hours=9)
    assert saturday_windows[-1].end == sunday_windows[0].start
    assert (
        saturday_windows[0].duration() + sunday_windows[0].duration()
    ) == timedelta(hours=9)
    assert calendar.add_business_hours(
        datetime(2026, 4, 4, 22, 0, tzinfo=santiago), 9
    ) == datetime(2026, 4, 5, 6, 0, tzinfo=santiago)


@pytest.mark.parametrize(
    "tz_key",
    ["America/Santiago", "America/Asuncion", "Australia/Lord_Howe", "Pacific/Chatham"],
)
def test_nightly_blocks_tile_every_day_of_a_year_in_awkward_timezones(tz_key: str) -> None:
    tz = ZoneInfo(tz_key)
    calendar = WorkingCalendar(
        tz=tz,
        weekly_schedule={weekday: [("22:00", "06:00", 1)] for weekday in range(7)},
    )

    day = date(2026, 1, 1)
    while day < date(2027, 1, 1):
        block = calendar.business_blocks_for_day(day)[0]
        today = calendar.business_windows_for_day(day)
        tomorrow = calendar.business_windows_for_day(day + timedelta(days=1))

        assert today[-1].end == tomorrow[0].start
        assert today[-1].duration() + tomorrow[0].duration() == block.duration()
        for window in (today[-1], tomorrow[0]):
            for boundary in (window.start, window.end):
                assert boundary == boundary.astimezone(UTC).astimezone(tz)
        day += timedelta(days=1)

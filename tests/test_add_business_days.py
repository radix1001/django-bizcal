from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from django_bizcal import UnionCalendar, ValidationError, WorkingCalendar

SANTIAGO = ZoneInfo("America/Santiago")
NEW_YORK = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def santiago(*args: int) -> datetime:
    return datetime(*args, tzinfo=SANTIAGO)


# --- forward ------------------------------------------------------------------


def test_keeps_wall_clock_on_the_next_business_day(support_calendar: WorkingCalendar) -> None:
    assert support_calendar.add_business_days(santiago(2026, 3, 4, 16, 30), 1) == santiago(
        2026, 3, 5, 16, 30
    )
    assert support_calendar.add_business_days(santiago(2026, 3, 2, 10, 0), 4) == santiago(
        2026, 3, 6, 10, 0
    )


def test_skips_weekends_and_closed_days(support_calendar: WorkingCalendar) -> None:
    assert support_calendar.add_business_days(santiago(2026, 3, 6, 10, 0), 1) == santiago(
        2026, 3, 9, 10, 0
    )
    assert support_calendar.add_business_days(santiago(2026, 12, 30, 10, 0), 1) == santiago(
        2027, 1, 1, 10, 0
    )


def test_skips_official_holidays() -> None:
    calendar = WorkingCalendar.from_country(
        country="CL",
        years=[2026],
        tz=SANTIAGO,
        weekly_schedule={weekday: [("09:00", "18:00")] for weekday in range(5)},
    )

    assert calendar.add_business_days(santiago(2026, 10, 9, 11, 0), 1) == santiago(
        2026, 10, 13, 11, 0
    )


def test_start_outside_business_time_is_anchored_to_the_next_business_datetime(
    support_calendar: WorkingCalendar,
) -> None:
    assert support_calendar.add_business_days(santiago(2026, 3, 2, 20, 0), 1) == santiago(
        2026, 3, 4, 9, 0
    )
    assert support_calendar.add_business_days(santiago(2026, 3, 2, 13, 30), 1) == santiago(
        2026, 3, 3, 14, 0
    )
    assert support_calendar.add_business_days(santiago(2026, 3, 7, 10, 0), 1) == santiago(
        2026, 3, 10, 9, 0
    )


def test_snaps_back_to_closing_on_a_shorter_day(support_calendar: WorkingCalendar) -> None:
    assert support_calendar.add_business_days(santiago(2026, 3, 5, 17, 30), 1) == santiago(
        2026, 3, 6, 17, 0
    )
    assert support_calendar.add_business_days(santiago(2026, 12, 23, 15, 0), 1) == santiago(
        2026, 12, 24, 12, 0
    )


def test_snaps_forward_to_a_later_opening() -> None:
    calendar = WorkingCalendar(
        tz=SANTIAGO,
        weekly_schedule={
            0: [("08:00", "14:00")],
            1: [("10:00", "12:00"), ("15:00", "18:00")],
        },
    )

    assert calendar.add_business_days(santiago(2026, 3, 2, 8, 30), 1) == santiago(
        2026, 3, 3, 10, 0
    )
    assert calendar.add_business_days(santiago(2026, 3, 2, 13, 0), 1) == santiago(
        2026, 3, 3, 15, 0
    )


# --- zero and backward ----------------------------------------------------------


def test_zero_days_matches_adding_zero_business_time(support_calendar: WorkingCalendar) -> None:
    for start in (santiago(2026, 3, 4, 16, 30), santiago(2026, 3, 4, 20, 0)):
        assert support_calendar.add_business_days(start, 0) == support_calendar.add_business_time(
            start, timedelta(0)
        )


def test_negative_days_move_backwards(support_calendar: WorkingCalendar) -> None:
    assert support_calendar.add_business_days(santiago(2026, 3, 9, 10, 0), -1) == santiago(
        2026, 3, 6, 10, 0
    )
    assert support_calendar.add_business_days(santiago(2026, 3, 5, 16, 30), -3) == santiago(
        2026, 3, 2, 16, 30
    )


def test_negative_days_anchor_to_the_previous_business_datetime(
    support_calendar: WorkingCalendar,
) -> None:
    assert support_calendar.add_business_days(santiago(2026, 3, 3, 20, 0), -1) == santiago(
        2026, 3, 2, 18, 0
    )
    assert support_calendar.add_business_days(santiago(2026, 3, 3, 13, 30), -1) == santiago(
        2026, 3, 2, 13, 0
    )


def test_forward_and_backward_round_trip(support_calendar: WorkingCalendar) -> None:
    start = santiago(2026, 3, 3, 11, 15)
    for days in (1, 3, 7, 20):
        forward = support_calendar.add_business_days(start, days)
        assert support_calendar.add_business_days(forward, -days) == start


# --- timezones ------------------------------------------------------------------


def test_result_keeps_the_timezone_of_the_start(support_calendar: WorkingCalendar) -> None:
    start = datetime(2026, 3, 4, 19, 30, tzinfo=UTC)

    result = support_calendar.add_business_days(start, 1)

    assert result.tzinfo is UTC
    assert result == santiago(2026, 3, 5, 16, 30)


def test_keeps_wall_clock_across_a_dst_transition() -> None:
    calendar = WorkingCalendar(
        tz=NEW_YORK,
        weekly_schedule={weekday: [("09:00", "17:00")] for weekday in range(5)},
    )
    start = datetime(2026, 3, 6, 10, 0, tzinfo=NEW_YORK)

    result = calendar.add_business_days(start, 1)

    assert result == datetime(2026, 3, 9, 10, 0, tzinfo=NEW_YORK)
    assert result.astimezone(UTC) - start.astimezone(UTC) == timedelta(hours=71)


def test_wall_clock_inside_a_dst_gap_is_normalized() -> None:
    calendar = WorkingCalendar(
        tz=NEW_YORK,
        weekly_schedule={5: [("01:30", "04:00")], 6: [("01:30", "04:00")]},
    )

    result = calendar.add_business_days(datetime(2026, 3, 7, 2, 30, tzinfo=NEW_YORK), 1)

    assert result == datetime(2026, 3, 8, 3, 30, tzinfo=NEW_YORK)
    assert result == result.astimezone(UTC).astimezone(NEW_YORK)
    assert result.utcoffset() == timedelta(hours=-4)


# --- other calendar shapes -------------------------------------------------------


def test_overnight_blocks_keep_the_wall_clock() -> None:
    calendar = WorkingCalendar(
        tz=SANTIAGO,
        weekly_schedule={weekday: [("22:00", "06:00", 1)] for weekday in range(5)},
    )

    assert calendar.add_business_days(santiago(2026, 3, 2, 23, 0), 1) == santiago(
        2026, 3, 3, 23, 0
    )
    assert calendar.add_business_days(santiago(2026, 3, 3, 3, 0), 1) == santiago(
        2026, 3, 4, 3, 0
    )


def test_composite_calendars_support_business_days() -> None:
    weekdays = WorkingCalendar(
        tz=SANTIAGO,
        weekly_schedule={weekday: [("09:00", "18:00")] for weekday in range(5)},
    )
    saturdays = WorkingCalendar(tz=SANTIAGO, weekly_schedule={5: [("09:00", "13:00")]})
    calendar = UnionCalendar([weekdays, saturdays], tz=SANTIAGO)

    assert calendar.add_business_days(santiago(2026, 3, 6, 10, 0), 1) == santiago(
        2026, 3, 7, 10, 0
    )
    assert calendar.add_business_days(santiago(2026, 3, 6, 15, 0), 1) == santiago(
        2026, 3, 7, 13, 0
    )


# --- validation -----------------------------------------------------------------


def test_rejects_naive_datetimes(support_calendar: WorkingCalendar) -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        support_calendar.add_business_days(datetime(2026, 3, 4, 16, 30), 1)


@pytest.mark.parametrize("days", [1.5, True, "1"])
def test_rejects_non_integer_days(support_calendar: WorkingCalendar, days: object) -> None:
    with pytest.raises(ValidationError, match="days must be an integer"):
        support_calendar.add_business_days(santiago(2026, 3, 4, 16, 30), days)  # type: ignore[arg-type]

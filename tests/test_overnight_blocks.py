from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from django_bizcal import (
    DifferenceCalendar,
    IntersectionCalendar,
    OverrideCalendar,
    ScheduleBlock,
    TimeWindow,
    UnionCalendar,
    WorkingCalendar,
    build_schedule_blocks,
)
from django_bizcal.exceptions import ValidationError
from django_bizcal.providers import SetHolidayProvider

UTC = ZoneInfo("UTC")
SUNDAY = date(2026, 3, 1)
MONDAY = date(2026, 3, 2)
TUESDAY = date(2026, 3, 3)


def night_shift_calendar(**kwargs: object) -> WorkingCalendar:
    """Monday night shift running from 22:00 to 06:00 on Tuesday."""
    return WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("22:00", "06:00", 1)]},
        **kwargs,  # type: ignore[arg-type]
    )


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=UTC)


# --- numeric correctness -------------------------------------------------------


def test_business_time_between_covers_the_whole_night_without_a_midnight_gap() -> None:
    calendar = night_shift_calendar()

    assert calendar.business_time_between(at(MONDAY, 22), at(TUESDAY, 6)) == timedelta(hours=8)


def test_add_business_hours_crosses_midnight_without_drift() -> None:
    calendar = night_shift_calendar()

    assert calendar.add_business_hours(at(MONDAY, 23), 4) == at(TUESDAY, 3)


def test_subtract_business_hours_crosses_midnight_without_drift() -> None:
    calendar = night_shift_calendar()

    assert calendar.add_business_hours(at(TUESDAY, 3), -4) == at(MONDAY, 23)


def test_business_windows_for_range_returns_a_single_merged_interval() -> None:
    calendar = night_shift_calendar()

    windows = calendar.business_windows_for_range(at(MONDAY, 22), at(TUESDAY, 6))

    assert len(windows) == 1
    assert windows[0].start == at(MONDAY, 22)
    assert windows[0].end == at(TUESDAY, 6)


def test_business_windows_for_day_clips_the_block_at_midnight() -> None:
    calendar = night_shift_calendar()

    monday = calendar.business_windows_for_day(MONDAY)
    tuesday = calendar.business_windows_for_day(TUESDAY)

    assert [(window.start, window.end) for window in monday] == [(at(MONDAY, 22), at(TUESDAY, 0))]
    assert [(window.start, window.end) for window in tuesday] == [(at(TUESDAY, 0), at(TUESDAY, 6))]


def test_clipped_days_tile_the_night_exactly() -> None:
    calendar = night_shift_calendar()
    monday = calendar.business_windows_for_day(MONDAY)
    tuesday = calendar.business_windows_for_day(TUESDAY)

    assert monday[-1].end == tuesday[0].start
    assert monday[0].duration() + tuesday[0].duration() == timedelta(hours=8)


def test_business_windows_for_day_renders_the_night_in_another_timezone() -> None:
    calendar = night_shift_calendar()
    santiago = ZoneInfo("America/Santiago")

    windows = calendar.business_windows_for_day(MONDAY, tz=santiago)

    assert sum((window.duration() for window in windows), timedelta(0)) == timedelta(hours=5)
    assert windows[0].start == at(MONDAY, 22).astimezone(santiago)


# --- anchoring semantics -------------------------------------------------------


def test_a_day_covered_only_by_a_spillover_tail_is_a_business_day() -> None:
    calendar = night_shift_calendar()

    assert calendar.is_business_day(TUESDAY) is True
    assert calendar.is_business_day(MONDAY) is True
    assert calendar.is_business_day(date(2026, 3, 4)) is False
    assert calendar.list_business_days(MONDAY, date(2026, 3, 8)) == [MONDAY, TUESDAY]


def test_is_business_time_covers_both_sides_of_midnight() -> None:
    calendar = night_shift_calendar()

    assert calendar.is_business_time(at(MONDAY, 23)) is True
    assert calendar.is_business_time(at(TUESDAY, 3)) is True
    assert calendar.is_business_time(at(TUESDAY, 7)) is False


def test_business_blocks_for_day_returns_the_whole_unclipped_block() -> None:
    calendar = night_shift_calendar()

    blocks = calendar.business_blocks_for_day(MONDAY)

    assert [(block.start, block.end) for block in blocks] == [(at(MONDAY, 22), at(TUESDAY, 6))]
    assert calendar.business_blocks_for_day(TUESDAY) == ()


def test_business_blocks_for_day_is_not_exposed_on_composites() -> None:
    calendar = night_shift_calendar()
    union = UnionCalendar([calendar], tz="UTC")

    assert hasattr(calendar, "business_blocks_for_day")
    for composite in (
        union,
        IntersectionCalendar([calendar], tz="UTC"),
        DifferenceCalendar(calendar, calendar, tz="UTC"),
        OverrideCalendar(calendar, overrides={}),
    ):
        assert not hasattr(composite, "business_blocks_for_day")


def test_closing_for_day_reports_the_civil_day_boundary() -> None:
    calendar = night_shift_calendar()

    assert calendar.closing_for_day(MONDAY) == at(TUESDAY, 0)
    assert calendar.opening_for_day(TUESDAY) == at(TUESDAY, 0)


def test_business_deadline_at_close_follows_the_block_past_midnight() -> None:
    calendar = night_shift_calendar()

    deadline = calendar.business_deadline_at_close(MONDAY, 1, include_start=True)

    assert deadline == at(TUESDAY, 6)


def test_close_of_business_policy_follows_the_block_past_midnight() -> None:
    calendar = night_shift_calendar()

    resolved = calendar.resolve_deadline_policy_dict(
        at(MONDAY, 23),
        {"type": "same_business_day", "at": "closing"},
    )

    assert resolved.deadline == at(TUESDAY, 6)


def test_closing_on_a_composite_stops_at_the_civil_day_boundary() -> None:
    calendar = night_shift_calendar()
    union = UnionCalendar([calendar], tz="UTC")

    resolved = union.resolve_deadline_policy_dict(
        at(MONDAY, 23),
        {"type": "same_business_day", "at": "closing"},
    )

    assert resolved.deadline == at(TUESDAY, 0)


def test_previous_business_datetime_lands_exactly_on_the_midnight_boundary() -> None:
    calendar = night_shift_calendar()

    assert calendar.previous_business_datetime(at(TUESDAY, 12)) == at(TUESDAY, 6)
    assert calendar.previous_closing_datetime(at(TUESDAY, 12)) == at(TUESDAY, 6)


# --- holidays ------------------------------------------------------------------


def sunday_night_calendar(*, truncates: bool, holidays: list[date]) -> WorkingCalendar:
    """Sunday night shift from 22:00 to 06:00 on Monday."""
    return WorkingCalendar(
        tz="UTC",
        weekly_schedule={6: [("22:00", "06:00", 1)]},
        holiday_provider=SetHolidayProvider.from_dates(holidays),
        holiday_truncates_overnight=truncates,
    )


def test_holiday_on_the_target_day_keeps_the_night_shift_tail_by_default() -> None:
    calendar = sunday_night_calendar(truncates=False, holidays=[MONDAY])

    monday = calendar.business_windows_for_day(MONDAY)

    assert [(window.start, window.end) for window in monday] == [(at(MONDAY, 0), at(MONDAY, 6))]
    assert calendar.business_time_between(at(SUNDAY, 22), at(MONDAY, 6)) == timedelta(hours=8)


def test_holiday_on_the_target_day_truncates_at_midnight_when_configured() -> None:
    calendar = sunday_night_calendar(truncates=True, holidays=[MONDAY])

    assert calendar.business_windows_for_day(MONDAY) == ()
    assert calendar.business_windows_for_day(SUNDAY)[0].end == at(MONDAY, 0)
    assert calendar.is_business_day(MONDAY) is False


def test_holiday_on_the_starting_day_suppresses_the_whole_block() -> None:
    for truncates in (False, True):
        calendar = sunday_night_calendar(truncates=truncates, holidays=[SUNDAY])

        assert calendar.business_windows_for_day(SUNDAY) == ()
        assert calendar.business_windows_for_day(MONDAY) == ()


def test_closing_day_override_truncates_the_tail_only_when_configured() -> None:
    kept = WorkingCalendar(
        tz="UTC",
        weekly_schedule={6: [("22:00", "06:00", 1)]},
        day_overrides={MONDAY: None},
    )
    truncated = WorkingCalendar(
        tz="UTC",
        weekly_schedule={6: [("22:00", "06:00", 1)]},
        day_overrides={MONDAY: None},
        holiday_truncates_overnight=True,
    )

    assert kept.business_windows_for_day(MONDAY)[0].end == at(MONDAY, 6)
    assert truncated.business_windows_for_day(MONDAY) == ()


def test_an_unscheduled_weekday_still_receives_the_spillover_tail() -> None:
    calendar = sunday_night_calendar(truncates=True, holidays=[])

    assert calendar.business_windows_for_day(MONDAY)[0].end == at(MONDAY, 6)


def test_a_partial_day_override_merges_with_the_incoming_tail() -> None:
    calendar = WorkingCalendar(
        tz="UTC",
        weekly_schedule={6: [("22:00", "06:00", 1)]},
        day_overrides={MONDAY: [("06:00", "12:00")]},
    )

    monday = calendar.business_windows_for_day(MONDAY)

    assert [(window.start, window.end) for window in monday] == [(at(MONDAY, 0), at(MONDAY, 12))]


# --- validation ----------------------------------------------------------------


def test_schedule_block_rejects_an_overnight_block_longer_than_a_day() -> None:
    with pytest.raises(ValidationError):
        ScheduleBlock.from_pair("22:00", "23:00", 1)


def test_schedule_block_rejects_offsets_beyond_one_day() -> None:
    with pytest.raises(ValidationError):
        ScheduleBlock.from_pair("22:00", "06:00", 2)
    with pytest.raises(ValidationError):
        ScheduleBlock.from_pair("22:00", "06:00", -1)


def test_schedule_block_rejects_an_empty_intraday_block() -> None:
    with pytest.raises(ValidationError):
        ScheduleBlock.from_pair("18:00", "09:00")


def test_schedule_block_accepts_a_full_twenty_four_hour_block() -> None:
    block = ScheduleBlock.from_pair("22:00", "22:00", 1)

    assert block.duration_hint() == timedelta(hours=24)


def test_schedule_block_from_spec_accepts_windows_pairs_triples_and_blocks() -> None:
    block = ScheduleBlock.from_pair("22:00", "06:00", 1)

    assert ScheduleBlock.from_spec(block) is block
    assert ScheduleBlock.from_spec(TimeWindow.from_pair("09:00", "18:00")) == ScheduleBlock(
        time(9, 0), time(18, 0)
    )
    assert ScheduleBlock.from_spec(("22:00", "06:00", 1)) == block
    assert ScheduleBlock.from_spec(["22:00", "06:00", 1]) == block
    assert ScheduleBlock.from_spec(("09:00", "18:00")).end_offset_days == 0
    with pytest.raises(ValidationError):
        ScheduleBlock.from_spec(("09:00",))  # type: ignore[arg-type]


def test_schedule_block_helpers_expose_span_and_window_conversion() -> None:
    overnight = ScheduleBlock.from_pair("22:00", "06:00", 1)
    intraday = ScheduleBlock.from_pair("09:00", "18:00")

    assert overnight.spans_midnight is True
    assert overnight.duration_hint() == timedelta(hours=8)
    assert intraday.spans_midnight is False
    assert intraday.as_time_window() == TimeWindow.from_pair("09:00", "18:00")
    with pytest.raises(ValidationError):
        overnight.as_time_window()


def test_build_schedule_blocks_merges_adjacent_blocks_across_midnight() -> None:
    assert build_schedule_blocks([("09:00", "18:00"), ("18:00", "02:00", 1)]) == (
        ScheduleBlock(time(9, 0), time(2, 0), 1),
    )


def test_build_schedule_blocks_keeps_blocks_that_cannot_merge_into_one_day() -> None:
    blocks = build_schedule_blocks([("00:00", "12:00"), ("12:00", "06:00", 1)])

    assert blocks == (
        ScheduleBlock(time(0, 0), time(12, 0)),
        ScheduleBlock(time(12, 0), time(6, 0), 1),
    )


def test_blocks_overlapping_across_consecutive_days_merge_when_materialized() -> None:
    calendar = WorkingCalendar(
        tz="UTC",
        weekly_schedule={
            0: [("20:00", "08:00", 1)],
            1: [("06:00", "14:00")],
        },
    )

    tuesday = calendar.business_windows_for_day(TUESDAY)

    assert [(window.start, window.end) for window in tuesday] == [(at(TUESDAY, 0), at(TUESDAY, 14))]
    assert calendar.business_time_between(at(MONDAY, 20), at(TUESDAY, 14)) == timedelta(hours=18)


def test_build_schedule_blocks_is_empty_for_empty_input() -> None:
    assert build_schedule_blocks([]) == ()


# --- backward compatibility ----------------------------------------------------


def test_intraday_calendars_keep_producing_plain_time_windows(
    support_calendar: WorkingCalendar,
) -> None:
    assert support_calendar.weekly_schedule[0] == (
        ScheduleBlock(time(9, 0), time(13, 0)),
        ScheduleBlock(time(14, 0), time(18, 0)),
    )
    assert all(
        block.end_offset_days == 0
        for blocks in support_calendar.weekly_schedule.values()
        for block in blocks
    )
    assert support_calendar.closing_for_day(date(2026, 3, 2)) == datetime(
        2026,
        3,
        2,
        18,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )


def test_a_daytime_block_on_the_previous_day_does_not_leak_into_the_next_day() -> None:
    calendar = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("09:00", "18:00"), ("22:00", "06:00", 1)]},
    )

    monday = calendar.business_windows_for_day(MONDAY)
    tuesday = calendar.business_windows_for_day(TUESDAY)

    assert [(window.start, window.end) for window in monday] == [
        (at(MONDAY, 9), at(MONDAY, 18)),
        (at(MONDAY, 22), at(TUESDAY, 0)),
    ]
    assert [(window.start, window.end) for window in tuesday] == [(at(TUESDAY, 0), at(TUESDAY, 6))]
    assert calendar.business_blocks_for_day(MONDAY)[-1].end == at(TUESDAY, 6)


def test_range_queries_reach_back_far_enough_for_a_full_length_block() -> None:
    calendar = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("22:00", "22:00", 1)]},
    )

    blocks = calendar.business_blocks_for_day(MONDAY)
    tail = calendar.business_windows_for_range(at(TUESDAY, 12), at(TUESDAY, 23))

    assert blocks[0].duration() == timedelta(hours=24)
    assert [(window.start, window.end) for window in tail] == [(at(TUESDAY, 12), at(TUESDAY, 22))]
    assert calendar.business_windows_for_day(TUESDAY)[0].end == at(TUESDAY, 22)
    assert calendar.business_time_between(at(MONDAY, 22), at(TUESDAY, 22)) == timedelta(hours=24)

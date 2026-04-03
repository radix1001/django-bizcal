from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from django_bizcal import (
    BusinessDeadline,
    WorkingCalendar,
    breach_at,
    business_deadline_at_close,
    deadline_for,
    due_on_next_business_day,
    is_breached,
    remaining_business_time,
)
from django_bizcal.exceptions import ValidationError


def test_deadline_for_returns_business_deadline(support_calendar: WorkingCalendar) -> None:
    tz = ZoneInfo("America/Santiago")
    start = datetime(2026, 3, 2, 10, 0, tzinfo=tz)

    deadline = deadline_for(
        start,
        timedelta(hours=4),
        calendar=support_calendar,
        calendar_name="support",
    )

    assert isinstance(deadline, BusinessDeadline)
    assert deadline.deadline == datetime(2026, 3, 2, 15, 0, tzinfo=tz)
    assert deadline.calendar_name == "support"


def test_breach_helpers_report_remaining_and_overdue_business_time(
    support_calendar: WorkingCalendar,
) -> None:
    tz = ZoneInfo("America/Santiago")
    start = datetime(2026, 3, 2, 10, 0, tzinfo=tz)
    deadline = deadline_for(start, timedelta(hours=4), calendar=support_calendar)

    assert breach_at(start, timedelta(hours=4), calendar=support_calendar) == deadline.deadline
    assert deadline.remaining(at=datetime(2026, 3, 2, 11, 0, tzinfo=tz)) == timedelta(hours=3)
    assert deadline.remaining_hours(at=datetime(2026, 3, 2, 11, 0, tzinfo=tz)) == 3.0
    assert (
        remaining_business_time(
            deadline,
            now=datetime(2026, 3, 2, 16, 0, tzinfo=tz),
        )
        == timedelta(hours=-1)
    )
    assert deadline.is_breached(at=datetime(2026, 3, 2, 16, 0, tzinfo=tz)) is True
    assert is_breached(deadline, now=datetime(2026, 3, 2, 16, 0, tzinfo=tz)) is True


def test_remaining_business_time_accepts_raw_datetime_deadline(
    support_calendar: WorkingCalendar,
) -> None:
    tz = ZoneInfo("America/Santiago")
    deadline = datetime(2026, 3, 2, 15, 0, tzinfo=tz)

    assert (
        remaining_business_time(
            deadline,
            calendar=support_calendar,
            now=datetime(2026, 3, 2, 11, 0, tzinfo=tz),
        )
        == timedelta(hours=3)
    )
    assert (
        is_breached(
            deadline,
            calendar=support_calendar,
            now=datetime(2026, 3, 2, 16, 0, tzinfo=tz),
        )
        is True
    )


def test_due_on_next_business_day_supports_boundaries_and_snaps(
    support_calendar: WorkingCalendar,
) -> None:
    tz = ZoneInfo("America/Santiago")

    assert due_on_next_business_day("2026-03-06", calendar=support_calendar) == datetime(
        2026,
        3,
        9,
        9,
        0,
        tzinfo=tz,
    )
    assert due_on_next_business_day(
        "2026-03-06",
        calendar=support_calendar,
        at="closing",
    ) == datetime(2026, 3, 9, 18, 0, tzinfo=tz)
    assert due_on_next_business_day(
        "2026-03-06",
        calendar=support_calendar,
        at="13:30",
    ) == datetime(2026, 3, 9, 14, 0, tzinfo=tz)
    assert due_on_next_business_day(
        "2026-03-06",
        calendar=support_calendar,
        at="20:00",
    ) == datetime(2026, 3, 9, 18, 0, tzinfo=tz)


def test_due_on_next_business_day_can_render_in_another_timezone(
    support_calendar: WorkingCalendar,
) -> None:
    local_due = due_on_next_business_day("2026-03-06", calendar=support_calendar)

    assert due_on_next_business_day(
        "2026-03-06",
        calendar=support_calendar,
        tz="UTC",
    ) == local_due.astimezone(ZoneInfo("UTC"))


def test_business_deadline_at_close_counts_business_days(
    support_calendar: WorkingCalendar,
) -> None:
    tz = ZoneInfo("America/Santiago")

    assert business_deadline_at_close(
        "2026-03-05",
        2,
        calendar=support_calendar,
    ) == datetime(2026, 3, 9, 18, 0, tzinfo=tz)
    assert business_deadline_at_close(
        "2026-03-05",
        2,
        calendar=support_calendar,
        include_start=True,
    ) == datetime(2026, 3, 6, 17, 0, tzinfo=tz)
    assert business_deadline_at_close(
        date(2026, 3, 7),
        1,
        calendar=support_calendar,
        include_start=True,
    ) == datetime(2026, 3, 9, 18, 0, tzinfo=tz)


def test_deadline_helpers_validate_inputs(support_calendar: WorkingCalendar) -> None:
    tz = ZoneInfo("America/Santiago")
    start = datetime(2026, 3, 2, 10, 0, tzinfo=tz)
    deadline = deadline_for(start, timedelta(hours=1), calendar=support_calendar)

    with pytest.raises(ValidationError):
        deadline_for(start, timedelta(hours=-1), calendar=support_calendar)
    with pytest.raises(ValidationError):
        deadline_for(start, timedelta(hours=1), calendar=support_calendar, calendar_name=" ")
    with pytest.raises(ValidationError):
        remaining_business_time(deadline.deadline)
    with pytest.raises(ValidationError):
        remaining_business_time(deadline, calendar=support_calendar)
    with pytest.raises(ValidationError):
        business_deadline_at_close("2026-03-05", 0, calendar=support_calendar)

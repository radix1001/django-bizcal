from __future__ import annotations

from django_bizcal import (
    BusinessCalendar,
    BusinessDeadline,
    BusinessInterval,
    CalendarBuilder,
    CalendarConfig,
    DateInput,
    DifferenceCalendar,
    DifferenceCalendarConfig,
    IntersectionCalendar,
    IntersectionCalendarConfig,
    OverrideCalendar,
    OverrideCalendarConfig,
    RenderTzInput,
    TimeInput,
    TimeWindow,
    TzInput,
    UnionCalendar,
    UnionCalendarConfig,
    WorkingCalendar,
    WorkingCalendarConfig,
    breach_at,
    business_deadline_at_close,
    deadline_for,
    due_on_next_business_day,
    is_breached,
    remaining_business_time,
)


def test_root_package_exports_public_api_symbols() -> None:
    assert BusinessCalendar is not None
    assert BusinessDeadline is not None
    assert BusinessInterval is not None
    assert CalendarBuilder is not None
    assert CalendarConfig is not None
    assert DateInput is not None
    assert DifferenceCalendar is not None
    assert DifferenceCalendarConfig is not None
    assert IntersectionCalendar is not None
    assert IntersectionCalendarConfig is not None
    assert OverrideCalendar is not None
    assert OverrideCalendarConfig is not None
    assert RenderTzInput is not None
    assert TimeInput is not None
    assert TimeWindow is not None
    assert TzInput is not None
    assert UnionCalendar is not None
    assert UnionCalendarConfig is not None
    assert WorkingCalendar is not None
    assert WorkingCalendarConfig is not None
    assert breach_at is not None
    assert business_deadline_at_close is not None
    assert deadline_for is not None
    assert due_on_next_business_day is not None
    assert is_breached is not None
    assert remaining_business_time is not None

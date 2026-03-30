from __future__ import annotations

from django_bizcal import (
    BusinessCalendar,
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
)


def test_root_package_exports_public_api_symbols() -> None:
    assert BusinessCalendar is not None
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

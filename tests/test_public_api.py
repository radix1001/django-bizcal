from __future__ import annotations

from django_bizcal import (
    BusinessCalendar,
    BusinessInterval,
    CalendarBuilder,
    DifferenceCalendar,
    IntersectionCalendar,
    OverrideCalendar,
    TimeWindow,
    UnionCalendar,
    WorkingCalendar,
)


def test_root_package_exports_public_api_symbols() -> None:
    assert BusinessCalendar is not None
    assert BusinessInterval is not None
    assert CalendarBuilder is not None
    assert DifferenceCalendar is not None
    assert IntersectionCalendar is not None
    assert OverrideCalendar is not None
    assert TimeWindow is not None
    assert UnionCalendar is not None
    assert WorkingCalendar is not None


from __future__ import annotations

from django_bizcal.django_api import (
    CalendarHoliday,
    DatabaseHolidayProvider,
    activate_calendar_holiday,
    apply_database_holiday_overrides,
    build_calendar,
    deactivate_calendar_holiday,
    delete_calendar_holiday,
    get_calendar,
    get_calendar_holiday,
    get_default_calendar,
    list_calendar_holidays,
    list_configured_calendars,
    now,
    reset_calendar_cache,
    set_calendar_holiday,
    sync_calendar_holidays,
)


def test_django_api_exports_stable_helpers() -> None:
    assert CalendarHoliday is not None
    assert DatabaseHolidayProvider is not None
    assert activate_calendar_holiday is not None
    assert apply_database_holiday_overrides is not None
    assert build_calendar is not None
    assert deactivate_calendar_holiday is not None
    assert delete_calendar_holiday is not None
    assert get_calendar is not None
    assert get_calendar_holiday is not None
    assert get_default_calendar is not None
    assert list_calendar_holidays is not None
    assert list_configured_calendars is not None
    assert now is not None
    assert reset_calendar_cache is not None
    assert set_calendar_holiday is not None
    assert sync_calendar_holidays is not None

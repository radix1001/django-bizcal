from __future__ import annotations

from django_bizcal.django_api import (
    BusinessDeadline,
    CalendarDayOverride,
    CalendarDayOverrideWindow,
    CalendarHoliday,
    CalendarResolution,
    DatabaseDayOverrideProvider,
    DatabaseHolidayProvider,
    activate_calendar_day_override,
    activate_calendar_holiday,
    apply_database_holiday_overrides,
    apply_database_overrides,
    breach_at,
    build_calendar,
    business_deadline_at_close,
    deactivate_calendar_day_override,
    deactivate_calendar_holiday,
    deadline_for,
    delete_calendar_day_override,
    delete_calendar_holiday,
    due_on_next_business_day,
    get_calendar,
    get_calendar_day_override,
    get_calendar_day_override_windows,
    get_calendar_for,
    get_calendar_holiday,
    get_default_calendar,
    is_breached,
    list_calendar_day_override_windows,
    list_calendar_day_overrides,
    list_calendar_holiday_days,
    list_calendar_holidays,
    list_configured_calendars,
    now,
    remaining_business_time,
    reset_calendar_cache,
    resolve_calendar_for,
    set_calendar_day_override,
    set_calendar_holiday,
    sync_calendar_day_overrides,
    sync_calendar_holidays,
)


def test_django_api_exports_stable_helpers() -> None:
    assert BusinessDeadline is not None
    assert CalendarDayOverride is not None
    assert CalendarDayOverrideWindow is not None
    assert CalendarHoliday is not None
    assert CalendarResolution is not None
    assert DatabaseDayOverrideProvider is not None
    assert DatabaseHolidayProvider is not None
    assert activate_calendar_day_override is not None
    assert activate_calendar_holiday is not None
    assert apply_database_overrides is not None
    assert apply_database_holiday_overrides is not None
    assert breach_at is not None
    assert build_calendar is not None
    assert business_deadline_at_close is not None
    assert deactivate_calendar_day_override is not None
    assert deactivate_calendar_holiday is not None
    assert deadline_for is not None
    assert delete_calendar_day_override is not None
    assert delete_calendar_holiday is not None
    assert due_on_next_business_day is not None
    assert get_calendar is not None
    assert get_calendar_for is not None
    assert get_calendar_day_override is not None
    assert get_calendar_day_override_windows is not None
    assert get_calendar_holiday is not None
    assert get_default_calendar is not None
    assert list_calendar_day_overrides is not None
    assert list_calendar_day_override_windows is not None
    assert list_calendar_holiday_days is not None
    assert list_calendar_holidays is not None
    assert list_configured_calendars is not None
    assert now is not None
    assert is_breached is not None
    assert remaining_business_time is not None
    assert reset_calendar_cache is not None
    assert resolve_calendar_for is not None
    assert set_calendar_day_override is not None
    assert set_calendar_holiday is not None
    assert sync_calendar_day_overrides is not None
    assert sync_calendar_holidays is not None

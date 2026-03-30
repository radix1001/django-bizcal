"""Stable Django-specific public API surface."""

from .db import DatabaseHolidayProvider, apply_database_holiday_overrides
from .models import CalendarHoliday
from .services import (
    activate_calendar_holiday,
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

__all__ = [
    "CalendarHoliday",
    "DatabaseHolidayProvider",
    "activate_calendar_holiday",
    "apply_database_holiday_overrides",
    "build_calendar",
    "deactivate_calendar_holiday",
    "delete_calendar_holiday",
    "get_calendar",
    "get_calendar_holiday",
    "get_default_calendar",
    "list_calendar_holidays",
    "list_configured_calendars",
    "now",
    "reset_calendar_cache",
    "set_calendar_holiday",
    "sync_calendar_holidays",
]

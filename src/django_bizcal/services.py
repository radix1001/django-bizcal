"""Service helpers for Django projects."""

from __future__ import annotations

from functools import cache
from typing import Any

from django.utils import timezone as django_timezone

from .builder import CalendarBuilder
from .calendars.base import BusinessCalendar
from .config import CalendarConfig
from .settings import get_bizcal_settings


@cache
def get_calendar(name: str) -> BusinessCalendar:
    """Return a configured named calendar resolved from Django settings."""
    current_settings = get_bizcal_settings()
    return current_settings.build_calendar(name)


def get_default_calendar() -> BusinessCalendar:
    """Return the default calendar resolved from Django settings."""
    current_settings = get_bizcal_settings()
    return get_calendar(current_settings.default_calendar_name)


def build_calendar(config: CalendarConfig | dict[str, Any]) -> BusinessCalendar:
    """Build a calendar using Django defaults as fallback context."""
    current_settings = get_bizcal_settings()
    return CalendarBuilder.from_dict(
        config,
        default_tz=current_settings.default_timezone.key,
        default_country=current_settings.default_country,
        preload_years=current_settings.preload_years,
    )


def now() -> Any:
    """Return Django's current timezone-aware datetime for convenience."""
    return django_timezone.now()


def list_configured_calendars() -> tuple[str, ...]:
    """Return configured logical calendar names from Django settings."""
    return tuple(get_bizcal_settings().calendar_configs)


def reset_calendar_cache() -> None:
    """Clear service-level calendar caches for tests or runtime reloads."""
    get_calendar.cache_clear()

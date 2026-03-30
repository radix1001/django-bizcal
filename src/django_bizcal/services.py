"""Service helpers for Django projects."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from django.utils import timezone as django_timezone

from .builder import CalendarBuilder
from .calendars.base import BusinessCalendar
from .settings import get_bizcal_settings


@lru_cache(maxsize=1)
def get_default_calendar() -> BusinessCalendar:
    """Return the default calendar resolved from Django settings."""
    return get_bizcal_settings().default_calendar


def build_calendar(config: dict[str, Any]) -> BusinessCalendar:
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


def reset_calendar_cache() -> None:
    """Clear service-level calendar caches for tests or runtime reloads."""
    get_default_calendar.cache_clear()


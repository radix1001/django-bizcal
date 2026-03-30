"""Django settings integration for django-bizcal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings as django_settings

from .builder import CalendarBuilder
from .calendars.base import BusinessCalendar
from .types import coerce_zoneinfo

DEFAULT_WEEKLY_SCHEDULE: dict[int, list[tuple[str, str]]] = {
    0: [("09:00", "18:00")],
    1: [("09:00", "18:00")],
    2: [("09:00", "18:00")],
    3: [("09:00", "18:00")],
    4: [("09:00", "18:00")],
}


@dataclass(frozen=True)
class BizcalSettings:
    """Resolved settings values consumed by the Django integration."""

    default_timezone: ZoneInfo
    default_country: str | None
    preload_years: tuple[int, ...]
    enable_db_models: bool
    default_calendar_config: dict[str, Any]

    @classmethod
    def load(cls) -> BizcalSettings:
        """Load and normalize settings from `django.conf.settings`."""
        timezone_name = str(
            getattr(django_settings, "BIZCAL_DEFAULT_TIMEZONE", None)
            or getattr(
                django_settings,
                "TIME_ZONE",
                "UTC",
            )
        )
        default_timezone = coerce_zoneinfo(timezone_name)
        default_country = getattr(django_settings, "BIZCAL_DEFAULT_COUNTRY", None)
        preload_years = _resolve_preload_years(
            getattr(django_settings, "BIZCAL_PRELOAD_YEARS", 3),
            default_timezone,
        )
        enable_db_models = bool(getattr(django_settings, "BIZCAL_ENABLE_DB_MODELS", False))
        configured_default = getattr(django_settings, "BIZCAL_DEFAULT_CALENDAR", None)
        if configured_default is None:
            configured_default = {
                "type": "working",
                "tz": default_timezone.key,
                "country": default_country,
                "years": list(preload_years),
                "weekly_schedule": DEFAULT_WEEKLY_SCHEDULE,
            }
        return cls(
            default_timezone=default_timezone,
            default_country=default_country,
            preload_years=preload_years,
            enable_db_models=enable_db_models,
            default_calendar_config=dict(configured_default),
        )

    @cached_property
    def default_calendar(self) -> BusinessCalendar:
        """Build the default calendar lazily from settings."""
        return CalendarBuilder.from_dict(
            self.default_calendar_config,
            default_tz=self.default_timezone.key,
            default_country=self.default_country,
            preload_years=self.preload_years,
        )


def get_bizcal_settings() -> BizcalSettings:
    """Return resolved settings for the current Django process."""
    return BizcalSettings.load()


def _resolve_preload_years(value: Any, timezone: ZoneInfo) -> tuple[int, ...]:
    current_year = datetime.now(timezone).year
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(
                "BIZCAL_PRELOAD_YEARS must be a positive integer "
                "or a sequence of years."
            )
        start_year = current_year - 1
        return tuple(start_year + offset for offset in range(value))
    years = tuple(sorted({int(year) for year in value}))
    if not years:
        raise ValueError("BIZCAL_PRELOAD_YEARS cannot be empty.")
    return years

"""Django settings integration for django-bizcal."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import Any, cast
from zoneinfo import ZoneInfo

from django.conf import settings as django_settings

from .builder import CalendarBuilder
from .calendars.base import BusinessCalendar
from .config import CalendarConfig
from .exceptions import CalendarConfigurationError
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
    default_calendar_name: str
    default_calendar_config: CalendarConfig
    calendar_configs: dict[str, CalendarConfig]

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
        default_calendar_name = _resolve_calendar_name(
            getattr(django_settings, "BIZCAL_DEFAULT_CALENDAR_NAME", "default")
        )
        preload_years = _resolve_preload_years(
            getattr(django_settings, "BIZCAL_PRELOAD_YEARS", 3),
            default_timezone,
        )
        enable_db_models = bool(getattr(django_settings, "BIZCAL_ENABLE_DB_MODELS", False))
        configured_default = getattr(django_settings, "BIZCAL_DEFAULT_CALENDAR", None)
        default_was_explicit = configured_default is not None
        if configured_default is None:
            configured_default = {
                "type": "working",
                "tz": default_timezone.key,
                "country": default_country,
                "years": list(preload_years),
                "weekly_schedule": DEFAULT_WEEKLY_SCHEDULE,
            }
        default_calendar_config = _copy_calendar_config(
            configured_default,
            setting_name="BIZCAL_DEFAULT_CALENDAR",
        )
        calendar_configs = _resolve_calendar_configs(
            configured=getattr(django_settings, "BIZCAL_CALENDARS", None),
            default_name=default_calendar_name,
            default_config=default_calendar_config,
            default_was_explicit=default_was_explicit,
        )
        return cls(
            default_timezone=default_timezone,
            default_country=default_country,
            preload_years=preload_years,
            enable_db_models=enable_db_models,
            default_calendar_name=default_calendar_name,
            default_calendar_config=calendar_configs[default_calendar_name],
            calendar_configs=calendar_configs,
        )

    @cached_property
    def default_calendar(self) -> BusinessCalendar:
        """Build the default calendar lazily from settings."""
        return self.build_calendar(self.default_calendar_name)

    def build_calendar(self, name: str) -> BusinessCalendar:
        """Build a configured named calendar using Django defaults as fallback context."""
        calendar = CalendarBuilder.from_dict(
            self.get_calendar_config(name),
            default_tz=self.default_timezone.key,
            default_country=self.default_country,
            preload_years=self.preload_years,
        )
        if not self.enable_db_models:
            return calendar
        from .db import apply_database_holiday_overrides

        return apply_database_holiday_overrides(calendar, calendar_name=name)

    def get_calendar_config(self, name: str) -> CalendarConfig:
        """Return a configured calendar definition by logical name."""
        try:
            return self.calendar_configs[name]
        except KeyError as exc:
            raise CalendarConfigurationError(
                f"Unknown calendar {name!r}. Configure it in BIZCAL_CALENDARS "
                "or BIZCAL_DEFAULT_CALENDAR."
            ) from exc


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


def _resolve_calendar_name(value: Any) -> str:
    name = str(value).strip()
    if not name:
        raise ValueError("BIZCAL_DEFAULT_CALENDAR_NAME cannot be blank.")
    return name


def _copy_calendar_config(value: Any, *, setting_name: str) -> CalendarConfig:
    if not isinstance(value, Mapping):
        raise ValueError(f"{setting_name} must be a mapping.")
    return cast(CalendarConfig, dict(value))


def _resolve_calendar_configs(
    *,
    configured: Any,
    default_name: str,
    default_config: CalendarConfig,
    default_was_explicit: bool,
) -> dict[str, CalendarConfig]:
    if configured is None:
        return {default_name: default_config}
    if not isinstance(configured, Mapping):
        raise ValueError("BIZCAL_CALENDARS must be a mapping of names to calendar definitions.")

    calendar_configs: dict[str, CalendarConfig] = {}
    for raw_name, raw_config in configured.items():
        name = _resolve_calendar_name(raw_name)
        calendar_configs[name] = _copy_calendar_config(
            raw_config,
            setting_name=f"BIZCAL_CALENDARS[{name!r}]",
        )

    if default_name in calendar_configs:
        if default_was_explicit:
            raise ValueError(
                "Configure the default calendar either in BIZCAL_DEFAULT_CALENDAR "
                "or in BIZCAL_CALENDARS under BIZCAL_DEFAULT_CALENDAR_NAME, but not both."
            )
        return calendar_configs

    if default_was_explicit:
        calendar_configs[default_name] = default_config
        return calendar_configs

    raise ValueError(
        "BIZCAL_DEFAULT_CALENDAR_NAME must reference an entry in BIZCAL_CALENDARS "
        "when BIZCAL_DEFAULT_CALENDAR is not explicitly configured."
    )

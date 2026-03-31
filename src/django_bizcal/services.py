"""Service helpers for Django projects."""

from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from typing import TYPE_CHECKING, Any, TypeAlias, cast

from django.db import transaction
from django.utils import timezone as django_timezone

from .builder import CalendarBuilder
from .calendars.base import BusinessCalendar
from .config import CalendarConfig
from .db import replace_day_override_windows
from .exceptions import ValidationError
from .settings import get_bizcal_settings
from .types import DateInput, TimeInput, coerce_date
from .windows import TimeWindow, build_time_windows

if TYPE_CHECKING:
    from .models import CalendarDayOverride as CalendarDayOverrideRow
    from .models import CalendarHoliday as CalendarHolidayRow
else:
    CalendarHolidayRow: TypeAlias = Any
    CalendarDayOverrideRow: TypeAlias = Any

_CALENDAR_CACHE: dict[str, BusinessCalendar] = {}
_CALENDAR_CACHE_LOCK = RLock()


def get_calendar(name: str) -> BusinessCalendar:
    """Return a configured named calendar resolved from Django settings."""
    normalized_name = _normalize_calendar_name(name)
    with _CALENDAR_CACHE_LOCK:
        cached = _CALENDAR_CACHE.get(normalized_name)
        if cached is not None:
            return cached
    current_settings = get_bizcal_settings()
    calendar = current_settings.build_calendar(normalized_name)
    with _CALENDAR_CACHE_LOCK:
        return _CALENDAR_CACHE.setdefault(normalized_name, calendar)


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
    """Return configured logical calendar names from settings."""
    return tuple(get_bizcal_settings().calendar_configs)


def list_calendar_holidays(
    calendar_name: str,
    *,
    include_inactive: bool = False,
    using: str = "default",
) -> tuple[CalendarHolidayRow, ...]:
    """Return persisted holiday rows for a logical calendar name."""
    from .models import CalendarHoliday

    normalized_name = _normalize_calendar_name(calendar_name)
    queryset = CalendarHoliday.objects.using(using).filter(calendar_name=normalized_name)
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return tuple(queryset.order_by("day"))


def list_calendar_day_overrides(
    calendar_name: str,
    *,
    include_inactive: bool = False,
    using: str = "default",
) -> tuple[CalendarDayOverrideRow, ...]:
    """Return persisted day override rows for a logical calendar name."""
    from .models import CalendarDayOverride

    normalized_name = _normalize_calendar_name(calendar_name)
    queryset = (
        CalendarDayOverride.objects.using(using)
        .filter(calendar_name=normalized_name)
        .prefetch_related("windows")
    )
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return tuple(queryset.order_by("day"))


def get_calendar_holiday(
    calendar_name: str,
    day: DateInput,
    *,
    include_inactive: bool = False,
    using: str = "default",
) -> CalendarHolidayRow | None:
    """Return a persisted holiday row for a logical calendar name and day."""
    from .models import CalendarHoliday

    normalized_name = _normalize_calendar_name(calendar_name)
    normalized_day = coerce_date(day)
    queryset = CalendarHoliday.objects.using(using).filter(
        calendar_name=normalized_name,
        day=normalized_day,
    )
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return cast(CalendarHolidayRow | None, queryset.first())


def get_calendar_day_override(
    calendar_name: str,
    day: DateInput,
    *,
    include_inactive: bool = False,
    using: str = "default",
) -> CalendarDayOverrideRow | None:
    """Return a persisted day override row for a logical calendar name and day."""
    from .models import CalendarDayOverride

    normalized_name = _normalize_calendar_name(calendar_name)
    normalized_day = coerce_date(day)
    queryset = (
        CalendarDayOverride.objects.using(using)
        .filter(calendar_name=normalized_name, day=normalized_day)
        .prefetch_related("windows")
    )
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return cast(CalendarDayOverrideRow | None, queryset.first())


def set_calendar_holiday(
    calendar_name: str,
    day: DateInput,
    *,
    name: str = "",
    is_active: bool = True,
    using: str = "default",
) -> CalendarHolidayRow:
    """Create or update a persisted holiday row and clear the relevant cached calendar."""
    from .models import CalendarHoliday

    normalized_name = _normalize_calendar_name(calendar_name)
    normalized_day = coerce_date(day)
    holiday, _ = CalendarHoliday.objects.using(using).update_or_create(
        calendar_name=normalized_name,
        day=normalized_day,
        defaults={
            "name": name,
            "is_active": is_active,
        },
    )
    reset_calendar_cache(normalized_name)
    return cast(CalendarHolidayRow, holiday)


def set_calendar_day_override(
    calendar_name: str,
    day: DateInput,
    windows: Iterable[tuple[TimeInput, TimeInput] | TimeWindow],
    *,
    name: str = "",
    is_active: bool = True,
    using: str = "default",
) -> CalendarDayOverrideRow:
    """Create or update a persisted per-day schedule override."""
    from .models import CalendarDayOverride

    normalized_name = _normalize_calendar_name(calendar_name)
    normalized_day = coerce_date(day)

    with transaction.atomic(using=using):
        override, _ = CalendarDayOverride.objects.using(using).update_or_create(
            calendar_name=normalized_name,
            day=normalized_day,
            defaults={
                "name": name,
                "is_active": is_active,
            },
        )
        replace_day_override_windows(override, windows, using=using)
    reset_calendar_cache(normalized_name)
    override = get_calendar_day_override(
        normalized_name,
        normalized_day,
        include_inactive=True,
        using=using,
    )
    assert override is not None
    return override


def activate_calendar_holiday(
    calendar_name: str,
    day: DateInput,
    *,
    name: str | None = None,
    using: str = "default",
) -> CalendarHolidayRow:
    """Mark a holiday as active, creating it when necessary."""
    existing = get_calendar_holiday(
        calendar_name,
        day,
        include_inactive=True,
        using=using,
    )
    resolved_name = existing.name if existing is not None and name is None else (name or "")
    return set_calendar_holiday(
        calendar_name,
        day,
        name=resolved_name,
        is_active=True,
        using=using,
    )


def activate_calendar_day_override(
    calendar_name: str,
    day: DateInput,
    *,
    windows: Iterable[tuple[TimeInput, TimeInput] | TimeWindow] | None = None,
    name: str | None = None,
    using: str = "default",
) -> CalendarDayOverrideRow:
    """Mark a day override as active, creating it when windows are provided."""
    normalized_name = _normalize_calendar_name(calendar_name)
    existing = get_calendar_day_override(
        normalized_name,
        day,
        include_inactive=True,
        using=using,
    )
    if existing is None and windows is None:
        raise ValidationError(
            "activate_calendar_day_override requires windows when the override does not exist."
        )
    if windows is not None:
        resolved_windows: Iterable[tuple[TimeInput, TimeInput] | TimeWindow] = windows
    else:
        assert existing is not None
        resolved_windows = [
            (window.start_time, window.end_time)
            for window in existing.windows.all().order_by("position", "start_time")
        ]
    resolved_name = existing.name if existing is not None and name is None else (name or "")
    return set_calendar_day_override(
        normalized_name,
        day,
        resolved_windows,
        name=resolved_name,
        is_active=True,
        using=using,
    )


def deactivate_calendar_holiday(
    calendar_name: str,
    day: DateInput,
    *,
    using: str = "default",
) -> CalendarHolidayRow | None:
    """Mark a persisted holiday as inactive and clear the relevant cached calendar."""
    normalized_name = _normalize_calendar_name(calendar_name)
    holiday = get_calendar_holiday(normalized_name, day, include_inactive=True, using=using)
    if holiday is None:
        return None
    if holiday.is_active:
        holiday.is_active = False
        holiday.save(update_fields=["is_active", "updated_at"])
        reset_calendar_cache(normalized_name)
    return holiday


def deactivate_calendar_day_override(
    calendar_name: str,
    day: DateInput,
    *,
    using: str = "default",
) -> CalendarDayOverrideRow | None:
    """Mark a persisted day override as inactive and clear the relevant cached calendar."""
    normalized_name = _normalize_calendar_name(calendar_name)
    override = get_calendar_day_override(normalized_name, day, include_inactive=True, using=using)
    if override is None:
        return None
    if override.is_active:
        override.is_active = False
        override.save(update_fields=["is_active", "updated_at"])
        reset_calendar_cache(normalized_name)
    return override


def delete_calendar_holiday(
    calendar_name: str,
    day: DateInput,
    *,
    using: str = "default",
) -> bool:
    """Delete a persisted holiday row and clear the relevant cached calendar."""
    normalized_name = _normalize_calendar_name(calendar_name)
    holiday = get_calendar_holiday(normalized_name, day, include_inactive=True, using=using)
    if holiday is None:
        return False
    holiday.delete(using=using)
    reset_calendar_cache(normalized_name)
    return True


def delete_calendar_day_override(
    calendar_name: str,
    day: DateInput,
    *,
    using: str = "default",
) -> bool:
    """Delete a persisted day override row and clear the relevant cached calendar."""
    normalized_name = _normalize_calendar_name(calendar_name)
    override = get_calendar_day_override(normalized_name, day, include_inactive=True, using=using)
    if override is None:
        return False
    override.delete(using=using)
    reset_calendar_cache(normalized_name)
    return True


def sync_calendar_holidays(
    calendar_name: str,
    days: Iterable[DateInput],
    *,
    using: str = "default",
) -> tuple[CalendarHolidayRow, ...]:
    """Make the active holiday set exactly match the provided days."""
    from .models import CalendarHoliday

    normalized_name = _normalize_calendar_name(calendar_name)
    normalized_days = tuple(sorted({coerce_date(day) for day in days}))
    holidays_by_day = {
        holiday.day: holiday
        for holiday in CalendarHoliday.objects.using(using).filter(calendar_name=normalized_name)
    }
    active_days = set(normalized_days)
    saved: list[CalendarHolidayRow] = []

    with transaction.atomic(using=using):
        for current_day in normalized_days:
            holiday = holidays_by_day.get(current_day)
            if holiday is None:
                holiday = CalendarHoliday.objects.using(using).create(
                    calendar_name=normalized_name,
                    day=current_day,
                    is_active=True,
                )
            elif not holiday.is_active:
                holiday.is_active = True
                holiday.save(update_fields=["is_active", "updated_at"])
            saved.append(holiday)

        for stale_day, holiday in holidays_by_day.items():
            if stale_day not in active_days and holiday.is_active:
                holiday.is_active = False
                holiday.save(update_fields=["is_active", "updated_at"])

    reset_calendar_cache(normalized_name)
    return tuple(saved)


def sync_calendar_day_overrides(
    calendar_name: str,
    overrides: dict[DateInput, Iterable[tuple[TimeInput, TimeInput] | TimeWindow]],
    *,
    using: str = "default",
) -> tuple[CalendarDayOverrideRow, ...]:
    """Make the active day-override set exactly match the provided mapping."""
    from .models import CalendarDayOverride

    normalized_name = _normalize_calendar_name(calendar_name)
    normalized_overrides = {
        coerce_date(day): build_time_windows(windows)
        for day, windows in overrides.items()
    }
    existing_by_day = {
        override.day: override
        for override in CalendarDayOverride.objects.using(using)
        .filter(calendar_name=normalized_name)
        .prefetch_related("windows")
    }
    active_days = set(normalized_overrides)
    saved: list[CalendarDayOverrideRow] = []

    with transaction.atomic(using=using):
        for current_day, windows in normalized_overrides.items():
            override = existing_by_day.get(current_day)
            if override is None:
                override = CalendarDayOverride.objects.using(using).create(
                    calendar_name=normalized_name,
                    day=current_day,
                    is_active=True,
                )
            elif not override.is_active:
                override.is_active = True
                override.save(update_fields=["is_active", "updated_at"])
            replace_day_override_windows(override, windows, using=using)
            saved.append(override)

        for stale_day, override in existing_by_day.items():
            if stale_day not in active_days and override.is_active:
                override.is_active = False
                override.save(update_fields=["is_active", "updated_at"])

    reset_calendar_cache(normalized_name)
    refreshed: list[CalendarDayOverrideRow] = []
    for override in saved:
        current = get_calendar_day_override(
            normalized_name,
            override.day,
            include_inactive=True,
            using=using,
        )
        assert current is not None
        refreshed.append(current)
    return tuple(refreshed)


def reset_calendar_cache(name: str | None = None) -> None:
    """Clear all cached calendars or just the one matching the given logical name."""
    with _CALENDAR_CACHE_LOCK:
        if name is None:
            _CALENDAR_CACHE.clear()
            return
        _CALENDAR_CACHE.pop(_normalize_calendar_name(name), None)


def _normalize_calendar_name(value: str) -> str:
    name = str(value).strip()
    if not name:
        raise ValidationError("calendar_name must not be blank.")
    return name

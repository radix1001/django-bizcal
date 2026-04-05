"""Service helpers for Django projects."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from threading import RLock
from typing import TYPE_CHECKING, Any, TypeAlias, cast

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone as django_timezone

from .calendars.base import BusinessCalendar
from .config import CalendarConfig, DeadlinePolicyConfig
from .db import replace_day_override_windows
from .deadlines import BusinessDeadline
from .exceptions import CalendarConfigurationError, ValidationError
from .policies import DeadlinePolicy, DeadlinePolicyBuilder
from .resolvers import (
    CalendarResolution,
    DeadlinePolicyResolution,
    normalize_calendar_resolution,
    normalize_deadline_policy_resolution,
)
from .settings import get_bizcal_settings
from .types import DateInput, TimeInput, coerce_date, ensure_aware
from .windows import TimeWindow, build_time_windows

if TYPE_CHECKING:
    from .models import CalendarDayOverride as CalendarDayOverrideRow
    from .models import CalendarHoliday as CalendarHolidayRow
else:
    CalendarHolidayRow: TypeAlias = Any
    CalendarDayOverrideRow: TypeAlias = Any

_CALENDAR_CACHE: dict[str, BusinessCalendar] = {}
_CALENDAR_CACHE_LOCK = RLock()
_CONTEXT_CALENDAR_CACHE: dict[str, _ContextCalendarCacheEntry] = {}
_DEADLINE_POLICY_CACHE: dict[str, DeadlinePolicy] = {}
_CONTEXT_DEADLINE_POLICY_CACHE: dict[str, _ContextDeadlinePolicyCacheEntry] = {}


@dataclass(frozen=True, slots=True)
class _ContextCalendarCacheEntry:
    calendar: BusinessCalendar
    invalidate_names: frozenset[str]


@dataclass(frozen=True, slots=True)
class _ContextDeadlinePolicyCacheEntry:
    policy: DeadlinePolicy
    invalidate_names: frozenset[str]


def get_calendar(name: str) -> BusinessCalendar:
    """Return a configured named calendar resolved from Django settings."""
    normalized_name = _normalize_calendar_name(name)
    with _CALENDAR_CACHE_LOCK:
        cached = _CALENDAR_CACHE.get(normalized_name)
        if cached is not None:
            return cached
    current_settings = get_bizcal_settings()
    calendar = _bind_calendar_name(
        current_settings.build_calendar(normalized_name),
        normalized_name,
    )
    with _CALENDAR_CACHE_LOCK:
        return _CALENDAR_CACHE.setdefault(normalized_name, calendar)


def get_default_calendar() -> BusinessCalendar:
    """Return the default calendar resolved from Django settings."""
    current_settings = get_bizcal_settings()
    return get_calendar(current_settings.default_calendar_name)


def get_deadline_policy(name: str) -> DeadlinePolicy:
    """Return a configured named deadline policy resolved from Django settings."""
    normalized_name = _normalize_calendar_name(name)
    with _CALENDAR_CACHE_LOCK:
        cached = _DEADLINE_POLICY_CACHE.get(normalized_name)
        if cached is not None:
            return cached
    current_settings = get_bizcal_settings()
    policy = current_settings.build_deadline_policy(normalized_name)
    with _CALENDAR_CACHE_LOCK:
        return _DEADLINE_POLICY_CACHE.setdefault(normalized_name, policy)


def resolve_deadline_policy_for(
    context: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> DeadlinePolicyResolution:
    """Resolve a contextual deadline-policy target using its configured resolver."""
    resolved_context = _normalize_context(context, kwargs)
    current_settings = get_bizcal_settings()
    resolver = current_settings.deadline_policy_resolver
    if resolver is None:
        raise CalendarConfigurationError(
            "BIZCAL_DEADLINE_POLICY_RESOLVER is not configured. "
            "Use get_deadline_policy(name) for direct named lookups or configure "
            "a contextual deadline-policy resolver."
        )
    return normalize_deadline_policy_resolution(
        resolver(context=resolved_context, bizcal_settings=current_settings)
    )


def get_deadline_policy_for(
    context: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> DeadlinePolicy:
    """Resolve and return a deadline policy for tenant-, region-, or client-like context."""
    resolution = resolve_deadline_policy_for(context, **kwargs)
    if resolution.config is None:
        assert resolution.name is not None
        return get_deadline_policy(resolution.name)
    if resolution.cache_key is None:
        return _build_contextual_deadline_policy(resolution)
    with _CALENDAR_CACHE_LOCK:
        cached = _CONTEXT_DEADLINE_POLICY_CACHE.get(resolution.cache_key)
        if cached is not None:
            return cached.policy
    policy = _build_contextual_deadline_policy(resolution)
    invalidate_names = frozenset((resolution.name,)) if resolution.name else frozenset()
    entry = _ContextDeadlinePolicyCacheEntry(policy=policy, invalidate_names=invalidate_names)
    with _CALENDAR_CACHE_LOCK:
        return _CONTEXT_DEADLINE_POLICY_CACHE.setdefault(resolution.cache_key, entry).policy


def get_deadline_policy_config(name: str) -> DeadlinePolicyConfig:
    """Return a configured named deadline policy definition from Django settings."""
    return get_bizcal_settings().get_deadline_policy_config(_normalize_calendar_name(name))


def build_deadline_policy(
    config: DeadlinePolicyConfig | Mapping[str, Any],
) -> DeadlinePolicy:
    """Build a deadline policy from declarative configuration."""
    return DeadlinePolicyBuilder.from_dict(config)


def compute_deadline(
    policy_name: str | None,
    start: Any,
    *,
    calendar: BusinessCalendar | None = None,
    context: Mapping[str, Any] | None = None,
    calendar_name: str | None = None,
    **kwargs: Any,
) -> BusinessDeadline:
    """Compute a deadline using a named or contextually resolved policy."""
    normalized_start = ensure_aware(start, param_name="start")
    has_context_inputs = context is not None or bool(kwargs)
    resolved_context = _normalize_context(context, kwargs) if has_context_inputs else None
    if calendar is not None and resolved_context is not None:
        raise ValidationError(
            "compute_deadline accepts either an explicit calendar "
            "or contextual resolver inputs, not both."
        )
    if policy_name is None and resolved_context is None:
        raise ValidationError(
            "compute_deadline requires policy_name when no contextual resolver inputs are provided."
        )
    if calendar is None:
        resolved_calendar = (
            get_calendar_for(resolved_context)
            if resolved_context is not None
            else get_default_calendar()
        )
    else:
        resolved_calendar = calendar
    resolved_policy = (
        get_deadline_policy(policy_name)
        if policy_name is not None
        else get_deadline_policy_for(resolved_context)
    )
    return resolved_policy.resolve(
        normalized_start,
        calendar=resolved_calendar,
        calendar_name=calendar_name or resolved_calendar.calendar_name,
    )


def resolve_calendar_for(
    context: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> CalendarResolution:
    """Resolve a contextual calendar target using `BIZCAL_CALENDAR_RESOLVER`."""
    resolved_context = _normalize_context(context, kwargs)
    current_settings = get_bizcal_settings()
    resolver = current_settings.calendar_resolver
    if resolver is None:
        raise CalendarConfigurationError(
            "BIZCAL_CALENDAR_RESOLVER is not configured. "
            "Use get_calendar(name) for direct named lookups or configure a contextual resolver."
        )
    return normalize_calendar_resolution(
        resolver(context=resolved_context, bizcal_settings=current_settings)
    )


def get_calendar_for(
    context: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> BusinessCalendar:
    """Resolve and return a business calendar for tenant-, region-, or client-like context."""
    resolution = resolve_calendar_for(context, **kwargs)
    if resolution.config is None:
        assert resolution.name is not None
        return get_calendar(resolution.name)
    if resolution.cache_key is None:
        return _build_contextual_calendar(resolution)
    with _CALENDAR_CACHE_LOCK:
        cached = _CONTEXT_CALENDAR_CACHE.get(resolution.cache_key)
        if cached is not None:
            return cached.calendar
    calendar = _build_contextual_calendar(resolution)
    invalidate_names = frozenset((resolution.name,)) if resolution.name else frozenset()
    entry = _ContextCalendarCacheEntry(calendar=calendar, invalidate_names=invalidate_names)
    with _CALENDAR_CACHE_LOCK:
        return _CONTEXT_CALENDAR_CACHE.setdefault(resolution.cache_key, entry).calendar


def build_calendar(config: CalendarConfig | dict[str, Any]) -> BusinessCalendar:
    """Build a calendar using Django defaults as fallback context."""
    current_settings = get_bizcal_settings()
    return current_settings.build_calendar_from_config(
        config,
    )


def now() -> Any:
    """Return Django's current timezone-aware datetime for convenience."""
    return django_timezone.now()


def list_configured_calendars() -> tuple[str, ...]:
    """Return configured logical calendar names from settings."""
    return tuple(get_bizcal_settings().calendar_configs)


def list_configured_deadline_policies() -> tuple[str, ...]:
    """Return configured named deadline policies from settings."""
    return tuple(get_bizcal_settings().deadline_policy_configs)


def reset_deadline_policy_cache(name: str | None = None) -> None:
    """Clear all cached deadline policies or only one logical policy name."""
    with _CALENDAR_CACHE_LOCK:
        if name is None:
            _DEADLINE_POLICY_CACHE.clear()
            _CONTEXT_DEADLINE_POLICY_CACHE.clear()
            return
        normalized_name = _normalize_calendar_name(name)
        _DEADLINE_POLICY_CACHE.pop(normalized_name, None)
        stale_context_keys = [
            cache_key
            for cache_key, entry in _CONTEXT_DEADLINE_POLICY_CACHE.items()
            if normalized_name in entry.invalidate_names
        ]
        for cache_key in stale_context_keys:
            _CONTEXT_DEADLINE_POLICY_CACHE.pop(cache_key, None)


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


def list_calendar_holiday_days(
    calendar_name: str,
    *,
    include_inactive: bool = False,
    using: str = "default",
) -> tuple[date, ...]:
    """Return persisted holiday dates for a logical calendar name."""
    return tuple(
        holiday.day
        for holiday in list_calendar_holidays(
            calendar_name,
            include_inactive=include_inactive,
            using=using,
        )
    )


def list_calendar_day_overrides(
    calendar_name: str,
    *,
    include_inactive: bool = False,
    using: str = "default",
) -> tuple[CalendarDayOverrideRow, ...]:
    """Return persisted day override rows for a logical calendar name."""
    from .models import CalendarDayOverride, CalendarDayOverrideWindow

    normalized_name = _normalize_calendar_name(calendar_name)
    queryset = (
        CalendarDayOverride.objects.using(using)
        .filter(calendar_name=normalized_name)
        .prefetch_related(
            Prefetch(
                "windows",
                queryset=CalendarDayOverrideWindow.objects.using(using).order_by(
                    "position",
                    "start_time",
                    "end_time",
                    "pk",
                ),
            )
        )
    )
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return tuple(queryset.order_by("day"))


def list_calendar_day_override_windows(
    calendar_name: str,
    *,
    include_inactive: bool = False,
    using: str = "default",
) -> dict[date, tuple[TimeWindow, ...]]:
    """Return normalized persisted override windows keyed by day."""
    return {
        override.day: _override_windows(override)
        for override in list_calendar_day_overrides(
            calendar_name,
            include_inactive=include_inactive,
            using=using,
        )
    }


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
    from .models import CalendarDayOverride, CalendarDayOverrideWindow

    normalized_name = _normalize_calendar_name(calendar_name)
    normalized_day = coerce_date(day)
    queryset = (
        CalendarDayOverride.objects.using(using)
        .filter(calendar_name=normalized_name, day=normalized_day)
        .prefetch_related(
            Prefetch(
                "windows",
                queryset=CalendarDayOverrideWindow.objects.using(using).order_by(
                    "position",
                    "start_time",
                    "end_time",
                    "pk",
                ),
            )
        )
    )
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return cast(CalendarDayOverrideRow | None, queryset.first())


def get_calendar_day_override_windows(
    calendar_name: str,
    day: DateInput,
    *,
    include_inactive: bool = False,
    using: str = "default",
) -> tuple[TimeWindow, ...] | None:
    """Return normalized persisted override windows for one logical day."""
    override = get_calendar_day_override(
        calendar_name,
        day,
        include_inactive=include_inactive,
        using=using,
    )
    if override is None:
        return None
    return _override_windows(override)


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
    from .models import CalendarDayOverride, CalendarDayOverrideWindow

    normalized_name = _normalize_calendar_name(calendar_name)
    normalized_overrides = {
        coerce_date(day): build_time_windows(windows)
        for day, windows in overrides.items()
    }
    existing_by_day = {
        override.day: override
        for override in CalendarDayOverride.objects.using(using)
        .filter(calendar_name=normalized_name)
        .prefetch_related(
            Prefetch(
                "windows",
                queryset=CalendarDayOverrideWindow.objects.using(using).order_by(
                    "position",
                    "start_time",
                    "end_time",
                    "pk",
                ),
            )
        )
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
            _CONTEXT_CALENDAR_CACHE.clear()
            _DEADLINE_POLICY_CACHE.clear()
            _CONTEXT_DEADLINE_POLICY_CACHE.clear()
            return
        normalized_name = _normalize_calendar_name(name)
        _CALENDAR_CACHE.pop(normalized_name, None)
        stale_context_keys = [
            cache_key
            for cache_key, entry in _CONTEXT_CALENDAR_CACHE.items()
            if normalized_name in entry.invalidate_names
        ]
        for cache_key in stale_context_keys:
            _CONTEXT_CALENDAR_CACHE.pop(cache_key, None)


def _normalize_calendar_name(value: str) -> str:
    name = str(value).strip()
    if not name:
        raise ValidationError("calendar_name must not be blank.")
    return name


def _normalize_context(
    context: Mapping[str, Any] | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    if context is None:
        resolved: dict[str, Any] = {}
    else:
        resolved = dict(context)
    overlapping_keys = set(resolved).intersection(kwargs)
    if overlapping_keys:
        duplicate = ", ".join(sorted(overlapping_keys))
        raise ValidationError(f"Duplicate context keys provided: {duplicate}.")
    resolved.update(kwargs)
    return resolved


def _build_contextual_calendar(resolution: CalendarResolution) -> BusinessCalendar:
    current_settings = get_bizcal_settings()
    assert resolution.config is not None
    return _bind_calendar_name(
        current_settings.build_calendar_from_config(
            resolution.config,
            calendar_name=resolution.name,
        ),
        resolution.name,
    )


def _build_contextual_deadline_policy(
    resolution: DeadlinePolicyResolution,
) -> DeadlinePolicy:
    assert resolution.config is not None
    return build_deadline_policy(resolution.config)


def _bind_calendar_name(
    calendar: BusinessCalendar,
    calendar_name: str | None,
) -> BusinessCalendar:
    if calendar_name is None:
        return calendar
    calendar._calendar_name = _normalize_calendar_name(calendar_name)
    return calendar


def _override_windows(override: CalendarDayOverrideRow) -> tuple[TimeWindow, ...]:
    return build_time_windows(
        (window.start_time, window.end_time) for window in override.windows.all()
    )

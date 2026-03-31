# mypy: disable-error-code="untyped-decorator"

"""Signal handlers for optional Django persistence models."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from .models import CalendarDayOverride, CalendarDayOverrideWindow, CalendarHoliday
from .services import reset_calendar_cache


def _reset_named_calendar_after_commit(calendar_name: str | None, *, using: str) -> None:
    if not calendar_name:
        return
    transaction.on_commit(lambda: reset_calendar_cache(calendar_name), using=using)


@receiver(post_save, sender=CalendarHoliday)
@receiver(post_delete, sender=CalendarHoliday)
def _invalidate_calendar_holiday_cache(
    sender: type[CalendarHoliday],
    instance: CalendarHoliday,
    using: str,
    **_: Any,
) -> None:
    _reset_named_calendar_after_commit(instance.calendar_name, using=using)


@receiver(post_save, sender=CalendarDayOverride)
@receiver(post_delete, sender=CalendarDayOverride)
def _invalidate_calendar_day_override_cache(
    sender: type[CalendarDayOverride],
    instance: CalendarDayOverride,
    using: str,
    **_: Any,
) -> None:
    _reset_named_calendar_after_commit(instance.calendar_name, using=using)


@receiver(pre_save, sender=CalendarDayOverrideWindow)
@receiver(pre_delete, sender=CalendarDayOverrideWindow)
def _capture_window_calendar_name(
    sender: type[CalendarDayOverrideWindow],
    instance: CalendarDayOverrideWindow,
    **_: Any,
) -> None:
    try:
        instance._cached_calendar_name = instance.override.calendar_name
    except CalendarDayOverride.DoesNotExist:
        instance._cached_calendar_name = None


@receiver(post_save, sender=CalendarDayOverrideWindow)
@receiver(post_delete, sender=CalendarDayOverrideWindow)
def _invalidate_calendar_day_override_window_cache(
    sender: type[CalendarDayOverrideWindow],
    instance: CalendarDayOverrideWindow,
    using: str,
    **_: Any,
) -> None:
    _reset_named_calendar_after_commit(
        getattr(instance, "_cached_calendar_name", None),
        using=using,
    )

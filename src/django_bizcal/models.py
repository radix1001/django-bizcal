"""Optional Django persistence models for django-bizcal."""

from __future__ import annotations

import django
from django.db import models
from django.db.models import F, Q

_CHECK_CONSTRAINT_ARG = "condition" if django.VERSION >= (5, 1) else "check"


class CalendarHoliday(models.Model):  # type: ignore[misc]
    """Persisted full-day holiday closure for a logical calendar name."""

    calendar_name = models.CharField(max_length=100, db_index=True)
    day = models.DateField(db_index=True)
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("calendar_name", "day")
        verbose_name = "calendar holiday"
        verbose_name_plural = "calendar holidays"
        constraints = [
            models.UniqueConstraint(
                fields=("calendar_name", "day"),
                name="bizcal_unique_calendar_holiday_day",
            )
        ]
        indexes = [
            models.Index(
                fields=("calendar_name", "day"),
                name="bizcal_holiday_calendar_day_idx",
            ),
            models.Index(
                fields=("calendar_name", "is_active"),
                name="bizcal_holiday_calendar_active_idx",
            ),
        ]

    def __str__(self) -> str:
        label = f" ({self.name})" if self.name else ""
        return f"{self.calendar_name} @ {self.day.isoformat()}{label}"


class CalendarDayOverride(models.Model):  # type: ignore[misc]
    """Persisted per-day override that replaces a calendar's normal schedule."""

    calendar_name = models.CharField(max_length=100, db_index=True)
    day = models.DateField(db_index=True)
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("calendar_name", "day")
        verbose_name = "calendar day override"
        verbose_name_plural = "calendar day overrides"
        constraints = [
            models.UniqueConstraint(
                fields=("calendar_name", "day"),
                name="bizcal_unique_calendar_day_override_day",
            )
        ]
        indexes = [
            models.Index(
                fields=("calendar_name", "day"),
                name="bizcal_day_override_calendar_day_idx",
            ),
            models.Index(
                fields=("calendar_name", "is_active"),
                name="bizcal_day_override_calendar_active_idx",
            ),
        ]

    def __str__(self) -> str:
        label = f" ({self.name})" if self.name else ""
        return f"{self.calendar_name} @ {self.day.isoformat()}{label}"


class CalendarDayOverrideWindow(models.Model):  # type: ignore[misc]
    """Persisted intraday time window belonging to a `CalendarDayOverride`."""

    override = models.ForeignKey(
        CalendarDayOverride,
        on_delete=models.CASCADE,
        related_name="windows",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("override", "position", "start_time", "end_time", "pk")
        verbose_name = "calendar day override window"
        verbose_name_plural = "calendar day override windows"
        constraints = [
            models.CheckConstraint(
                **{
                    _CHECK_CONSTRAINT_ARG: Q(end_time__gt=F("start_time")),
                    "name": "bizcal_day_override_window_start_before_end",
                }
            ),
            models.UniqueConstraint(
                fields=("override", "position"),
                name="bizcal_unique_day_override_window_position",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.override.calendar_name} @ {self.override.day.isoformat()} "
            f"{self.start_time.isoformat()}-{self.end_time.isoformat()}"
        )

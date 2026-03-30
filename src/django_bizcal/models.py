"""Optional Django persistence models for django-bizcal."""

from __future__ import annotations

from django.db import models


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

"""Admin registrations for optional django-bizcal models."""

from __future__ import annotations

from django.contrib import admin

from .models import CalendarHoliday


@admin.register(CalendarHoliday)
class CalendarHolidayAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Minimal admin for managing persisted holiday closures."""

    list_display = ("calendar_name", "day", "name", "is_active")
    list_filter = ("calendar_name", "is_active")
    search_fields = ("calendar_name", "name")
    ordering = ("calendar_name", "day")

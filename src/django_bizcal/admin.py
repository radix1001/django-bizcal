"""Admin registrations for optional django-bizcal models."""

from __future__ import annotations

from django.contrib import admin

from .models import CalendarDayOverride, CalendarDayOverrideWindow, CalendarHoliday


class CalendarDayOverrideWindowInline(admin.TabularInline):  # type: ignore[misc]
    """Inline editor for intraday override windows."""

    model = CalendarDayOverrideWindow
    extra = 0
    ordering = ("position", "start_time")


@admin.register(CalendarHoliday)
class CalendarHolidayAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Minimal admin for managing persisted holiday closures."""

    list_display = ("calendar_name", "day", "name", "is_active")
    list_filter = ("calendar_name", "is_active")
    search_fields = ("calendar_name", "name")
    ordering = ("calendar_name", "day")


@admin.register(CalendarDayOverride)
class CalendarDayOverrideAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin for persisted per-day schedule replacements."""

    list_display = ("calendar_name", "day", "name", "is_active")
    list_filter = ("calendar_name", "is_active")
    search_fields = ("calendar_name", "name")
    ordering = ("calendar_name", "day")
    inlines = [CalendarDayOverrideWindowInline]

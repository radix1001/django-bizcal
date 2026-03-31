"""Admin registrations for optional django-bizcal models."""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.forms import BaseInlineFormSet
from django.http import HttpRequest

from .db import replace_day_override_windows
from .models import CalendarDayOverride, CalendarDayOverrideWindow, CalendarHoliday
from .services import reset_calendar_cache


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

    def save_model(
        self,
        request: HttpRequest,
        obj: CalendarHoliday,
        form: Any,
        change: bool,
    ) -> None:
        super().save_model(request, obj, form, change)
        reset_calendar_cache(obj.calendar_name)

    def delete_model(self, request: HttpRequest, obj: CalendarHoliday) -> None:
        calendar_name = obj.calendar_name
        super().delete_model(request, obj)
        reset_calendar_cache(calendar_name)


@admin.register(CalendarDayOverride)
class CalendarDayOverrideAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin for persisted per-day schedule replacements."""

    list_display = ("calendar_name", "day", "name", "is_active")
    list_filter = ("calendar_name", "is_active")
    search_fields = ("calendar_name", "name")
    ordering = ("calendar_name", "day")
    inlines = [CalendarDayOverrideWindowInline]

    def save_model(
        self,
        request: HttpRequest,
        obj: CalendarDayOverride,
        form: Any,
        change: bool,
    ) -> None:
        super().save_model(request, obj, form, change)
        reset_calendar_cache(obj.calendar_name)

    def save_related(
        self,
        request: HttpRequest,
        form: Any,
        formsets: list[BaseInlineFormSet[Any]],
        change: bool,
    ) -> None:
        super().save_related(request, form, formsets, change)
        override = form.instance
        using = override._state.db or "default"
        replace_day_override_windows(
            override,
            (
                (window.start_time, window.end_time)
                for window in override.windows.all().order_by(
                    "position",
                    "start_time",
                    "end_time",
                    "pk",
                )
            ),
            using=using,
        )
        reset_calendar_cache(override.calendar_name)

    def delete_model(self, request: HttpRequest, obj: CalendarDayOverride) -> None:
        calendar_name = obj.calendar_name
        super().delete_model(request, obj)
        reset_calendar_cache(calendar_name)

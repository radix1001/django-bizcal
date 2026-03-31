# mypy: disable-error-code="untyped-decorator"

"""Admin registrations for optional django-bizcal models."""

from __future__ import annotations

from typing import Any, cast

from django.contrib import admin
from django.db.models import Prefetch
from django.forms import BaseInlineFormSet
from django.http import HttpRequest
from django.utils import timezone

from .db import replace_day_override_windows
from .models import CalendarDayOverride, CalendarDayOverrideWindow, CalendarHoliday
from .services import reset_calendar_cache


class CalendarDayOverrideWindowInline(admin.TabularInline):  # type: ignore[misc]
    """Inline editor for intraday override windows."""

    model = CalendarDayOverrideWindow
    extra = 0
    fields = ("position", "start_time", "end_time")
    ordering = ("position", "start_time")


@admin.register(CalendarHoliday)
class CalendarHolidayAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Minimal admin for managing persisted holiday closures."""

    actions = ("activate_selected", "deactivate_selected")
    date_hierarchy = "day"
    list_display = ("calendar_name", "day", "name", "is_active", "updated_at")
    list_editable = ("is_active",)
    list_filter = ("calendar_name", "is_active")
    readonly_fields = ("created_at", "updated_at")
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

    @admin.action(description="Activate selected holidays")
    def activate_selected(self, request: HttpRequest, queryset: Any) -> None:
        self._set_active_state(queryset, True)

    @admin.action(description="Deactivate selected holidays")
    def deactivate_selected(self, request: HttpRequest, queryset: Any) -> None:
        self._set_active_state(queryset, False)

    def _set_active_state(self, queryset: Any, is_active: bool) -> None:
        changed = queryset.exclude(is_active=is_active)
        names = tuple(sorted(set(changed.values_list("calendar_name", flat=True))))
        if not names:
            return
        changed.update(is_active=is_active, updated_at=timezone.now())
        for name in names:
            reset_calendar_cache(name)


@admin.register(CalendarDayOverride)
class CalendarDayOverrideAdmin(admin.ModelAdmin):  # type: ignore[misc]
    """Admin for persisted per-day schedule replacements."""

    actions = ("activate_selected", "deactivate_selected")
    date_hierarchy = "day"
    list_display = (
        "calendar_name",
        "day",
        "name",
        "window_count",
        "window_summary",
        "is_active",
        "updated_at",
    )
    list_editable = ("is_active",)
    list_filter = ("calendar_name", "is_active")
    readonly_fields = ("window_summary", "created_at", "updated_at")
    search_fields = ("calendar_name", "name")
    ordering = ("calendar_name", "day")
    inlines = [CalendarDayOverrideWindowInline]

    def get_queryset(self, request: HttpRequest) -> Any:
        return super().get_queryset(request).prefetch_related(
            Prefetch(
                "windows",
                queryset=CalendarDayOverrideWindow.objects.order_by(
                    "position",
                    "start_time",
                    "end_time",
                    "pk",
                ),
            )
        )

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

    @admin.display(description="Window count")
    def window_count(self, obj: CalendarDayOverride) -> int:
        return cast(int, obj.windows.count())

    @admin.display(description="Windows")
    def window_summary(self, obj: CalendarDayOverride) -> str:
        windows = tuple(obj.windows.all())
        if not windows:
            return "Closed"
        return ", ".join(
            f"{window.start_time.strftime('%H:%M')}-{window.end_time.strftime('%H:%M')}"
            for window in windows
        )

    @admin.action(description="Activate selected day overrides")
    def activate_selected(self, request: HttpRequest, queryset: Any) -> None:
        self._set_active_state(queryset, True)

    @admin.action(description="Deactivate selected day overrides")
    def deactivate_selected(self, request: HttpRequest, queryset: Any) -> None:
        self._set_active_state(queryset, False)

    def _set_active_state(self, queryset: Any, is_active: bool) -> None:
        changed = queryset.exclude(is_active=is_active)
        names = tuple(sorted(set(changed.values_list("calendar_name", flat=True))))
        if not names:
            return
        changed.update(is_active=is_active, updated_at=timezone.now())
        for name in names:
            reset_calendar_cache(name)

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from django.contrib import admin
from django.test import RequestFactory

from django_bizcal import WorkingCalendar
from django_bizcal import deadlines as deadlines_module
from django_bizcal import resolvers as resolvers_module
from django_bizcal import services as services_module
from django_bizcal import signals as signals_module
from django_bizcal.deadlines import BusinessDeadline, _resolve_day_deadline
from django_bizcal.exceptions import CalendarConfigurationError, ValidationError
from django_bizcal.models import CalendarDayOverride, CalendarDayOverrideWindow, CalendarHoliday
from django_bizcal.services import (
    activate_calendar_day_override,
    deactivate_calendar_day_override,
    deactivate_calendar_holiday,
    delete_calendar_day_override,
    get_calendar,
    get_calendar_day_override_windows,
    reset_calendar_cache,
    set_calendar_day_override,
    set_calendar_holiday,
    sync_calendar_day_overrides,
    sync_calendar_holidays,
)
from django_bizcal.settings import get_bizcal_settings


def test_deadline_helpers_cover_remaining_snap_and_validation(
    monkeypatch: pytest.MonkeyPatch,
    support_calendar: WorkingCalendar,
) -> None:
    fixed_now = datetime(2026, 3, 2, 12, 0, tzinfo=ZoneInfo("America/Santiago"))

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return fixed_now if tz is None else fixed_now.astimezone(tz)

    monkeypatch.setattr(deadlines_module, "datetime", FrozenDateTime)
    start = datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("America/Santiago"))
    deadline = BusinessDeadline(
        start=start,
        service_time=timedelta(hours=4),
        deadline=datetime(2026, 3, 2, 15, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
        calendar_name=" support ",
    )

    assert deadline.remaining() == timedelta(hours=2)
    assert deadline.remaining_minutes() == 120.0
    assert support_calendar.due_on_next_business_day(
        datetime(2026, 3, 6, 12, 0),
        at="15:30",
    ) == datetime(2026, 3, 9, 15, 30, tzinfo=ZoneInfo("America/Santiago"))

    closed_calendar = WorkingCalendar(tz="UTC", weekly_schedule={})
    with pytest.raises(ValidationError):
        _resolve_day_deadline(date(2026, 3, 2), calendar=closed_calendar, at="opening", tz=None)
    with pytest.raises(ValidationError):
        BusinessDeadline(
            start=start,
            service_time=timedelta(hours=-1),
            deadline=start,
            calendar=support_calendar,
        )
    with pytest.raises(ValidationError):
        BusinessDeadline(
            start=start,
            service_time=timedelta(hours=1),
            deadline=start,
            calendar=support_calendar,
            calendar_name="   ",
        )


def test_resolvers_cover_mapping_and_validation_branches() -> None:
    resolution = resolvers_module.normalize_calendar_resolution(
        {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"0": [["09:00", "18:00"]]},
        }
    )

    assert resolution.config is not None
    assert resolution.name is None

    deadline_policy_resolution = resolvers_module.normalize_deadline_policy_resolution(
        {
            "type": "business_duration",
            "business_hours": 4,
        }
    )

    assert deadline_policy_resolution.config is not None
    assert deadline_policy_resolution.name is None

    with pytest.raises(CalendarConfigurationError):
        resolvers_module.CalendarResolution()
    with pytest.raises(CalendarConfigurationError):
        resolvers_module.CalendarResolution.for_config(
            {
                "type": "working",
                "tz": "UTC",
                "weekly_schedule": {"0": [["09:00", "18:00"]]},
            },
            cache_key="   ",
        )
    with pytest.raises(CalendarConfigurationError):
        resolvers_module.DeadlinePolicyResolution()
    with pytest.raises(CalendarConfigurationError):
        resolvers_module.DeadlinePolicyResolution.for_config(
            {
                "type": "business_duration",
                "business_hours": 4,
            },
            cache_key="   ",
        )


def test_signals_cover_blank_name_and_missing_override(monkeypatch: pytest.MonkeyPatch) -> None:
    callbacks: list[tuple[object, str]] = []
    monkeypatch.setattr(
        signals_module.transaction,
        "on_commit",
        lambda callback, *, using: callbacks.append((callback, using)),
    )

    signals_module._reset_named_calendar_after_commit(None, using="default")
    assert callbacks == []

    class MissingOverride:
        @property
        def calendar_name(self) -> str:
            raise CalendarDayOverride.DoesNotExist

    window = SimpleNamespace(override=MissingOverride())
    signals_module._capture_window_calendar_name(
        sender=CalendarDayOverrideWindow,
        instance=window,
    )

    assert window._cached_calendar_name is None


def test_settings_cover_validation_and_explicit_default_branch(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "custom"
    settings.BIZCAL_DEFAULT_CALENDAR = {
        "type": "working",
        "tz": "UTC",
        "weekly_schedule": {"0": [["09:00", "17:00"]]},
    }
    settings.BIZCAL_CALENDARS = {
        "support": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"1": [["10:00", "16:00"]]},
        }
    }
    reset_calendar_cache()

    resolved = get_bizcal_settings()

    assert tuple(resolved.calendar_configs) == ("support", "custom")
    assert resolved.default_calendar.tz.key == "UTC"

    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "   "
    reset_calendar_cache()
    with pytest.raises(ValueError):
        get_bizcal_settings()

    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "custom"
    settings.BIZCAL_DEFAULT_CALENDAR = []
    reset_calendar_cache()
    with pytest.raises(ValueError):
        get_bizcal_settings()

    settings.BIZCAL_DEFAULT_CALENDAR = {
        "type": "working",
        "tz": "UTC",
        "weekly_schedule": {"0": [["09:00", "17:00"]]},
    }
    settings.BIZCAL_CALENDARS = []
    reset_calendar_cache()
    with pytest.raises(ValueError):
        get_bizcal_settings()


@pytest.mark.django_db
def test_service_helpers_cover_missing_and_reactivation_branches() -> None:
    assert get_calendar_day_override_windows("support", "2026-12-24") is None
    assert deactivate_calendar_holiday("support", "2026-12-24") is None
    assert deactivate_calendar_day_override("support", "2026-12-24") is None
    assert delete_calendar_day_override("support", "2026-12-24") is False

    with pytest.raises(ValidationError):
        activate_calendar_day_override("support", "2026-12-24")
    with pytest.raises(ValidationError):
        get_calendar("   ")

    set_calendar_holiday("support", "2026-12-24", is_active=False)
    synced_holidays = sync_calendar_holidays("support", ["2026-12-24"])
    assert synced_holidays[0].is_active is True

    set_calendar_day_override("support", "2026-12-25", [("09:00", "11:00")], is_active=False)
    synced_overrides = sync_calendar_day_overrides(
        "support",
        {"2026-12-25": [("10:00", "12:00")]},
    )
    assert synced_overrides[0].is_active is True

    calendar = WorkingCalendar(tz="UTC", weekly_schedule={0: [("09:00", "18:00")]})
    assert services_module._bind_calendar_name(calendar, None) is calendar


@pytest.mark.django_db
def test_model_string_representations_cover_optional_labels() -> None:
    holiday = CalendarHoliday.objects.create(calendar_name="support", day=date(2026, 12, 24))
    override = CalendarDayOverride.objects.create(calendar_name="support", day=date(2026, 12, 25))
    window = CalendarDayOverrideWindow.objects.create(
        override=override,
        start_time=time(9, 0),
        end_time=time(11, 0),
        position=0,
    )

    assert str(holiday) == "support @ 2026-12-24"
    assert str(override) == "support @ 2026-12-25"
    assert str(window) == "support @ 2026-12-25 09:00:00-11:00:00"


@pytest.mark.django_db
def test_admin_helpers_cover_save_delete_and_noop_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = RequestFactory().get("/admin/")
    reset_calls: list[str] = []
    monkeypatch.setattr("django_bizcal.admin.reset_calendar_cache", reset_calls.append)

    holiday_admin = admin.site._registry[CalendarHoliday]
    holiday = CalendarHoliday(calendar_name="support", day=date(2026, 12, 24), is_active=True)
    holiday_admin.save_model(request, holiday, form=None, change=False)
    assert reset_calls == ["support"]

    reset_calls.clear()
    holiday_admin.activate_selected(request, CalendarHoliday.objects.filter(pk=holiday.pk))
    assert reset_calls == []

    holiday.is_active = False
    holiday.save(update_fields=["is_active", "updated_at"])
    holiday_admin.activate_selected(request, CalendarHoliday.objects.filter(pk=holiday.pk))
    holiday.refresh_from_db()
    assert holiday.is_active is True
    assert reset_calls == ["support"]

    reset_calls.clear()
    holiday_admin.deactivate_selected(request, CalendarHoliday.objects.filter(pk=holiday.pk))
    holiday.refresh_from_db()
    assert holiday.is_active is False
    assert reset_calls == ["support"]

    reset_calls.clear()
    holiday_admin.delete_model(request, holiday)
    assert reset_calls == ["support"]

    override_admin = admin.site._registry[CalendarDayOverride]
    override = CalendarDayOverride.objects.create(
        calendar_name="support",
        day=date(2026, 12, 25),
        is_active=True,
    )
    CalendarDayOverrideWindow.objects.create(
        override=override,
        start_time=time(9, 0),
        end_time=time(11, 0),
        position=0,
    )
    empty_override = CalendarDayOverride.objects.create(
        calendar_name="support",
        day=date(2026, 12, 26),
        is_active=True,
    )

    queryset = override_admin.get_queryset(request)
    prefetched = queryset.get(pk=override.pk)
    assert override_admin.window_summary(empty_override) == "Closed"
    assert override_admin.window_summary(prefetched) == "09:00-11:00"

    reset_calls.clear()
    new_override = CalendarDayOverride(calendar_name="support", day=date(2026, 12, 27))
    override_admin.save_model(request, new_override, form=None, change=False)
    assert reset_calls == ["support"]

    reset_calls.clear()
    captured: list[tuple[tuple[time, time], ...]] = []
    monkeypatch.setattr(
        "django_bizcal.admin.replace_day_override_windows",
        lambda obj, windows, *, using: captured.append(tuple(windows)),
    )
    monkeypatch.setattr(
        admin.ModelAdmin,
        "save_related",
        lambda self, request, form, formsets, change: None,
    )
    override_admin.save_related(
        request,
        form=SimpleNamespace(instance=prefetched),
        formsets=[],
        change=True,
    )
    assert captured == [((time(9, 0), time(11, 0)),)]
    assert reset_calls == ["support"]

    reset_calls.clear()
    override_admin.activate_selected(request, CalendarDayOverride.objects.filter(pk=prefetched.pk))
    assert reset_calls == []

    override_admin.deactivate_selected(
        request,
        CalendarDayOverride.objects.filter(pk=prefetched.pk),
    )
    prefetched.refresh_from_db()
    assert prefetched.is_active is False
    assert reset_calls == ["support"]

    reset_calls.clear()
    override_admin.delete_model(request, prefetched)
    assert reset_calls == ["support"]

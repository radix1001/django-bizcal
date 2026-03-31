from __future__ import annotations

from datetime import date

import pytest
from django.contrib import admin
from django.db import IntegrityError, connection
from django.db.migrations.executor import MigrationExecutor

from django_bizcal.admin import CalendarHolidayAdmin
from django_bizcal.calendars.working import WorkingCalendar
from django_bizcal.db import DatabaseHolidayProvider, apply_database_holiday_overrides
from django_bizcal.django_api import CalendarHoliday as CalendarHolidayFromApi
from django_bizcal.exceptions import ValidationError
from django_bizcal.models import CalendarHoliday
from django_bizcal.services import (
    activate_calendar_holiday,
    deactivate_calendar_holiday,
    delete_calendar_holiday,
    get_calendar,
    get_calendar_holiday,
    list_calendar_holiday_days,
    list_calendar_holidays,
    reset_calendar_cache,
    set_calendar_holiday,
    sync_calendar_holidays,
)

pytestmark = pytest.mark.django_db


def test_calendar_holiday_model_enforces_uniqueness() -> None:
    CalendarHoliday.objects.create(
        calendar_name="support",
        day=date(2026, 12, 24),
        name="Company shutdown",
    )
    with pytest.raises(IntegrityError):
        CalendarHoliday.objects.create(
            calendar_name="support",
            day=date(2026, 12, 24),
            name="Duplicate",
        )


def test_django_persistence_public_surface_and_admin_registration() -> None:
    assert CalendarHolidayFromApi is CalendarHoliday
    assert isinstance(admin.site._registry[CalendarHoliday], CalendarHolidayAdmin)


def test_django_persistence_migration_is_registered() -> None:
    executor = MigrationExecutor(connection)
    assert ("django_bizcal", "0001_initial") in executor.loader.graph.nodes
    assert "django_bizcal_calendarholiday" in connection.introspection.table_names()


def test_database_holiday_provider_reads_active_rows_only() -> None:
    CalendarHoliday.objects.create(calendar_name="support", day=date(2026, 12, 24))
    CalendarHoliday.objects.create(
        calendar_name="support",
        day=date(2026, 12, 31),
        is_active=False,
    )

    provider = DatabaseHolidayProvider("support")

    assert provider.is_holiday(date(2026, 12, 24)) is True
    assert provider.is_holiday(date(2026, 12, 31)) is False


def test_database_holiday_provider_validates_name_and_model_string() -> None:
    holiday = CalendarHoliday.objects.create(
        calendar_name="support",
        day=date(2026, 12, 24),
        name="Company shutdown",
    )
    assert str(holiday) == "support @ 2026-12-24 (Company shutdown)"
    with pytest.raises(ValidationError):
        DatabaseHolidayProvider("   ")


def test_apply_database_holiday_overrides_returns_base_calendar_when_empty() -> None:
    calendar = WorkingCalendar(tz="UTC", weekly_schedule={0: [("09:00", "18:00")]})

    resolved = apply_database_holiday_overrides(calendar, calendar_name="support")

    assert resolved is calendar


def test_calendar_holiday_service_helpers_support_crud_and_listing() -> None:
    created = set_calendar_holiday("support", "2026-12-24", name="Shutdown")
    listed = list_calendar_holidays("support")

    assert created.name == "Shutdown"
    assert [holiday.day for holiday in listed] == [date(2026, 12, 24)]
    assert list_calendar_holiday_days("support") == (date(2026, 12, 24),)
    assert get_calendar_holiday("support", "2026-12-24") is not None
    assert delete_calendar_holiday("support", "2026-12-24") is True
    assert get_calendar_holiday("support", "2026-12-24") is None
    assert delete_calendar_holiday("support", "2026-12-24") is False


def test_calendar_holiday_service_helpers_support_activate_and_deactivate() -> None:
    set_calendar_holiday("support", "2026-12-24", name="Shutdown")

    deactivated = deactivate_calendar_holiday("support", "2026-12-24")

    assert deactivated is not None
    assert deactivated.is_active is False
    assert get_calendar_holiday("support", "2026-12-24") is None

    reactivated = activate_calendar_holiday("support", "2026-12-24")

    assert reactivated.is_active is True
    assert reactivated.name == "Shutdown"


def test_sync_calendar_holidays_sets_the_exact_active_set() -> None:
    set_calendar_holiday("support", "2026-12-24", name="Shutdown")
    set_calendar_holiday("support", "2026-12-31", name="Year end")

    synced = sync_calendar_holidays("support", ["2026-12-31", "2027-01-02"])

    assert [holiday.day for holiday in synced] == [date(2026, 12, 31), date(2027, 1, 2)]
    assert [holiday.day for holiday in list_calendar_holidays("support")] == [
        date(2026, 12, 31),
        date(2027, 1, 2),
    ]
    all_rows = list_calendar_holidays("support", include_inactive=True)
    assert any(
        holiday.day == date(2026, 12, 24) and holiday.is_active is False
        for holiday in all_rows
    )


def test_calendar_holiday_helpers_clear_cached_named_calendars(settings) -> None:
    settings.BIZCAL_ENABLE_DB_MODELS = True
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"
    settings.BIZCAL_CALENDARS = {
        "support": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"3": [["09:00", "18:00"]]},
        }
    }
    reset_calendar_cache()

    calendar = get_calendar("support")
    assert calendar.is_business_day(date(2026, 12, 24)) is True

    set_calendar_holiday("support", "2026-12-24", name="Shutdown")

    assert get_calendar("support").is_business_day(date(2026, 12, 24)) is False

    delete_calendar_holiday("support", "2026-12-24")

    assert get_calendar("support").is_business_day(date(2026, 12, 24)) is True


def test_selective_cache_invalidation_keeps_other_named_calendars_hot(settings) -> None:
    settings.BIZCAL_ENABLE_DB_MODELS = True
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"
    settings.BIZCAL_CALENDARS = {
        "support": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"3": [["09:00", "18:00"]]},
        },
        "operations": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"3": [["08:00", "12:00"]]},
        },
    }
    reset_calendar_cache()

    support_before = get_calendar("support")
    operations_before = get_calendar("operations")

    set_calendar_holiday("support", "2026-12-24", name="Shutdown")

    support_after = get_calendar("support")
    operations_after = get_calendar("operations")

    assert support_after is not support_before
    assert operations_after is operations_before


def test_database_holidays_are_auto_applied_to_named_working_calendars(settings) -> None:
    settings.BIZCAL_ENABLE_DB_MODELS = True
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"
    settings.BIZCAL_CALENDARS = {
        "support": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"3": [["09:00", "18:00"]]},
        }
    }
    CalendarHoliday.objects.create(
        calendar_name="support",
        day=date(2026, 12, 24),
        name="Company shutdown",
    )
    reset_calendar_cache()

    calendar = get_calendar("support")

    assert calendar.is_business_day(date(2026, 12, 24)) is False


def test_database_holidays_are_auto_applied_to_named_composite_calendars(settings) -> None:
    settings.BIZCAL_ENABLE_DB_MODELS = True
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "regional"
    settings.BIZCAL_CALENDARS = {
        "regional": {
            "type": "union",
            "tz": "UTC",
            "children": [
                {
                    "type": "working",
                    "tz": "UTC",
                    "weekly_schedule": {"3": [["09:00", "12:00"]]},
                },
                {
                    "type": "working",
                    "tz": "UTC",
                    "weekly_schedule": {"3": [["13:00", "18:00"]]},
                },
            ],
        }
    }
    CalendarHoliday.objects.create(calendar_name="regional", day=date(2026, 12, 24))
    reset_calendar_cache()

    calendar = get_calendar("regional")

    assert calendar.is_business_day(date(2026, 12, 24)) is False


def test_database_holidays_are_ignored_when_feature_flag_is_disabled(settings) -> None:
    settings.BIZCAL_ENABLE_DB_MODELS = False
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"
    settings.BIZCAL_CALENDARS = {
        "support": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"3": [["09:00", "18:00"]]},
        }
    }
    CalendarHoliday.objects.create(calendar_name="support", day=date(2026, 12, 24))
    reset_calendar_cache()

    calendar = get_calendar("support")

    assert calendar.is_business_day(date(2026, 12, 24)) is True


@pytest.mark.django_db(transaction=True)
def test_direct_orm_holiday_changes_invalidate_named_calendar_cache(settings) -> None:
    settings.BIZCAL_ENABLE_DB_MODELS = True
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"
    settings.BIZCAL_CALENDARS = {
        "support": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"3": [["09:00", "18:00"]]},
        }
    }
    reset_calendar_cache()

    before = get_calendar("support")
    assert before.is_business_day(date(2026, 12, 24)) is True

    CalendarHoliday.objects.create(calendar_name="support", day=date(2026, 12, 24), name="Shutdown")

    after = get_calendar("support")

    assert after is not before
    assert after.is_business_day(date(2026, 12, 24)) is False

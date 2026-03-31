from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from django.contrib import admin
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext

from django_bizcal.admin import CalendarDayOverrideAdmin
from django_bizcal.db import (
    DatabaseDayOverrideProvider,
    DatabaseHolidayProvider,
    apply_database_overrides,
    replace_day_override_windows,
)
from django_bizcal.django_api import (
    CalendarDayOverride,
    CalendarDayOverrideWindow,
)
from django_bizcal.django_api import (
    DatabaseDayOverrideProvider as DatabaseDayOverrideProviderFromApi,
)
from django_bizcal.models import CalendarHoliday
from django_bizcal.services import (
    activate_calendar_day_override,
    deactivate_calendar_day_override,
    delete_calendar_day_override,
    get_calendar,
    get_calendar_day_override,
    list_calendar_day_overrides,
    reset_calendar_cache,
    set_calendar_day_override,
    sync_calendar_day_overrides,
)

pytestmark = pytest.mark.django_db


def test_day_override_public_surface_admin_and_migration_are_registered() -> None:
    assert DatabaseDayOverrideProviderFromApi is DatabaseDayOverrideProvider
    assert isinstance(admin.site._registry[CalendarDayOverride], CalendarDayOverrideAdmin)
    executor = MigrationExecutor(connection)
    assert ("django_bizcal", "0002_day_overrides") in executor.loader.graph.nodes
    table_names = connection.introspection.table_names()
    assert "django_bizcal_calendardayoverride" in table_names
    assert "django_bizcal_calendayoverridewindow" not in table_names
    assert "django_bizcal_calendardayoverridewindow" in table_names


def test_day_override_model_uniqueness_and_window_position_uniqueness() -> None:
    override = CalendarDayOverride.objects.create(calendar_name="support", day=date(2026, 12, 24))
    CalendarDayOverrideWindow.objects.create(
        override=override,
        start_time=time(10, 0),
        end_time=time(12, 0),
        position=0,
    )

    with transaction.atomic():
        with pytest.raises(IntegrityError):
            CalendarDayOverride.objects.create(calendar_name="support", day=date(2026, 12, 24))
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            CalendarDayOverrideWindow.objects.create(
                override=override,
                start_time=time(13, 0),
                end_time=time(15, 0),
                position=0,
            )


def test_database_day_override_provider_reads_active_rows_and_normalizes_windows() -> None:
    set_calendar_day_override(
        "support",
        "2026-12-24",
        [("10:00", "12:00"), ("12:00", "14:00")],
    )
    set_calendar_day_override(
        "support",
        "2026-12-31",
        [("09:00", "11:00")],
        is_active=False,
    )

    provider = DatabaseDayOverrideProvider("support")

    assert provider.overrides[date(2026, 12, 24)] == (provider.overrides[date(2026, 12, 24)][0],)
    assert date(2026, 12, 31) not in provider.overrides
    assert provider.overrides[date(2026, 12, 24)][0].start == time(10, 0)
    assert provider.overrides[date(2026, 12, 24)][0].end == time(14, 0)


def test_replace_day_override_windows_normalizes_and_reindexes_rows() -> None:
    override = CalendarDayOverride.objects.create(calendar_name="support", day=date(2026, 12, 24))
    CalendarDayOverrideWindow.objects.create(
        override=override,
        start_time=time(14, 0),
        end_time=time(16, 0),
        position=3,
    )

    replace_day_override_windows(
        override,
        [("10:00", "12:00"), ("12:00", "14:00"), ("14:00", "16:00")],
    )

    rows = list(override.windows.all().order_by("position", "start_time", "end_time"))

    assert len(rows) == 1
    assert rows[0].position == 0
    assert rows[0].start_time == time(10, 0)
    assert rows[0].end_time == time(16, 0)


def test_database_day_override_provider_uses_prefetch_without_n_plus_one_queries() -> None:
    set_calendar_day_override("support", "2026-12-24", [("09:00", "11:00")])
    set_calendar_day_override("support", "2026-12-31", [("14:00", "16:00")])

    with CaptureQueriesContext(connection) as queries:
        provider = DatabaseDayOverrideProvider("support")
        overrides = provider.overrides

    assert len(queries) == 2
    assert set(overrides) == {date(2026, 12, 24), date(2026, 12, 31)}


def test_public_db_helpers_normalize_calendar_names_consistently() -> None:
    from django_bizcal import WorkingCalendar

    CalendarHoliday.objects.create(calendar_name="support", day=date(2026, 12, 31))
    set_calendar_day_override("support", "2026-12-24", [("10:00", "12:00")])

    holiday_provider = DatabaseHolidayProvider(" support ")
    override_provider = DatabaseDayOverrideProvider(" support ")
    resolved = apply_database_overrides(
        WorkingCalendar(
            tz="UTC",
            weekly_schedule={3: [("09:00", "18:00")], 4: [("09:00", "18:00")]},
        ),
        calendar_name=" support ",
    )

    assert holiday_provider.is_holiday(date(2026, 12, 31)) is True
    assert date(2026, 12, 24) in override_provider.overrides
    assert resolved.business_windows_for_day(date(2026, 12, 24))[0].start == datetime(
        2026,
        12,
        24,
        10,
        0,
        tzinfo=ZoneInfo("UTC"),
    )


def test_apply_database_overrides_gives_day_override_precedence_over_holiday() -> None:
    from django_bizcal import WorkingCalendar

    base = WorkingCalendar(tz="UTC", weekly_schedule={3: [("09:00", "18:00")]})
    CalendarHoliday.objects.create(calendar_name="support", day=date(2026, 12, 24))
    set_calendar_day_override("support", "2026-12-24", [("10:00", "12:00"), ("14:00", "16:00")])

    resolved = apply_database_overrides(base, calendar_name="support")
    windows = resolved.business_windows_for_day(date(2026, 12, 24))

    assert len(windows) == 2
    assert windows[0].start == datetime(2026, 12, 24, 10, 0, tzinfo=ZoneInfo("UTC"))
    assert windows[0].end == datetime(2026, 12, 24, 12, 0, tzinfo=ZoneInfo("UTC"))
    assert windows[1].start == datetime(2026, 12, 24, 14, 0, tzinfo=ZoneInfo("UTC"))
    assert windows[1].end == datetime(2026, 12, 24, 16, 0, tzinfo=ZoneInfo("UTC"))


@pytest.mark.django_db(transaction=True)
def test_direct_orm_day_override_changes_invalidate_named_calendar_cache(settings) -> None:
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
    assert before.business_windows_for_day(date(2026, 12, 24))[0].start == datetime(
        2026,
        12,
        24,
        9,
        0,
        tzinfo=ZoneInfo("UTC"),
    )

    override = CalendarDayOverride.objects.create(calendar_name="support", day=date(2026, 12, 24))
    CalendarDayOverrideWindow.objects.create(
        override=override,
        start_time=time(10, 0),
        end_time=time(12, 0),
        position=0,
    )

    after = get_calendar("support")
    windows = after.business_windows_for_day(date(2026, 12, 24))

    assert after is not before
    assert len(windows) == 1
    assert windows[0].start == datetime(2026, 12, 24, 10, 0, tzinfo=ZoneInfo("UTC"))
    assert windows[0].end == datetime(2026, 12, 24, 12, 0, tzinfo=ZoneInfo("UTC"))


def test_day_override_service_helpers_support_crud_and_sync() -> None:
    created = set_calendar_day_override(
        "support",
        "2026-12-24",
        [("10:00", "12:00")],
        name="Half day",
    )

    assert created.name == "Half day"
    assert [row.day for row in list_calendar_day_overrides("support")] == [date(2026, 12, 24)]
    assert get_calendar_day_override("support", "2026-12-24") is not None

    deactivated = deactivate_calendar_day_override("support", "2026-12-24")
    assert deactivated is not None
    assert deactivated.is_active is False

    reactivated = activate_calendar_day_override("support", "2026-12-24")
    assert reactivated.is_active is True

    synced = sync_calendar_day_overrides(
        "support",
        {
            "2026-12-31": [("09:00", "11:00")],
            "2027-01-02": [("14:00", "18:00")],
        },
    )
    assert [row.day for row in synced] == [date(2026, 12, 31), date(2027, 1, 2)]
    assert [row.day for row in list_calendar_day_overrides("support")] == [
        date(2026, 12, 31),
        date(2027, 1, 2),
    ]
    assert delete_calendar_day_override("support", "2026-12-31") is True


def test_day_override_helpers_invalidate_only_the_affected_named_calendar(settings) -> None:
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

    set_calendar_day_override("support", "2026-12-24", [("10:00", "12:00")], name="Half day")

    support_after = get_calendar("support")
    operations_after = get_calendar("operations")

    assert support_after is not support_before
    assert operations_after is operations_before
    windows = support_after.business_windows_for_day(date(2026, 12, 24))
    assert len(windows) == 1
    assert windows[0].start == datetime(2026, 12, 24, 10, 0, tzinfo=ZoneInfo("UTC"))
    assert windows[0].end == datetime(2026, 12, 24, 12, 0, tzinfo=ZoneInfo("UTC"))

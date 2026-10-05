from __future__ import annotations

import pytest
from django.apps import apps
from django.core import checks
from django.core.management import call_command
from django.db import connection

from django_bizcal.models import CalendarDayOverride, CalendarHoliday

LEGACY_INDEX_NAMES = {
    "bizcal_holiday_calendar_day_idx",
    "bizcal_holiday_calendar_active_idx",
    "bizcal_day_override_calendar_day_idx",
    "bizcal_day_override_calendar_active_idx",
}


def _index_names(model: type) -> set[str]:
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, model._meta.db_table)
    return {name for name, info in constraints.items() if info["index"]}


def test_app_passes_django_system_checks() -> None:
    app_config = apps.get_app_config("django_bizcal")

    errors = [
        message
        for message in checks.run_checks(app_configs=[app_config])
        if message.level >= checks.ERROR
    ]

    assert errors == []


@pytest.mark.django_db
def test_migrated_index_names_match_the_models() -> None:
    for model in (CalendarHoliday, CalendarDayOverride):
        names = _index_names(model)
        assert {index.name for index in model._meta.indexes} <= names
        assert not names & LEGACY_INDEX_NAMES


@pytest.mark.django_db(transaction=True)
def test_index_rename_migration_is_reversible() -> None:
    call_command("migrate", "django_bizcal", "0003", verbosity=0)
    try:
        assert LEGACY_INDEX_NAMES <= _index_names(CalendarHoliday) | _index_names(
            CalendarDayOverride
        )
    finally:
        call_command("migrate", "django_bizcal", verbosity=0)

    for model in (CalendarHoliday, CalendarDayOverride):
        assert {index.name for index in model._meta.indexes} <= _index_names(model)

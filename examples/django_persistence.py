"""Django persistence example for django-bizcal.

Requires a configured Django project with `django_bizcal` in `INSTALLED_APPS`
and `BIZCAL_ENABLE_DB_MODELS = True`.
"""

from __future__ import annotations

from datetime import date

from django_bizcal.django_api import (
    get_calendar,
    get_calendar_day_override_windows,
    list_calendar_holiday_days,
    set_calendar_day_override,
    set_calendar_holiday,
)


def main() -> None:
    set_calendar_holiday("support", date(2026, 12, 31), name="Year-end close")
    set_calendar_day_override(
        "support",
        date(2026, 12, 24),
        [("09:00", "13:00"), ("14:00", "16:00")],
        name="Christmas Eve reduced hours",
    )

    calendar = get_calendar("support")
    windows = get_calendar_day_override_windows("support", date(2026, 12, 24))
    holidays = list_calendar_holiday_days("support")

    print(calendar.business_windows_for_day(date(2026, 12, 24)))
    print(windows)
    print(holidays)


if __name__ == "__main__":
    main()

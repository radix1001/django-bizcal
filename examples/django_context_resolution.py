"""Django contextual calendar resolution example.

Requires a configured Django project with `django_bizcal` in `INSTALLED_APPS`
and `BIZCAL_CALENDAR_RESOLVER` pointing at `support_calendar_resolver`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django_bizcal.django_api import CalendarResolution, get_calendar_for


def support_calendar_resolver(*, context, bizcal_settings):
    region = str(context.get("region", "")).strip().lower()
    if region in {"cl", "mx"}:
        return f"support_{region}"

    tenant = str(context["tenant"]).strip().lower()
    timezone = "America/Santiago" if region != "mx" else "UTC"
    return CalendarResolution.for_config(
        {
            "type": "working",
            "tz": timezone,
            "weekly_schedule": {
                "0": [["09:00", "18:00"]],
                "1": [["09:00", "18:00"]],
                "2": [["09:00", "18:00"]],
                "3": [["09:00", "18:00"]],
                "4": [["09:00", "18:00"]],
            },
        },
        name=f"tenant:{tenant}",
        cache_key=f"tenant:{tenant}:{region or 'default'}",
    )


def main() -> None:
    regional_support = get_calendar_for(region="cl")
    tenant_calendar = get_calendar_for(tenant="acme", region="cl")
    start = datetime.fromisoformat("2026-12-24T15:00:00+00:00")
    tenant_deadline = tenant_calendar.deadline_for(start, timedelta(hours=2))

    print(regional_support.add_business_hours(start, 4))
    print(tenant_deadline.deadline)
    print(tenant_calendar.business_minutes_between(start, tenant_deadline.deadline))


if __name__ == "__main__":
    main()

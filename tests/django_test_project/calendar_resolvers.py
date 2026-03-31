from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django_bizcal.django_api import CalendarResolution


def region_calendar_resolver(
    *,
    context: Mapping[str, Any],
    bizcal_settings,
) -> str:
    region = str(context["region"]).strip().lower()
    mapping = {
        "cl": "support_cl",
        "mx": "support_mx",
    }
    return mapping[region]


def tenant_calendar_resolver(
    *,
    context: Mapping[str, Any],
    bizcal_settings,
) -> CalendarResolution:
    tenant = str(context["tenant"]).strip().lower()
    region = str(context.get("region", "cl")).strip().lower()
    timezone = "America/Santiago" if region == "cl" else "UTC"
    end_time = "18:00" if region == "cl" else "17:00"
    return CalendarResolution.for_config(
        {
            "type": "working",
            "tz": timezone,
            "weekly_schedule": {
                "3": [["09:00", end_time]],
            },
        },
        name=f"tenant:{tenant}",
        cache_key=f"tenant:{tenant}:{region}",
    )


def invalid_calendar_resolver(
    *,
    context: Mapping[str, Any],
    bizcal_settings,
) -> int:
    return 123

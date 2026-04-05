from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django_bizcal.django_api import DeadlinePolicyResolution


def priority_deadline_policy_resolver(
    *,
    context: Mapping[str, Any],
    bizcal_settings,
) -> str:
    priority = str(context["priority"]).strip().lower()
    mapping = {
        "critical": "support_p1",
        "high": "support_same_day",
    }
    return mapping[priority]


def tenant_deadline_policy_resolver(
    *,
    context: Mapping[str, Any],
    bizcal_settings,
) -> DeadlinePolicyResolution:
    tenant = str(context["tenant"]).strip().lower()
    priority = str(context.get("priority", "normal")).strip().lower()
    hours_by_priority = {
        "critical": 4,
        "high": 8,
        "normal": 16,
    }
    return DeadlinePolicyResolution.for_config(
        {
            "type": "business_duration",
            "business_hours": hours_by_priority[priority],
        },
        name=f"tenant_policy:{tenant}:{priority}",
        cache_key=f"tenant_policy:{tenant}:{priority}",
    )


def invalid_deadline_policy_resolver(
    *,
    context: Mapping[str, Any],
    bizcal_settings,
) -> int:
    return 123

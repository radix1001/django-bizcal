"""Helpdesk SLA example for django-bizcal.

Requires a configured Django project with `django_bizcal` in `INSTALLED_APPS`
and a contextual resolver or named calendar registry already configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django_bizcal.django_api import (
    get_calendar_for,
    get_deadline_policy_for,
    is_breached,
    remaining_business_time,
)


@dataclass(frozen=True)
class Ticket:
    tenant: str
    region: str
    created_at: datetime
    priority: str

def main() -> None:
    ticket = Ticket(
        tenant="acme",
        region="cl",
        created_at=datetime.fromisoformat("2026-12-24T12:30:00+00:00"),
        priority="high",
    )

    calendar = get_calendar_for(tenant=ticket.tenant, region=ticket.region)
    policy = get_deadline_policy_for(
        tenant=ticket.tenant,
        region=ticket.region,
        priority=ticket.priority,
    )
    deadline = calendar.resolve_deadline_policy(ticket.created_at, policy)
    checkpoint = datetime.fromisoformat("2026-12-24T18:00:00+00:00")

    print(deadline.calendar_name)
    print(deadline.deadline.isoformat())
    print(remaining_business_time(deadline, now=checkpoint))
    print(is_breached(deadline, now=checkpoint))


if __name__ == "__main__":
    main()

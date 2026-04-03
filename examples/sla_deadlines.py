"""Deadline helper example for django-bizcal."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django_bizcal import (
    WorkingCalendar,
    breach_at,
    business_deadline_at_close,
    deadline_for,
    due_on_next_business_day,
)


def main() -> None:
    calendar = WorkingCalendar(
        tz="America/Santiago",
        weekly_schedule={
            0: [("09:00", "13:00"), ("14:00", "18:00")],
            1: [("09:00", "13:00"), ("14:00", "18:00")],
            2: [("09:00", "13:00"), ("14:00", "18:00")],
            3: [("09:00", "13:00"), ("14:00", "18:00")],
            4: [("09:00", "13:00"), ("14:00", "17:00")],
        },
    )
    start = datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("America/Santiago"))
    target = deadline_for(start, timedelta(hours=8), calendar=calendar)

    print(target.deadline.isoformat())
    print(breach_at(start, timedelta(hours=8), calendar=calendar).isoformat())
    print(due_on_next_business_day("2026-03-06", calendar=calendar, at="closing").isoformat())
    print(business_deadline_at_close("2026-03-05", 2, calendar=calendar).isoformat())


if __name__ == "__main__":
    main()

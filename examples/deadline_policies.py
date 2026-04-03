from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django_bizcal import DeadlinePolicyBuilder, WorkingCalendar


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

    policy = DeadlinePolicyBuilder.from_dict(
        {
            "type": "cutoff",
            "cutoff": "15:00",
            "before": {"type": "close_of_business"},
            "after": {"type": "next_business_day", "at": "closing"},
        }
    )

    before_cutoff = policy.resolve(
        datetime(2026, 3, 5, 14, 30, tzinfo=ZoneInfo("America/Santiago")),
        calendar=calendar,
    )
    after_cutoff = calendar.resolve_deadline_policy(
        datetime(2026, 3, 5, 16, 30, tzinfo=ZoneInfo("America/Santiago")),
        policy,
    )
    serialized = DeadlinePolicyBuilder.to_dict(policy)

    print("before cutoff:", before_cutoff.deadline.isoformat())
    print("after cutoff: ", after_cutoff.deadline.isoformat())
    print("serialized:   ", serialized)


if __name__ == "__main__":
    main()

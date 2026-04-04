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
    vendor_follow_up = DeadlinePolicyBuilder.from_dict(
        {
            "type": "business_days",
            "business_days": 2,
            "at": "13:30",
            "include_start": True,
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
    follow_up = calendar.resolve_deadline_policy(
        datetime(2026, 3, 5, 10, 0, tzinfo=ZoneInfo("America/Santiago")),
        vendor_follow_up,
    )
    serialized = DeadlinePolicyBuilder.to_dict(policy)
    serialized_follow_up = DeadlinePolicyBuilder.to_dict(vendor_follow_up)

    print("before cutoff:", before_cutoff.deadline.isoformat())
    print("after cutoff: ", after_cutoff.deadline.isoformat())
    print("follow up:    ", follow_up.deadline.isoformat())
    print("serialized:   ", serialized)
    print("serialized 2: ", serialized_follow_up)


if __name__ == "__main__":
    main()

"""Overnight work blocks that start one day and end the next."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django_bizcal import CalendarBuilder, WorkingCalendar

SANTIAGO = ZoneInfo("America/Santiago")


def main() -> None:
    night_shift = CalendarBuilder.from_dict(
        {
            "type": "working",
            "country": "CL",
            "tz": "America/Santiago",
            "years": [2026, 2027],
            # A single block per night: 22:00 through 06:00 on the following day.
            "weekly_schedule": {
                "0": [["22:00", "06:00", 1]],
                "1": [["22:00", "06:00", 1]],
                "2": [["22:00", "06:00", 1]],
                "3": [["22:00", "06:00", 1]],
                "4": [["22:00", "06:00", 1]],
            },
            # Default behavior: a holiday suppresses only the shifts starting that day,
            # so a night already running into a holiday morning is preserved.
            "holiday_truncates_overnight": False,
        }
    )
    assert isinstance(night_shift, WorkingCalendar)

    shift_start = datetime(2026, 3, 2, 22, 0, tzinfo=SANTIAGO)
    shift_end = datetime(2026, 3, 3, 6, 0, tzinfo=SANTIAGO)

    print("full shift:", night_shift.business_time_between(shift_start, shift_end))
    print("after 5 business hours:", night_shift.add_business_hours(shift_start, 5).isoformat())
    print("the morning after is a business day:", night_shift.is_business_day("2026-03-03"))

    # Day queries report coverage clipped to the civil day, so the two halves of the
    # night tile the timeline exactly with no gap at midnight.
    monday = night_shift.business_windows_for_day("2026-03-02")
    tuesday = night_shift.business_windows_for_day("2026-03-03")
    print("monday coverage:", [(w.start.isoformat(), w.end.isoformat()) for w in monday])
    print("tuesday coverage:", [(w.start.isoformat(), w.end.isoformat()) for w in tuesday])
    assert monday[-1].end == tuesday[0].start

    # The whole unclipped block, anchored to the day it starts on.
    block = night_shift.business_blocks_for_day("2026-03-02")[0]
    print("whole block:", block.start.isoformat(), "->", block.end.isoformat())
    assert block.duration() == timedelta(hours=8)

    # Close of business follows the block past midnight.
    closing = night_shift.resolve_deadline_policy_dict(
        datetime(2026, 3, 2, 23, 30, tzinfo=SANTIAGO),
        {"type": "same_business_day", "at": "closing"},
    )
    print("close of business:", closing.deadline.isoformat())


if __name__ == "__main__":
    main()

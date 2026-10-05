"""Business-hour and business-day arithmetic with django-bizcal."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django_bizcal import BusinessDaysPolicy, WorkingCalendar

SANTIAGO = ZoneInfo("America/Santiago")


def main() -> None:
    # Monday to Friday, 09:00-13:00 and 14:00-18:00, with Chilean public holidays.
    calendar = WorkingCalendar.from_country(
        country="CL",
        years=[2026, 2027],
        tz="America/Santiago",
        weekly_schedule={
            weekday: [("09:00", "13:00"), ("14:00", "18:00")] for weekday in range(5)
        },
    )
    # Wednesday 16:30. Monday 2026-10-12 is a public holiday.
    start = datetime(2026, 10, 7, 16, 30, tzinfo=SANTIAGO)

    # Business hours: time outside the schedule (lunch, nights, weekends) is skipped.
    print("+2 hours:", calendar.add_business_hours(start, 2))  # Thursday 09:30
    print("+10 hours:", calendar.add_business_hours(start, 10))  # Friday 09:30
    print("+90 minutes:", calendar.add_business_minutes(start, 90))  # Wednesday 18:00
    print("-3 hours:", calendar.add_business_hours(start, -3))  # Wednesday 12:30
    print(
        "+2h30:",
        calendar.add_business_time(start, timedelta(hours=2, minutes=30)),
    )  # Thursday 10:00

    # Business days: the wall-clock time is kept.
    print("+1 day:", calendar.add_business_days(start, 1))  # Thursday 16:30
    print("+3 days:", calendar.add_business_days(start, 3))  # Tuesday 16:30
    print("-1 day:", calendar.add_business_days(start, -1))  # Tuesday 6, 16:30
    after_hours = datetime(2026, 10, 7, 20, 0, tzinfo=SANTIAGO)
    print("+1 day after hours:", calendar.add_business_days(after_hours, 1))  # Friday 09:00

    # Business days at a fixed boundary instead of the start's wall-clock time.
    print("+3 days at close:", calendar.business_deadline_at_close(start, 3))  # Tuesday 18:00
    at_opening = BusinessDaysPolicy(3, at="opening").resolve(start, calendar=calendar)
    print("+3 days at opening:", at_opening.deadline)  # Tuesday 09:00

    # Days and hours combined: move by days first, then add hours.
    print(
        "+3 days and 4 hours:",
        calendar.add_business_hours(at_opening.deadline, 4),
    )  # Tuesday 13:00


if __name__ == "__main__":
    main()

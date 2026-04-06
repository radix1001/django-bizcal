from __future__ import annotations

from datetime import date, datetime, timedelta
from timeit import timeit
from zoneinfo import ZoneInfo

from django_bizcal import WorkingCalendar


def main() -> None:
    calendar = WorkingCalendar(
        tz="America/Santiago",
        weekly_schedule={
            0: [("09:00", "13:00"), ("14:00", "18:00")],
            1: [("09:00", "13:00"), ("14:00", "18:00")],
            2: [("09:00", "13:00"), ("14:00", "18:00")],
            3: [("09:00", "13:00"), ("14:00", "18:00")],
            4: [("09:00", "13:00"), ("14:00", "18:00")],
        },
        day_overrides={"2026-12-24": [("09:00", "12:00")]},
    )

    local_tz = ZoneInfo("America/Santiago")
    day = date(2026, 3, 2)
    start = datetime(2026, 3, 2, 9, 30, tzinfo=local_tz)
    end = datetime(2026, 3, 2, 17, 30, tzinfo=local_tz)

    calendar.business_windows_for_day(day)

    warm_day = timeit(lambda: calendar.business_windows_for_day(day), number=50000)
    uncached_day = timeit(lambda: calendar._business_windows_for_day_local(day), number=50000)
    business_time = timeit(lambda: calendar.business_time_between(start, end), number=20000)
    add_time = timeit(
        lambda: calendar.add_business_time(start, timedelta(hours=6)),
        number=20000,
    )

    print("django-bizcal hot-path benchmark")
    print(f"warm business_windows_for_day x50000: {warm_day:.6f}s")
    print(f"uncached _business_windows_for_day_local x50000: {uncached_day:.6f}s")
    print(f"business_time_between x20000: {business_time:.6f}s")
    print(f"add_business_time x20000: {add_time:.6f}s")


if __name__ == "__main__":
    main()

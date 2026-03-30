"""Quickstart example for django-bizcal."""

from datetime import datetime
from zoneinfo import ZoneInfo

from django_bizcal import CalendarBuilder


def main() -> None:
    calendar = CalendarBuilder.from_dict(
        {
            "type": "working",
            "country": "CL",
            "tz": "America/Santiago",
            "years": [2026, 2027],
            "weekly_schedule": {
                "0": [["09:00", "13:00"], ["14:00", "18:00"]],
                "1": [["09:00", "13:00"], ["14:00", "18:00"]],
                "2": [["09:00", "13:00"], ["14:00", "18:00"]],
                "3": [["09:00", "13:00"], ["14:00", "18:00"]],
                "4": [["09:00", "13:00"], ["14:00", "17:00"]],
            },
            "extra_holidays": ["2026-12-24", "2026-12-31"],
        }
    )
    start = datetime(2026, 3, 2, 12, 0, tzinfo=ZoneInfo("America/Santiago"))
    deadline = calendar.add_business_hours(start, 10)
    print(deadline.isoformat())


if __name__ == "__main__":
    main()


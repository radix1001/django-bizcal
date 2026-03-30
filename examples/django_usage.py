"""Django-oriented example for django-bizcal."""

from django_bizcal.services import get_default_calendar, now


def main() -> None:
    calendar = get_default_calendar()
    deadline = calendar.add_business_hours(now(), 8)
    print(deadline.isoformat())


if __name__ == "__main__":
    main()


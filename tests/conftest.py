from __future__ import annotations

from datetime import date

import pytest

from django_bizcal import WorkingCalendar


@pytest.fixture()
def support_calendar() -> WorkingCalendar:
    return WorkingCalendar(
        tz="America/Santiago",
        weekly_schedule={
            0: [("09:00", "13:00"), ("14:00", "18:00")],
            1: [("09:00", "13:00"), ("14:00", "18:00")],
            2: [("09:00", "13:00"), ("14:00", "18:00")],
            3: [("09:00", "13:00"), ("14:00", "18:00")],
            4: [("09:00", "13:00"), ("14:00", "17:00")],
        },
        day_overrides={
            date(2026, 12, 24): [("09:00", "12:00")],
            date(2026, 12, 31): None,
        },
    )


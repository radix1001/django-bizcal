from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):  # type: ignore[misc]
    """Rename indexes whose names exceeded Django's 30-character limit (models.E034)."""

    dependencies = [
        ("django_bizcal", "0003_overnight_blocks"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="calendarholiday",
            new_name="bizcal_holiday_cal_day_idx",
            old_name="bizcal_holiday_calendar_day_idx",
        ),
        migrations.RenameIndex(
            model_name="calendarholiday",
            new_name="bizcal_holiday_cal_active_idx",
            old_name="bizcal_holiday_calendar_active_idx",
        ),
        migrations.RenameIndex(
            model_name="calendardayoverride",
            new_name="bizcal_override_cal_day_idx",
            old_name="bizcal_day_override_calendar_day_idx",
        ),
        migrations.RenameIndex(
            model_name="calendardayoverride",
            new_name="bizcal_override_cal_active_idx",
            old_name="bizcal_day_override_calendar_active_idx",
        ),
    ]

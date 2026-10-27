"""Начальная разметка флагов формы бронирования (правила — apps/references/reservation.py)."""

from django.db import migrations

from apps.references.reservation import mark_reservation_flags


def mark(apps, schema_editor):
    mark_reservation_flags(
        apps.get_model("references", "MilitarySpeciality"),
        apps.get_model("references", "RegistrationDocument"),
    )


class Migration(migrations.Migration):
    dependencies = [("references", "0004_reservation_flags")]

    operations = [migrations.RunPython(mark, migrations.RunPython.noop)]

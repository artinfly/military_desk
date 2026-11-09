"""Документ 3767 мог быть перенесён под другим названием."""

from django.db import migrations
from django.db.models import Q


def mark(apps, schema_editor):
    Document = apps.get_model("references", "RegistrationDocument")
    Document.objects.using(schema_editor.connection.alias).filter(
        Q(code="3767")
        | Q(
            name__in=(
                "Временное удостоверение взамен военного билета",
                "Справка взамен военного билета",
            )
        )
    ).update(in_reservation_appendix=True)


class Migration(migrations.Migration):
    dependencies = [("references", "0006_remove_unused")]
    operations = [migrations.RunPython(mark, migrations.RunPython.noop)]

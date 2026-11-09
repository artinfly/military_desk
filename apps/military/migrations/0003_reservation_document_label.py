from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("military", "0002_remove_unused")]

    operations = [
        migrations.AlterField(
            model_name="militaryrecord",
            name="reservation_document",
            field=models.CharField("Приказ о бронировании", max_length=50, blank=True),
        ),
    ]

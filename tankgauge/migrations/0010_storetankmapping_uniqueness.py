from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tankgauge", "0009_tankchart_is_official_tankchart_store_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="storetankmapping",
            constraint=models.UniqueConstraint(
                fields=("store", "fuel_type", "tank_index"),
                name="uniq_store_fuel_tank_index",
            ),
        ),
    ]

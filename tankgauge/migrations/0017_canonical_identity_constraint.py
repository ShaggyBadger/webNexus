from django.db import migrations, models


def populate_canonical_fuel(apps, schema_editor):
    StoreTankMapping = apps.get_model("tankgauge", "StoreTankMapping")

    for mapping in StoreTankMapping.objects.all().iterator():
        mapping.canonical_fuel_type = (mapping.fuel_type or "").strip().lower()
        mapping.save(update_fields=["canonical_fuel_type"])


class Migration(migrations.Migration):
    dependencies = [("tankgauge", "0016_storetankmapping_canonical_fuel_type_and_more")]

    operations = [
        migrations.RunPython(populate_canonical_fuel, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="storetankmapping",
            name="uniq_store_fuel_tank_index",
        ),
        migrations.AddConstraint(
            model_name="storetankmapping",
            constraint=models.UniqueConstraint(
                fields=("store", "canonical_fuel_type", "tank_index"),
                name="uniq_store_fuel_tank_index",
            ),
        ),
    ]

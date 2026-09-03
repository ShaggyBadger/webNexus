from django.db import migrations


def correct_site_111_regular_tank(apps, schema_editor):
    Store = apps.get_model("tankgauge", "Store")
    StoreTankMapping = apps.get_model("tankgauge", "StoreTankMapping")
    TankType = apps.get_model("tankgauge", "TankType")

    store = Store.objects.filter(store_num=8203).first()
    tank_type = TankType.objects.filter(name="15k119").first()
    if not store or not tank_type:
        return

    StoreTankMapping.objects.filter(
        store=store,
        tank_index=2,
        fuel_type__iexact="regular",
    ).update(tank_type=tank_type)


class Migration(migrations.Migration):
    dependencies = [
        ("tankgauge", "0013_search_indexes"),
    ]

    operations = [
        migrations.RunPython(
            correct_site_111_regular_tank,
            migrations.RunPython.noop,
        ),
    ]

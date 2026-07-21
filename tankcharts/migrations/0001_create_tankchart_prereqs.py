from django.db import migrations
from django.utils.text import slugify


def create_tankchart_prereqs(apps, schema_editor):
    user_model = apps.get_model("auth", "User")
    category_model = apps.get_model("dms", "Category")
    tag_model = apps.get_model("dms", "Tag")
    fuel_type_model = apps.get_model("missionlog", "FuelType")

    user_model.objects.get_or_create(
        username="system",
        defaults={
            "first_name": "System",
            "last_name": "Automated",
            "is_staff": False,
            "is_active": True,
        },
    )

    category_model.objects.get_or_create(
        slug="tankchart",
        defaults={"name": "Tank Chart", "active": True, "sort_order": 10},
    )

    tag_model.objects.get_or_create(
        slug="tankchart",
        defaults={"name": "Tank Chart"},
    )

    for fuel_type in fuel_type_model.objects.all():
        abbreviation = (
            (fuel_type.abbreviation or fuel_type.name[:3] or "UNK").upper().strip()
        )
        tag_model.objects.get_or_create(
            slug=slugify(abbreviation),
            defaults={"name": abbreviation},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("dms", "0004_tag_document_is_public_document_tags"),
        ("missionlog", "0008_fueltype_abbreviation"),
        ("tankgauge", "0011_add_tankgauge_config"),
    ]

    operations = [
        migrations.RunPython(create_tankchart_prereqs, migrations.RunPython.noop),
    ]

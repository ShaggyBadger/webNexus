from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("missionlog", "0011_productionreportemailaudit_recipient"),
    ]

    operations = [
        migrations.CreateModel(
            name="MissionLogConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "production_gph_target",
                    models.DecimalField(
                        decimal_places=1,
                        default=7000,
                        help_text="Production target used by MissionLog charts and reports (GPH).",
                        max_digits=10,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "MissionLog Configuration",
                "verbose_name_plural": "MissionLog Configuration",
            },
        ),
    ]

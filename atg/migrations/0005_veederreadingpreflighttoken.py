import django.db.models.deletion
import atg.utils.storage
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tankgauge", "0011_add_tankgauge_config"),
        ("missionlog", "0006_mission_hours_on_duty_not_driving"),
        ("atg", "0004_veederticket_ocr_completed_at_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VeederReadingPreflightToken",
            fields=[
                (
                    "id",
                    models.CharField(
                        default=atg.utils.storage.generate_ulid,
                        editable=False,
                        max_length=26,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("tank_index", models.IntegerField()),
                ("payload_hash", models.CharField(db_index=True, max_length=64)),
                (
                    "decision",
                    models.CharField(
                        choices=[
                            ("within_threshold", "Within threshold"),
                            (
                                "outside_threshold_requires_override",
                                "Outside threshold requires override",
                            ),
                            (
                                "bootstrap_requires_confirmation",
                                "Bootstrap requires confirmation",
                            ),
                        ],
                        max_length=64,
                    ),
                ),
                ("threshold_percent", models.FloatField(default=0.01)),
                ("metrics_snapshot", models.JSONField(blank=True, default=dict)),
                ("trace_id", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "consumed_by_ticket",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="consumed_preflight_tokens",
                        to="atg.veederticket",
                    ),
                ),
                (
                    "fuel_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="veeder_preflight_tokens",
                        to="missionlog.fueltype",
                    ),
                ),
                (
                    "issued_to_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="issued_veeder_preflight_tokens",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="veeder_preflight_tokens",
                        to="tankgauge.store",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="veederreadingpreflighttoken",
            index=models.Index(
                fields=["store", "tank_index", "fuel_type", "expires_at"],
                name="atg_veederre_store_i_715305_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="veederreadingpreflighttoken",
            index=models.Index(
                fields=["expires_at", "consumed_at"],
                name="atg_veederre_expires_7588f6_idx",
            ),
        ),
    ]

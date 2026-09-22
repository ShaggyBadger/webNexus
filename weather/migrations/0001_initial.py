import uuid

from django.db import migrations, models


def create_quota_lock(apps, schema_editor):
    quota_lock = apps.get_model("weather", "WeatherQuotaLock")
    quota_lock.objects.create(singleton_key=1)


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="WeatherQuotaLock",
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
                    "singleton_key",
                    models.PositiveSmallIntegerField(default=1, unique=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="WeatherRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("latitude", models.DecimalField(decimal_places=6, max_digits=9)),
                ("longitude", models.DecimalField(decimal_places=6, max_digits=9)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("RESERVED", "Reserved"),
                            ("SUCCEEDED", "Succeeded"),
                            ("FAILED", "Failed"),
                            ("ABANDONED", "Abandoned"),
                        ],
                        max_length=16,
                    ),
                ),
                ("requested_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("reservation_expires_at", models.DateTimeField(blank=True, null=True)),
                ("response_json", models.JSONField(blank=True, null=True)),
                (
                    "http_status",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("error_code", models.CharField(blank=True, max_length=64, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("request_version", models.CharField(default="v1", max_length=20)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["requested_at"], name="weather_req_time_idx"),
                    models.Index(
                        fields=["status", "requested_at"],
                        name="weather_req_status_time_idx",
                    ),
                    models.Index(fields=["completed_at"], name="weather_req_done_idx"),
                ],
            },
        ),
        migrations.RunPython(create_quota_lock, migrations.RunPython.noop),
    ]

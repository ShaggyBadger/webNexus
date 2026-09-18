from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("genericcharts", "0003_tankestimatesyncrun"),
        ("tankgauge", "0017_canonical_identity_constraint"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="tankestimatesyncrun",
            name="scope_type",
            field=models.CharField(
                choices=[("mapping", "One mapping"), ("store", "One store"), ("all", "All stores")],
                default="all",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="tankestimatesyncrun",
            name="mapping",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="estimate_sync_runs",
                to="tankgauge.storetankmapping",
            ),
        ),
        migrations.AddField(
            model_name="tankestimatesyncrun",
            name="requested_profile_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tankestimatesyncrun",
            name="idempotency_key",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(model_name="tankestimatesyncrun", name="affected_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="tankestimatesyncrun", name="succeeded_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="tankestimatesyncrun", name="skipped_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="tankestimatesyncrun", name="failed_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="tankestimatesyncrun", name="warning_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="tankestimatesyncrun", name="preview", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="tankestimatesyncrun", name="result_summary", field=models.JSONField(blank=True, default=dict)),
        migrations.AlterField(
            model_name="tankestimatesyncrun",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("running", "Running"),
                    ("completed", "Completed"),
                    ("partial_failure", "Partial failure"),
                    ("failed", "Failed"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="tankestimatesyncrun",
            constraint=models.UniqueConstraint(
                condition=models.Q(idempotency_key__isnull=False),
                fields=("idempotency_key",),
                name="uniq_tank_sync_idempotency_key",
            ),
        ),
    ]

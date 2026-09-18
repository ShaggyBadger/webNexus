from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("dms", "0006_document_email_count"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="operational_state",
            field=models.CharField(
                choices=[
                    ("USABLE", "Usable"),
                    ("STALE", "Stale"),
                    ("UNSAFE", "Unsafe"),
                    ("SUPERSEDED", "Superseded"),
                ],
                db_index=True,
                default="USABLE",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="invalidation_reason",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="document",
            name="source_profile_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="source_estimate_version",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="invalidated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="invalidated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="invalidated_documents",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["operational_state"], name="dms_doc_operational_state_idx"
            ),
        ),
    ]

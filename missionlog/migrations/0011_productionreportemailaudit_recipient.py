from django.db import migrations, models


def backfill_recipient_email(apps, schema_editor):
    audit_model = apps.get_model("missionlog", "ProductionReportEmailAudit")
    user_model = apps.get_model("auth", "User")

    user_emails = {
        user.pk: (user.email or "").strip() or None
        for user in user_model.objects.only("pk", "email")
    }
    for audit in audit_model.objects.all().iterator():
        recipient_email = user_emails.get(audit.user_id)
        if recipient_email:
            audit.recipient_email = recipient_email
            audit.save(update_fields=["recipient_email"])


class Migration(migrations.Migration):
    dependencies = [
        ("missionlog", "0010_productionreportemailaudit"),
    ]

    operations = [
        migrations.AddField(
            model_name="productionreportemailaudit",
            name="recipient_email",
            field=models.EmailField(
                blank=True,
                help_text="Validated destination captured when the report was queued.",
                max_length=254,
                null=True,
            ),
        ),
        migrations.RunPython(
            backfill_recipient_email,
            migrations.RunPython.noop,
        ),
    ]

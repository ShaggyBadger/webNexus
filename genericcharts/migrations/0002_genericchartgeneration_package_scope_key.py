from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("genericcharts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="genericchartgeneration",
            name="package_scope_key",
            field=models.CharField(
                default="full",
                help_text="Stable selection key used to isolate package files and DMS history.",
                max_length=180,
            ),
        ),
    ]

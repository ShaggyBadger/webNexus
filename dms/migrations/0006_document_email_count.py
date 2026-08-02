from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dms", "0005_search_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="email_count",
            field=models.PositiveIntegerField(
                default=0,
                help_text="Cumulative email send count",
            ),
        ),
    ]

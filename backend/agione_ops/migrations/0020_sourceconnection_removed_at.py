from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agione_ops", "0019_scheduled_report_state")]

    operations = [
        migrations.AddField(
            model_name="sourceconnection",
            name="removed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

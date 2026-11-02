"""Track daily report analysis independently from collection and delivery."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agione_ops", "0018_auto_refresh_state")]

    operations = [
        migrations.AddField(model_name="notificationrules", name="last_report_date",
                            field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="notificationrules", name="last_report_status",
                            field=models.CharField(default="idle", max_length=24)),
        migrations.AddField(model_name="notificationrules", name="last_report_attempts",
                            field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="notificationrules", name="last_report_updated_at",
                            field=models.DateTimeField(blank=True, null=True)),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cloud_billing", "0010_add_balance_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="alertrule",
            name="days_remaining_threshold",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "Estimated days remaining threshold, e.g., 7 means alert "
                    "when projected remaining days drop below 7"
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="alertrecord",
            name="alert_type",
            field=models.CharField(
                choices=[
                    ("cost", "Cost Threshold"),
                    ("growth", "Cost Growth"),
                    ("balance", "Balance Threshold"),
                    ("days_remaining", "Estimated Days Remaining"),
                ],
                default="growth",
                help_text="Primary alert type that triggered this record",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="alertrecord",
            name="current_days_remaining",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Projected remaining days when the alert was triggered",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="alertrecord",
            name="days_remaining_threshold",
            field=models.PositiveIntegerField(
                blank=True,
                help_text=(
                    "Projected remaining days threshold that triggered the alert"
                ),
                null=True,
            ),
        ),
    ]

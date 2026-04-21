from django.db import migrations, models
from django.utils import timezone


def populate_day_from_collected_at(apps, schema_editor):
    BillingData = apps.get_model("cloud_billing", "BillingData")
    for row in BillingData.objects.all().iterator():
        collected_at = row.collected_at
        day = timezone.localtime(collected_at).date() if collected_at else timezone.localdate()
        BillingData.objects.filter(id=row.id).update(day=day)


class Migration(migrations.Migration):

    dependencies = [
        ("cloud_billing", "0011_add_days_remaining_thresholds"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingdata",
            name="day",
            field=models.DateField(
                blank=True,
                db_index=True,
                help_text="Collection day in local timezone",
                null=True,
            ),
        ),
        migrations.RunPython(
            populate_day_from_collected_at,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="billingdata",
            name="day",
            field=models.DateField(
                db_index=True,
                default=timezone.localdate,
                help_text="Collection day in local timezone",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="billingdata",
            unique_together={("provider", "account_id", "period", "day", "hour")},
        ),
        migrations.AddIndex(
            model_name="billingdata",
            index=models.Index(
                fields=["provider", "account_id", "day", "hour"],
                name="cloud_billi_provide_5d6967_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="billingdata",
            index=models.Index(
                fields=["provider", "day", "hour"],
                name="cloud_billi_provide_2811e7_idx",
            ),
        ),
    ]

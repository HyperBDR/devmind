from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cloud_billing", "0009_add_volcengine_provider_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cloudprovider",
            name="provider_type",
            field=models.CharField(
                choices=[
                    ("aws", "AWS"),
                    ("huawei", "Huawei Cloud (China)"),
                    ("huawei-intl", "Huawei Cloud (International)"),
                    ("alibaba", "Alibaba Cloud"),
                    ("azure", "Azure"),
                    ("tencentcloud", "Tencent Cloud"),
                    ("volcengine", "Volcengine"),
                    ("baidu", "Baidu AI Cloud"),
                    ("zhipu", "Zhipu AI"),
                ],
                help_text="Cloud provider type",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="alertrecord",
            name="balance_threshold",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Balance threshold that triggered the alert",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="alertrecord",
            name="current_balance",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Current account balance when alert triggered",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="alertrule",
            name="balance_threshold",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Balance threshold, e.g., 100.00 means alert when account balance drops below 100.00",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="billingdata",
            name="balance",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Account cash balance at collection time",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="cloudprovider",
            name="balance",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Latest synced account balance for this provider",
                max_digits=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="cloudprovider",
            name="balance_currency",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Currency code for the latest synced balance",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="cloudprovider",
            name="balance_updated_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the latest provider balance was synced",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="cloudprovider",
            name="tags",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Custom tags for this provider/account",
            ),
        ),
    ]

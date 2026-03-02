# Generated migration for adding Tencent Cloud provider type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cloud_billing", "0006_alter_billingdata_total_cost_and_more"),
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
                ],
                help_text="Cloud provider type",
                max_length=20,
            ),
        ),
    ]

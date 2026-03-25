# Generated migration for adding Baidu provider type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cloud_billing", "0010_add_balance_fields"),
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
                ],
                help_text="Cloud provider type",
                max_length=20,
            ),
        ),
    ]

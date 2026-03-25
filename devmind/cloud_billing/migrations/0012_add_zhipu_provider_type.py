# Generated migration for adding Zhipu provider type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cloud_billing", "0011_add_baidu_provider_type"),
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
    ]

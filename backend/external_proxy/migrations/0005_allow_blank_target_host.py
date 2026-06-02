from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("external_proxy", "0004_externalsite_target_scheme"),
    ]

    operations = [
        migrations.AlterField(
            model_name="externalsite",
            name="target_host",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "代理模式下填写 host:port，如 frontend:3000 "
                    "或 127.0.0.1:18082"
                ),
                max_length=200,
                verbose_name="目标服务地址",
            ),
        ),
    ]

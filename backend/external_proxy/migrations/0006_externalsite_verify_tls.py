from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("external_proxy", "0005_allow_blank_target_host"),
    ]

    operations = [
        migrations.AddField(
            model_name="externalsite",
            name="verify_tls",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "HTTPS 目标是否校验证书。生产环境强烈建议保持开启；"
                    "仅当目标使用自签证书且无法替换时再关闭。"
                ),
                verbose_name="校验 HTTPS 证书",
            ),
        ),
    ]

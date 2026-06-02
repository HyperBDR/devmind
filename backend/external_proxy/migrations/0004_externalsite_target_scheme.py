from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "external_proxy",
            "0003_externalsite_access_mode_externalsite_external_url_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="externalsite",
            name="target_scheme",
            field=models.CharField(
                choices=[("http", "HTTP"), ("https", "HTTPS")],
                default="http",
                help_text="代理模式下目标服务使用的协议",
                max_length=10,
                verbose_name="目标服务协议",
            ),
        ),
    ]

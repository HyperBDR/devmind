from django.db import migrations

import external_proxy.encrypted_fields


class Migration(migrations.Migration):

    dependencies = [
        ("external_proxy", "0006_externalsite_verify_tls"),
    ]

    operations = [
        migrations.AlterField(
            model_name="externalsite",
            name="static_token",
            field=external_proxy.encrypted_fields.EncryptedCharField(
                blank=True,
                default="",
                help_text="静态 Token，auth_type 为 static_token 时使用",
                max_length=500,
                verbose_name="静态 Token",
            ),
        ),
        migrations.AlterField(
            model_name="externalsite",
            name="hmac_secret",
            field=external_proxy.encrypted_fields.EncryptedCharField(
                blank=True,
                default="",
                help_text="与外部服务共享的 HMAC 密钥",
                max_length=500,
                verbose_name="HMAC 密钥",
            ),
        ),
        migrations.AlterField(
            model_name="externalsite",
            name="token_fetch_headers",
            field=external_proxy.encrypted_fields.EncryptedJSONField(
                blank=True,
                default=dict,
                help_text=(
                    '获取 Token 时的额外请求头，如 {"X-API-Key": "xxx"}'
                ),
                verbose_name="Token 获取请求头",
            ),
        ),
        migrations.AlterField(
            model_name="externalsite",
            name="token_fetch_body",
            field=external_proxy.encrypted_fields.EncryptedJSONField(
                blank=True,
                default=dict,
                help_text="获取 Token 时的请求体 JSON",
                verbose_name="Token 获取请求体",
            ),
        ),
        migrations.AlterField(
            model_name="externalsite",
            name="cached_token",
            field=external_proxy.encrypted_fields.EncryptedTextField(
                blank=True,
                default="",
                editable=False,
                verbose_name="缓存的 Token",
            ),
        ),
    ]

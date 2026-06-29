from django.db import migrations, models


ENCRYPTED_SECRET_PREFIX = "fernet:"


def encrypt_existing_feishu_app_secrets(apps, schema_editor):
    """Encrypt existing Feishu app secrets after widening the field."""
    from hyperbdr_dashboard.encryption import encryption_service

    global_config = apps.get_model("llm_ops", "LLMOpsGlobalConfig")
    queryset = global_config.objects.exclude(feishu_app_secret="")
    for config in queryset.iterator():
        value = config.feishu_app_secret
        if value.startswith(ENCRYPTED_SECRET_PREFIX):
            continue
        config.feishu_app_secret = (
            ENCRYPTED_SECRET_PREFIX + encryption_service.encrypt(value)
        )
        config.save(update_fields=["feishu_app_secret"])


def decrypt_existing_feishu_app_secrets(apps, schema_editor):
    """Restore plaintext secrets when reversing the migration."""
    from hyperbdr_dashboard.encryption import encryption_service

    global_config = apps.get_model("llm_ops", "LLMOpsGlobalConfig")
    queryset = global_config.objects.exclude(feishu_app_secret="")
    for config in queryset.iterator():
        value = config.feishu_app_secret
        if not value.startswith(ENCRYPTED_SECRET_PREFIX):
            continue
        encrypted = value[len(ENCRYPTED_SECRET_PREFIX) :]
        config.feishu_app_secret = encryption_service.decrypt(encrypted)
        config.save(update_fields=["feishu_app_secret"])


class Migration(migrations.Migration):

    dependencies = [
        ("llm_ops", "0005_llmopsglobalconfig"),
    ]

    operations = [
        migrations.AlterField(
            model_name="llmopsglobalconfig",
            name="feishu_app_secret",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.RunPython(
            encrypt_existing_feishu_app_secrets,
            decrypt_existing_feishu_app_secrets,
        ),
    ]

from django.db import migrations

TOKEN_PREFIX = "enc::"


def encrypt_tokens(apps, schema_editor):
    from hyperbdr_dashboard.encryption import encryption_service

    connection_model = apps.get_model("quotation", "FeishuConnection")
    for connection in connection_model.objects.all().iterator():
        changed = []
        for field_name in ("access_token", "refresh_token"):
            value = getattr(connection, field_name) or ""
            if value and not value.startswith(TOKEN_PREFIX):
                encrypted = encryption_service.encrypt(value)
                setattr(connection, field_name, f"{TOKEN_PREFIX}{encrypted}")
                changed.append(field_name)
        if changed:
            connection.save(update_fields=changed)


def decrypt_tokens(apps, schema_editor):
    from hyperbdr_dashboard.encryption import encryption_service

    connection_model = apps.get_model("quotation", "FeishuConnection")
    for connection in connection_model.objects.all().iterator():
        changed = []
        for field_name in ("access_token", "refresh_token"):
            value = getattr(connection, field_name) or ""
            if value.startswith(TOKEN_PREFIX):
                encrypted = value[len(TOKEN_PREFIX) :]
                setattr(
                    connection,
                    field_name,
                    encryption_service.decrypt(encrypted),
                )
                changed.append(field_name)
        if changed:
            connection.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0009_feishuconnection_shared_folder_bookmarks"),
    ]

    operations = [
        migrations.RunPython(encrypt_tokens, decrypt_tokens),
    ]

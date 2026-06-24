from django.db import migrations


def _column_names(schema_editor, table_name):
    with schema_editor.connection.cursor() as cursor:
        introspection = schema_editor.connection.introspection
        description = introspection.get_table_description(cursor, table_name)
    return {column.name for column in description}


def add_missing_channel_model_price_limit_columns(apps, schema_editor):
    channel_model_price = apps.get_model("llm_ops", "ChannelModelPrice")
    table_name = channel_model_price._meta.db_table
    existing_columns = _column_names(schema_editor, table_name)

    for field_name in ("tpm_limit", "rpm_limit", "latency_ms"):
        if field_name in existing_columns:
            continue
        field = channel_model_price._meta.get_field(field_name)
        schema_editor.add_field(channel_model_price, field)


def remove_channel_model_price_limit_columns(apps, schema_editor):
    channel_model_price = apps.get_model("llm_ops", "ChannelModelPrice")
    table_name = channel_model_price._meta.db_table
    existing_columns = _column_names(schema_editor, table_name)

    for field_name in ("latency_ms", "rpm_limit", "tpm_limit"):
        if field_name not in existing_columns:
            continue
        field = channel_model_price._meta.get_field(field_name)
        schema_editor.remove_field(channel_model_price, field)
        existing_columns.remove(field_name)


class Migration(migrations.Migration):

    dependencies = [
        ("llm_ops", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            add_missing_channel_model_price_limit_columns,
            remove_channel_model_price_limit_columns,
        )
    ]

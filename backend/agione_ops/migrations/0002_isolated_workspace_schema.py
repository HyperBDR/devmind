"""Add an isolated workspace schema without touching earlier AGIOne tables.

Some local installations already recorded a different agione_ops 0001 with
an unrelated eleven-model schema. The new workspace models deliberately use
a disjoint physical namespace. Existing legacy tables and their data are
never adopted, renamed, dropped or inspected for business values here.
"""

from django.db import migrations

MODEL_TABLES = (
    ("SourceConnection", "devmind_agione_source_connection"),
    ("ConnectionGrant", "devmind_agione_connection_grant"),
    ("SyncRun", "devmind_agione_sync_run"),
    ("DatasetVersion", "devmind_agione_dataset_version"),
    ("CallFact", "devmind_agione_call_fact"),
    ("VersionCall", "devmind_agione_version_call"),
)


def ensure_isolated_schema(apps, schema_editor):
    """Create all six isolated tables, or validate an already-complete set."""

    models = [apps.get_model("agione_ops", name) for name, _ in MODEL_TABLES]
    expected = {table for _, table in MODEL_TABLES}
    if {model._meta.db_table for model in models} != expected:
        raise RuntimeError(
            "The isolated AGIOne migration state is unexpected."
        )
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        existing = set(connection.introspection.table_names(cursor))
        present = existing.intersection(expected)
        if present and present != expected:
            raise RuntimeError(
                "Partial isolated AGIOne schema detected; refusing automatic repair."
            )
        if present == expected:
            for model in models:
                actual_columns = {
                    column.name
                    for column in connection.introspection.get_table_description(
                        cursor,
                        model._meta.db_table,
                    )
                }
                required_columns = {
                    field.column for field in model._meta.local_concrete_fields
                }
                if not required_columns.issubset(actual_columns):
                    raise RuntimeError(
                        "The isolated AGIOne schema has incompatible columns; "
                        "refusing automatic repair."
                    )
            return
    # Foreign-key order is explicit; these are historical migration models.
    for model in models:
        schema_editor.create_model(model)


class Migration(migrations.Migration):
    """Only add namespaced tables; reversal intentionally retains all data."""

    dependencies = [("agione_ops", "0001_initial")]
    operations = [
        migrations.RunPython(
            ensure_isolated_schema,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

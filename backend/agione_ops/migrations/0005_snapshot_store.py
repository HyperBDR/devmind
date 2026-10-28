"""Add DevMind-owned immutable normalized historical snapshot imports."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agione_ops", "0004_native_source_choice")]

    operations = [
        migrations.CreateModel(
            name="ImmutableDemoSnapshot",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("owner_connection_id", models.UUIDField()),
                ("connection_id", models.CharField(max_length=32)),
                ("source_id", models.CharField(max_length=160)),
                ("version", models.UUIDField()),
                ("schema_version", models.PositiveSmallIntegerField(default=1)),
                ("digest", models.CharField(max_length=64)),
                ("source_digest", models.CharField(max_length=64)),
                ("metadata", models.JSONField()),
                ("content", models.JSONField()),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "devmind_agione_immutable_demo_snapshot",
                "constraints": [models.UniqueConstraint(
                    fields=("owner_connection_id", "connection_id", "source_id",
                            "version"),
                    name="agione_immutable_snapshot_identity",
                )],
            },
        ),
    ]

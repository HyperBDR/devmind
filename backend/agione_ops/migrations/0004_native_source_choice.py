"""Add a direct API source without changing existing binding identities."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("agione_ops", "0003_demo_snapshot_binding")]

    operations = [
        migrations.AlterField(
            model_name="sourceconnection",
            name="source_kind",
            field=models.CharField(
                max_length=16,
                default="synthetic",
                choices=[
                    ("synthetic", "Synthetic"),
                    ("demo_snapshot", "Demo snapshot (read-only)"),
                    ("native", "AGIOne direct API"),
                ],
            ),
        ),
    ]

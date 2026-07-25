import django.db.models.deletion
import django.utils.timezone
import quotation.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0014_export_version_restrict"),
    ]

    operations = [
        migrations.CreateModel(
            name="RemoteFileCleanup",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "id",
                    models.CharField(
                        default=quotation.models._uuid,
                        editable=False,
                        max_length=36,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "remote_file_token",
                    models.CharField(max_length=255, unique=True),
                ),
                ("owned", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("cancelled", "Cancelled"),
                            ("completed", "Completed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                (
                    "last_error",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "next_dispatch_at",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                    ),
                ),
                (
                    "processed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "connection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="remote_file_cleanups",
                        to="quotation.storageconnection",
                    ),
                ),
            ],
            options={
                "db_table": "quotation_remote_file_cleanups",
                "ordering": ["created_at", "id"],
            },
        ),
    ]

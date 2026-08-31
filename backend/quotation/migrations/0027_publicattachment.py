from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("quotation", "0026_quotation_access_request"),
    ]

    operations = [
        migrations.CreateModel(
            name="PublicAttachment",
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
                        default=uuid.uuid4,
                        editable=False,
                        max_length=36,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("scope", models.CharField(max_length=255)),
                (
                    "product_line",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                    ),
                ),
                (
                    "service_name",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("archived", "Archived")],
                        db_index=True,
                        default="active",
                        max_length=20,
                    ),
                ),
                (
                    "asset",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="public_attachment",
                        to="quotation.documentasset",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_public_attachments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "quotation_public_attachments",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="publicattachment",
            index=models.Index(
                fields=["status", "product_line", "-created_at"],
                name="public_attach_status_line",
            ),
        ),
    ]

import django.db.models.deletion
import quotation.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("quotation", "0012_quote_desk_audit_storage"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuotationTemplate",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                ("name", models.CharField(max_length=120)),
                ("version", models.PositiveIntegerField()),
                ("storage_key", models.CharField(max_length=512)),
                ("content_hash", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("active", "Active"),
                            ("archived", "Archived"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="quotation_templates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "quotation_templates",
                "ordering": ["name", "-version"],
            },
        ),
        migrations.AddConstraint(
            model_name="quotationtemplate",
            constraint=models.UniqueConstraint(
                fields=("name", "version"),
                name="quotation_template_name_version_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="quotationtemplate",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "active")),
                fields=("status",),
                name="quotation_template_single_active",
            ),
        ),
        migrations.CreateModel(
            name="ExportJob",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                ("quotation_version_no", models.PositiveIntegerField()),
                ("template_version", models.PositiveIntegerField()),
                ("renderer_version", models.CharField(max_length=80)),
                ("formats", models.JSONField(default=list)),
                ("archive_to_feishu", models.BooleanField(default=False)),
                (
                    "idempotency_key",
                    models.CharField(
                        db_index=True,
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("rendering_excel", "Rendering Excel"),
                            ("converting_pdf", "Converting PDF"),
                            ("rendered", "Rendered"),
                            ("upload_queued", "Upload queued"),
                            ("uploading", "Uploading"),
                            ("completed", "Completed"),
                            ("render_failed", "Render failed"),
                            ("upload_failed", "Upload failed"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=30,
                    ),
                ),
                (
                    "request_id",
                    models.CharField(blank=True, default="", max_length=100),
                ),
                (
                    "trace_id",
                    models.CharField(blank=True, default="", max_length=100),
                ),
                (
                    "celery_task_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "error_code",
                    models.CharField(blank=True, default="", max_length=100),
                ),
                (
                    "error_message",
                    models.CharField(blank=True, default="", max_length=500),
                ),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "quotation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="export_jobs",
                        to="quotation.quotation",
                    ),
                ),
                (
                    "quotation_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="export_jobs",
                        to="quotation.quotationversion",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="quotation_export_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="export_jobs",
                        to="quotation.quotationtemplate",
                    ),
                ),
            ],
            options={
                "db_table": "quotation_export_jobs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddField(
            model_name="documentasset",
            name="content_hash",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="export_job",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assets",
                to="quotation.exportjob",
            ),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="quotation_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="document_assets",
                to="quotation.quotationversion",
            ),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="renderer_version",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="template",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="document_assets",
                to="quotation.quotationtemplate",
            ),
        ),
        migrations.AddField(
            model_name="documentasset",
            name="template_version",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddConstraint(
            model_name="documentasset",
            constraint=models.UniqueConstraint(
                condition=models.Q(export_job__isnull=False),
                fields=("export_job", "doc_type"),
                name="quotation_export_asset_format_unique",
            ),
        ),
    ]

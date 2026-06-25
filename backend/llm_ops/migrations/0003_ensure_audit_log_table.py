from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def ensure_audit_log_table(apps, schema_editor):
    class MigrationAuditLog(models.Model):
        actor = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            blank=True,
            null=True,
            on_delete=django.db.models.deletion.SET_NULL,
            related_name="+",
        )
        actor_identifier = models.CharField(
            max_length=255,
            blank=True,
            default="",
        )
        action = models.CharField(max_length=50)
        category = models.CharField(max_length=50)
        target_type = models.CharField(max_length=100, db_index=True)
        target_id = models.CharField(max_length=100, blank=True, default="")
        target_repr = models.CharField(max_length=255, blank=True, default="")
        summary = models.CharField(max_length=500, blank=True, default="")
        before = models.JSONField(blank=True, default=dict)
        after = models.JSONField(blank=True, default=dict)
        changes = models.JSONField(blank=True, default=dict)
        metadata = models.JSONField(blank=True, default=dict)
        request_id = models.CharField(max_length=100, blank=True, default="")
        ip_address = models.GenericIPAddressField(blank=True, null=True)
        user_agent = models.CharField(max_length=500, blank=True, default="")
        created_at = models.DateTimeField(auto_now_add=True, db_index=True)

        class Meta:
            app_label = "llm_ops"
            db_table = "llm_ops_auditlog"
            indexes = [
                models.Index(
                    fields=["category", "action", "created_at"],
                    name="llm_ops_aud_categor_fd751a_idx",
                ),
                models.Index(
                    fields=["target_type", "target_id", "created_at"],
                    name="llm_ops_aud_target__f14162_idx",
                ),
                models.Index(
                    fields=["actor", "created_at"],
                    name="llm_ops_aud_actor_i_a48bfd_idx",
                ),
            ]

    table_name = MigrationAuditLog._meta.db_table
    existing_tables = schema_editor.connection.introspection.table_names()
    if table_name in existing_tables:
        return
    schema_editor.create_model(MigrationAuditLog)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("llm_ops", "0002_channel_model_price_limits"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    ensure_audit_log_table,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name="AuditLog",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        (
                            "actor_identifier",
                            models.CharField(
                                blank=True,
                                default="",
                                max_length=255,
                            ),
                        ),
                        (
                            "action",
                            models.CharField(
                                choices=[
                                    ("create", "Create"),
                                    ("update", "Update"),
                                    ("delete", "Delete"),
                                    ("collect", "Collect"),
                                    ("import", "Import"),
                                    ("bulk_upsert", "Bulk Upsert"),
                                    ("bulk_draft", "Bulk Draft"),
                                    ("bulk_replace", "Bulk Replace"),
                                    ("transition", "Transition"),
                                    ("offline", "Offline"),
                                    ("restore", "Restore"),
                                    ("sync", "Sync"),
                                ],
                                max_length=50,
                            ),
                        ),
                        (
                            "category",
                            models.CharField(
                                choices=[
                                    ("configuration", "Configuration"),
                                    ("pricing", "Pricing"),
                                    ("publishing", "Publishing"),
                                    ("approval", "Approval"),
                                    ("collection", "Collection"),
                                    ("reconciliation", "Reconciliation"),
                                ],
                                max_length=50,
                            ),
                        ),
                        (
                            "target_type",
                            models.CharField(db_index=True, max_length=100),
                        ),
                        (
                            "target_id",
                            models.CharField(
                                blank=True,
                                default="",
                                max_length=100,
                            ),
                        ),
                        (
                            "target_repr",
                            models.CharField(
                                blank=True,
                                default="",
                                max_length=255,
                            ),
                        ),
                        (
                            "summary",
                            models.CharField(
                                blank=True,
                                default="",
                                max_length=500,
                            ),
                        ),
                        ("before", models.JSONField(blank=True, default=dict)),
                        ("after", models.JSONField(blank=True, default=dict)),
                        ("changes", models.JSONField(blank=True, default=dict)),
                        ("metadata", models.JSONField(blank=True, default=dict)),
                        (
                            "request_id",
                            models.CharField(
                                blank=True,
                                default="",
                                max_length=100,
                            ),
                        ),
                        (
                            "ip_address",
                            models.GenericIPAddressField(
                                blank=True,
                                null=True,
                            ),
                        ),
                        (
                            "user_agent",
                            models.CharField(
                                blank=True,
                                default="",
                                max_length=500,
                            ),
                        ),
                        (
                            "created_at",
                            models.DateTimeField(
                                auto_now_add=True,
                                db_index=True,
                            ),
                        ),
                        (
                            "actor",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="llm_ops_audit_logs",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "ordering": ["-created_at", "-id"],
                        "indexes": [
                            models.Index(
                                fields=["category", "action", "created_at"],
                                name="llm_ops_aud_categor_fd751a_idx",
                            ),
                            models.Index(
                                fields=[
                                    "target_type",
                                    "target_id",
                                    "created_at",
                                ],
                                name="llm_ops_aud_target__f14162_idx",
                            ),
                            models.Index(
                                fields=["actor", "created_at"],
                                name="llm_ops_aud_actor_i_a48bfd_idx",
                            ),
                        ],
                    },
                ),
            ],
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("llm_ops", "0004_alter_pricecollectionrun_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="LLMOpsGlobalConfig",
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
                    "singleton_key",
                    models.CharField(
                        default="default",
                        editable=False,
                        max_length=50,
                        unique=True,
                    ),
                ),
                (
                    "meta_model_sync_enabled",
                    models.BooleanField(default=True),
                ),
                (
                    "meta_model_sync_source_url",
                    models.URLField(
                        default="https://models.dev/api.json",
                        max_length=1000,
                    ),
                ),
                (
                    "meta_model_sync_cron",
                    models.CharField(
                        default="35 2 * * *",
                        max_length=100,
                    ),
                ),
                (
                    "price_collection_enabled",
                    models.BooleanField(default=True),
                ),
                (
                    "price_collection_source_ids",
                    models.JSONField(blank=True, default=list),
                ),
                (
                    "price_collection_cron",
                    models.CharField(
                        default="15 1,7,13,19 * * *",
                        max_length=100,
                    ),
                ),
                (
                    "feishu_app_id",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "feishu_app_secret",
                    models.CharField(blank=True, default="", max_length=500),
                ),
                (
                    "feishu_approval_code",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "feishu_tenant_key",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="llm_ops_global_config_updates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "LLM Ops Global Config",
                "verbose_name_plural": "LLM Ops Global Config",
            },
        ),
    ]

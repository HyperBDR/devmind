from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("llm_ops", "0002_resaleplatform_metadata"),
    ]

    operations = [
        migrations.CreateModel(
            name="ResaleWorkflowConfig",
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
                ("config", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "platform",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow_config",
                        to="llm_ops.resaleplatform",
                    ),
                ),
            ],
            options={
                "ordering": ["platform__name", "id"],
            },
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DataSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("api_url", models.URLField(max_length=255)),
                ("username", models.CharField(max_length=100)),
                ("password", models.TextField()),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("api_timeout", models.PositiveIntegerField(default=30)),
                ("api_retry_count", models.PositiveIntegerField(default=3)),
                ("api_retry_delay", models.PositiveIntegerField(default=2)),
                ("collect_interval", models.PositiveIntegerField(default=3600)),
                ("last_collected_at", models.DateTimeField(
                    blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "hyperbdr_dashboard_data_source",
                "ordering": ["name", "id"],
            },
        ),
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("id", models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name="ID")),
                ("source_tenant_id", models.CharField(max_length=50)),
                ("name", models.CharField(db_index=True, max_length=255)),
                ("description", models.CharField(
                    blank=True, default="", max_length=500)),
                ("status", models.CharField(blank=True,
                 db_index=True, default="", max_length=50)),
                ("agent_enabled", models.BooleanField(default=False)),
                ("trialed", models.BooleanField(default=False)),
                ("migration_way", models.CharField(
                    blank=True, default="", max_length=100)),
                ("last_collected_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "data_source",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                      related_name="tenants", to="hyperbdr_dashboard.datasource"),
                ),
            ],
            options={
                "db_table": "hyperbdr_dashboard_tenant",
                "ordering": ["name", "source_tenant_id"],
            },
        ),
        migrations.CreateModel(
            name="CollectionTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), (
                    "completed", "Completed"), ("failed", "Failed")], db_index=True, default="pending", max_length=50)),
                ("celery_task_id", models.CharField(blank=True,
                 db_index=True, default="", max_length=255)),
                ("trigger_mode", models.CharField(
                    blank=True, default="manual", max_length=32)),
                ("start_time", models.DateTimeField(db_index=True)),
                ("end_time", models.DateTimeField(blank=True, null=True)),
                ("duration_seconds", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=10, null=True)),
                ("total_tenants", models.PositiveIntegerField(default=0)),
                ("total_licenses", models.PositiveIntegerField(default=0)),
                ("total_hosts", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "data_source",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                      related_name="tasks", to="hyperbdr_dashboard.datasource"),
                ),
            ],
            options={
                "db_table": "hyperbdr_dashboard_collection_task",
                "ordering": ["-start_time", "-id"],
            },
        ),
        migrations.CreateModel(
            name="License",
            fields=[
                ("id", models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name="ID")),
                ("total_amount", models.PositiveIntegerField(default=0)),
                ("total_used", models.PositiveIntegerField(default=0)),
                ("total_unused", models.PositiveIntegerField(default=0)),
                ("scene", models.CharField(blank=True,
                 db_index=True, default="dr", max_length=50)),
                ("start_at", models.DateTimeField(blank=True, null=True)),
                ("expire_at", models.DateTimeField(blank=True, null=True)),
                ("last_collected_at", models.DateTimeField(
                    blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "data_source",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                      related_name="licenses", to="hyperbdr_dashboard.datasource"),
                ),
                (
                    "tenant",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                      related_name="licenses", to="hyperbdr_dashboard.tenant"),
                ),
            ],
            options={
                "db_table": "hyperbdr_dashboard_license",
                "ordering": ["tenant__name", "scene"],
            },
        ),
        migrations.CreateModel(
            name="Host",
            fields=[
                ("id", models.BigAutoField(auto_created=True,
                 primary_key=True, serialize=False, verbose_name="ID")),
                ("source_host_id", models.CharField(max_length=50)),
                ("name", models.CharField(db_index=True, max_length=255)),
                ("status", models.CharField(blank=True,
                 db_index=True, default="", max_length=50)),
                ("boot_status", models.CharField(blank=True,
                 db_index=True, default="", max_length=50)),
                ("health_status", models.CharField(blank=True,
                 db_index=True, default="", max_length=50)),
                ("os_type", models.CharField(blank=True,
                 db_index=True, default="", max_length=100)),
                ("host_type", models.CharField(blank=True,
                 db_index=True, default="", max_length=100)),
                ("cpu_num", models.PositiveIntegerField(default=0)),
                ("ram_size", models.DecimalField(
                    decimal_places=2, default=0, max_digits=10)),
                ("license_valid", models.BooleanField(
                    db_index=True, default=False)),
                ("error_message", models.TextField(blank=True, default="")),
                ("last_collected_at", models.DateTimeField(
                    blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "data_source",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                      related_name="hosts", to="hyperbdr_dashboard.datasource"),
                ),
                (
                    "tenant",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                      related_name="hosts", to="hyperbdr_dashboard.tenant"),
                ),
            ],
            options={
                "db_table": "hyperbdr_dashboard_host",
                "ordering": ["tenant__name", "name", "source_host_id"],
            },
        ),
        migrations.AddConstraint(
            model_name="tenant",
            constraint=models.UniqueConstraint(fields=(
                "data_source", "source_tenant_id"), name="hyperbdr_dashboard_tenant_source_unique"),
        ),
        migrations.AddConstraint(
            model_name="license",
            constraint=models.UniqueConstraint(fields=(
                "data_source", "tenant", "scene"), name="hyperbdr_dashboard_license_source_tenant_scene_unique"),
        ),
        migrations.AddConstraint(
            model_name="host",
            constraint=models.UniqueConstraint(fields=(
                "data_source", "source_host_id"), name="hyperbdr_dashboard_host_source_unique"),
        ),
        migrations.AddIndex(
            model_name="tenant",
            index=models.Index(
                fields=["data_source", "status"], name="hbdr_moni_data_so_bb4939_idx"),
        ),
        migrations.AddIndex(
            model_name="tenant",
            index=models.Index(
                fields=["data_source", "name"], name="hbdr_moni_data_so_24a173_idx"),
        ),
        migrations.AddIndex(
            model_name="license",
            index=models.Index(
                fields=["data_source", "scene"], name="hbdr_moni_data_so_d12949_idx"),
        ),
        migrations.AddIndex(
            model_name="license",
            index=models.Index(
                fields=["tenant", "scene"], name="hbdr_moni_tenant_8a5776_idx"),
        ),
        migrations.AddIndex(
            model_name="host",
            index=models.Index(
                fields=["data_source", "tenant"], name="hbdr_moni_data_so_b431b2_idx"),
        ),
        migrations.AddIndex(
            model_name="host",
            index=models.Index(
                fields=["data_source", "status"], name="hbdr_moni_data_so_6c83d7_idx"),
        ),
        migrations.AddIndex(
            model_name="host",
            index=models.Index(
                fields=["data_source", "health_status"], name="hbdr_moni_data_so_333a64_idx"),
        ),
    ]

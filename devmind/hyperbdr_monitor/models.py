from django.db import models


class DataSource(models.Model):
    name = models.CharField(max_length=255)
    api_url = models.URLField(max_length=255)
    username = models.CharField(max_length=100)
    password = models.TextField()
    is_active = models.BooleanField(default=True, db_index=True)
    api_timeout = models.PositiveIntegerField(default=30)
    api_retry_count = models.PositiveIntegerField(default=3)
    api_retry_delay = models.PositiveIntegerField(default=2)
    collect_interval = models.PositiveIntegerField(default=3600)
    last_collected_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "hyperbdr_monitor"
        db_table = "hyperbdr_monitor_data_source"
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Tenant(models.Model):
    source_tenant_id = models.CharField(max_length=50)
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="tenants",
    )
    name = models.CharField(max_length=255, db_index=True)
    description = models.CharField(max_length=500, blank=True, default="")
    status = models.CharField(max_length=50, db_index=True, blank=True, default="")
    agent_enabled = models.BooleanField(default=False)
    trialed = models.BooleanField(default=False)
    migration_way = models.CharField(max_length=100, blank=True, default="")
    last_collected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "hyperbdr_monitor"
        db_table = "hyperbdr_monitor_tenant"
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "source_tenant_id"],
                name="hyperbdr_monitor_tenant_source_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["data_source", "status"],
                name="hbdr_moni_data_so_bb4939_idx",
            ),
            models.Index(
                fields=["data_source", "name"],
                name="hbdr_moni_data_so_24a173_idx",
            ),
        ]
        ordering = ["name", "source_tenant_id"]

    def __str__(self):
        return f"{self.name} ({self.source_tenant_id})"


class License(models.Model):
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="licenses",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="licenses",
    )
    total_amount = models.PositiveIntegerField(default=0)
    total_used = models.PositiveIntegerField(default=0)
    total_unused = models.PositiveIntegerField(default=0)
    scene = models.CharField(max_length=50, db_index=True, blank=True, default="dr")
    start_at = models.DateTimeField(null=True, blank=True)
    expire_at = models.DateTimeField(null=True, blank=True)
    last_collected_at = models.DateTimeField(db_index=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "hyperbdr_monitor"
        db_table = "hyperbdr_monitor_license"
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "tenant", "scene"],
                name="hyperbdr_monitor_license_source_tenant_scene_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["data_source", "scene"],
                name="hbdr_moni_data_so_d12949_idx",
            ),
            models.Index(
                fields=["tenant", "scene"],
                name="hbdr_moni_tenant_8a5776_idx",
            ),
        ]
        ordering = ["tenant__name", "scene"]


class Host(models.Model):
    source_host_id = models.CharField(max_length=50)
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="hosts",
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="hosts",
    )
    name = models.CharField(max_length=255, db_index=True)
    status = models.CharField(max_length=50, db_index=True, blank=True, default="")
    boot_status = models.CharField(max_length=50, db_index=True, blank=True, default="")
    health_status = models.CharField(max_length=50, db_index=True, blank=True, default="")
    os_type = models.CharField(max_length=100, db_index=True, blank=True, default="")
    host_type = models.CharField(max_length=100, db_index=True, blank=True, default="")
    cpu_num = models.PositiveIntegerField(default=0)
    ram_size = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    license_valid = models.BooleanField(default=False, db_index=True)
    error_message = models.TextField(blank=True, default="")
    last_collected_at = models.DateTimeField(db_index=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "hyperbdr_monitor"
        db_table = "hyperbdr_monitor_host"
        constraints = [
            models.UniqueConstraint(
                fields=["data_source", "source_host_id"],
                name="hyperbdr_monitor_host_source_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["data_source", "tenant"],
                name="hbdr_moni_data_so_b431b2_idx",
            ),
            models.Index(
                fields=["data_source", "status"],
                name="hbdr_moni_data_so_6c83d7_idx",
            ),
            models.Index(
                fields=["data_source", "health_status"],
                name="hbdr_moni_data_so_333a64_idx",
            ),
        ]
        ordering = ["tenant__name", "name", "source_host_id"]


class CollectionTask(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    celery_task_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    trigger_mode = models.CharField(max_length=32, blank=True, default="manual")
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_tenants = models.PositiveIntegerField(default=0)
    total_licenses = models.PositiveIntegerField(default=0)
    total_hosts = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "hyperbdr_monitor"
        db_table = "hyperbdr_monitor_collection_task"
        ordering = ["-start_time", "-id"]

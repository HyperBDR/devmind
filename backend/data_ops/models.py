import uuid

from django.db import models
from django.utils import timezone

from hyperbdr_dashboard.encryption import encryption_service


class ActiveSourceRecordManager(models.Manager):
    """Return records still present in source systems."""

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class SourceRecordModel(models.Model):
    """Base fields for records synchronized from Feishu Bitable."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_record_id = models.CharField(max_length=255, db_index=True)
    source_app_token = models.CharField(max_length=100)
    source_table_id = models.CharField(max_length=100)
    raw_data = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    synced_at = models.DateTimeField(default=timezone.now, db_index=True)

    objects = ActiveSourceRecordManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True


class Contract(SourceRecordModel):
    contract_number = models.CharField(max_length=100, blank=True)
    customer_name = models.CharField(max_length=255, blank=True)
    signing_entity = models.CharField(max_length=255, blank=True)
    channel_type = models.CharField(max_length=100, blank=True)
    enduser_customer = models.CharField(max_length=255, blank=True)
    order_platform = models.CharField(max_length=100, blank=True)
    sales_person = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    currency = models.CharField(max_length=20, blank=True)
    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    product_category = models.CharField(max_length=100, blank=True)
    signing_type = models.CharField(max_length=100, blank=True)
    signing_date = models.DateField(null=True, blank=True)
    service_start = models.DateField(null=True, blank=True)
    service_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, blank=True)
    filing_type = models.CharField(max_length=100, blank=True)
    contract_sub_type = models.CharField(max_length=100, blank=True)
    expiry_status = models.CharField(max_length=50, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source_app_token",
                    "source_table_id",
                    "source_record_id",
                ],
                name="uq_data_ops_contract_source",
            ),
        ]
        indexes = [
            models.Index(fields=["contract_number"]),
            models.Index(fields=["customer_name"]),
            models.Index(fields=["sales_person"]),
            models.Index(fields=["service_end"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.contract_number or self.customer_name or str(self.id)


class SalesRecord(SourceRecordModel):
    project_name = models.CharField(max_length=255, blank=True)
    po_number = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    product_type = models.CharField(max_length=100, blank=True)
    total_amount_usd = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    allocation_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    order_type = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50, blank=True)
    sales_person = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source_app_token",
                    "source_table_id",
                    "source_record_id",
                ],
                name="uq_data_ops_sales_record_source",
            ),
        ]
        indexes = [
            models.Index(fields=["project_name"]),
            models.Index(fields=["sales_person"]),
            models.Index(fields=["expiry_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.project_name or self.po_number or str(self.id)


class DomesticLedger(SourceRecordModel):
    ledger_type = models.CharField(max_length=20, blank=True)
    currency = models.CharField(max_length=20, blank=True)
    signing_date = models.DateField(null=True, blank=True)
    customer_name = models.CharField(max_length=255, blank=True)
    project_name = models.CharField(max_length=255, blank=True)
    order_number = models.CharField(max_length=100, blank=True)
    sales_person = models.CharField(max_length=100, blank=True)
    signing_entity = models.CharField(max_length=255, blank=True)
    total_contract_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    single_receive_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    invoice_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    payment_received = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    outstanding = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    invoice_date = models.DateField(null=True, blank=True)
    receipt_time = models.DateField(null=True, blank=True)
    expected_payment_date = models.DateField(null=True, blank=True)
    license_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    license_unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    payment_progress = models.CharField(max_length=100, blank=True)
    payment_status = models.CharField(max_length=100, blank=True)
    payment_situation = models.CharField(max_length=255, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    sales_mode = models.CharField(max_length=50, blank=True)
    purchase_product = models.CharField(max_length=100, blank=True)
    tax_rate = models.CharField(max_length=20, blank=True)
    year = models.CharField(max_length=10, blank=True)
    project_code = models.CharField(max_length=100, blank=True)
    remarks = models.CharField(max_length=1000, blank=True)
    contract = models.ForeignKey(
        Contract,
        null=True,
        blank=True,
        related_name="ledger_entries",
        on_delete=models.SET_NULL,
    )
    linked_ledger = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="linked_payments",
        on_delete=models.SET_NULL,
    )
    payment_item = models.CharField(max_length=255, blank=True)
    payment_party = models.CharField(max_length=255, blank=True)
    payee_name = models.CharField(max_length=255, blank=True)
    payment_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    signing_mode = models.CharField(max_length=100, blank=True)
    counterparty_name = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source_app_token",
                    "source_table_id",
                    "source_record_id",
                ],
                name="uq_data_ops_ledger_source",
            ),
        ]
        indexes = [
            models.Index(fields=["ledger_type", "payment_status"]),
            models.Index(fields=["sales_person"]),
            models.Index(fields=["signing_entity"]),
            models.Index(fields=["expected_payment_date"]),
            models.Index(fields=["year"]),
        ]

    def __str__(self):
        return self.project_name or self.customer_name or str(self.id)


class ContractHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(
        Contract,
        related_name="history_entries",
        on_delete=models.CASCADE,
    )
    source_record_id = models.CharField(max_length=100, db_index=True)
    field_name = models.CharField(max_length=255)
    old_value = models.CharField(max_length=5000, blank=True)
    new_value = models.CharField(max_length=5000, blank=True)
    changed_by = models.CharField(max_length=255, blank=True, db_index=True)
    changed_at = models.DateTimeField(db_index=True)
    change_type = models.CharField(max_length=20, default="update")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "contract",
                    "source_record_id",
                    "field_name",
                    "changed_at",
                ],
                name="uq_data_ops_history_dedup",
            ),
        ]
        indexes = [
            models.Index(fields=["contract", "changed_at"]),
        ]


class ProjectInit(SourceRecordModel):
    project_code = models.CharField(max_length=100, blank=True)
    domestic_international = models.CharField(max_length=50, blank=True)
    customer_full_name = models.CharField(max_length=255, blank=True)
    oa_initiation_date = models.DateField(null=True, blank=True)
    project_name = models.CharField(max_length=255, blank=True)
    project_description = models.CharField(max_length=1000, blank=True)
    sales_person = models.CharField(max_length=100, blank=True)
    sales_products = models.CharField(max_length=500, blank=True)
    estimated_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=20, blank=True)
    signing_party_type = models.CharField(max_length=255, blank=True)
    enduser_customer = models.CharField(max_length=255, blank=True)
    contract_link = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source_app_token",
                    "source_table_id",
                    "source_record_id",
                ],
                name="uq_data_ops_project_init_source",
            ),
        ]
        indexes = [
            models.Index(fields=["project_code"]),
            models.Index(fields=["domestic_international"]),
            models.Index(fields=["sales_person"]),
            models.Index(fields=["oa_initiation_date"]),
        ]

    def __str__(self):
        return self.project_name or self.project_code or str(self.id)


class OverseaProject(SourceRecordModel):
    project_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=100, blank=True)
    po_number = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    payment_channel = models.CharField(max_length=100, blank=True)
    signing_customer = models.CharField(max_length=255, blank=True)
    product_type = models.CharField(max_length=100, blank=True)
    product_spec = models.CharField(max_length=255, blank=True)
    order_date = models.DateField(null=True, blank=True)
    order_year = models.IntegerField(null=True, blank=True)
    order_month = models.IntegerField(null=True, blank=True)
    purchase_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    purchase_cycle = models.IntegerField(null=True, blank=True)
    unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=20, blank=True)
    stat_amount_usd = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    allocation_date = models.DateField(null=True, blank=True)
    allocation_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    license_order_no = models.CharField(max_length=100, blank=True)
    huawei_cloud_expiry = models.DateField(null=True, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    license_reg_code = models.CharField(max_length=255, blank=True)
    kg_username = models.CharField(max_length=100, blank=True)
    kg_full_name = models.CharField(max_length=255, blank=True)
    end_customer = models.CharField(max_length=255, blank=True)
    kg_email = models.CharField(max_length=255, blank=True)
    cc_email = models.CharField(max_length=500, blank=True)
    project_owner = models.CharField(max_length=100, blank=True)
    invoice_no = models.CharField(max_length=100, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    payment_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    payment_currency = models.CharField(max_length=20, blank=True)
    payment_recipient = models.CharField(max_length=255, blank=True)
    customer_type = models.CharField(max_length=100, blank=True)
    cost_for = models.CharField(max_length=255, blank=True)
    cost_usd = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    payment_terms = models.CharField(max_length=100, blank=True)
    tax_status = models.CharField(max_length=100, blank=True)
    tax_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    order_type = models.CharField(max_length=100, blank=True)
    acceptance_status = models.CharField(max_length=100, blank=True)
    order_status = models.CharField(max_length=100, blank=True)
    order_category = models.CharField(max_length=100, blank=True)
    customer_id = models.CharField(max_length=100, blank=True)
    payment_id = models.CharField(max_length=100, blank=True)
    project_sub_no = models.CharField(max_length=100, blank=True)
    remarks = models.CharField(max_length=1000, blank=True)
    tax_voucher = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source_app_token",
                    "source_table_id",
                    "source_record_id",
                ],
                name="uq_data_ops_oversea_project_source",
            ),
        ]
        indexes = [
            models.Index(fields=["country"]),
            models.Index(fields=["project_owner"]),
            models.Index(fields=["status"]),
            models.Index(fields=["license_expiry"]),
        ]

    def __str__(self):
        return self.project_name or self.po_number or str(self.id)


class OverseaSettlement(SourceRecordModel):
    project_name_en = models.CharField(max_length=255, blank=True)
    project_name_cn = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=100, blank=True)
    project_category = models.CharField(max_length=100, blank=True)
    project_code = models.CharField(max_length=100, blank=True)
    project_progress = models.CharField(max_length=255, blank=True)
    todo_notes = models.CharField(max_length=2000, blank=True)
    project_overview = models.CharField(max_length=2000, blank=True)
    final_customer = models.CharField(max_length=255, blank=True)
    integrator = models.CharField(max_length=255, blank=True)
    huawei_settlement_party = models.CharField(max_length=255, blank=True)
    selling_products = models.CharField(max_length=1000, blank=True)
    actual_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    unit = models.CharField(max_length=20, blank=True)
    overseas_initial_quote = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    initial_quote_unit = models.CharField(max_length=20, blank=True)
    estimated_exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        null=True,
        blank=True,
    )
    estimated_revenue = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    estimated_revenue_unit = models.CharField(max_length=20, blank=True)
    revenue_diff = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    revenue_diff_unit = models.CharField(max_length=20, blank=True)
    revenue_diff_reason = models.CharField(max_length=500, blank=True)
    receivable_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    received_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=20, blank=True)
    aisun_sub_fee_estimate = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    payment_date = models.DateField(null=True, blank=True)
    huawei_order_time = models.CharField(max_length=100, blank=True)
    huawei_est_payment_time = models.CharField(max_length=100, blank=True)
    transit_merchant_est_payment_time = models.CharField(
        max_length=100,
        blank=True,
    )
    master_overseas_link = models.CharField(max_length=1000, blank=True)
    aisun_sub_fee_link = models.CharField(max_length=1000, blank=True)
    authorization_status_link = models.CharField(max_length=1000, blank=True)
    has_initial_quote_attachment = models.BooleanField(default=False)
    has_contract_attachment = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source_app_token",
                    "source_table_id",
                    "source_record_id",
                ],
                name="uq_data_ops_settlement_source",
            ),
        ]
        indexes = [
            models.Index(fields=["project_code"]),
            models.Index(fields=["region"]),
            models.Index(fields=["payment_date"]),
        ]

    def __str__(self):
        return self.project_name_cn or self.project_name_en or str(self.id)


class ProjectScope(models.TextChoices):
    DOMESTIC = "domestic", "Domestic"
    OVERSEAS = "overseas", "Overseas"


class Project(SourceRecordModel):
    project_scope = models.CharField(
        max_length=20,
        choices=ProjectScope.choices,
    )
    project_code = models.CharField(max_length=100, blank=True)
    domestic_type = models.CharField(max_length=50, blank=True)
    customer_full_name = models.CharField(max_length=255, blank=True)
    oa_initiation_date = models.DateField(null=True, blank=True)
    estimated_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    sales_products = models.CharField(max_length=500, blank=True)
    signing_party_type = models.CharField(max_length=255, blank=True)
    project_description = models.CharField(max_length=1000, blank=True)
    contract_link = models.CharField(max_length=500, blank=True)
    country = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=100, blank=True)
    po_number = models.CharField(max_length=100, blank=True)
    payment_channel = models.CharField(max_length=100, blank=True)
    signing_customer = models.CharField(max_length=255, blank=True)
    end_customer = models.CharField(max_length=255, blank=True)
    customer_type = models.CharField(max_length=100, blank=True)
    product_type = models.CharField(max_length=100, blank=True)
    product_spec = models.CharField(max_length=255, blank=True)
    order_type = models.CharField(max_length=100, blank=True)
    order_status = models.CharField(max_length=100, blank=True)
    acceptance_status = models.CharField(max_length=100, blank=True)
    order_date = models.DateField(null=True, blank=True)
    order_year = models.IntegerField(null=True, blank=True)
    order_month = models.IntegerField(null=True, blank=True)
    order_category = models.CharField(max_length=100, blank=True)
    customer_id = models.CharField(max_length=100, blank=True)
    payment_id = models.CharField(max_length=100, blank=True)
    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    stat_amount_usd = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    allocation_date = models.DateField(null=True, blank=True)
    allocation_quantity = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    license_order_no = models.CharField(max_length=100, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    huawei_cloud_expiry = models.DateField(null=True, blank=True)
    timezone = models.CharField(max_length=50, blank=True)
    license_reg_code = models.CharField(max_length=255, blank=True)
    kg_username = models.CharField(max_length=100, blank=True)
    kg_full_name = models.CharField(max_length=255, blank=True)
    kg_email = models.CharField(max_length=255, blank=True)
    cc_email = models.CharField(max_length=500, blank=True)
    invoice_no = models.CharField(max_length=100, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    payment_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    payment_currency = models.CharField(max_length=20, blank=True)
    payment_recipient = models.CharField(max_length=255, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    received_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    cost_for = models.CharField(max_length=255, blank=True)
    cost_usd = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    tax_status = models.CharField(max_length=100, blank=True)
    tax_amount = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    tax_voucher = models.CharField(max_length=255, blank=True)
    project_sub_no = models.CharField(max_length=100, blank=True)
    remarks = models.CharField(max_length=1000, blank=True)
    project_name = models.CharField(max_length=255, blank=True)
    sales_person = models.CharField(max_length=100, blank=True)
    project_owner = models.CharField(max_length=100, blank=True)
    enduser_customer = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=20, blank=True)
    is_high_potential = models.BooleanField(default=False)
    is_landed = models.BooleanField(default=False)
    license_days_left = models.IntegerField(null=True, blank=True)
    license_risk_level = models.CharField(max_length=20, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source_app_token",
                    "source_table_id",
                    "source_record_id",
                ],
                name="uq_data_ops_project_source",
            ),
        ]
        indexes = [
            models.Index(fields=["project_scope"]),
            models.Index(fields=["domestic_type"]),
            models.Index(fields=["country"]),
            models.Index(fields=["sales_person"]),
            models.Index(fields=["project_owner"]),
            models.Index(fields=["status"]),
            models.Index(fields=["license_expiry"]),
            models.Index(fields=["project_scope", "sales_person"]),
            models.Index(fields=["project_scope", "country"]),
            models.Index(fields=["project_scope", "status"]),
        ]

    def __str__(self):
        return self.project_name or self.project_code or str(self.id)


class SyncStatus(models.TextChoices):
    OK = "ok", "OK"
    WARNING = "warning", "Warning"
    FAILED = "failed", "Failed"
    RUNNING = "running", "Running"
    PENDING = "pending", "Pending"


class SyncIssueCode(models.TextChoices):
    NONE = "", "None"
    CONFIG_MISSING = "config_missing", "Configuration missing"
    TOKEN_ERROR = "token_error", "Token error"
    APP_ACCESS_DENIED = "app_access_denied", "App access denied"
    TABLE_ACCESS_DENIED = "table_access_denied", "Table access denied"
    FIELD_ACCESS_DENIED = "field_access_denied", "Field access denied"
    FIELD_MISSING = "field_missing", "Field missing"
    PAGINATION_INCOMPLETE = "pagination_incomplete", "Pagination incomplete"
    ZERO_RECORDS_UNEXPECTED = "zero_records_unexpected", "Unexpected zero"
    NETWORK_ERROR = "network_error", "Network error"
    UNKNOWN = "unknown", "Unknown"


def default_feishu_required_permissions():
    """Return Feishu permissions needed for Bitable collection."""
    return [
        "bitable:app",
        "bitable:app:readonly",
        "bitable:record:readonly",
        "bitable:field:readonly",
    ]


class CollectionFrequency(models.TextChoices):
    MANUAL = "manual", "Manual"
    HOURLY = "hourly", "Hourly"
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"


class DataOpsGlobalConfig(models.Model):
    """Singleton runtime configuration for the Data Ops app."""

    ENCRYPTED_SECRET_PREFIX = "fernet:"

    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True)
    feishu_app_id = models.CharField(max_length=255, blank=True)
    feishu_app_secret = models.TextField(blank=True)
    feishu_date_timezone = models.CharField(
        max_length=64,
        default="Asia/Shanghai",
    )
    active_sync_job_timeout_hours = models.PositiveIntegerField(default=3)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Data Ops Global Configuration"
        verbose_name_plural = "Data Ops Global Configuration"

    @classmethod
    def encrypt_secret(cls, value):
        """Encrypt a secret unless it is already encrypted."""
        if not value:
            return ""
        if value.startswith(cls.ENCRYPTED_SECRET_PREFIX):
            return value
        encrypted = encryption_service.encrypt(value)
        return f"{cls.ENCRYPTED_SECRET_PREFIX}{encrypted}"

    @classmethod
    def decrypt_secret(cls, value):
        """Decrypt a stored secret with plaintext fallback."""
        if not value:
            return ""
        if value.startswith(cls.ENCRYPTED_SECRET_PREFIX):
            encrypted = value[len(cls.ENCRYPTED_SECRET_PREFIX):]
            return encryption_service.decrypt(encrypted)
        return value

    def set_feishu_app_secret(self, value):
        """Store the Feishu app secret in encrypted form."""
        self.feishu_app_secret = self.encrypt_secret(value)

    def get_feishu_app_secret(self):
        """Return the decrypted Feishu app secret."""
        return self.decrypt_secret(self.feishu_app_secret)

    def save(self, *args, **kwargs):
        self.singleton_key = 1
        if self.feishu_app_secret:
            self.feishu_app_secret = self.encrypt_secret(
                self.feishu_app_secret
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return "Data Ops global configuration"

    @classmethod
    def get_solo(cls):
        config, _created = cls.objects.get_or_create(singleton_key=1)
        return config


class FeishuBitableCollectionConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_key = models.CharField(max_length=50)
    table_key = models.CharField(max_length=100)
    source_name = models.CharField(max_length=255, blank=True)
    table_name = models.CharField(max_length=255, blank=True)
    app_token = models.CharField(max_length=100)
    table_id = models.CharField(max_length=100)
    is_enabled = models.BooleanField(default=True)
    sync_frequency = models.CharField(
        max_length=20,
        choices=CollectionFrequency.choices,
        default=CollectionFrequency.DAILY,
    )
    required_permissions = models.JSONField(
        default=default_feishu_required_permissions,
        blank=True,
    )
    expected_min_records = models.IntegerField(null=True, blank=True)
    last_preflight_at = models.DateTimeField(null=True, blank=True)
    last_manual_trigger_at = models.DateTimeField(null=True, blank=True)
    last_scheduled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_key", "table_key"],
                name="uq_data_ops_feishu_collection_config",
            ),
        ]
        indexes = [
            models.Index(fields=["source_key", "table_key"]),
            models.Index(fields=["is_enabled", "sync_frequency"]),
        ]

    def __str__(self):
        return f"{self.source_key}/{self.table_key}"


class SyncCursor(models.Model):
    app_token = models.CharField(max_length=100)
    table_id = models.CharField(max_length=100)
    source_key = models.CharField(max_length=50, blank=True)
    table_key = models.CharField(max_length=100, blank=True)
    table_name = models.CharField(max_length=255, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    record_count = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["app_token", "table_id"],
                name="uq_data_ops_sync_cursor",
            ),
        ]

    def __str__(self):
        return f"{self.source_key}/{self.table_key}"


class SyncTableStatus(models.Model):
    source_key = models.CharField(max_length=50)
    table_key = models.CharField(max_length=100)
    app_token = models.CharField(max_length=100)
    table_id = models.CharField(max_length=100)
    table_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
    )
    issue_code = models.CharField(
        max_length=50,
        choices=SyncIssueCode.choices,
        blank=True,
    )
    message = models.CharField(max_length=1000, blank=True)
    resolution_hint = models.CharField(max_length=1000, blank=True)
    expected_fields = models.JSONField(default=list, blank=True)
    missing_fields = models.JSONField(default=list, blank=True)
    expected_min_records = models.IntegerField(null=True, blank=True)
    expected_record_floor = models.IntegerField(default=0)
    record_count = models.IntegerField(default=0)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_key", "table_key"],
                name="uq_data_ops_sync_table_status",
            ),
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["issue_code"]),
        ]

    def __str__(self):
        return f"{self.source_key}/{self.table_key}: {self.status}"


class SyncJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_key = models.CharField(max_length=50, blank=True)
    table_key = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
    )
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    records_synced = models.IntegerField(default=0)
    error_message = models.CharField(max_length=2000, blank=True)
    locked_by = models.CharField(max_length=100, blank=True)
    lock_acquired_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    results = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "started_at"]),
            models.Index(fields=["source_key", "started_at"]),
            models.Index(fields=["source_key", "table_key", "started_at"]),
        ]

    def __str__(self):
        target = self.source_key or "full"
        if self.table_key:
            target = f"{target}/{self.table_key}"
        return f"{target} sync {self.status}"

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def uuid_pk():
    return (
        "id",
        models.UUIDField(
            default=uuid.uuid4,
            editable=False,
            primary_key=True,
            serialize=False,
        ),
    )


def source_fields():
    return [
        uuid_pk(),
        ("source_record_id", models.CharField(db_index=True, max_length=255)),
        ("source_app_token", models.CharField(max_length=100)),
        ("source_table_id", models.CharField(max_length=100)),
        ("raw_data", models.JSONField(blank=True, default=dict)),
        (
            "synced_at",
            models.DateTimeField(
                db_index=True,
                default=django.utils.timezone.now,
            ),
        ),
    ]


def money_field():
    return models.DecimalField(
        blank=True,
        decimal_places=4,
        max_digits=18,
        null=True,
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Contract",
            fields=source_fields()
            + [
                ("contract_number", models.CharField(blank=True, max_length=100)),
                ("customer_name", models.CharField(blank=True, max_length=255)),
                ("signing_entity", models.CharField(blank=True, max_length=255)),
                ("channel_type", models.CharField(blank=True, max_length=100)),
                ("enduser_customer", models.CharField(blank=True, max_length=255)),
                ("order_platform", models.CharField(blank=True, max_length=100)),
                ("sales_person", models.CharField(blank=True, max_length=100)),
                ("region", models.CharField(blank=True, max_length=100)),
                ("currency", models.CharField(blank=True, max_length=20)),
                ("total_amount", money_field()),
                ("product_category", models.CharField(blank=True, max_length=100)),
                ("signing_type", models.CharField(blank=True, max_length=100)),
                ("signing_date", models.DateField(blank=True, null=True)),
                ("service_start", models.DateField(blank=True, null=True)),
                ("service_end", models.DateField(blank=True, null=True)),
                ("status", models.CharField(blank=True, max_length=50)),
                ("filing_type", models.CharField(blank=True, max_length=100)),
                (
                    "contract_sub_type",
                    models.CharField(blank=True, max_length=100),
                ),
                ("expiry_status", models.CharField(blank=True, max_length=50)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["contract_number"],
                        name="data_ops_co_contrac_0506e8_idx",
                    ),
                    models.Index(
                        fields=["customer_name"],
                        name="data_ops_co_custome_94b9a5_idx",
                    ),
                    models.Index(
                        fields=["sales_person"],
                        name="data_ops_co_sales_p_a2fae2_idx",
                    ),
                    models.Index(
                        fields=["service_end"],
                        name="data_ops_co_service_a75472_idx",
                    ),
                    models.Index(
                        fields=["status"],
                        name="data_ops_co_status_905e72_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "source_app_token",
                            "source_table_id",
                            "source_record_id",
                        ],
                        name="uq_data_ops_contract_source",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SalesRecord",
            fields=source_fields()
            + [
                ("project_name", models.CharField(blank=True, max_length=255)),
                ("po_number", models.CharField(blank=True, max_length=100)),
                ("region", models.CharField(blank=True, max_length=100)),
                ("product_type", models.CharField(blank=True, max_length=100)),
                ("total_amount_usd", money_field()),
                ("allocation_date", models.DateField(blank=True, null=True)),
                ("expiry_date", models.DateField(blank=True, null=True)),
                ("order_type", models.CharField(blank=True, max_length=100)),
                ("status", models.CharField(blank=True, max_length=50)),
                ("sales_person", models.CharField(blank=True, max_length=100)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["project_name"],
                        name="data_ops_sa_project_67ece7_idx",
                    ),
                    models.Index(
                        fields=["sales_person"],
                        name="data_ops_sa_sales_p_a10836_idx",
                    ),
                    models.Index(
                        fields=["expiry_date"],
                        name="data_ops_sa_expiry__d169ba_idx",
                    ),
                    models.Index(
                        fields=["status"],
                        name="data_ops_sa_status_b7b683_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "source_app_token",
                            "source_table_id",
                            "source_record_id",
                        ],
                        name="uq_data_ops_sales_record_source",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ProjectInit",
            fields=source_fields()
            + [
                ("project_code", models.CharField(blank=True, max_length=100)),
                (
                    "domestic_international",
                    models.CharField(blank=True, max_length=50),
                ),
                (
                    "customer_full_name",
                    models.CharField(blank=True, max_length=255),
                ),
                ("oa_initiation_date", models.DateField(blank=True, null=True)),
                ("project_name", models.CharField(blank=True, max_length=255)),
                (
                    "project_description",
                    models.CharField(blank=True, max_length=1000),
                ),
                ("sales_person", models.CharField(blank=True, max_length=100)),
                ("sales_products", models.CharField(blank=True, max_length=500)),
                ("estimated_amount", money_field()),
                ("currency", models.CharField(blank=True, max_length=20)),
                (
                    "signing_party_type",
                    models.CharField(blank=True, max_length=255),
                ),
                (
                    "enduser_customer",
                    models.CharField(blank=True, max_length=255),
                ),
                ("contract_link", models.CharField(blank=True, max_length=500)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["project_code"],
                        name="data_ops_pr_project_67758b_idx",
                    ),
                    models.Index(
                        fields=["domestic_international"],
                        name="data_ops_pr_domesti_e77b5f_idx",
                    ),
                    models.Index(
                        fields=["sales_person"],
                        name="data_ops_pr_sales_p_01ec23_idx",
                    ),
                    models.Index(
                        fields=["oa_initiation_date"],
                        name="data_ops_pr_oa_init_ccc420_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "source_app_token",
                            "source_table_id",
                            "source_record_id",
                        ],
                        name="uq_data_ops_project_init_source",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="OverseaProject",
            fields=source_fields()
            + [
                ("project_name", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(blank=True, max_length=100)),
                ("po_number", models.CharField(blank=True, max_length=100)),
                ("country", models.CharField(blank=True, max_length=100)),
                ("payment_channel", models.CharField(blank=True, max_length=100)),
                ("signing_customer", models.CharField(blank=True, max_length=255)),
                ("product_type", models.CharField(blank=True, max_length=100)),
                ("product_spec", models.CharField(blank=True, max_length=255)),
                ("order_date", models.DateField(blank=True, null=True)),
                ("order_year", models.IntegerField(blank=True, null=True)),
                ("order_month", models.IntegerField(blank=True, null=True)),
                ("purchase_quantity", money_field()),
                ("purchase_cycle", models.IntegerField(blank=True, null=True)),
                ("unit_price", money_field()),
                ("total_amount", money_field()),
                ("currency", models.CharField(blank=True, max_length=20)),
                ("stat_amount_usd", money_field()),
                ("allocation_date", models.DateField(blank=True, null=True)),
                ("allocation_quantity", money_field()),
                ("license_order_no", models.CharField(blank=True, max_length=100)),
                ("huawei_cloud_expiry", models.DateField(blank=True, null=True)),
                ("license_expiry", models.DateField(blank=True, null=True)),
                ("timezone", models.CharField(blank=True, max_length=50)),
                ("license_reg_code", models.CharField(blank=True, max_length=255)),
                ("kg_username", models.CharField(blank=True, max_length=100)),
                ("kg_full_name", models.CharField(blank=True, max_length=255)),
                ("end_customer", models.CharField(blank=True, max_length=255)),
                ("kg_email", models.CharField(blank=True, max_length=255)),
                ("cc_email", models.CharField(blank=True, max_length=500)),
                ("project_owner", models.CharField(blank=True, max_length=100)),
                ("invoice_no", models.CharField(blank=True, max_length=100)),
                ("payment_date", models.DateField(blank=True, null=True)),
                ("payment_amount", money_field()),
                ("payment_currency", models.CharField(blank=True, max_length=20)),
                ("payment_recipient", models.CharField(blank=True, max_length=255)),
                ("customer_type", models.CharField(blank=True, max_length=100)),
                ("cost_for", models.CharField(blank=True, max_length=255)),
                ("cost_usd", money_field()),
                ("payment_terms", models.CharField(blank=True, max_length=100)),
                ("tax_status", models.CharField(blank=True, max_length=100)),
                ("tax_amount", money_field()),
                ("order_type", models.CharField(blank=True, max_length=100)),
                ("acceptance_status", models.CharField(blank=True, max_length=100)),
                ("order_status", models.CharField(blank=True, max_length=100)),
                ("order_category", models.CharField(blank=True, max_length=100)),
                ("customer_id", models.CharField(blank=True, max_length=100)),
                ("payment_id", models.CharField(blank=True, max_length=100)),
                ("project_sub_no", models.CharField(blank=True, max_length=100)),
                ("remarks", models.CharField(blank=True, max_length=1000)),
                ("tax_voucher", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["country"],
                        name="data_ops_ov_country_54f107_idx",
                    ),
                    models.Index(
                        fields=["project_owner"],
                        name="data_ops_ov_project_9d7544_idx",
                    ),
                    models.Index(
                        fields=["status"],
                        name="data_ops_ov_status_3bb14b_idx",
                    ),
                    models.Index(
                        fields=["license_expiry"],
                        name="data_ops_ov_license_71d5d0_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "source_app_token",
                            "source_table_id",
                            "source_record_id",
                        ],
                        name="uq_data_ops_oversea_project_source",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="OverseaSettlement",
            fields=source_fields()
            + [
                ("project_name_en", models.CharField(blank=True, max_length=255)),
                ("project_name_cn", models.CharField(blank=True, max_length=255)),
                ("region", models.CharField(blank=True, max_length=100)),
                ("project_category", models.CharField(blank=True, max_length=100)),
                ("project_code", models.CharField(blank=True, max_length=100)),
                ("project_progress", models.CharField(blank=True, max_length=255)),
                ("todo_notes", models.CharField(blank=True, max_length=2000)),
                ("project_overview", models.CharField(blank=True, max_length=2000)),
                ("final_customer", models.CharField(blank=True, max_length=255)),
                ("integrator", models.CharField(blank=True, max_length=255)),
                (
                    "huawei_settlement_party",
                    models.CharField(blank=True, max_length=255),
                ),
                ("selling_products", models.CharField(blank=True, max_length=1000)),
                ("actual_revenue", money_field()),
                ("unit", models.CharField(blank=True, max_length=20)),
                ("overseas_initial_quote", money_field()),
                ("initial_quote_unit", models.CharField(blank=True, max_length=20)),
                (
                    "estimated_exchange_rate",
                    models.DecimalField(
                        blank=True,
                        decimal_places=8,
                        max_digits=18,
                        null=True,
                    ),
                ),
                ("estimated_revenue", money_field()),
                ("estimated_revenue_unit", models.CharField(blank=True, max_length=20)),
                ("revenue_diff", money_field()),
                ("revenue_diff_unit", models.CharField(blank=True, max_length=20)),
                ("revenue_diff_reason", models.CharField(blank=True, max_length=500)),
                ("receivable_amount", money_field()),
                ("received_amount", money_field()),
                ("currency", models.CharField(blank=True, max_length=20)),
                ("aisun_sub_fee_estimate", money_field()),
                ("payment_date", models.DateField(blank=True, null=True)),
                ("huawei_order_time", models.CharField(blank=True, max_length=100)),
                (
                    "huawei_est_payment_time",
                    models.CharField(blank=True, max_length=100),
                ),
                (
                    "transit_merchant_est_payment_time",
                    models.CharField(blank=True, max_length=100),
                ),
                ("master_overseas_link", models.CharField(blank=True, max_length=1000)),
                ("aisun_sub_fee_link", models.CharField(blank=True, max_length=1000)),
                (
                    "authorization_status_link",
                    models.CharField(blank=True, max_length=1000),
                ),
                ("has_initial_quote_attachment", models.BooleanField(default=False)),
                ("has_contract_attachment", models.BooleanField(default=False)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["project_code"],
                        name="data_ops_ov_project_4f375c_idx",
                    ),
                    models.Index(
                        fields=["region"],
                        name="data_ops_ov_region_d2f619_idx",
                    ),
                    models.Index(
                        fields=["payment_date"],
                        name="data_ops_ov_payment_6c90a2_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "source_app_token",
                            "source_table_id",
                            "source_record_id",
                        ],
                        name="uq_data_ops_settlement_source",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SyncCursor",
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
                ("app_token", models.CharField(max_length=100)),
                ("table_id", models.CharField(max_length=100)),
                ("source_key", models.CharField(blank=True, max_length=50)),
                ("table_key", models.CharField(blank=True, max_length=100)),
                ("table_name", models.CharField(blank=True, max_length=255)),
                ("last_sync_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
                ("record_count", models.IntegerField(default=0)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=["app_token", "table_id"],
                        name="uq_data_ops_sync_cursor",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SyncJob",
            fields=[
                uuid_pk(),
                ("source_key", models.CharField(blank=True, max_length=50)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ok", "OK"),
                            ("warning", "Warning"),
                            ("failed", "Failed"),
                            ("running", "Running"),
                            ("pending", "Pending"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "started_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("records_synced", models.IntegerField(default=0)),
                ("error_message", models.CharField(blank=True, max_length=2000)),
                ("locked_by", models.CharField(blank=True, max_length=100)),
                ("lock_acquired_at", models.DateTimeField(blank=True, null=True)),
                ("celery_task_id", models.CharField(blank=True, max_length=255)),
                ("results", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["status", "started_at"],
                        name="data_ops_sy_status_eb2090_idx",
                    ),
                    models.Index(
                        fields=["source_key", "started_at"],
                        name="data_ops_sy_source__5aef17_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="SyncTableStatus",
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
                ("source_key", models.CharField(max_length=50)),
                ("table_key", models.CharField(max_length=100)),
                ("app_token", models.CharField(max_length=100)),
                ("table_id", models.CharField(max_length=100)),
                ("table_name", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ok", "OK"),
                            ("warning", "Warning"),
                            ("failed", "Failed"),
                            ("running", "Running"),
                            ("pending", "Pending"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "issue_code",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "None"),
                            ("config_missing", "Configuration missing"),
                            ("token_error", "Token error"),
                            ("app_access_denied", "App access denied"),
                            ("table_access_denied", "Table access denied"),
                            ("field_access_denied", "Field access denied"),
                            ("field_missing", "Field missing"),
                            ("pagination_incomplete", "Pagination incomplete"),
                            ("zero_records_unexpected", "Unexpected zero"),
                            ("network_error", "Network error"),
                            ("unknown", "Unknown"),
                        ],
                        max_length=50,
                    ),
                ),
                ("message", models.CharField(blank=True, max_length=1000)),
                (
                    "resolution_hint",
                    models.CharField(blank=True, max_length=1000),
                ),
                ("expected_fields", models.JSONField(blank=True, default=list)),
                ("missing_fields", models.JSONField(blank=True, default=list)),
                ("expected_min_records", models.IntegerField(blank=True, null=True)),
                ("expected_record_floor", models.IntegerField(default=0)),
                ("record_count", models.IntegerField(default=0)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_success_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["status"],
                        name="data_ops_sy_status_eb89cf_idx",
                    ),
                    models.Index(
                        fields=["issue_code"],
                        name="data_ops_sy_issue__0b54dd_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=["source_key", "table_key"],
                        name="uq_data_ops_sync_table_status",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Project",
            fields=source_fields()
            + [
                (
                    "project_scope",
                    models.CharField(
                        choices=[
                            ("domestic", "Domestic"),
                            ("overseas", "Overseas"),
                        ],
                        max_length=20,
                    ),
                ),
                ("project_code", models.CharField(blank=True, max_length=100)),
                ("domestic_type", models.CharField(blank=True, max_length=50)),
                (
                    "customer_full_name",
                    models.CharField(blank=True, max_length=255),
                ),
                ("oa_initiation_date", models.DateField(blank=True, null=True)),
                ("estimated_amount", money_field()),
                ("sales_products", models.CharField(blank=True, max_length=500)),
                (
                    "signing_party_type",
                    models.CharField(blank=True, max_length=255),
                ),
                (
                    "project_description",
                    models.CharField(blank=True, max_length=1000),
                ),
                ("contract_link", models.CharField(blank=True, max_length=500)),
                ("country", models.CharField(blank=True, max_length=100)),
                ("status", models.CharField(blank=True, max_length=100)),
                ("po_number", models.CharField(blank=True, max_length=100)),
                ("payment_channel", models.CharField(blank=True, max_length=100)),
                ("signing_customer", models.CharField(blank=True, max_length=255)),
                ("end_customer", models.CharField(blank=True, max_length=255)),
                ("customer_type", models.CharField(blank=True, max_length=100)),
                ("product_type", models.CharField(blank=True, max_length=100)),
                ("product_spec", models.CharField(blank=True, max_length=255)),
                ("order_type", models.CharField(blank=True, max_length=100)),
                ("order_status", models.CharField(blank=True, max_length=100)),
                ("acceptance_status", models.CharField(blank=True, max_length=100)),
                ("order_date", models.DateField(blank=True, null=True)),
                ("order_year", models.IntegerField(blank=True, null=True)),
                ("order_month", models.IntegerField(blank=True, null=True)),
                ("order_category", models.CharField(blank=True, max_length=100)),
                ("customer_id", models.CharField(blank=True, max_length=100)),
                ("payment_id", models.CharField(blank=True, max_length=100)),
                ("total_amount", money_field()),
                ("stat_amount_usd", money_field()),
                ("allocation_date", models.DateField(blank=True, null=True)),
                ("allocation_quantity", money_field()),
                ("license_order_no", models.CharField(blank=True, max_length=100)),
                ("license_expiry", models.DateField(blank=True, null=True)),
                ("huawei_cloud_expiry", models.DateField(blank=True, null=True)),
                ("timezone", models.CharField(blank=True, max_length=50)),
                ("license_reg_code", models.CharField(blank=True, max_length=255)),
                ("kg_username", models.CharField(blank=True, max_length=100)),
                ("kg_full_name", models.CharField(blank=True, max_length=255)),
                ("kg_email", models.CharField(blank=True, max_length=255)),
                ("cc_email", models.CharField(blank=True, max_length=500)),
                ("invoice_no", models.CharField(blank=True, max_length=100)),
                ("payment_date", models.DateField(blank=True, null=True)),
                ("payment_amount", money_field()),
                ("payment_currency", models.CharField(blank=True, max_length=20)),
                ("payment_recipient", models.CharField(blank=True, max_length=255)),
                ("payment_terms", models.CharField(blank=True, max_length=100)),
                ("received_amount", money_field()),
                ("cost_for", models.CharField(blank=True, max_length=255)),
                ("cost_usd", money_field()),
                ("tax_status", models.CharField(blank=True, max_length=100)),
                ("tax_amount", money_field()),
                ("tax_voucher", models.CharField(blank=True, max_length=255)),
                ("project_sub_no", models.CharField(blank=True, max_length=100)),
                ("remarks", models.CharField(blank=True, max_length=1000)),
                ("project_name", models.CharField(blank=True, max_length=255)),
                ("sales_person", models.CharField(blank=True, max_length=100)),
                ("project_owner", models.CharField(blank=True, max_length=100)),
                (
                    "enduser_customer",
                    models.CharField(blank=True, max_length=255),
                ),
                ("currency", models.CharField(blank=True, max_length=20)),
                ("is_high_potential", models.BooleanField(default=False)),
                ("is_landed", models.BooleanField(default=False)),
                ("license_days_left", models.IntegerField(blank=True, null=True)),
                ("license_risk_level", models.CharField(blank=True, max_length=20)),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["project_scope"],
                        name="data_ops_pr_project_74c639_idx",
                    ),
                    models.Index(
                        fields=["domestic_type"],
                        name="data_ops_pr_domesti_4b812c_idx",
                    ),
                    models.Index(
                        fields=["country"],
                        name="data_ops_pr_country_b7772c_idx",
                    ),
                    models.Index(
                        fields=["sales_person"],
                        name="data_ops_pr_sales_p_d8d36a_idx",
                    ),
                    models.Index(
                        fields=["project_owner"],
                        name="data_ops_pr_project_458d97_idx",
                    ),
                    models.Index(
                        fields=["status"],
                        name="data_ops_pr_status_0eea51_idx",
                    ),
                    models.Index(
                        fields=["license_expiry"],
                        name="data_ops_pr_license_9a2a14_idx",
                    ),
                    models.Index(
                        fields=["project_scope", "sales_person"],
                        name="data_ops_pr_project_ee573b_idx",
                    ),
                    models.Index(
                        fields=["project_scope", "country"],
                        name="data_ops_pr_project_d891cf_idx",
                    ),
                    models.Index(
                        fields=["project_scope", "status"],
                        name="data_ops_pr_project_9fb2a6_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "source_app_token",
                            "source_table_id",
                            "source_record_id",
                        ],
                        name="uq_data_ops_project_source",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="DomesticLedger",
            fields=source_fields()
            + [
                ("ledger_type", models.CharField(blank=True, max_length=20)),
                ("currency", models.CharField(blank=True, max_length=20)),
                ("signing_date", models.DateField(blank=True, null=True)),
                ("customer_name", models.CharField(blank=True, max_length=255)),
                ("project_name", models.CharField(blank=True, max_length=255)),
                ("order_number", models.CharField(blank=True, max_length=100)),
                ("sales_person", models.CharField(blank=True, max_length=100)),
                ("signing_entity", models.CharField(blank=True, max_length=255)),
                ("total_contract_amount", money_field()),
                ("single_receive_amount", money_field()),
                ("invoice_amount", money_field()),
                ("payment_received", money_field()),
                ("outstanding", money_field()),
                ("invoice_date", models.DateField(blank=True, null=True)),
                ("receipt_time", models.DateField(blank=True, null=True)),
                ("expected_payment_date", models.DateField(blank=True, null=True)),
                ("license_quantity", money_field()),
                ("license_unit_price", money_field()),
                ("payment_progress", models.CharField(blank=True, max_length=100)),
                ("payment_status", models.CharField(blank=True, max_length=100)),
                ("payment_situation", models.CharField(blank=True, max_length=255)),
                ("payment_terms", models.CharField(blank=True, max_length=100)),
                ("sales_mode", models.CharField(blank=True, max_length=50)),
                ("purchase_product", models.CharField(blank=True, max_length=100)),
                ("tax_rate", models.CharField(blank=True, max_length=20)),
                ("year", models.CharField(blank=True, max_length=10)),
                ("project_code", models.CharField(blank=True, max_length=100)),
                ("remarks", models.CharField(blank=True, max_length=1000)),
                ("payment_item", models.CharField(blank=True, max_length=255)),
                ("payment_party", models.CharField(blank=True, max_length=255)),
                ("payee_name", models.CharField(blank=True, max_length=255)),
                ("payment_amount", money_field()),
                ("signing_mode", models.CharField(blank=True, max_length=100)),
                (
                    "counterparty_name",
                    models.CharField(blank=True, max_length=255),
                ),
                (
                    "contract",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ledger_entries",
                        to="data_ops.contract",
                    ),
                ),
                (
                    "linked_ledger",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="linked_payments",
                        to="data_ops.domesticledger",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["ledger_type", "payment_status"],
                        name="data_ops_do_ledger__d32dd9_idx",
                    ),
                    models.Index(
                        fields=["sales_person"],
                        name="data_ops_do_sales_p_1f8e19_idx",
                    ),
                    models.Index(
                        fields=["signing_entity"],
                        name="data_ops_do_signing_f4e28c_idx",
                    ),
                    models.Index(
                        fields=["expected_payment_date"],
                        name="data_ops_do_expecte_5e3fe3_idx",
                    ),
                    models.Index(
                        fields=["year"],
                        name="data_ops_do_year_cb648b_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "source_app_token",
                            "source_table_id",
                            "source_record_id",
                        ],
                        name="uq_data_ops_ledger_source",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="ContractHistory",
            fields=[
                uuid_pk(),
                ("source_record_id", models.CharField(db_index=True, max_length=100)),
                ("field_name", models.CharField(max_length=255)),
                ("old_value", models.CharField(blank=True, max_length=5000)),
                ("new_value", models.CharField(blank=True, max_length=5000)),
                ("changed_by", models.CharField(blank=True, db_index=True, max_length=255)),
                ("changed_at", models.DateTimeField(db_index=True)),
                ("change_type", models.CharField(default="update", max_length=20)),
                (
                    "created_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "contract",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="history_entries",
                        to="data_ops.contract",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["contract", "changed_at"],
                        name="data_ops_co_contrac_5706de_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=[
                            "contract",
                            "source_record_id",
                            "field_name",
                            "changed_at",
                        ],
                        name="uq_data_ops_history_dedup",
                    ),
                ],
            },
        ),
    ]

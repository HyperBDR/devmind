import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def sync_submitter_columns(apps, schema_editor):
    table_name = "cloud_billing_recharge_approval_record"
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(
            cursor, table_name
        )
        existing_columns = {col.name for col in description}

    if "submitter_identifier" not in existing_columns:
        schema_editor.execute(
            f"ALTER TABLE {table_name} "
            "ADD COLUMN submitter_identifier varchar(255) NOT NULL DEFAULT ''"
        )
        existing_columns.add("submitter_identifier")

    if "resolved_submitter_user_id" not in existing_columns:
        schema_editor.execute(
            f"ALTER TABLE {table_name} "
            "ADD COLUMN resolved_submitter_user_id varchar(128) NOT NULL DEFAULT ''"
        )
        existing_columns.add("resolved_submitter_user_id")

    if "submitter_user_id" in existing_columns:
        schema_editor.execute(
            f"UPDATE {table_name} "
            "SET submitter_identifier = submitter_user_id "
            "WHERE COALESCE(submitter_identifier, '') = '' "
            "AND COALESCE(submitter_user_id, '') <> ''"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("agentcore_metering", "0018_alter_llmusageseries_options_and_more"),
        ("cloud_billing", "0013_billingdata_performance_indexes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="cloudprovider",
            name="recharge_info",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Raw recharge approval input text. Store all recharge-related "
                    "parameters here and pass it to the recharge approval agent."
                ),
            ),
        ),
        migrations.AddField(
            model_name="alertrule",
            name="auto_submit_recharge_approval",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Whether to independently trigger the recharge approval SOP "
                    "when this alert rule is hit."
                ),
            ),
        ),
        migrations.CreateModel(
            name="RechargeApprovalRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trace_id", models.UUIDField(db_index=True, default=uuid.uuid4, help_text="Trace id used to correlate approval events and LLM runs.")),
                ("trigger_source", models.CharField(choices=[("manual", "Manual"), ("alert", "Alert")], default="manual", max_length=20)),
                ("trigger_reason", models.CharField(blank=True, default="", help_text="Why this approval was triggered, e.g. manual or balance_threshold.", max_length=64)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("submitted", "Submitted"), ("approved", "Approved"), ("rejected", "Rejected"), ("canceled", "Canceled"), ("failed", "Failed")], db_index=True, default="pending", max_length=20)),
                ("latest_stage", models.CharField(blank=True, default="", help_text="Latest execution stage, such as parse_input or submit_request.", max_length=64)),
                ("raw_recharge_info", models.TextField(blank=True, default="")),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("context_payload", models.JSONField(blank=True, default=dict)),
                ("response_payload", models.JSONField(blank=True, null=True)),
                ("callback_payload", models.JSONField(blank=True, null=True)),
                ("approval_timeline", models.JSONField(blank=True, default=list)),
                ("feishu_instance_code", models.CharField(blank=True, db_index=True, default=None, max_length=128, null=True, unique=True)),
                ("feishu_approval_code", models.CharField(blank=True, default=None, max_length=128, null=True)),
                ("status_message", models.TextField(blank=True, default="")),
                ("triggered_by_username_snapshot", models.CharField(blank=True, default="", help_text="Trigger user's username snapshot for auditing.", max_length=150)),
                ("submitter_identifier", models.CharField(blank=True, default="", help_text="Submitter email address or mobile number provided by the user.", max_length=255)),
                ("resolved_submitter_user_id", models.CharField(blank=True, default="", help_text="Resolved Feishu applicant user_id used for the actual submission.", max_length=128)),
                ("submitter_user_label", models.CharField(blank=True, default="", help_text="Display label snapshot for the Feishu applicant.", max_length=255)),
                ("llm_trace_summary", models.JSONField(blank=True, default=dict, help_text="Compact summary of related LLM or agent execution.")),
                ("latest_node_name", models.CharField(blank=True, default="", help_text="Latest approval node name or execution node label.", max_length=255)),
                ("latest_node_status", models.CharField(blank=True, default="", help_text="Latest approval node status snapshot.", max_length=64)),
                ("last_latency_ms", models.PositiveIntegerField(blank=True, help_text="Latency of the latest execution stage in milliseconds.", null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                ("last_callback_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("alert_record", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recharge_approval_records", to="cloud_billing.alertrecord")),
                ("latest_llm_usage", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recharge_approval_records", to="agentcore_metering.llmusage")),
                ("provider", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recharge_approval_records", to="cloud_billing.cloudprovider")),
                ("submitted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submitted_recharge_approvals", to=settings.AUTH_USER_MODEL)),
                ("triggered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="triggered_recharge_approvals", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "cloud_billing_recharge_approval_record",
                "verbose_name": "Recharge Approval Record",
                "verbose_name_plural": "Recharge Approval Records",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="RechargeApprovalLLMRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trace_id", models.UUIDField(db_index=True)),
                ("span_id", models.UUIDField(db_index=True, default=uuid.uuid4)),
                ("parent_span_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("runner_type", models.CharField(choices=[("agent", "Agent"), ("llm", "LLM"), ("script", "Script")], default="agent", max_length=20)),
                ("stage", models.CharField(db_index=True, max_length=64)),
                ("provider", models.CharField(blank=True, default="", max_length=128)),
                ("model", models.CharField(blank=True, default="", max_length=200)),
                ("input_snapshot", models.TextField(blank=True, default="")),
                ("output_snapshot", models.TextField(blank=True, default="")),
                ("parsed_payload", models.JSONField(blank=True, default=dict)),
                ("usage_payload", models.JSONField(blank=True, default=dict)),
                ("stdout", models.TextField(blank=True, default="")),
                ("stderr", models.TextField(blank=True, default="")),
                ("success", models.BooleanField(db_index=True, default=True)),
                ("error_message", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("llm_usage", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recharge_approval_llm_runs", to="agentcore_metering.llmusage")),
                ("record", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="llm_runs", to="cloud_billing.rechargeapprovalrecord")),
            ],
            options={
                "db_table": "cloud_billing_recharge_approval_llm_run",
                "verbose_name": "Recharge Approval LLM Run",
                "verbose_name_plural": "Recharge Approval LLM Runs",
                "ordering": ["created_at", "id"],
            },
        ),
        migrations.CreateModel(
            name="RechargeApprovalEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("trace_id", models.UUIDField(db_index=True, help_text="Trace id copied from the parent approval record.")),
                ("event_type", models.CharField(db_index=True, max_length=64)),
                ("stage", models.CharField(blank=True, default="", max_length=64)),
                ("source", models.CharField(blank=True, default="", max_length=64)),
                ("message", models.TextField(blank=True, default="")),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("operator_label", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("operator", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="recharge_approval_events", to=settings.AUTH_USER_MODEL)),
                ("record", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="cloud_billing.rechargeapprovalrecord")),
            ],
            options={
                "db_table": "cloud_billing_recharge_approval_event",
                "verbose_name": "Recharge Approval Event",
                "verbose_name_plural": "Recharge Approval Events",
                "ordering": ["created_at", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="rechargeapprovalrecord",
            index=models.Index(fields=["provider", "created_at"], name="cloud_billi_provide_e0e6a9_idx"),
        ),
        migrations.AddIndex(
            model_name="rechargeapprovalrecord",
            index=models.Index(fields=["status", "created_at"], name="cloud_billi_status_25a8ae_idx"),
        ),
        migrations.AddIndex(
            model_name="rechargeapprovalrecord",
            index=models.Index(fields=["trace_id"], name="cloud_billi_trace_i_7940d6_idx"),
        ),
        migrations.AddIndex(
            model_name="rechargeapprovalllmrun",
            index=models.Index(fields=["record", "created_at"], name="cloud_billi_record__8d41a1_idx"),
        ),
        migrations.AddIndex(
            model_name="rechargeapprovalllmrun",
            index=models.Index(fields=["trace_id", "created_at"], name="cloud_billi_trace_i_26fd11_idx"),
        ),
        migrations.AddIndex(
            model_name="rechargeapprovalllmrun",
            index=models.Index(fields=["stage", "created_at"], name="cloud_billi_stage_efced4_idx"),
        ),
        migrations.AddIndex(
            model_name="rechargeapprovalevent",
            index=models.Index(fields=["record", "created_at"], name="cloud_billi_record__8708f8_idx"),
        ),
        migrations.AddIndex(
            model_name="rechargeapprovalevent",
            index=models.Index(fields=["trace_id", "created_at"], name="cloud_billi_trace_i_d4ca9f_idx"),
        ),
        migrations.AddIndex(
            model_name="rechargeapprovalevent",
            index=models.Index(fields=["event_type", "created_at"], name="cloud_billi_event_t_4b27c4_idx"),
        ),
        migrations.RunPython(
            sync_submitter_columns,
            migrations.RunPython.noop,
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0007_resaleplatform_fee_config"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="pricecollectionrun",
            index=models.Index(
                fields=["source", "-started_at", "-id"],
                name="llmops_run_src_start_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="pricecollectionrun",
            index=models.Index(
                fields=["status", "-started_at", "-id"],
                name="llmops_run_status_start_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="resalelisting",
            index=models.Index(
                fields=["platform", "is_active"],
                name="llmops_listing_plat_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="resalelisting",
            index=models.Index(
                fields=["platform", "publish_status"],
                name="llmops_listing_plat_pub_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="resalelisting",
            index=models.Index(
                fields=["platform", "workflow_status"],
                name="llmops_listing_plat_flow_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usagereconciliationrecord",
            index=models.Index(
                fields=["status", "-date", "-id"],
                name="llmops_recon_status_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usagereconciliationrecord",
            index=models.Index(
                fields=["model", "-date", "-id"],
                name="llmops_recon_model_date_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="usagereconciliationrecord",
            index=models.Index(
                fields=["channel", "model", "-date"],
                name="llmops_recon_ch_model_dt_idx",
            ),
        ),
    ]

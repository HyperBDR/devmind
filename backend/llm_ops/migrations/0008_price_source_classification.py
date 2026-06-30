from django.db import migrations, models


CLOUD_PROVIDER_CODES = {"aliyun", "aliyun-wanx", "baidu", "volcengine"}


def classify_source(source):
    """Map legacy source category rows to the new source dimensions."""
    source_category = source.source_category
    source_type = source.source_type
    provider_code = ""
    if source.provider_id:
        provider_code = str(source.provider.code or "").lower()

    if source_category == "official_provider":
        if provider_code in CLOUD_PROVIDER_CODES:
            source_owner_type = "cloud_provider_official"
        else:
            source_owner_type = "model_provider_official"
        collection_method = "auto_collect"
    elif source_category == "supplier":
        source_owner_type = "supplier"
        collection_method = "api_sync" if source_type == "yunce" else "unknown"
    elif source_category == "manual":
        source_owner_type = "internal"
        collection_method = "manual_entry"
    else:
        source_owner_type = "unknown"
        collection_method = "unknown"
    return source_owner_type, collection_method


def classify_price_role(source, meta_model):
    """Return the model-row role for one source and canonical model."""
    if source is None:
        return "unknown"

    if source.source_category == "supplier":
        return "supplier"
    if source.source_category == "manual":
        return "manual"
    if source.source_category != "official_provider":
        return "unknown"

    source_vendor_id = source.provider_id
    model_vendor_id = getattr(meta_model, "vendor_id", None)
    if (
        source_vendor_id
        and model_vendor_id
        and source_vendor_id == model_vendor_id
    ):
        return "official"
    if source.source_owner_type == "cloud_provider_official":
        return "cloud_hosted"
    return "supplier"


def forwards(apps, schema_editor):
    price_source = apps.get_model("llm_ops", "PriceCollectionSource")
    llm_model = apps.get_model("llm_ops", "LLMModel")
    price_item = apps.get_model("llm_ops", "ModelPriceItem")

    for source in price_source.objects.select_related("provider"):
        source_owner_type, collection_method = classify_source(source)
        source.source_owner_type = source_owner_type
        source.collection_method = collection_method
        source.save(
            update_fields=[
                "source_owner_type",
                "collection_method",
                "updated_at",
            ]
        )

    for model in llm_model.objects.select_related(
        "source",
        "source__provider",
        "meta_model",
        "meta_model__vendor",
    ):
        role = classify_price_role(model.source, model.meta_model)
        if model.price_role != role:
            model.price_role = role
            model.save(update_fields=["price_role", "updated_at"])

    for item in price_item.objects.select_related(
        "source",
        "source__provider",
        "model",
        "model__source",
        "model__source__provider",
        "meta_model",
        "meta_model__vendor",
    ):
        source = item.source or item.model.source
        role = classify_price_role(source, item.meta_model)
        if item.price_role != role:
            item.price_role = role
            item.save(update_fields=["price_role", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("llm_ops", "0007_llmopsglobalconfig_price_sync_llm_config_uuid"),
    ]

    operations = [
        migrations.AddField(
            model_name="pricecollectionsource",
            name="collection_method",
            field=models.CharField(
                choices=[
                    ("auto_collect", "Auto Collect"),
                    ("manual_entry", "Manual Entry"),
                    ("manual_import", "Manual Import"),
                    ("api_sync", "API Sync"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="pricecollectionsource",
            name="source_owner_type",
            field=models.CharField(
                choices=[
                    (
                        "model_provider_official",
                        "Model Provider Official",
                    ),
                    (
                        "cloud_provider_official",
                        "Cloud Provider Official",
                    ),
                    ("supplier", "Supplier"),
                    ("internal", "Internal"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="modelpriceitem",
            name="price_role",
            field=models.CharField(
                choices=[
                    ("official", "Official"),
                    ("supplier", "Supplier"),
                    ("cloud_hosted", "Cloud Hosted"),
                    ("market_reference", "Market Reference"),
                    ("manual", "Manual"),
                    ("unknown", "Unknown"),
                ],
                db_index=True,
                default="unknown",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="llmmodel",
            name="price_role",
            field=models.CharField(
                choices=[
                    ("official", "Official"),
                    ("supplier", "Supplier"),
                    ("cloud_hosted", "Cloud Hosted"),
                    ("market_reference", "Market Reference"),
                    ("manual", "Manual"),
                    ("unknown", "Unknown"),
                ],
                db_index=True,
                default="unknown",
                max_length=50,
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]

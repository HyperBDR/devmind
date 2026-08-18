import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


MIGRATION_MARKER = "0012_channel_offerings"


def populate_default_offerings(apps, schema_editor):
    """Create one default offering for each legacy channel/meta-model pair."""
    ChannelOffering = apps.get_model("llm_ops", "ChannelOffering")
    ChannelModelPrice = apps.get_model("llm_ops", "ChannelModelPrice")
    ChannelModelPriceHistory = apps.get_model(
        "llm_ops",
        "ChannelModelPriceHistory",
    )
    ChannelPriceItem = apps.get_model("llm_ops", "ChannelPriceItem")
    MetaModel = apps.get_model("llm_ops", "MetaModel")

    offering_ids = {}
    price_rows = ChannelModelPrice.objects.all().values(
        "channel_id",
        "meta_model_id",
    ).distinct()
    for row in price_rows:
        key = (row["channel_id"], row["meta_model_id"])
        meta_model = MetaModel.objects.get(pk=row["meta_model_id"])
        offering, _created = ChannelOffering.objects.get_or_create(
            channel_id=row["channel_id"],
            meta_model_id=row["meta_model_id"],
            is_default=True,
            defaults={
                "offering_key": f"default-{row['meta_model_id']}",
                "display_name": meta_model.name,
                "source_metadata": {"migration": MIGRATION_MARKER},
            },
        )
        offering_ids[key] = offering.id

    model_groups = (
        (ChannelModelPrice, "offering_id"),
        (ChannelModelPriceHistory, "offering_id"),
        (ChannelPriceItem, "offering_id"),
    )
    for model, field_name in model_groups:
        rows = model.objects.filter(offering_id__isnull=True).values(
            "channel_id",
            "meta_model_id",
        ).distinct()
        for row in rows:
            key = (row["channel_id"], row["meta_model_id"])
            offering_id = offering_ids.get(key)
            if offering_id is None:
                meta_model = MetaModel.objects.get(pk=row["meta_model_id"])
                offering, _created = ChannelOffering.objects.get_or_create(
                    channel_id=row["channel_id"],
                    meta_model_id=row["meta_model_id"],
                    is_default=True,
                    defaults={
                        "offering_key": f"default-{row['meta_model_id']}",
                        "display_name": meta_model.name,
                        "source_metadata": {
                            "migration": MIGRATION_MARKER,
                        },
                    },
                )
                offering_id = offering.id
                offering_ids[key] = offering_id
            model.objects.filter(
                channel_id=row["channel_id"],
                meta_model_id=row["meta_model_id"],
                offering_id__isnull=True,
            ).update(**{field_name: offering_id})


def remove_default_offerings(apps, schema_editor):
    """Detach and remove only offerings created by this migration."""
    ChannelOffering = apps.get_model("llm_ops", "ChannelOffering")
    ChannelModelPrice = apps.get_model("llm_ops", "ChannelModelPrice")
    ChannelModelPriceHistory = apps.get_model(
        "llm_ops",
        "ChannelModelPriceHistory",
    )
    ChannelPriceItem = apps.get_model("llm_ops", "ChannelPriceItem")

    offerings = ChannelOffering.objects.filter(
        source_metadata__migration=MIGRATION_MARKER,
    )
    offering_ids = list(offerings.values_list("id", flat=True))
    ChannelModelPrice.objects.filter(offering_id__in=offering_ids).update(
        offering_id=None
    )
    ChannelModelPriceHistory.objects.filter(
        offering_id__in=offering_ids
    ).update(offering_id=None)
    ChannelPriceItem.objects.filter(offering_id__in=offering_ids).update(
        offering_id=None
    )
    offerings.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0011_modelpriceitem_source_current_meta_index"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChannelOffering",
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
                ("offering_key", models.CharField(max_length=255)),
                ("display_name", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("inactive", "Inactive"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=20,
                    ),
                ),
                (
                    "source_metadata",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "is_default",
                    models.BooleanField(db_index=True, default=False),
                ),
                (
                    "is_sales_enabled",
                    models.BooleanField(db_index=True, default=False),
                ),
                (
                    "is_cache_sales_enabled",
                    models.BooleanField(db_index=True, default=False),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "channel",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="offerings",
                        to="llm_ops.procurementchannel",
                    ),
                ),
                (
                    "meta_model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="procurement_offerings",
                        to="llm_ops.metamodel",
                    ),
                ),
                (
                    "model",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="procurement_offerings",
                        to="llm_ops.llmmodel",
                    ),
                ),
                (
                    "source_offering",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="channel_offerings",
                        to="llm_ops.sourceskuoffering",
                    ),
                ),
            ],
            options={
                "ordering": [
                    "channel__name",
                    "meta_model__name",
                    "display_name",
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="channeloffering",
            constraint=models.UniqueConstraint(
                fields=("channel", "offering_key"),
                name="uq_llm_ops_channel_offering_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="channeloffering",
            constraint=models.UniqueConstraint(
                condition=Q(is_default=True),
                fields=("channel", "meta_model"),
                name="uq_llm_ops_default_channel_offering",
            ),
        ),
        migrations.AddField(
            model_name="channelmodelprice",
            name="offering",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="model_prices",
                to="llm_ops.channeloffering",
            ),
        ),
        migrations.AddField(
            model_name="channelmodelpricehistory",
            name="offering",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="model_price_history",
                to="llm_ops.channeloffering",
            ),
        ),
        migrations.AddField(
            model_name="channelpriceitem",
            name="offering",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="price_items",
                to="llm_ops.channeloffering",
            ),
        ),
        migrations.RunPython(
            populate_default_offerings,
            remove_default_offerings,
        ),
        migrations.RemoveConstraint(
            model_name="channelmodelprice",
            name="uq_llm_ops_channel_model_price",
        ),
        migrations.AddConstraint(
            model_name="channelmodelprice",
            constraint=models.UniqueConstraint(
                fields=("channel", "model", "offering"),
                name="uq_llm_ops_channel_model_offering_price",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="channelpriceitem",
            name="uq_llm_ops_channel_price_item_fingerprint",
        ),
        migrations.AddConstraint(
            model_name="channelpriceitem",
            constraint=models.UniqueConstraint(
                fields=(
                    "channel",
                    "model",
                    "offering",
                    "dimension",
                    "billing_unit",
                    "currency",
                    "price_fingerprint",
                ),
                name="uq_llm_ops_channel_offer_price_item_fp",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="channelmodelpricehistory",
            name="uq_llm_ops_channel_price_history_fingerprint",
        ),
        migrations.AddConstraint(
            model_name="channelmodelpricehistory",
            constraint=models.UniqueConstraint(
                fields=(
                    "channel",
                    "model",
                    "offering",
                    "price_fingerprint",
                ),
                name="uq_llm_ops_offering_price_history_fingerprint",
            ),
        ),
    ]

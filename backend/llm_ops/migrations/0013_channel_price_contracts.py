import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0012_channel_offerings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="usagereconciliationrecord",
            name="business_occurred_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="usagereconciliationrecord",
            name="business_timezone",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="usagereconciliationrecord",
            name="exchange_rate_snapshot",
            field=models.DecimalField(
                blank=True,
                decimal_places=8,
                max_digits=18,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="usagereconciliationrecord",
            name="exchange_rate_source",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.AddField(
            model_name="usagereconciliationrecord",
            name="final_price_snapshot",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                max_digits=14,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="usagereconciliationrecord",
            name="offering",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reconciliation_records",
                to="llm_ops.channeloffering",
            ),
        ),
        migrations.AddField(
            model_name="usagereconciliationrecord",
            name="price_rule_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="usagereconciliationrecord",
            name="unit_price_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="ChannelPriceVersion",
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
                ("version", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("scheduled", "Scheduled"),
                            ("active", "Active"),
                            ("expired", "Expired"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "effective_from",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        null=True,
                    ),
                ),
                (
                    "effective_to",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        null=True,
                    ),
                ),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                (
                    "discount_basis",
                    models.CharField(
                        choices=[
                            ("list_price", "List Price"),
                            ("contract_price", "Contract Price"),
                        ],
                        default="contract_price",
                        max_length=30,
                    ),
                ),
                (
                    "discount_type",
                    models.CharField(
                        choices=[
                            ("none", "None"),
                            ("ratio", "Ratio"),
                            ("fixed", "Fixed Price"),
                        ],
                        default="none",
                        max_length=20,
                    ),
                ),
                (
                    "discount_value",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=14,
                        null=True,
                    ),
                ),
                (
                    "rounding_mode",
                    models.CharField(
                        choices=[
                            ("half_up", "Half Up"),
                            ("up", "Up"),
                            ("down", "Down"),
                        ],
                        default="half_up",
                        max_length=20,
                    ),
                ),
                (
                    "rounding_places",
                    models.PositiveSmallIntegerField(
                        default=6,
                        validators=[
                            django.core.validators.MaxValueValidator(12)
                        ],
                    ),
                ),
                (
                    "contract_currency",
                    models.CharField(blank=True, default="", max_length=10),
                ),
                (
                    "contract_exchange_rate",
                    models.DecimalField(
                        blank=True,
                        decimal_places=8,
                        max_digits=18,
                        null=True,
                    ),
                ),
                (
                    "exchange_rate_effective_from",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "exchange_rate_effective_to",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "source_evidence",
                    models.JSONField(blank=True, default=dict),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_channel_price_versions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "meta_model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="channel_price_versions",
                        to="llm_ops.metamodel",
                    ),
                ),
                (
                    "model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="channel_price_versions",
                        to="llm_ops.llmmodel",
                    ),
                ),
                (
                    "offering",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="price_versions",
                        to="llm_ops.channeloffering",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_channel_price_versions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["offering", "model", "-version"],
            },
        ),
        migrations.AddField(
            model_name="channelpriceitem",
            name="price_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="price_items",
                to="llm_ops.channelpriceversion",
            ),
        ),
        migrations.AddField(
            model_name="usagereconciliationrecord",
            name="price_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reconciliation_records",
                to="llm_ops.channelpriceversion",
            ),
        ),
        migrations.AddIndex(
            model_name="channelpriceversion",
            index=models.Index(
                fields=[
                    "offering",
                    "model",
                    "status",
                    "effective_from",
                ],
                name="llmops_price_ver_effective_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="channelpriceversion",
            constraint=models.UniqueConstraint(
                fields=("offering", "model", "version"),
                name="uq_llm_ops_channel_price_version",
            ),
        ),
    ]

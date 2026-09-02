import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import quotation.models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("quotation", "0031_merge_quotation_currency_heads"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuotationNote",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "id",
                    models.CharField(
                        default=quotation.models._uuid,
                        editable=False,
                        max_length=36,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "author_name",
                    models.CharField(max_length=255),
                ),
                (
                    "author_email",
                    models.CharField(db_index=True, max_length=255),
                ),
                (
                    "content",
                    models.TextField(max_length=4000),
                ),
                (
                    "author",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="quotation_notes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "quotation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notes",
                        to="quotation.quotation",
                    ),
                ),
            ],
            options={
                "db_table": "quotation_notes",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="quotationnote",
            index=models.Index(
                fields=["quotation", "created_at"],
                name="quote_note_quote_created",
            ),
        ),
    ]

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("llm_ops", "0002_resaleplatform_metadata"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pricecollectionrun",
            name="source",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="collection_runs",
                to="llm_ops.pricecollectionsource",
            ),
        ),
    ]

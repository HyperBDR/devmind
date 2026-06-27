import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("llm_ops", "0003_resale_workflow_config"),
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

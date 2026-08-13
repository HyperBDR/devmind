from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm_ops", "0010_resalelisting_pricing_format"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="modelpriceitem",
            index=models.Index(
                fields=["source", "is_current", "meta_model"],
                name="llmops_pi_src_cur_meta_idx",
            ),
        ),
    ]

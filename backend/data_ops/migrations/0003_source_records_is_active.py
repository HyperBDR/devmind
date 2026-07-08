from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("data_ops", "0002_feishu_collection_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="domesticledger",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="overseaproject",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="overseasettlement",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="project",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="projectinit",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="salesrecord",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
    ]

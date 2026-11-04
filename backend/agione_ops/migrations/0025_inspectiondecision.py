from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("agione_ops", "0024_inspectiongapacknowledgement"),
    ]

    operations = [
        migrations.CreateModel(
            name="InspectionDecision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("details", models.JSONField(default=dict)),
                ("rules", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="inspections", to="agione_ops.notificationrules",
                )),
                ("run", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="inspection_decision", to="agione_ops.syncrun",
                )),
            ],
            options={"db_table": "devmind_agione_inspection_decision",
                     "ordering": ["-created_at", "-pk"]},
        ),
    ]

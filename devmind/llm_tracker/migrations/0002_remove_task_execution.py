# Remove task_execution FK, use metadata for source tracking

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("llm_tracker", "0001_initial"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="llmusage",
            name="llm_track_task_exec_idx",
        ),
        migrations.RemoveField(
            model_name="llmusage",
            name="task_execution",
        ),
    ]

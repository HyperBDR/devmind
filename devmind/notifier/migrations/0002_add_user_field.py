# Generated manually for notifier app

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('notifier', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='notificationrecord',
            name='user',
            field=models.ForeignKey(
                blank=True,
                help_text='User who should receive this notification',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='notification_records',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddIndex(
            model_name='notificationrecord',
            index=models.Index(
                fields=['user', 'created_at'],
                name='notifier_no_user_created_idx'
            ),
        ),
    ]

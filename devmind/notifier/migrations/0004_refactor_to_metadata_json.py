# Generated manually for notifier app

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifier', '0003_add_email_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='notificationrecord',
            name='metadata',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Notification type specific metadata stored as JSON'
            ),
        ),
        migrations.RemoveField(
            model_name='notificationrecord',
            name='webhook_url',
        ),
        migrations.RemoveField(
            model_name='notificationrecord',
            name='recipient_email',
        ),
        migrations.RemoveField(
            model_name='notificationrecord',
            name='email_subject',
        ),
        migrations.RemoveField(
            model_name='notificationrecord',
            name='email_body_text',
        ),
        migrations.RemoveField(
            model_name='notificationrecord',
            name='email_body_html',
        ),
        migrations.RemoveField(
            model_name='notificationrecord',
            name='from_email',
        ),
        migrations.RemoveField(
            model_name='notificationrecord',
            name='from_name',
        ),
    ]

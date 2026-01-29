# Generated manually for notifier app

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='NotificationRecord',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID'
                    )
                ),
                (
                    'provider_type',
                    models.CharField(
                        choices=[
                            ('feishu', 'Feishu'),
                            ('wecom', 'WeCom'),
                            ('wechat', 'WeChat Work')
                        ],
                        help_text='Notification provider type',
                        max_length=20
                    )
                ),
                (
                    'channel',
                    models.CharField(
                        default='webhook',
                        help_text=(
                            'Notification channel (webhook, email, sms, etc.)'
                        ),
                        max_length=50
                    )
                ),
                (
                    'source_app',
                    models.CharField(
                        help_text=(
                            'Source application that triggered the notification'
                        ),
                        max_length=100
                    )
                ),
                (
                    'source_type',
                    models.CharField(
                        blank=True,
                        help_text='Source type (e.g., alert, task, event)',
                        max_length=100
                    )
                ),
                (
                    'source_id',
                    models.CharField(
                        blank=True,
                        help_text='Source identifier (e.g., alert_record_id)',
                        max_length=100
                    )
                ),
                (
                    'payload',
                    models.JSONField(
                        help_text='Notification payload sent to the provider'
                    )
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pending'),
                            ('success', 'Success'),
                            ('failed', 'Failed')
                        ],
                        db_index=True,
                        default='pending',
                        help_text='Notification status',
                        max_length=20
                    )
                ),
                (
                    'response',
                    models.JSONField(
                        blank=True,
                        help_text='Response from notification provider',
                        null=True
                    )
                ),
                (
                    'error_message',
                    models.TextField(
                        blank=True,
                        help_text='Error message if notification failed'
                    )
                ),
                (
                    'webhook_url',
                    models.URLField(
                        blank=True,
                        help_text='Webhook URL used for notification',
                        max_length=500
                    )
                ),
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        help_text='When the notification was created'
                    )
                ),
                (
                    'sent_at',
                    models.DateTimeField(
                        blank=True,
                        help_text='When the notification was actually sent',
                        null=True
                    )
                ),
            ],
            options={
                'verbose_name': 'Notification Record',
                'verbose_name_plural': 'Notification Records',
                'db_table': 'notifier_notification_record',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notificationrecord',
            index=models.Index(
                fields=['status', 'created_at'],
                name='notifier_no_status_created_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='notificationrecord',
            index=models.Index(
                fields=['source_app', 'source_type'],
                name='notifier_no_source_app_type_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='notificationrecord',
            index=models.Index(
                fields=['provider_type', 'status'],
                name='notifier_no_provider_status_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='notificationrecord',
            index=models.Index(
                fields=['created_at'],
                name='notifier_no_created_at_idx'
            ),
        ),
    ]

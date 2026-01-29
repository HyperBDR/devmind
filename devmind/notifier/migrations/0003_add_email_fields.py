# Generated manually for notifier app

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifier', '0002_add_user_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='notificationrecord',
            name='recipient_email',
            field=models.EmailField(
                blank=True,
                help_text='Recipient email address (email channel only)',
                max_length=255
            ),
        ),
        migrations.AddField(
            model_name='notificationrecord',
            name='email_subject',
            field=models.CharField(
                blank=True,
                help_text='Email subject (email channel only)',
                max_length=500
            ),
        ),
        migrations.AddField(
            model_name='notificationrecord',
            name='email_body_text',
            field=models.TextField(
                blank=True,
                help_text='Email body in plain text (email channel only)'
            ),
        ),
        migrations.AddField(
            model_name='notificationrecord',
            name='email_body_html',
            field=models.TextField(
                blank=True,
                help_text='Email body in HTML format (email channel only)'
            ),
        ),
        migrations.AddField(
            model_name='notificationrecord',
            name='from_email',
            field=models.EmailField(
                blank=True,
                help_text='Sender email address (email channel only)',
                max_length=255
            ),
        ),
        migrations.AddField(
            model_name='notificationrecord',
            name='from_name',
            field=models.CharField(
                blank=True,
                help_text='Sender display name (email channel only)',
                max_length=255
            ),
        ),
        migrations.AlterField(
            model_name='notificationrecord',
            name='provider_type',
            field=models.CharField(
                choices=[
                    ('feishu', 'Feishu'),
                    ('wecom', 'WeCom'),
                    ('wechat', 'WeChat Work'),
                    ('email', 'Email')
                ],
                help_text='Notification provider type',
                max_length=20
            ),
        ),
    ]

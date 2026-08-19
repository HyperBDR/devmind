from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_role_profile_preferred_platform'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='display_name',
            field=models.CharField(
                blank=True,
                help_text=(
                    'User-chosen display name shown across platforms. '
                    'Falls back to first/last name or username when empty.'
                ),
                max_length=120,
            ),
        ),
    ]

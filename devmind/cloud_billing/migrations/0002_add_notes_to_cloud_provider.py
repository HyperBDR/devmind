# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cloud_billing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='cloudprovider',
            name='notes',
            field=models.TextField(blank=True, null=True, help_text='Optional notes or description for this provider'),
        ),
    ]

"""
Merge migration for hourly_cost and unique_together updates.

This migration merges two parallel migrations:
- 0002_billingdata_hourly_cost (adds hourly_cost field)
- 0004_update_billingdata_unique_together (updates unique_together)
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cloud_billing', '0002_billingdata_hourly_cost'),
        ('cloud_billing', '0004_update_billingdata_unique_together'),
    ]

    operations = [
        # This is a merge migration with no operations
        # Both migrations are already applied independently
    ]

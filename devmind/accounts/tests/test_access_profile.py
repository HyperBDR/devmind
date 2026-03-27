from django.contrib.auth.models import Group, User
from django.test import TestCase

from accounts.access import get_access_profile
from accounts.models import Role


class AccessProfileTests(TestCase):
    def test_effective_roles_include_group_union(self):
        user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='password123',
        )
        group = Group.objects.create(name='operators')
        role = Role.objects.create(
            name='Ops',
            visible_features=['cloud_billing', 'data_collector'],
            preferred_platform='cloud_billing',
        )
        role.groups.add(group)
        user.groups.add(group)

        access_profile = get_access_profile(user)

        self.assertEqual(
            access_profile['visible_features'],
            ['operations_console'],
        )
        self.assertEqual(
            access_profile['preferred_platform'],
            'operations_console',
        )
        self.assertEqual(
            access_profile['landing_path'],
            '/operations/dashboard',
        )

    def test_legacy_default_features_preserved_without_roles(self):
        user = User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='password123',
        )

        access_profile = get_access_profile(user)

        self.assertEqual(
            access_profile['visible_features'],
            ['workspace', 'admin_console', 'operations_console'],
        )

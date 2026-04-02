from django.contrib.auth.models import Group, User
from django.test import TestCase

from accounts.access import (
    get_access_profile,
    normalize_feature_keys,
    normalize_platform_key,
)
from accounts.models import Role


class AccessProfileTests(TestCase):
    def test_hyperbdr_dashboard_alias_normalizes_to_hyperbdr_dashboard(self):
        self.assertEqual(
            normalize_feature_keys(['hyperbdr_dashboard']),
            ['hyperbdr_dashboard'],
        )
        self.assertEqual(
            normalize_platform_key('hyperbdr_dashboard'),
            'hyperbdr_dashboard',
        )

    def test_access_profile_includes_hyperbdr_dashboard_feature(self):
        user = User.objects.create_user(
            username='carol',
            email='carol@example.com',
            password='password123',
        )
        role = Role.objects.create(
            name='HyperBDR',
            visible_features=['hyperbdr_dashboard'],
            preferred_platform='hyperbdr_dashboard',
        )
        user.platform_roles.add(role)

        access_profile = get_access_profile(user)

        self.assertIn('hyperbdr_dashboard', access_profile['visible_features'])
        self.assertTrue(
            any(
                platform['key'] == 'hyperbdr_dashboard'
                and platform['default_path'] == '/hyperbdr-dashboard'
                for platform in access_profile['available_platforms']
            )
        )

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
            ['workspace', 'admin_console', 'operations_console', 'hyperbdr_dashboard'],
        )

from django.contrib.auth import get_user_model
from django.test import TestCase

from quotation.models import FeishuConnection


class FeishuTokenEncryptionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="token-owner@example.com",
            email="token-owner@example.com",
            password="password",
        )

    def test_tokens_are_encrypted_at_rest_and_decrypted_for_use(self):
        connection = FeishuConnection.objects.create(
            user=self.user,
            user_email=self.user.email,
            access_token="access-secret",
            refresh_token="refresh-secret",
        )

        stored = FeishuConnection.objects.get(pk=connection.pk)
        self.assertTrue(stored.access_token.startswith("enc::"))
        self.assertTrue(stored.refresh_token.startswith("enc::"))
        self.assertNotIn("access-secret", stored.access_token)
        self.assertNotIn("refresh-secret", stored.refresh_token)
        self.assertEqual(stored.get_access_token(), "access-secret")
        self.assertEqual(stored.get_refresh_token(), "refresh-secret")

    def test_saving_encrypted_tokens_does_not_encrypt_twice(self):
        connection = FeishuConnection.objects.create(
            user=self.user,
            user_email=self.user.email,
            access_token="access-secret",
            refresh_token="refresh-secret",
        )
        first_access = connection.access_token
        first_refresh = connection.refresh_token

        connection.save()
        connection.refresh_from_db()

        self.assertEqual(connection.access_token, first_access)
        self.assertEqual(connection.refresh_token, first_refresh)
        self.assertEqual(connection.get_access_token(), "access-secret")
        self.assertEqual(connection.get_refresh_token(), "refresh-secret")

    def test_empty_tokens_remain_empty(self):
        connection = FeishuConnection.objects.create(
            user=self.user,
            user_email=self.user.email,
        )

        self.assertEqual(connection.access_token, "")
        self.assertEqual(connection.refresh_token, "")
        self.assertEqual(connection.get_access_token(), "")
        self.assertEqual(connection.get_refresh_token(), "")

    def test_plaintext_legacy_values_are_readable(self):
        connection = FeishuConnection.objects.create(
            user=self.user,
            user_email=self.user.email,
        )
        FeishuConnection.objects.filter(pk=connection.pk).update(
            access_token="legacy-access",
            refresh_token="legacy-refresh",
        )
        connection.refresh_from_db()

        self.assertEqual(connection.get_access_token(), "legacy-access")
        self.assertEqual(connection.get_refresh_token(), "legacy-refresh")

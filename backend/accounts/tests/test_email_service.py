from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from accounts.services.email import get_email_delivery_options


class EmailDeliveryOptionsTests(SimpleTestCase):
    @override_settings(
        EMAIL_HOST_USER='env-user@example.com',
        DEFAULT_FROM_EMAIL='noreply@example.com',
    )
    def test_falls_back_to_django_settings_when_runtime_smtp_disabled(self):
        with patch('accounts.services.email.get_config', return_value={'enable': False}):
            from_email, connection = get_email_delivery_options()

        assert from_email == 'env-user@example.com'
        assert connection is None

    @override_settings(DEFAULT_FROM_EMAIL='noreply@example.com')
    def test_uses_runtime_smtp_config_when_enabled(self):
        smtp_config = {
            'enable': True,
            'host': 'smtp.example.com',
            'port': 465,
            'username': 'mailer@example.com',
            'password': 'secret',
            'use_tls': False,
            'use_ssl': True,
            'from_email': 'support@example.com',
            'from_name': 'DevMind Support',
        }

        with (
            patch('accounts.services.email.get_config', return_value=smtp_config),
            patch('accounts.services.email.get_connection', return_value='smtp-connection') as mock_connection,
        ):
            from_email, connection = get_email_delivery_options()

        assert from_email == 'DevMind Support <support@example.com>'
        assert connection == 'smtp-connection'
        mock_connection.assert_called_once_with(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host='smtp.example.com',
            port=465,
            username='mailer@example.com',
            password='secret',
            use_tls=False,
            use_ssl=True,
        )

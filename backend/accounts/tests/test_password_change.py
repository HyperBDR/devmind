import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from accounts.views.password import normalize_password_change_data


def test_normalize_password_change_data_accepts_parser_digit_aliases():
    data = {
        'old_password': 'old-secret',
        'new_password_1': 'NewSecret123',
        'new_password_2': 'NewSecret123',
    }

    normalized = normalize_password_change_data(data)

    assert normalized['old_password'] == 'old-secret'
    assert normalized['new_password1'] == 'NewSecret123'
    assert normalized['new_password2'] == 'NewSecret123'


@pytest.mark.django_db
def test_password_change_accepts_camel_case_fields():
    user = User.objects.create_user(
        username='password-user',
        email='password-user@example.com',
        password='OldSecret123',
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        '/api/v1/auth/password/change',
        {
            'oldPassword': 'OldSecret123',
            'newPassword1': 'NewSecret123',
            'newPassword2': 'NewSecret123',
        },
        format='json',
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password('NewSecret123')


@pytest.mark.django_db
def test_password_change_accepts_camel_parser_digit_aliases():
    user = User.objects.create_user(
        username='parser-password-user',
        email='parser-password-user@example.com',
        password='OldSecret123',
    )
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.post(
        '/api/v1/auth/password/change',
        {
            'old_password': 'OldSecret123',
            'new_password_1': 'NewSecret123',
            'new_password_2': 'NewSecret123',
        },
        format='json',
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password('NewSecret123')

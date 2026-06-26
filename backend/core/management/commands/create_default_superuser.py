"""
Create the default Django superuser from environment variables.

This command is intentionally separate from ``init_backend`` so service
startup does not query the user table on every deploy or restart.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Create the default superuser if it does not already exist."""

    help = (
        "Create the default superuser from DJANGO_SUPERUSER_* environment "
        "variables. Existing users are left unchanged."
    )

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "adminpassword")

        user_model = get_user_model()
        username_field = user_model.USERNAME_FIELD
        lookup = {username_field: username}

        if user_model._default_manager.filter(**lookup).exists():
            self.stdout.write(
                f"Superuser \"{username}\" already exists; skipping."
            )
            return

        user_data = {
            username_field: username,
            "email": email,
            "password": password,
        }
        for field_name in user_model.REQUIRED_FIELDS:
            env_name = f"DJANGO_SUPERUSER_{field_name.upper()}"
            if field_name == "email":
                user_data[field_name] = email
            elif field_name not in user_data:
                user_data[field_name] = os.getenv(env_name, "")

        user_model._default_manager.create_superuser(**user_data)
        self.stdout.write(
            self.style.SUCCESS(f"Superuser \"{username}\" created.")
        )

"""Explicit, guarded setup of local synthetic accounts and four connections."""

import os
import re
import sys
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.access import get_effective_feature_keys
from accounts.models import Profile, Role
from agione_ops.client import SYNTHETIC_TENANT_ID
from agione_ops.models import ConnectionGrant, SourceConnection, SyncRun
from agione_ops.sync import submit_sync, verify_connection

MARKER = "AGIONE_LOCAL_DEMO_V1"
DEFAULT_USERNAME = "agione-local-demo"
ACTIONS = ("view_business", "run_sync")


class Command(BaseCommand):
    """Create only explicitly managed synthetic demo resources."""

    help = "Set up a guarded local AGIOne demo; never runs at startup."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=DEFAULT_USERNAME)
        secrets = parser.add_mutually_exclusive_group()
        secrets.add_argument("--password-env", metavar="ENVIRONMENT_KEY")
        secrets.add_argument("--password-stdin", action="store_true")
        parser.add_argument("--grant-existing-user", default=None)

    def handle(self, *args, **options):
        """Require all local flags before reading a password or database."""

        for name in (
            "AGIONE_OPS_LOCAL_DEMO_ENABLED",
            "AGIONE_OPS_SYNTHETIC_ENABLED",
            "AGIONE_OPS_LOCAL_EAGER",
        ):
            if getattr(settings, name, False) is not True:
                raise CommandError(
                    "Local synthetic demo flags are not enabled."
                )
        username = options["username"]
        if not re.fullmatch(
            r"agione-local-demo(?:-[A-Za-z0-9._-]+)?", username
        ):
            raise CommandError("Use the reserved agione-local-demo namespace.")
        if len(username) > 80:
            raise CommandError("The local demo username is too long.")
        password = self._password(options)
        runs = []
        try:
            with transaction.atomic():
                extra = self._existing_grantee(options["grant_existing_user"])
                user, role = self._managed_user(username, password)
                user.user_permissions.add(*self._permissions(*ACTIONS))
                role.users.add(user)
                self._profile(user)
                if extra is not None:
                    extra.user_permissions.add(*self._permissions(*ACTIONS))
                manager_permission = self._permissions("manage_connections")[0]
                user.user_permissions.add(manager_permission)
                try:
                    connections = []
                    for platform in ("pro", "cc"):
                        for principal in ("provider", "operator"):
                            connection = self._connection(
                                user,
                                platform,
                                principal,
                            )
                            self._grant(connection, user)
                            if extra is not None:
                                self._grant(connection, extra)
                            verify_connection(connection, user)
                            connections.append(connection)
                    zone = ZoneInfo("Asia/Shanghai")
                    end = datetime.combine(
                        timezone.now().astimezone(zone).date(),
                        time.min,
                        tzinfo=zone,
                    )
                    start = end - timedelta(days=1)
                    for connection in connections:
                        run, _ = submit_sync(
                            connection,
                            user,
                            start,
                            end,
                            "Asia/Shanghai",
                            f"local-demo-{start:%Y%m%d}",
                        )
                        runs.append(run.pk)
                finally:
                    user.user_permissions.remove(manager_permission)
        except CommandError:
            raise
        except Exception:
            raise CommandError(
                "Local demo setup failed; no private error details are shown."
            ) from None
        # on_commit executes this application's inline fixture after setup.
        failed = False
        self.stdout.write(f"Local synthetic demo account: {username}")
        if extra is not None:
            self.stdout.write(
                f"Explicit existing-user access: {extra.username}"
            )
        published_runs = list(
            SyncRun.objects.filter(pk__in=runs).select_related("connection")
        )
        if len(published_runs) != 4:
            raise CommandError(
                "The four synthetic demo runs were not retained."
            )
        for run in published_runs:
            self.stdout.write(
                f"{run.connection.platform}/{run.connection.principal_kind} "
                f"connection={run.connection_id} status={run.status}"
            )
            failed = failed or run.status != "succeeded"
        if failed:
            raise CommandError(
                "Demo setup exists, but a synthetic run is not ready."
            )
        self.stdout.write(
            self.style.SUCCESS("Four synthetic connections are ready.")
        )

    def _password(self, options):
        """Read only an explicitly supplied source; never inspect .env files."""

        name = options.get("password_env")
        if name:
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,99}", name):
                raise CommandError("Invalid password environment key name.")
            password = os.environ.get(name)
            if password is None:
                raise CommandError(
                    "The explicit password environment key is absent."
                )
        elif options.get("password_stdin"):
            password = sys.stdin.read(4097).rstrip("\r\n")
        else:
            return None
        if not 16 <= len(password) <= 512:
            raise CommandError(
                "Supply a generated password of 16 to 512 characters."
            )
        if any(ord(character) < 32 for character in password):
            raise CommandError(
                "The demo password contains invalid characters."
            )
        return password

    def _permissions(self, *codenames):
        """Resolve only this application's explicit action permissions."""

        permissions = []
        for code in codenames:
            try:
                permissions.append(
                    Permission.objects.get(
                        content_type__app_label="agione_ops",
                        content_type__model="sourceconnection",
                        codename=code,
                    )
                )
            except Permission.DoesNotExist:
                raise CommandError(
                    "Apply the local schema before demo setup."
                ) from None
        return permissions

    def _existing_grantee(self, username):
        """An extra existing account is affected only by an explicit option."""

        if username is None:
            return None
        user = (
            get_user_model()
            .objects.select_for_update()
            .filter(
                username=username,
                is_active=True,
            )
            .first()
        )
        if user is None:
            raise CommandError(
                "The explicitly requested active user was not found."
            )
        if "agione_ops" not in get_effective_feature_keys(user):
            raise CommandError(
                "The selected user needs explicit AGIOne feature visibility first."
            )
        return user

    def _managed_user(self, username, password):
        """Never claim or reset an existing non-demo account."""

        user = (
            get_user_model()
            .objects.select_for_update()
            .filter(
                username=username,
            )
            .first()
        )
        role_name = f"AGIOne Local Demo: {username}"
        role = Role.objects.select_for_update().filter(name=role_name).first()
        if user is not None:
            if (
                user.last_name != MARKER
                or user.is_staff
                or user.is_superuser
                or not user.is_active
                or role is None
                or not role.users.filter(pk=user.pk).exists()
                or user.groups.exists()
                or user.platform_roles.exclude(pk=role.pk).exists()
                or user.user_permissions.exclude(
                    content_type__app_label="agione_ops",
                    content_type__model="sourceconnection",
                    codename__in=ACTIONS,
                ).exists()
            ):
                raise CommandError(
                    "Refusing to alter an existing non-demo account."
                )
        elif role is not None:
            raise CommandError("The reserved demo role is already in use.")
        if role is not None and (
            role.visible_features != ["agione_ops"]
            or role.preferred_platform != "agione_ops"
            or not role.is_active
            or role.groups.exists()
            or role.users.exclude(pk=user.pk).exists()
        ):
            raise CommandError(
                "The reserved demo role no longer matches its marker."
            )
        if user is None:
            if password is None:
                raise CommandError(
                    "A new demo account requires an explicit password source."
                )
            user = get_user_model().objects.create_user(
                username=username,
                password=password,
                last_name=MARKER,
                is_staff=False,
                is_superuser=False,
            )
            role = Role.objects.create(
                name=role_name,
                visible_features=["agione_ops"],
                preferred_platform="agione_ops",
            )
        elif password is not None:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user, role

    def _profile(self, user):
        """Complete only the dedicated demo profile, never an existing grantee."""

        profile, _ = Profile.objects.get_or_create(user=user)
        profile.registration_completed = True
        profile.preferred_platform = "agione_ops"
        profile.save(
            update_fields=["registration_completed", "preferred_platform"]
        )

    def _connection(self, user, platform, principal):
        """Reuse only a source matching the dedicated account and fixture."""

        name = f"AGIOne Local Demo [{user.username}] {platform.upper()} {principal}"
        candidates = list(
            SourceConnection.objects.select_for_update().filter(name=name)
        )
        if len(candidates) > 1:
            raise CommandError(
                "The reserved demo connection name is ambiguous."
            )
        if candidates:
            connection = candidates[0]
            if (
                connection.created_by_id != user.pk
                or connection.platform != platform
                or connection.principal_kind != principal
                or connection.source_kind != "synthetic"
                or connection.synthetic_fixture != "basic"
                or connection.expected_tenant_id != SYNTHETIC_TENANT_ID
                or connection.endpoint
                or connection.credential_ciphertext
                or connection.key_id
            ):
                raise CommandError(
                    "Refusing to alter an unmarked or real connection."
                )
            if not connection.enabled:
                raise CommandError(
                    "The managed demo connection was disabled explicitly."
                )
            return connection
        return SourceConnection.objects.create(
            name=name,
            platform=platform,
            principal_kind=principal,
            source_kind="synthetic",
            synthetic_fixture="basic",
            expected_tenant_id=SYNTHETIC_TENANT_ID,
            enabled=True,
            created_by=user,
        )

    def _grant(self, connection, user):
        """Only explicitly named users receive the synthetic connection scope."""

        grant, created = ConnectionGrant.objects.get_or_create(
            connection=connection,
            user=user,
            defaults={"can_view": True, "can_sync": True},
        )
        if not created and not (grant.can_view and grant.can_sync):
            grant.can_view = True
            grant.can_sync = True
            grant.save(update_fields=["can_view", "can_sync"])

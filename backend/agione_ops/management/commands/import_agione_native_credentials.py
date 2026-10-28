"""Import native connection credentials from private standard input."""

import json
import re
import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from agione_ops.models import ConnectionGrant, SourceConnection
from agione_ops.native_client import NativeClient


class Command(BaseCommand):
    """Create explicitly scoped connections without a Demo dependency."""

    help = "Import AGIOne connection credentials from private stdin."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)
        parser.add_argument("--allow-sync", action="store_true")
        parser.add_argument("--allow-manage", action="store_true")

    def handle(self, *args, **options):
        try:
            raw = sys.stdin.read(65537)
            if len(raw) > 65536:
                raise ValueError
            rows = json.loads(raw)
            if not isinstance(rows, list) or not 1 <= len(rows) <= 4:
                raise ValueError
            user = get_user_model().objects.get(
                pk=options["user_id"], is_active=True,
            )
            identities = set()
            connections = []
            with transaction.atomic():
                for row in rows:
                    if not isinstance(row, dict) or set(row) != {
                        "platform", "principal_kind", "endpoint",
                        "expected_tenant_id", "credentials",
                    }:
                        raise ValueError
                    platform, role = row["platform"], row["principal_kind"]
                    tenant = row["expected_tenant_id"]
                    if (
                        platform not in {"pro", "cc"}
                        or role not in {"provider", "operator"}
                        or not isinstance(tenant, str)
                        or not re.fullmatch(r"[0-9]{1,40}", tenant)
                        or (platform, role, tenant) in identities
                    ):
                        raise ValueError
                    identities.add((platform, role, tenant))
                    name = f"AGIOne {platform.upper()} · {role.title()} · API"
                    connection, _ = SourceConnection.objects.get_or_create(
                        source_kind="native", platform=platform,
                        principal_kind=role, expected_tenant_id=tenant,
                        defaults={"name": name, "created_by": user},
                    )
                    connection.endpoint = row["endpoint"]
                    connection.enabled = True
                    connection.set_credentials(row["credentials"])
                    connection.full_clean(
                        validate_unique=False, validate_constraints=False,
                    )
                    client = NativeClient(connection)
                    client.close()
                    connection.save()
                    connections.append(connection)
                    grant, _ = ConnectionGrant.objects.get_or_create(
                        connection=connection, user=user,
                    )
                    grant.can_view = True
                    grant.can_sync = grant.can_sync or options["allow_sync"]
                    grant.save()
                actions = ["view_business"]
                if options["allow_sync"]:
                    actions.append("run_sync")
                if options["allow_manage"]:
                    actions.append("manage_connections")
                permissions = Permission.objects.filter(
                    content_type__app_label="agione_ops",
                    content_type__model="sourceconnection",
                    codename__in=actions,
                )
                if permissions.count() != len(actions):
                    raise ValueError
                user.user_permissions.add(*permissions)
        except Exception:
            raise CommandError(
                "Native credential import failed; no secret details emitted."
            ) from None
        if options["allow_sync"]:
            from agione_ops.tasks import start_initial_native_sync

            for connection in connections:
                start_initial_native_sync(connection, user)
        self.stdout.write(
            f"Imported {len(rows)} encrypted native connections; "
            "grants apply only to the requested user."
        )

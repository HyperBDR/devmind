"""Initialize AGIOne from explicitly supplied deployment secrets."""

import io
import os
import sys

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from agione_ops.models import SourceConnection
from agione_ops.native_client import NativeClient


def initialize_native_connections():
    """Import initial connections once without changing existing credentials."""
    credentials = os.environ.get("AGIONE_OPS_BOOTSTRAP_CREDENTIALS")
    if not credentials:
        return
    if SourceConnection.objects.filter(source_kind="native").exists():
        return
    user_id = os.environ.get("AGIONE_OPS_BOOTSTRAP_USER_ID", "")
    if not settings.AGIONE_OPS_NATIVE_ENABLED or not user_id.isdecimal():
        raise CommandError("Invalid AGIOne deployment bootstrap configuration.")
    previous = sys.stdin
    try:
        sys.stdin = io.StringIO(credentials)
        with transaction.atomic():
            call_command("import_agione_native_credentials", "--user-id", user_id,
                         "--allow-sync")
            for connection in SourceConnection.objects.filter(source_kind="native"):
                with NativeClient(connection) as client:
                    identity = client.identity()
                if any(identity.get(key) != getattr(connection, field)
                       for key, field in (
                           ("tenant_id", "expected_tenant_id"),
                           ("platform", "platform"),
                           ("principal_kind", "principal_kind"),
                       )):
                    raise CommandError("AGIOne bootstrap identity mismatch.")
                connection.verified_tenant_id = identity["tenant_id"]
                connection.verified_at = timezone.now()
                connection.save(update_fields=["verified_tenant_id", "verified_at"])
    finally:
        sys.stdin = previous

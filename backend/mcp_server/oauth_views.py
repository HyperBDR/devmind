"""Authenticated endpoints used by the MCP OAuth consent page."""

import hashlib
import secrets
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from mcp_server.models import (
    McpOAuthAuthorization,
    McpOAuthAuthorizationCode,
    McpOAuthClient,
)
from mcp_server.oauth import CODE_SECONDS


class McpOAuthConsentView(APIView):
    """Show the requesting MCP client and approve or deny delegated access."""

    permission_classes = [IsAuthenticated]

    def get(self, request, transaction_id):
        item = self._authorization(transaction_id)
        if not item:
            return Response(
                {"detail": "Authorization request expired or unavailable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        client = McpOAuthClient.objects.filter(
            client_id=item.client_id
        ).first()
        return Response(
            {
                "client_name": (
                    client.metadata.get("client_name")
                    if client
                    else "MCP client"
                ),
                "devmind_user": {
                    "username": request.user.get_username(),
                    "email": request.user.email,
                },
                "scopes": item.scopes,
                "expires_at": item.expires_at,
            }
        )

    def post(self, request, transaction_id):
        approved = request.data.get("approved") is True
        code = secrets.token_urlsafe(32) if approved else ""
        with transaction.atomic():
            item = (
                McpOAuthAuthorization.objects.select_for_update()
                .filter(
                    pk=transaction_id,
                    expires_at__gt=timezone.now(),
                    consumed_at__isnull=True,
                    issuer=settings.MCP_OAUTH_ISSUER_URL,
                )
                .first()
            )
            if not item:
                return Response(
                    {"detail": "Authorization request expired or unavailable."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if approved and not request.user.is_active:
                return Response(
                    {"detail": "This DevMind account is disabled."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            item.consumed_at = timezone.now()
            item.save(update_fields=["consumed_at"])
            if approved:
                McpOAuthAuthorizationCode.objects.create(
                    code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
                    client_id=item.client_id,
                    user=request.user,
                    redirect_uri=item.redirect_uri,
                    code_challenge=item.code_challenge,
                    scopes=item.scopes,
                    resource=item.resource,
                    issuer=item.issuer,
                    expires_at=timezone.now()
                    + timedelta(seconds=CODE_SECONDS),
                )
                query = {"code": code}
            else:
                query = {"error": "access_denied"}
            if item.state:
                query["state"] = item.state
            query["iss"] = str(settings.MCP_OAUTH_ISSUER_URL)
            parts = urlsplit(item.redirect_uri)
            params = [
                (key, value)
                for key, value in parse_qsl(
                    parts.query,
                    keep_blank_values=True,
                )
                if key not in query
            ]
            params.extend(query.items())
            redirect_url = urlunsplit(
                (
                    parts.scheme,
                    parts.netloc,
                    parts.path,
                    urlencode(params),
                    "",
                )
            )
        return Response({"redirect_url": redirect_url})

    @staticmethod
    def _authorization(transaction_id):
        return McpOAuthAuthorization.objects.filter(
            pk=transaction_id,
            expires_at__gt=timezone.now(),
            consumed_at__isnull=True,
            issuer=settings.MCP_OAUTH_ISSUER_URL,
        ).first()

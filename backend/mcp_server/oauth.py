"""OAuth authorization server and bearer-token verification for MCP."""

import hashlib
import secrets
import uuid
from datetime import timedelta
from urllib.parse import urlencode

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RegistrationError,
    RefreshToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl

from mcp_server.models import (
    McpOAuthAuthorization,
    McpOAuthAuthorizationCode,
    McpOAuthClient,
    McpOAuthToken,
    McpRobotCredential,
)

ACCESS_TOKEN_SECONDS = 3600
REFRESH_TOKEN_SECONDS = 30 * 24 * 3600
AUTHORIZATION_SECONDS = 600
CODE_SECONDS = 60
READ_SCOPE = "mcp:read"
CLIENT_AUTH_METHODS = (
    "client_secret_basic",
    "client_secret_post",
    "none",
)


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _public_url(value):
    return str(value).rstrip("/")


class DevMindOAuthProvider(
    OAuthAuthorizationServerProvider[
        AuthorizationCode,
        RefreshToken,
        AccessToken,
    ]
):
    """Issue opaque, resource-bound tokens to explicitly authorized users."""

    async def get_client(self, client_id):
        return await sync_to_async(self._get_client, thread_sensitive=True)(
            client_id
        )

    @staticmethod
    def _get_client(client_id):
        record = McpOAuthClient.objects.filter(client_id=client_id).first()
        if not record:
            return None
        metadata = record.metadata.copy()
        metadata["client_secret"] = record.get_client_secret() or None
        return OAuthClientInformationFull.model_validate(metadata)

    async def register_client(self, client_info):
        await sync_to_async(self._register_client, thread_sensitive=True)(
            client_info
        )

    @staticmethod
    def _register_client(client_info):
        if (
            client_info.token_endpoint_auth_method
            not in CLIENT_AUTH_METHODS
            or "authorization_code" not in client_info.grant_types
            or "refresh_token" not in client_info.grant_types
            or (
                client_info.token_endpoint_auth_method != "none"
                and not client_info.client_secret
            )
        ):
            raise RegistrationError(
                error="invalid_client_metadata",
                error_description=(
                    "MCP clients must use PKCE authorization with a "
                    "supported client authentication method and refresh."
                ),
            )
        metadata = client_info.model_dump(
            exclude={"client_secret"},
            mode="json",
        )
        client, _ = McpOAuthClient.objects.update_or_create(
            client_id=client_info.client_id,
            defaults={"metadata": metadata},
        )
        client.set_client_secret(client_info.client_secret or "")
        client.save(update_fields=["client_secret_encrypted"])

    async def authorize(self, client, params: AuthorizationParams):
        scopes = params.scopes or [READ_SCOPE]
        resource = _public_url(settings.MCP_OAUTH_RESOURCE_URL)
        if (
            params.resource != resource
            or READ_SCOPE not in scopes
            or any(scope != READ_SCOPE for scope in scopes)
        ):
            raise AuthorizeError(
                error="invalid_target",
                error_description="The requested MCP resource or scope is invalid.",
            )
        authorization = await sync_to_async(
            self._create_authorization,
            thread_sensitive=True,
        )(
            client.client_id,
            str(params.redirect_uri),
            params.state or "",
            params.code_challenge,
            scopes,
            resource,
            settings.MCP_OAUTH_ISSUER_URL,
        )
        return (
            f"{settings.MCP_OAUTH_CONSENT_URL}?"
            f"{urlencode({'transaction': authorization})}"
        )

    @staticmethod
    def _create_authorization(
        client_id, redirect_uri, state, challenge, scopes, resource, issuer
    ):
        item = McpOAuthAuthorization.objects.create(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=challenge,
            scopes=scopes,
            resource=resource,
            issuer=issuer,
            expires_at=timezone.now()
            + timedelta(seconds=AUTHORIZATION_SECONDS),
        )
        return str(item.pk)

    async def load_authorization_code(self, client, authorization_code):
        return await sync_to_async(
            self._load_authorization_code,
            thread_sensitive=True,
        )(client.client_id, authorization_code)

    @staticmethod
    def _load_authorization_code(client_id, code):
        item = McpOAuthAuthorizationCode.objects.select_related("user").filter(
            code_hash=_digest(code),
            client_id=client_id,
            expires_at__gt=timezone.now(),
            issuer=settings.MCP_OAUTH_ISSUER_URL,
            user__is_active=True,
        ).first()
        if not item:
            return None
        return AuthorizationCode(
            code=code,
            scopes=item.scopes,
            expires_at=item.expires_at.timestamp(),
            client_id=item.client_id,
            code_challenge=item.code_challenge,
            redirect_uri=AnyUrl(item.redirect_uri),
            redirect_uri_provided_explicitly=(
                item.redirect_uri_provided_explicitly
            ),
            resource=item.resource,
            subject=str(item.user_id),
        )

    async def exchange_authorization_code(self, client, authorization_code):
        return await sync_to_async(
            self._exchange_authorization_code,
            thread_sensitive=True,
        )(client.client_id, authorization_code)

    @classmethod
    def _exchange_authorization_code(cls, client_id, authorization_code):
        with transaction.atomic():
            item = McpOAuthAuthorizationCode.objects.select_for_update().filter(
                code_hash=_digest(authorization_code.code),
                client_id=client_id,
                expires_at__gt=timezone.now(),
                issuer=settings.MCP_OAUTH_ISSUER_URL,
                user__is_active=True,
            ).first()
            if not item:
                raise TokenError(
                    error="invalid_grant",
                    error_description="The authorization code is invalid.",
                )
            item.delete()
            return cls._issue_tokens(
                item.user,
                client_id,
                item.scopes,
                item.resource,
            )

    @staticmethod
    def _issue_tokens(user, client_id, scopes, resource, family_id=None):
        now = timezone.now()
        family_id = family_id or uuid.uuid4()
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(48)
        McpOAuthToken.objects.bulk_create(
            [
                McpOAuthToken(
                    token_hash=_digest(access_token),
                    family_id=family_id,
                    token_type=McpOAuthToken.ACCESS,
                    client_id=client_id,
                    user=user,
                    scopes=scopes,
                    resource=resource,
                    issuer=settings.MCP_OAUTH_ISSUER_URL,
                    expires_at=now + timedelta(seconds=ACCESS_TOKEN_SECONDS),
                ),
                McpOAuthToken(
                    token_hash=_digest(refresh_token),
                    family_id=family_id,
                    token_type=McpOAuthToken.REFRESH,
                    client_id=client_id,
                    user=user,
                    scopes=scopes,
                    resource=resource,
                    issuer=settings.MCP_OAUTH_ISSUER_URL,
                    expires_at=now + timedelta(seconds=REFRESH_TOKEN_SECONDS),
                ),
            ]
        )
        return OAuthToken(
            access_token=access_token,
            expires_in=ACCESS_TOKEN_SECONDS,
            scope=" ".join(scopes),
            refresh_token=refresh_token,
        )

    async def load_refresh_token(self, client, refresh_token):
        return await sync_to_async(
            self._load_refresh_token,
            thread_sensitive=True,
        )(client.client_id, refresh_token)

    @staticmethod
    def _load_refresh_token(client_id, token):
        item = McpOAuthToken.objects.select_related("user").filter(
            token_hash=_digest(token),
            token_type=McpOAuthToken.REFRESH,
            client_id=client_id,
            expires_at__gt=timezone.now(),
            issuer=settings.MCP_OAUTH_ISSUER_URL,
            revoked_at__isnull=True,
            user__is_active=True,
        ).first()
        if not item:
            return None
        return RefreshToken(
            token=token,
            client_id=item.client_id,
            scopes=item.scopes,
            expires_at=int(item.expires_at.timestamp()),
            resource=item.resource,
            subject=str(item.user_id),
        )

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        return await sync_to_async(
            self._exchange_refresh_token,
            thread_sensitive=True,
        )(client.client_id, refresh_token, scopes)

    @classmethod
    def _exchange_refresh_token(cls, client_id, refresh_token, scopes):
        with transaction.atomic():
            item = McpOAuthToken.objects.select_for_update().select_related(
                "user"
            ).filter(
                token_hash=_digest(refresh_token.token),
                token_type=McpOAuthToken.REFRESH,
                client_id=client_id,
                expires_at__gt=timezone.now(),
                issuer=settings.MCP_OAUTH_ISSUER_URL,
                revoked_at__isnull=True,
                user__is_active=True,
            ).first()
            if not item:
                raise TokenError(
                    error="invalid_grant",
                    error_description="The refresh token is invalid.",
                )
            item.revoked_at = timezone.now()
            item.save(update_fields=["revoked_at"])
            McpOAuthToken.objects.filter(
                family_id=item.family_id,
                revoked_at__isnull=True,
            ).update(revoked_at=timezone.now())
            return cls._issue_tokens(
                item.user,
                client_id,
                scopes,
                item.resource,
            )

    async def load_access_token(self, token):
        return await sync_to_async(
            self._load_access_token,
            thread_sensitive=True,
        )(token)

    @staticmethod
    def _load_access_token(token):
        item = McpOAuthToken.objects.select_related("user").filter(
            token_hash=_digest(token),
            token_type=McpOAuthToken.ACCESS,
            issuer=settings.MCP_OAUTH_ISSUER_URL,
            expires_at__gt=timezone.now(),
            revoked_at__isnull=True,
            user__is_active=True,
        ).first()
        if not item:
            return None
        return AccessToken(
            token=token,
            client_id=item.client_id,
            scopes=item.scopes,
            expires_at=int(item.expires_at.timestamp()),
            resource=item.resource,
            subject=str(item.user_id),
        )

    async def revoke_token(self, token):
        await sync_to_async(self._revoke_token, thread_sensitive=True)(token)

    @staticmethod
    def _revoke_token(token):
        item = McpOAuthToken.objects.filter(
            token_hash=_digest(token.token),
            client_id=token.client_id,
            revoked_at__isnull=True,
        ).first()
        if item:
            McpOAuthToken.objects.filter(
                family_id=item.family_id,
                revoked_at__isnull=True,
            ).update(revoked_at=timezone.now())


class DevMindTokenVerifier:
    """Validate OAuth or robot bearer tokens and bind them to a user."""

    async def verify_token(self, token):
        robot_token = await sync_to_async(
            self._load_robot_token,
            thread_sensitive=True,
        )(token)
        if robot_token is not None:
            return robot_token
        return await sync_to_async(
            DevMindOAuthProvider._load_access_token,
            thread_sensitive=True,
        )(token)

    @staticmethod
    def _load_robot_token(token):
        item = McpRobotCredential.objects.select_related("user").filter(
            token_hash=_digest(token),
            issuer=settings.MCP_OAUTH_ISSUER_URL,
            resource=_public_url(settings.MCP_OAUTH_RESOURCE_URL),
            revoked_at__isnull=True,
            user__is_active=True,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).first()
        if item is None:
            return None
        now = timezone.now()
        McpRobotCredential.objects.filter(pk=item.pk).update(
            last_used_at=now
        )
        scopes = [READ_SCOPE, *item.scopes]
        return AccessToken(
            token=token,
            client_id=f"robot:{item.pk}",
            scopes=scopes,
            expires_at=(
                int(item.expires_at.timestamp())
                if item.expires_at
                else None
            ),
            resource=item.resource,
            subject=str(item.user_id),
        )


oauth_provider = DevMindOAuthProvider()

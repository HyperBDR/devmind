from __future__ import annotations

from datetime import timezone as dt_timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quotation.models import FeishuConnection
from quotation.permissions import user_display_email
from quotation.services.feishu_client import (
    FeishuAPIError,
    extract_feishu_token_from_url,
    token_expires_at,
)

from . import common

DEFAULT_FEISHU_OAUTH_RETURN_TO = "/quotation/list"


def _sanitize_oauth_return_to(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw or any(char in raw for char in ("\r", "\n")):
        return DEFAULT_FEISHU_OAUTH_RETURN_TO
    parsed = urlsplit(raw)
    if parsed.scheme or parsed.netloc:
        return DEFAULT_FEISHU_OAUTH_RETURN_TO
    if parsed.path != "/quotation" and not parsed.path.startswith(
        "/quotation/"
    ):
        return DEFAULT_FEISHU_OAUTH_RETURN_TO
    return urlunsplit(("", "", parsed.path, parsed.query, parsed.fragment))


def _append_feishu_connected(return_to: str | None) -> str:
    parsed = urlsplit(_sanitize_oauth_return_to(return_to))
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key != "feishu"]
    query.append(("feishu", "connected"))
    return urlunsplit(("", "", parsed.path, urlencode(query), parsed.fragment))


def _encode_oauth_state(user_email: str, return_to: str | None = None) -> str:
    return jwt.encode(
        {
            "sub": user_email,
            "purpose": "feishu_oauth",
            "nonce": str(uuid4()),
            "return_to": _sanitize_oauth_return_to(return_to),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def _decode_oauth_state(state: str) -> dict:
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise ValueError("invalid OAuth state") from exc
    if payload.get("purpose") != "feishu_oauth" or not payload.get("sub"):
        raise ValueError("invalid OAuth state")
    payload["return_to"] = _sanitize_oauth_return_to(payload.get("return_to"))
    return payload


class FeishuStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        email = user_display_email(request.user)
        connection = common._get_connection(email)
        return Response(
            {
                "configured": bool(
                    settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET
                ),
                "connected": bool(
                    connection and connection.get_access_token()
                ),
                "feishu_user_name": (
                    connection.feishu_user_name if connection else None
                ),
                "feishu_open_id": (
                    connection.feishu_open_id if connection else None
                ),
                "expires_at": connection.expires_at if connection else None,
                "preferred_folder_token": (
                    connection.preferred_folder_token if connection else None
                ),
                "preferred_folder_name": (
                    connection.preferred_folder_name if connection else None
                ),
                "fallback_folder_token": settings.FEISHU_TEST_FOLDER_TOKEN
                or None,
                "redirect_uri": settings.FEISHU_OAUTH_REDIRECT_URI,
            }
        )


class FeishuOAuthStartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
            return Response(
                {"detail": "Feishu credentials are not configured"}, status=400
            )
        state = _encode_oauth_state(
            user_display_email(request.user),
            request.query_params.get("return_to"),
        )
        try:
            url = common._client().build_user_oauth_url(state)
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"authorize_url": url})


class FeishuOAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            return Response({"detail": "code and state required"}, status=400)
        try:
            oauth_state = _decode_oauth_state(state)
            user_email = str(oauth_state["sub"]).lower()
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        User = get_user_model()
        user = User.objects.filter(
            Q(email__iexact=user_email) | Q(username__iexact=user_email)
        ).first()
        if not user:
            return Response({"detail": "OAuth user not found"}, status=400)

        client = common._client()
        try:
            bundle = client.exchange_code_for_user_token(code)
            profile = client.get_user_info(bundle.access_token)
        except FeishuAPIError as exc:
            return Response(
                {"detail": f"Feishu OAuth failed: {exc}"}, status=400
            )

        connection = common._get_connection(user_email)
        if not connection:
            connection = FeishuConnection(user=user, user_email=user_email)
        else:
            connection.user = user
        connection.set_access_token(bundle.access_token)
        connection.set_refresh_token(bundle.refresh_token)
        connection.token_type = bundle.token_type
        expires = token_expires_at(bundle.expires_in)
        if timezone.is_naive(expires):
            expires = timezone.make_aware(expires, dt_timezone.utc)
        connection.expires_at = expires
        connection.scope = bundle.scope
        connection.feishu_open_id = profile.get("open_id")
        connection.feishu_union_id = profile.get("union_id")
        connection.feishu_user_name = profile.get("name") or profile.get(
            "en_name"
        )
        connection.save()

        frontend = settings.FRONTEND_URL.rstrip("/")
        return HttpResponseRedirect(
            f"{frontend}{_append_feishu_connected(oauth_state.get('return_to'))}"
        )


class FeishuPreferredFolderView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        try:
            connection = common._require_connection(user_display_email(request.user))
            folder_token = extract_feishu_token_from_url(
                request.data.get("folder_token") or ""
            )
        except (PermissionError, FeishuAPIError) as exc:
            return Response(
                {"detail": str(exc)},
                status=400 if isinstance(exc, FeishuAPIError) else 401,
            )
        connection.preferred_folder_token = folder_token
        connection.preferred_folder_name = (
            request.data.get("folder_name") or ""
        ).strip() or None
        connection.save()
        return Response(
            {
                "preferred_folder_token": folder_token,
                "preferred_folder_name": connection.preferred_folder_name,
            }
        )


class FeishuHealthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            token = common._client().get_tenant_access_token()
        except FeishuAPIError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"ok": True, "tenant_token_prefix": token[:8] + "..."})

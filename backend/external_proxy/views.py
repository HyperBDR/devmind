"""Admin API views for external proxy configuration."""
import ipaddress

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from rest_framework.authentication import (
    BaseAuthentication,
    SessionAuthentication,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from accounts.access import get_effective_feature_keys
from accounts.permissions import HasRequiredFeature

from .models import ExternalSite
from .serializers import ExternalSiteSerializer
from .routing import build_routing_table

INTERNAL_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]


def _is_internal_request(request) -> bool:
    """Check if request originates from within the Docker network.

    Only trusts REMOTE_ADDR (set by the network layer) to avoid
    X-Forwarded-For spoofing from external clients.
    """
    ip_str = request.META.get("REMOTE_ADDR", "")
    if not ip_str:
        return False
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in INTERNAL_NETWORKS)
    except ValueError:
        return False


class ExternalSiteListView(APIView):
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_console"

    def get(self, request):
        queryset = ExternalSite.objects.all().order_by("order", "id")
        serializer = ExternalSiteSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ExternalSiteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            ExternalSiteSerializer(instance).data,
            status=HTTP_201_CREATED,
        )


class ExternalSiteLaunchView(APIView):
    """Return launch URL for iframe/redirect mode sites.

    Proxy-mode sites are handled directly by OpenResty and do not
    need a launch URL from this endpoint.

    The launch URL is exactly the admin-configured `external_url`.
    We do not merge in any client-supplied query string: an attacker
    who tricked a user into clicking a link of the form
    `?redirect=https://evil` would otherwise influence the target.
    The URL has already been validated for http(s) scheme and
    non-internal host at write time, so no extra filtering happens
    here.
    """
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_console"

    def post(self, request, site_id):
        instance = get_object_or_404(ExternalSite, pk=site_id, is_active=True)

        if instance.access_mode == ExternalSite.ACCESS_MODE_PROXY:
            return Response(
                {"detail": "Proxy-mode sites are opened directly."},
                status=400,
            )

        launch_url = (instance.external_url or "").strip()
        if not launch_url:
            return Response(
                {"detail": "External URL is not configured."},
                status=400,
            )

        return Response(
            {
                "id": instance.id,
                "name": instance.name,
                "slug": instance.slug,
                "access_mode": instance.access_mode,
                "launch_url": launch_url,
            }
        )


class ExternalSiteDetailView(APIView):
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_console"

    def put(self, request, site_id):
        instance = get_object_or_404(ExternalSite, pk=site_id)
        serializer = ExternalSiteSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(ExternalSiteSerializer(instance).data)

    def patch(self, request, site_id):
        instance = get_object_or_404(ExternalSite, pk=site_id)
        serializer = ExternalSiteSerializer(
            instance,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(ExternalSiteSerializer(instance).data)

    def delete(self, request, site_id):
        instance = get_object_or_404(ExternalSite, pk=site_id)
        instance.delete()
        return Response(status=HTTP_204_NO_CONTENT)


class InternalRoutingConfigView(View):
    """Internal endpoint for OpenResty to fetch routing config.

    Only accessible from within the Docker network.
    Returns a plain JSON routing table that Lua can parse.
    """

    def get(self, request):
        if not _is_internal_request(request):
            return JsonResponse({"error": "forbidden"}, status=403)
        table = build_routing_table()
        return JsonResponse({"routes": table})


class InternalAuthTokenView(View):
    """Internal endpoint for OpenResty to get auth headers.

    Handles token_fetch auth: returns the cached token or fetches
    a new one. Called by Lua when a proxied request needs auth.
    """

    def get(self, request):
        if not _is_internal_request(request):
            return JsonResponse({"error": "forbidden"}, status=403)

        from .services import get_proxy_headers

        slug = request.GET.get("slug", "").strip()
        path = request.GET.get("path", "").strip()

        if not slug:
            return JsonResponse(
                {"error": "slug required"}, status=400
            )

        try:
            site = ExternalSite.objects.get(
                slug=slug, is_active=True
            )
        except ExternalSite.DoesNotExist:
            return JsonResponse(
                {"error": "site not found"}, status=404
            )

        headers = get_proxy_headers(site, path)
        return JsonResponse(
            {
                "authorization": headers.get("Authorization", ""),
                "headers": headers,
            }
        )


class CookieJWTAuthentication(BaseAuthentication):
    """Read JWT from access_token cookie as a fallback."""

    def authenticate(self, request):
        token = request.COOKIES.get("access_token")
        if not token:
            return None

        jwt_auth = JWTAuthentication()
        try:
            validated = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated)
            return (user, validated)
        except (InvalidToken, TokenError):
            return None


class InternalAuthCheckView(APIView):
    """Verify user authentication and feature permission for proxy access.

    Tries JWT from Authorization header, then from access_token cookie,
    then from session cookie.
    """
    authentication_classes = [
        JWTAuthentication,
        CookieJWTAuthentication,
        SessionAuthentication,
    ]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_internal_request(request):
            return JsonResponse({"error": "forbidden"}, status=403)

        feature = request.GET.get("feature", "").strip()
        if not feature:
            return JsonResponse({"ok": True})

        user = request.user
        if feature in get_effective_feature_keys(user):
            return JsonResponse({"ok": True})

        return JsonResponse(
            {"error": "forbidden"}, status=403
        )

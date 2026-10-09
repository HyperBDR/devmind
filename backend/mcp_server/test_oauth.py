import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from starlette.testclient import TestClient

from mcp_server.models import (
    McpOAuthAuthorizationCode,
    McpOAuthClient,
    McpOAuthToken,
)
from mcp_server.server import build_asgi_app


@override_settings(
    DEBUG=True,
    MCP_OAUTH_ISSUER_URL="http://client.internal:18000/",
    MCP_OAUTH_RESOURCE_URL="http://client.internal:18000/mcp",
    MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL=(
        "http://browser.local:18000/authorize"
    ),
    MCP_OAUTH_TOKEN_ENDPOINT_URL="http://client.internal:18000/token",
    MCP_OAUTH_REGISTRATION_ENDPOINT_URL=(
        "http://client.internal:18000/register"
    ),
    MCP_OAUTH_REVOCATION_ENDPOINT_URL=(
        "http://client.internal:18000/revoke"
    ),
    MCP_OAUTH_CONSENT_URL=(
        "http://browser.local:18000/oauth/mcp/authorize"
    ),
    MCP_OAUTH_SCOPES=["mcp:read"],
    MCP_ALLOWED_HOSTS=["localhost:8000", "client.internal:18000"],
)
class McpOAuthFlowTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="oauth-user",
            email="oauth-user@example.com",
            password="not-used",
        )
        self.app = build_asgi_app()
        self.client = TestClient(self.app, base_url="http://localhost:8000")
        self.client.__enter__()
        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "oauth-user", "password": "not-used"},
        )
        payload = login.json().get("data", login.json())
        self.jwt = payload.get("access", "")
        if login.status_code != 200 or not self.jwt:
            raise AssertionError(f"Test login failed: {login.text}")

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def test_pkce_user_authorization_issues_user_bound_opaque_tokens(self):
        client_response = self.client.post(
            "/register",
            json={
                "client_name": "Independent MCP Client",
                "redirect_uris": [
                    "https://client.example/callback/oauth"
                ],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "scope": "mcp:read",
                "token_endpoint_auth_method": "client_secret_post",
            },
        )
        self.assertEqual(client_response.status_code, 201, client_response.text)
        oauth_client = client_response.json()
        self.assertEqual(
            oauth_client["redirect_uris"],
            ["https://client.example/callback/oauth"],
        )
        saved_client = McpOAuthClient.objects.get(
            client_id=oauth_client["client_id"]
        )
        self.assertEqual(
            saved_client.metadata["redirect_uris"],
            ["https://client.example/callback/oauth"],
        )

        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip("=")
        wrong_redirect = self.client.get(
            "http://browser.local:18000/authorize",
            params={
                "response_type": "code",
                "client_id": oauth_client["client_id"],
                "redirect_uri": "https://attacker.example/callback",
                "scope": "mcp:read",
                "state": "state-123",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": "http://client.internal:18000/mcp",
            },
        )
        self.assertEqual(wrong_redirect.status_code, 400)
        authorize = self.client.get(
            "http://browser.local:18000/authorize",
            params={
                "response_type": "code",
                "client_id": oauth_client["client_id"],
                "redirect_uri": "https://client.example/callback/oauth",
                "response_mode": "query",
                "scope": "mcp:read",
                "state": "state-123",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": "http://client.internal:18000/mcp",
            },
            follow_redirects=False,
        )
        self.assertEqual(authorize.status_code, 302, authorize.text)
        self.assertTrue(
            authorize.headers["location"].startswith(
                "http://browser.local:18000/oauth/mcp/authorize?"
            )
        )
        transaction_id = parse_qs(
            urlsplit(authorize.headers["location"]).query
        )["transaction"][0]
        consent_headers = {"Authorization": f"Bearer {self.jwt}"}
        details = self.client.get(
            f"/api/v1/mcp/oauth/transactions/{transaction_id}",
            headers=consent_headers,
        )
        self.assertEqual(details.status_code, 200, details.text)
        self.assertEqual(
            details.json()["data"]["client_name"],
            "Independent MCP Client",
        )
        self.assertEqual(
            details.json()["data"]["devmind_user"],
            {
                "username": "oauth-user",
                "email": "oauth-user@example.com",
            },
        )

        decision = self.client.post(
            f"/api/v1/mcp/oauth/transactions/{transaction_id}",
            json={"approved": True},
            headers=consent_headers,
        )
        self.assertEqual(decision.status_code, 200, decision.text)
        callback = urlsplit(decision.json()["data"]["redirect_url"])
        self.assertEqual(
            (callback.scheme, callback.netloc, callback.path),
            (
                "https",
                "client.example",
                "/callback/oauth",
            ),
        )
        redirect_query = parse_qs(
            callback.query
        )
        self.assertEqual(redirect_query["state"], ["state-123"])
        self.assertEqual(
            redirect_query["iss"], ["http://client.internal:18000/"]
        )
        code = redirect_query["code"][0]

        invalid_verifier = self.client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": oauth_client["client_id"],
                "client_secret": oauth_client["client_secret"],
                "redirect_uri": "https://client.example/callback/oauth",
                "code_verifier": "wrong-verifier",
            },
        )
        self.assertEqual(invalid_verifier.status_code, 400)
        self.assertEqual(invalid_verifier.json()["error"], "invalid_grant")

        token_response = self.client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": oauth_client["client_id"],
                "client_secret": oauth_client["client_secret"],
                "redirect_uri": "https://client.example/callback/oauth",
                "code_verifier": verifier,
            },
        )
        self.assertEqual(token_response.status_code, 200, token_response.text)
        tokens = token_response.json()
        self.assertEqual(tokens["token_type"], "Bearer")
        self.assertEqual(tokens["scope"], "mcp:read")
        self.assertEqual(tokens["expires_in"], 3600)
        self.assertEqual(len(tokens["access_token"].split(".")), 1)

        from mcp_server.oauth import oauth_provider

        access = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": "oauth-user",
                "method": "tools/call",
                "params": {
                    "name": "search_quotations",
                    "arguments": {"query": "", "user_id": 999999},
                },
            },
            headers={
                "accept": "application/json, text/event-stream",
                "host": "client.internal:18000",
                "authorization": f"Bearer {tokens['access_token']}",
            },
        )
        self.assertEqual(access.status_code, 200, access.text)
        stored_token = oauth_provider._load_access_token(
            tokens["access_token"]
        )
        self.assertEqual(stored_token.subject, str(self.user.pk))
        stored_record = McpOAuthToken.objects.get(
            token_hash=hashlib.sha256(
                tokens["access_token"].encode()
            ).hexdigest()
        )
        self.assertEqual(stored_record.issuer, "http://client.internal:18000/")
        self.assertEqual(
            stored_record.resource,
            "http://client.internal:18000/mcp",
        )
        replay = self.client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": oauth_client["client_id"],
                "client_secret": oauth_client["client_secret"],
                "redirect_uri": "https://client.example/callback/oauth",
                "code_verifier": verifier,
            },
        )
        self.assertEqual(replay.status_code, 400)
        self.assertEqual(replay.json()["error"], "invalid_grant")

    def test_local_callback_keeps_port_path_and_existing_query(self):
        redirect_uri = (
            "http://localhost:8765/client/oauth/callback/"
            "?tenant=first&tenant=second"
        )
        registration = self.client.post(
            "/register",
            json={
                "client_name": "Local MCP Client",
                "redirect_uris": [redirect_uri],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "scope": "mcp:read",
                "token_endpoint_auth_method": "none",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        client = registration.json()
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip("=")
        authorization = self.client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client["client_id"],
                "redirect_uri": redirect_uri,
                "scope": "mcp:read",
                "state": "local-state",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": "http://client.internal:18000/mcp",
            },
            follow_redirects=False,
        )
        self.assertEqual(authorization.status_code, 302)
        transaction_id = parse_qs(
            urlsplit(authorization.headers["location"]).query
        )["transaction"][0]
        response = self.client.post(
            f"/api/v1/mcp/oauth/transactions/{transaction_id}",
            json={"approved": True},
            headers={"Authorization": f"Bearer {self.jwt}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        callback = urlsplit(response.json()["data"]["redirect_url"])
        self.assertEqual(
            (callback.scheme, callback.netloc, callback.path),
            (
                "http",
                "localhost:8765",
                "/client/oauth/callback/",
            ),
        )
        query = parse_qs(callback.query)
        self.assertEqual(query["tenant"], ["first", "second"])
        self.assertEqual(query["state"], ["local-state"])
        self.assertEqual(len(query["code"][0]), 43)

    def test_denial_redirects_with_oauth_error_and_original_state(self):
        redirect_uri = "https://client.example/oauth/callback"
        registration = self.client.post(
            "/register",
            json={
                "client_name": "Another MCP Client",
                "redirect_uris": [redirect_uri],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "scope": "mcp:read",
                "token_endpoint_auth_method": "none",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        client = registration.json()
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(b"verifier").digest()
        ).decode().rstrip("=")
        authorization = self.client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": client["client_id"],
                "redirect_uri": redirect_uri,
                "scope": "mcp:read",
                "state": "denied-state",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": "http://client.internal:18000/mcp",
            },
            follow_redirects=False,
        )
        self.assertEqual(authorization.status_code, 302)
        transaction_id = parse_qs(
            urlsplit(authorization.headers["location"]).query
        )["transaction"][0]
        response = self.client.post(
            f"/api/v1/mcp/oauth/transactions/{transaction_id}",
            json={"approved": False},
            headers={"Authorization": f"Bearer {self.jwt}"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        callback = urlsplit(response.json()["data"]["redirect_url"])
        self.assertEqual(
            (callback.scheme, callback.netloc, callback.path),
            ("https", "client.example", "/oauth/callback"),
        )
        query = parse_qs(callback.query)
        self.assertEqual(query["error"], ["access_denied"])
        self.assertEqual(query["state"], ["denied-state"])
        self.assertNotIn("code", query)

    def test_unregistered_redirect_uri_is_rejected(self):
        registration = self.client.post(
            "/register",
            json={
                "client_name": "Callback Validation Client",
                "redirect_uris": ["https://client.example/registered"],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "scope": "mcp:read",
                "token_endpoint_auth_method": "none",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(b"verifier").digest()
        ).decode().rstrip("=")
        response = self.client.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": registration.json()["client_id"],
                "redirect_uri": "https://client.example/not-registered",
                "scope": "mcp:read",
                "state": "state",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": "http://client.internal:18000/mcp",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)

        metadata = self.client.get(
            "/.well-known/oauth-authorization-server"
        )
        self.assertEqual(metadata.status_code, 200)
        self.assertEqual(
            metadata.json()["token_endpoint_auth_methods_supported"],
            ["client_secret_basic", "client_secret_post", "none"],
        )
        self.assertEqual(
            metadata.json()["issuer"],
            "http://client.internal:18000/",
        )
        self.assertEqual(
            metadata.json()["authorization_endpoint"],
            "http://browser.local:18000/authorize",
        )
        self.assertEqual(
            metadata.json()["token_endpoint"],
            "http://client.internal:18000/token",
        )
        self.assertEqual(
            metadata.json()["registration_endpoint"],
            "http://client.internal:18000/register",
        )
        spoofed_host_metadata = self.client.get(
            "/.well-known/oauth-authorization-server",
            headers={"host": "attacker.example"},
        )
        self.assertEqual(
            spoofed_host_metadata.json()["issuer"],
            "http://client.internal:18000/",
        )
        browser_authorization = self.client.get(
            metadata.json()["authorization_endpoint"]
        )
        self.assertEqual(browser_authorization.status_code, 400)
        protected = self.client.get(
            "/.well-known/oauth-protected-resource/mcp"
        )
        self.assertEqual(protected.status_code, 200)
        self.assertEqual(
            protected.json()["resource"],
            "http://client.internal:18000/mcp",
        )
        self.assertEqual(
            protected.json()["authorization_servers"],
            ["http://client.internal:18000/"],
        )
        root_resource = self.client.get(
            "/.well-known/oauth-protected-resource"
        )
        self.assertEqual(root_resource.status_code, 200)
        self.assertEqual(
            root_resource.json()["resource"],
            "http://client.internal:18000/",
        )

    def test_client_secret_basic_is_registered_and_encrypted(self):
        response = self.client.post(
            "/register",
            json={
                "client_name": "Example MCP Client",
                "redirect_uris": [
                    "https://another-client.example/oauth/return"
                ],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "scope": "mcp:read",
                "token_endpoint_auth_method": "client_secret_basic",
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        registration = response.json()
        record = McpOAuthClient.objects.get(
            client_id=registration["client_id"]
        )
        self.assertNotIn("client_secret", record.metadata)
        self.assertNotEqual(
            record.client_secret_encrypted,
            registration["client_secret"],
        )
        self.assertEqual(
            record.get_client_secret(),
            registration["client_secret"],
        )
        credentials = base64.b64encode(
            f"{registration['client_id']}:"
            f"{registration['client_secret']}".encode()
        ).decode()
        token_response = self.client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": "invalid",
                "client_id": registration["client_id"],
                "redirect_uri": (
                    "https://another-client.example/oauth/return"
                ),
                "code_verifier": "invalid",
            },
            headers={"Authorization": f"Basic {credentials}"},
        )
        self.assertEqual(token_response.status_code, 400)
        self.assertEqual(token_response.json()["error"], "invalid_grant")

    def test_mcp_rejects_missing_or_wrong_resource_access_token(self):
        unauthenticated = self.client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            headers={
                "accept": "application/json, text/event-stream",
                "host": "client.internal:18000",
            },
        )
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertIn("resource_metadata", unauthenticated.headers["www-authenticate"])

    def test_mcp_rejects_wrong_issuer_resource_scope_and_expiry(self):
        valid_issuer = "http://client.internal:18000/"
        valid_resource = "http://client.internal:18000/mcp"
        cases = [
            ("wrong-issuer", "http://wrong-issuer/", valid_resource,
             ["mcp:read"], 401),
            ("wrong-resource", valid_issuer, "http://other/mcp",
             ["mcp:read"], 401),
            ("wrong-scope", valid_issuer, valid_resource,
             ["mcp:write"], 403),
            ("expired-token", valid_issuer, valid_resource,
             ["mcp:read"], 401),
        ]
        for label, issuer, resource, scopes, expected_status in cases:
            token = f"access-{label}"
            McpOAuthToken.objects.create(
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                token_type=McpOAuthToken.ACCESS,
                client_id="test-client",
                user=self.user,
                scopes=scopes,
                resource=resource,
                issuer=issuer,
                expires_at=(
                    timezone.now() - timedelta(minutes=1)
                    if label == "expired-token"
                    else timezone.now() + timedelta(minutes=1)
                ),
            )
            response = self.client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": label, "method": "initialize"},
                headers={
                    "accept": "application/json, text/event-stream",
                    "host": "client.internal:18000",
                    "authorization": f"Bearer {token}",
                },
            )
            self.assertEqual(response.status_code, expected_status, label)

    def test_expired_authorization_code_is_rejected(self):
        registration = self.client.post(
            "/register",
            json={
                "client_name": "Fresh MCP Client",
                "redirect_uris": ["https://client.example/return"],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "scope": "mcp:read",
                "token_endpoint_auth_method": "none",
            },
        )
        self.assertEqual(registration.status_code, 201, registration.text)
        client = registration.json()
        code = "expired-authorization-code"
        McpOAuthAuthorizationCode.objects.create(
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
            client_id=client["client_id"],
            user=self.user,
            redirect_uri="https://client.example/return",
            code_challenge="unused-challenge",
            scopes=["mcp:read"],
            resource="http://client.internal:18000/mcp",
            issuer="http://client.internal:18000/",
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        response = self.client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client["client_id"],
                "redirect_uri": "https://client.example/return",
                "code_verifier": "unused-verifier",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_grant")

    def test_issuer_path_uses_rfc8414_well_known_location(self):
        with override_settings(
            DEBUG=False,
            MCP_OAUTH_ISSUER_URL="https://auth.example/tenant/",
            MCP_OAUTH_RESOURCE_URL="https://resource.example/mcp",
            MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL=(
                "https://browser.example/authorize"
            ),
            MCP_OAUTH_TOKEN_ENDPOINT_URL="https://api.example/token",
            MCP_OAUTH_REGISTRATION_ENDPOINT_URL=(
                "https://api.example/register"
            ),
            MCP_OAUTH_REVOCATION_ENDPOINT_URL=(
                "https://api.example/revoke"
            ),
            MCP_OAUTH_CONSENT_URL=(
                "https://browser.example/oauth/mcp/authorize"
            ),
            MCP_OAUTH_SCOPES=["mcp:read"],
            MCP_ALLOWED_HOSTS=["resource.example:*"],
        ):
            with TestClient(
                build_asgi_app(),
                base_url="https://auth.example",
            ) as client:
                response = client.get(
                    "/.well-known/oauth-authorization-server/tenant"
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["issuer"],
            "https://auth.example/tenant/",
        )

    def test_production_rejects_http_oauth_urls_at_startup(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(ImproperlyConfigured):
                build_asgi_app()

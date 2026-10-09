"""Check MCP defaults without Django setup or a database connection."""

import os
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


SETTINGS_PATH = (
    Path(__file__).resolve().parents[1] / "core/settings/mcp_server.py"
)
ENDPOINT_PATHS = {
    "MCP_OAUTH_ISSUER_URL": "/",
    "MCP_OAUTH_RESOURCE_URL": "/mcp",
    "MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL": "/authorize",
    "MCP_OAUTH_TOKEN_ENDPOINT_URL": "/token",
    "MCP_OAUTH_REGISTRATION_ENDPOINT_URL": "/register",
    "MCP_OAUTH_REVOCATION_ENDPOINT_URL": "/revoke",
    "MCP_OAUTH_CONSENT_URL": "/oauth/mcp/authorize",
}


def load_settings(**environment):
    """Load settings against only the supplied deployment environment."""
    with patch.dict(os.environ, environment, clear=True):
        return runpy.run_path(str(SETTINGS_PATH))


class McpSettingsTests(unittest.TestCase):
    def assert_origin(self, settings, origin):
        """Check all generated public URLs and the narrow host allowlist."""
        for key, path in ENDPOINT_PATHS.items():
            self.assertEqual(settings[key], origin + path)
        self.assertEqual(settings["MCP_OAUTH_SCOPES"], ["mcp:read"])
        host = origin.split("://", 1)[1].split(":", 1)[0]
        self.assertEqual(settings["MCP_ALLOWED_HOSTS"], [f"{host}:*"])

    def test_existing_production_env_needs_no_mcp_variables(self):
        self.assert_origin(load_settings(), "https://tower.oneprocloud.com")

    def test_existing_site_domain_takes_precedence(self):
        self.assert_origin(
            load_settings(
                SITE_DOMAIN="quotes.company.test:10443",
                FRONTEND_URL="https://frontend.company.test",
            ),
            "https://quotes.company.test:10443",
        )

    def test_frontend_origin_is_reused_with_https(self):
        self.assert_origin(
            load_settings(
                SITE_DOMAIN="localhost:8000",
                FRONTEND_URL="http://quotes.company.test/app/",
            ),
            "https://quotes.company.test",
        )

    def test_local_and_example_site_values_use_hosted_default(self):
        for value in (
            "localhost:8000", "127.0.0.1:8000", "[::1]:8000",
            "host.docker.internal:18000", "devmind.example.com",
            "https://user:password@quotes.company.test",
        ):
            with self.subTest(value=value):
                self.assert_origin(
                    load_settings(SITE_DOMAIN=value, FRONTEND_URL=value),
                    "https://tower.oneprocloud.com",
                )

    def test_development_keeps_split_local_defaults(self):
        settings = load_settings(DJANGO_DEBUG="true")
        self.assertEqual(
            settings["MCP_OAUTH_RESOURCE_URL"],
            "http://host.docker.internal:18000/mcp",
        )
        self.assertEqual(
            settings["MCP_OAUTH_AUTHORIZATION_ENDPOINT_URL"],
            "http://localhost:18000/authorize",
        )
        self.assertEqual(
            settings["MCP_ALLOWED_HOSTS"],
            ["localhost:*", "127.0.0.1:*", "host.docker.internal:*"],
        )

    def test_explicit_endpoints_and_allowed_hosts_are_preserved(self):
        overrides = {
            key: "https://custom.company.test" + path
            for key, path in ENDPOINT_PATHS.items()
        }
        overrides["MCP_ALLOWED_HOSTS"] = "custom.company.test:443"
        settings = load_settings(**overrides)
        for key, value in overrides.items():
            expected = [value] if key == "MCP_ALLOWED_HOSTS" else value
            self.assertEqual(settings[key], expected)

    def test_split_base_overrides_derive_paths_and_hosts(self):
        settings = load_settings(
            MCP_OAUTH_CLIENT_BASE_URL="https://api.company.test/",
            MCP_OAUTH_BROWSER_BASE_URL="https://web.company.test/",
        )
        self.assertEqual(
            settings["MCP_OAUTH_TOKEN_ENDPOINT_URL"],
            "https://api.company.test/token",
        )
        self.assertEqual(
            settings["MCP_OAUTH_CONSENT_URL"],
            "https://web.company.test/oauth/mcp/authorize",
        )
        self.assertEqual(
            settings["MCP_ALLOWED_HOSTS"],
            ["api.company.test:*", "web.company.test:*"],
        )

    def test_empty_mcp_values_use_defaults(self):
        overrides = {key: "  " for key in ENDPOINT_PATHS}
        overrides.update(MCP_ALLOWED_HOSTS="", MCP_OAUTH_SCOPES="")
        self.assert_origin(
            load_settings(**overrides), "https://tower.oneprocloud.com"
        )

    def test_explicit_http_is_not_silently_rewritten(self):
        settings = load_settings(
            MCP_OAUTH_TOKEN_ENDPOINT_URL="http://custom.company.test/token"
        )
        self.assertEqual(
            settings["MCP_OAUTH_TOKEN_ENDPOINT_URL"],
            "http://custom.company.test/token",
        )

    def test_sample_environment_has_no_placeholder_mcp_urls(self):
        sample = SETTINGS_PATH.parents[3] / "env.sample"
        environment = dict(
            line.split("=", 1)
            for line in sample.read_text().splitlines()
            if line and not line.startswith("#") and "=" in line
        )
        self.assert_origin(
            load_settings(**environment), "https://tower.oneprocloud.com"
        )
        environment["DJANGO_DEBUG"] = "true"
        self.assertEqual(
            load_settings(**environment)["MCP_OAUTH_RESOURCE_URL"],
            "http://host.docker.internal:18000/mcp",
        )


if __name__ == "__main__":
    unittest.main()

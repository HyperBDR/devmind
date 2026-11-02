"""Check the production dashboard link configuration."""

import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        (None, "https://tower.oneprocloud.com/agione#focus"),
        (
            "https://preview.example/agione#focus",
            "https://preview.example/agione#focus",
        ),
    ],
)
def test_production_dashboard_url(configured, expected):
    """Use the production URL by default and honor explicit overrides."""
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "core.settings"
    if configured is None:
        env.pop("AGIONE_OPS_PUBLIC_URL", None)
    else:
        env["AGIONE_OPS_PUBLIC_URL"] = configured
    result = subprocess.run(
        [sys.executable, "-c", "from django.conf import settings; "
         "print(settings.AGIONE_OPS_PUBLIC_URL)"],
        env=env,
        capture_output=True,
        check=True,
        text=True,
    )
    assert result.stdout.strip() == expected

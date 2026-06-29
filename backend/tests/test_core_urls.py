import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")


def test_root_redirects_to_swagger():
    from django.test import Client

    response = Client().get("/")

    assert response.status_code == 302
    assert response["Location"] == "/swagger"

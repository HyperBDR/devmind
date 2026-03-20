"""
ASGI config for core project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.apps import apps
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

http_application = get_asgi_application()

if apps.is_installed("agentcore_runner"):
    try:
        from agentcore_runner.adapters.django.routing import (
            websocket_urlpatterns,
        )
    except Exception:
        websocket_urlpatterns = []
    application = ProtocolTypeRouter({
        "http": http_application,
        "websocket": URLRouter(websocket_urlpatterns),
    })
else:
    application = http_application

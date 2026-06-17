"""Test urlconf used by ``llm_ops`` view tests.

Wraps the production ``llm_ops.urls`` module so URL reverses
(e.g. ``reverse("llm-ops-yunce-collect")``) work in
``django.test.TestCase`` runs. The production project
settings cannot be used directly because they pull in
``cloud_billing`` / ``hyperbdr_dashboard`` which have
pre-existing migration issues on SQLite.
"""
from llm_ops.urls import urlpatterns  # noqa: F401

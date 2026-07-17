from django.urls import path

from quotation.views.health import HealthView

urlpatterns = [
    path("", HealthView.as_view()),
]

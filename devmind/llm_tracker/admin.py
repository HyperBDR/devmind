"""LLM Tracker admin configuration."""
from django.contrib import admin
from .models import LLMUsage


@admin.register(LLMUsage)
class LLMUsageAdmin(admin.ModelAdmin):
    """Admin interface for LLMUsage model."""

    list_display = (
        "id",
        "model",
        "user",
        "total_tokens",
        "prompt_tokens",
        "completion_tokens",
        "success",
        "created_at",
    )
    list_filter = ("success", "model", "created_at")
    search_fields = ("model", "user__username", "metadata")
    readonly_fields = (
        "id",
        "user",
        "model",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cached_tokens",
        "reasoning_tokens",
        "success",
        "error",
        "metadata",
        "created_at",
    )
    ordering = ["-created_at"]

"""
Admin configuration for external proxy models.
"""
from django.contrib import admin

from .models import ExternalSite


@admin.register(ExternalSite)
class ExternalSiteAdmin(admin.ModelAdmin):
    """
    Admin interface for ExternalSite model.

    Used to configure external sites that should be proxied through DevMind.
    """

    list_display = [
        "name",
        "slug",
        "path_prefix",
        "access_mode",
        "target_host",
        "target_scheme",
        "verify_tls",
        "auth_type",
        "is_active",
        "order",
    ]
    list_filter = ["access_mode", "auth_type", "is_active"]
    search_fields = ["name", "slug", "target_host"]
    readonly_fields = [
        "cached_token",
        "cached_token_expires_at",
        "created_at",
        "updated_at",
    ]
    ordering = ["order", "name"]

    fieldsets = [
        (
            "基本信息",
            {
                "fields": [
                    "name",
                    "slug",
                    "access_mode",
                    "target_host",
                    "target_scheme",
                    "verify_tls",
                    "external_url",
                    "required_feature",
                    "description",
                    "is_active",
                    "order",
                ],
            },
        ),
        (
            "认证配置",
            {
                "fields": ["auth_type"],
                "description": (
                    "选择认证方式后，显示对应的配置选项"
                ),
            },
        ),
        (
            "静态 Token 配置",
            {
                "fields": ["static_token"],
                "classes": ["collapse"],
                "description": 'auth_type 为 "静态 Token" 时使用',
            },
        ),
        (
            "Token 获取配置",
            {
                "fields": [
                    "token_fetch_url",
                    "token_fetch_method",
                    "token_fetch_headers",
                    "token_fetch_body",
                ],
                "classes": ["collapse"],
                "description": (
                    'auth_type 为 "外部服务自签发 Token" 时使用'
                ),
            },
        ),
        (
            "HMAC 配置",
            {
                "fields": ["hmac_secret"],
                "classes": ["collapse"],
                "description": 'auth_type 为 "HMAC 签名" 时使用',
            },
        ),
        (
            "Token 缓存 (只读)",
            {
                "fields": ["cached_token", "cached_token_expires_at"],
                "classes": ["collapse"],
                "description": (
                    "自动管理的 Token 缓存，请勿手动修改"
                ),
            },
        ),
        (
            "时间戳",
            {
                "fields": ["created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

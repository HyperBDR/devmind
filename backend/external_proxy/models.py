"""
External site configuration for proxy routing.
"""
from django.db import models

from .encrypted_fields import (
    EncryptedCharField,
    EncryptedJSONField,
    EncryptedTextField,
)


class ExternalSite(models.Model):
    """
    External site configuration for proxy routing and iframe embedding.
    """

    ACCESS_MODE_PROXY = "proxy"
    ACCESS_MODE_IFRAME = "iframe"
    ACCESS_MODE_REDIRECT = "redirect"
    ACCESS_MODE_CHOICES = [
        (ACCESS_MODE_PROXY, "平台代理"),
        (ACCESS_MODE_IFRAME, "Iframe 嵌入"),
        (ACCESS_MODE_REDIRECT, "直接跳转"),
    ]

    AUTH_TYPE_NONE = "none"
    AUTH_TYPE_TOKEN_FETCH = "token_fetch"
    AUTH_TYPE_STATIC_TOKEN = "static_token"
    AUTH_TYPE_HMAC = "hmac"
    AUTH_TYPE_CHOICES = [
        (AUTH_TYPE_NONE, "无认证"),
        (AUTH_TYPE_TOKEN_FETCH, "外部服务自签发 Token"),
        (AUTH_TYPE_STATIC_TOKEN, "静态 Token"),
        (AUTH_TYPE_HMAC, "HMAC 签名"),
    ]

    TARGET_SCHEME_HTTP = "http"
    TARGET_SCHEME_HTTPS = "https"
    TARGET_SCHEME_CHOICES = [
        (TARGET_SCHEME_HTTP, "HTTP"),
        (TARGET_SCHEME_HTTPS, "HTTPS"),
    ]

    name = models.CharField(
        "名称",
        max_length=100,
    )
    slug = models.SlugField(
        "代理标识",
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        help_text=(
            "仅填写标识，如 romo_log，实际访问路径为 "
            "/proxy/<slug>/"
        ),
    )
    access_mode = models.CharField(
        "访问方式",
        max_length=20,
        choices=ACCESS_MODE_CHOICES,
        default=ACCESS_MODE_PROXY,
    )
    target_host = models.CharField(
        "目标服务地址",
        max_length=200,
        blank=True,
        default="",
        help_text=(
            "代理模式下填写 host:port，如 frontend:3000 "
            "或 127.0.0.1:18082"
        ),
    )
    target_scheme = models.CharField(
        "目标服务协议",
        max_length=10,
        choices=TARGET_SCHEME_CHOICES,
        default=TARGET_SCHEME_HTTP,
        help_text="代理模式下目标服务使用的协议",
    )
    verify_tls = models.BooleanField(
        "校验 HTTPS 证书",
        default=True,
        help_text=(
            "HTTPS 目标是否校验证书。"
            "生产环境强烈建议保持开启；"
            "仅当目标使用自签证书且无法替换时再关闭。"
        ),
    )
    external_url = models.CharField(
        "外部 URL",
        max_length=500,
        blank=True,
        default="",
        help_text=(
            "iframe/跳转模式下填写浏览器可访问地址，如 "
            "https://myteamone.io"
        ),
    )
    description = models.TextField("描述", blank=True)
    required_feature = models.CharField(
        "所需功能标识",
        max_length=100,
        blank=True,
        default="admin_console",
        help_text="为空时默认使用 admin_console",
    )

    # Authentication configuration.
    auth_type = models.CharField(
        "认证方式",
        max_length=20,
        choices=AUTH_TYPE_CHOICES,
        default=AUTH_TYPE_NONE,
    )
    # Static token used when auth_type is static_token.
    static_token = EncryptedCharField(
        "静态 Token",
        max_length=500,
        blank=True,
        default="",
        help_text="静态 Token，auth_type 为 static_token 时使用",
    )
    # Token fetch configuration used when auth_type is token_fetch.
    token_fetch_url = models.CharField(
        "Token 获取 URL",
        max_length=500,
        blank=True,
        default="",
        help_text=(
            "从外部服务获取 Token 的接口，如 "
            "http://1.2.3.4:8080/auth/token"
        ),
    )
    token_fetch_method = models.CharField(
        "Token 获取方法",
        max_length=10,
        choices=[
            ("GET", "GET"),
            ("POST", "POST"),
        ],
        default="POST",
    )
    # Token fetch headers and body are encrypted at rest.
    token_fetch_headers = EncryptedJSONField(
        "Token 获取请求头",
        default=dict,
        blank=True,
        help_text=(
            "获取 Token 时的额外请求头，如 {\"X-API-Key\": \"xxx\"}"
        ),
    )
    token_fetch_body = EncryptedJSONField(
        "Token 获取请求体",
        default=dict,
        blank=True,
        help_text="获取 Token 时的请求体 JSON",
    )
    # Cached runtime tokens are sensitive and encrypted at rest.
    cached_token = EncryptedTextField(
        "缓存的 Token",
        blank=True,
        default="",
        editable=False,
    )
    cached_token_expires_at = models.DateTimeField(
        "Token 过期时间",
        null=True,
        blank=True,
        editable=False,
    )
    # HMAC configuration used when auth_type is hmac.
    hmac_secret = EncryptedCharField(
        "HMAC 密钥",
        max_length=500,
        blank=True,
        default="",
        help_text="与外部服务共享的 HMAC 密钥",
    )

    is_active = models.BooleanField("启用", default=True)
    order = models.IntegerField("排序", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "external_proxy_site"
        verbose_name = "外部站点"
        verbose_name_plural = "外部站点"
        ordering = ["order", "name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
        ]

    @property
    def path_prefix(self) -> str:
        return f"/proxy/{self.slug}/"

    def __str__(self):
        return f"{self.name} ({self.path_prefix})"

    def is_token_expired(self) -> bool:
        """Return whether the cached token has expired."""
        if not self.cached_token:
            return True
        if not self.cached_token_expires_at:
            return False
        from django.utils import timezone

        return timezone.now() >= self.cached_token_expires_at

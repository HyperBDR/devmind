from django.apps import AppConfig


class ExternalProxyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "external_proxy"
    verbose_name = "外部站点代理"

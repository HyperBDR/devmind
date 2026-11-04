"""Safe, actionable descriptions for collection failures."""

STAGES = {
    "authentication": "身份认证",
    "identity": "校验账号身份",
    "calls": "请求调用记录接口",
    "finance": "请求财务数据接口",
    "source": "请求 AGIOne 接口",
}
NETWORKS = {
    "dns", "dns_not_found", "dns_temporary", "connection",
    "connection_refused", "connection_reset", "network_unreachable",
    "host_unreachable", "tls", "tls_certificate", "tls_cert_expired",
    "tls_hostname", "protocol", "connect_timeout", "read_timeout", "timeout",
}


def safe_diagnostic(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    if isinstance(value.get("stage"), str) and value["stage"] in STAGES:
        result["stage"] = value["stage"]
    if isinstance(value.get("network"), str) and value["network"] in NETWORKS:
        result["network"] = value["network"]
    status = value.get("http_status")
    if type(status) is int and 100 <= status <= 599:
        result["http_status"] = status
    return result


def describe_failure(code, diagnostic):
    """Return observed facts and suggestions without guessing responsibility."""
    status = diagnostic.get("http_status")
    network = diagnostic.get("network")
    http = {
        401: ("上游返回 HTTP 401，身份认证未通过。",
              "DevMind 管理员核对凭据；AGIOne 管理员检查账号状态。"),
        403: ("上游返回 HTTP 403，访问被拒绝。",
              "请 AGIOne 管理员检查账号角色和接口权限。"),
        404: ("上游返回 HTTP 404，请求的地址未找到。",
              "DevMind 管理员核对地址和版本；必要时联系 AGIOne 管理员。"),
        429: ("上游返回 HTTP 429，请求受到限流。",
              "检查采集频率，并请 AGIOne 管理员核对限流策略。"),
    }
    networks = {
        "dns": ("AGIOne 服务域名解析失败。",
                "DevMind 或网络管理员检查域名和 DNS 配置。"),
        "dns_not_found": ("DNS 未找到 AGIOne 服务域名。",
                          "DevMind 管理员核对域名，网络管理员检查 DNS 记录。"),
        "dns_temporary": ("DNS 解析暂时失败。",
                          "网络管理员检查 DNS 服务和网络连通性。"),
        "connection": ("无法与 AGIOne 建立或维持连接。",
                       "检查网络链路和地址，并联系 AGIOne 管理员检查服务。"),
        "connection_refused": ("连接被对端或中间网络设备拒绝。",
                               "核对地址和端口，检查服务监听与网络策略。"),
        "connection_reset": ("连接被对端或中间网络设备重置。",
                             "检查 AGIOne 服务、网关及网络设备日志。"),
        "network_unreachable": ("系统报告目标网络不可达。",
                                "DevMind 或网络管理员检查路由和网络配置。"),
        "host_unreachable": ("系统报告目标主机不可达。",
                             "DevMind 或网络管理员检查路由和目标主机。"),
        "tls_cert_expired": ("AGIOne HTTPS 证书校验失败：证书已过期。",
                             "请 AGIOne 或网关管理员检查并更新证书。"),
        "tls_hostname": ("AGIOne HTTPS 证书校验失败：域名不匹配。",
                         "核对连接域名，并请服务或网关管理员检查证书。"),
        "tls_certificate": ("AGIOne HTTPS 证书校验失败。",
                             "请服务或网关管理员检查证书和信任链。"),
        "tls": ("与 AGIOne 建立 HTTPS 安全连接时发生 TLS 错误。",
                "请网络及服务管理员检查 TLS 配置和网关日志。"),
        "protocol": ("上游连接发生 HTTP 协议错误。",
                     "请 AGIOne 或网关管理员检查服务和网关日志。"),
        "connect_timeout": ("连接 AGIOne 时超时。",
                            "检查网络链路，并联系 AGIOne 管理员检查服务。"),
        "read_timeout": ("等待 AGIOne 响应时超时。",
                         "检查网络链路，并联系 AGIOne 管理员检查服务负载。"),
        "timeout": ("请求 AGIOne 时超时。",
                    "检查网络链路，并联系 AGIOne 管理员检查服务。"),
    }
    errors = {
        "SOURCE_AUTH_FAILED": ("AGIOne 身份认证未通过。",
                               "核对连接凭据，并检查 AGIOne 账号状态。"),
        "SOURCE_FORBIDDEN": ("AGIOne 拒绝访问。",
                             "请 AGIOne 管理员检查账号和接口权限。"),
        "SOURCE_NOT_CONFIGURED": ("连接配置不完整。",
                                  "请 DevMind 管理员检查连接配置。"),
        "SOURCE_ENDPOINT_FORBIDDEN": ("连接地址未通过安全校验。",
                                     "请 DevMind 管理员核对地址和允许列表。"),
        "SOURCE_IDENTITY_MISMATCH": ("账号身份与配置的租户或角色不一致。",
                                    "核对连接配置和 AGIOne 账号归属。"),
        "SOURCE_ROLE_NOT_VERIFIED": ("无法确认连接账号的角色。",
                                    "请 AGIOne 管理员核对账号角色。"),
        "SOURCE_TIMEOUT": ("请求 AGIOne 时超时。",
                           "检查网络链路及 AGIOne 服务状态。"),
        "SOURCE_UNREACHABLE": ("无法连接 AGIOne。",
                               "检查网络链路及 AGIOne 服务状态。"),
        "SOURCE_RATE_LIMITED": ("AGIOne 接口触发限流。",
                                "检查采集频率和 AGIOne 限流策略。"),
        "SOURCE_REJECTED": ("AGIOne 接口拒绝了请求。",
                            "检查上游状态码和接口配置。"),
        "SOURCE_NON_JSON": ("上游返回了无法解析的响应。",
                            "检查 AGIOne 接口、网关和连接地址。"),
        "SOURCE_SHAPE_CHANGED": ("上游数据格式不符合采集要求。",
                                 "请 DevMind 开发人员检查接口兼容性。"),
        "SOURCE_REDIRECT_BLOCKED": ("上游请求发生重定向，采集已阻止跳转。",
                                    "核对连接地址和 AGIOne 网关配置。"),
        "SOURCE_RESPONSE_TOO_LARGE": ("上游返回的数据超过采集大小限制。",
                                      "检查 AGIOne 返回数据和采集范围。"),
        "NATIVE_DISABLED": ("DevMind 中的 AGIOne 原生采集已停用。",
                            "请 DevMind 管理员检查采集功能配置。"),
        "ACCESS_REVOKED": ("采集账号的访问授权已撤销。",
                           "请 DevMind 管理员检查账号和连接授权。"),
        "CONFIGURATION_CHANGED": ("采集过程中连接配置发生变化。",
                                  "请 DevMind 管理员确认配置后重新采集。"),
        "CONNECTION_NOT_VERIFIED": ("采集连接尚未通过身份验证。",
                                    "请 DevMind 管理员检查并验证连接。"),
        "NATIVE_SYNC_DEADLINE": ("采集任务超过执行时间限制。",
                                 "检查采集范围、worker 和 AGIOne 响应速度。"),
        "LEASE_EXPIRED": ("采集任务心跳超时，任务已中断。",
                          "请 DevMind 管理员检查 worker 和调度状态。"),
        "DISPATCH_FAILED": ("采集任务无法派发。",
                            "请 DevMind 管理员检查任务队列和 worker。"),
        "FINANCE_REFRESH_TIMEOUT": ("财务采集任务超时。",
                                    "检查 DevMind worker 和 AGIOne 服务。"),
    }
    if status in http:
        return http[status]
    if status and 500 <= status <= 599:
        return (f"上游返回 HTTP {status}，服务未能完成请求。",
                "请 AGIOne 管理员检查服务和网关状态。")
    if status and 400 <= status <= 499:
        return (f"上游返回 HTTP {status}，请求未成功。",
                "DevMind 管理员核对配置；必要时联系 AGIOne 管理员。")
    if network in networks:
        return networks[network]
    if code in errors:
        return errors[code]
    if code in {"SOURCE_INCOMPLETE_PAGING", "SOURCE_DUPLICATE_PAGE",
                "SOURCE_CHANGED_DURING_PAGING", "SOURCE_PAGE_LIMIT",
                "SOURCE_SHARDS_INCOMPLETE", "SOURCE_SLICE_TOO_DENSE",
                "SOURCE_TIME_PRECISION_CHANGED", "SOURCE_TIME_SHAPE",
                "SOURCE_TIME_INVALID", "SOURCE_WINDOW_MISMATCH",
                "SOURCE_RECORD_ID_MISSING", "SOURCE_DUPLICATE_DIRECTORY"}:
        return ("上游分页数据不完整或不一致，本次未发布。",
                "请 DevMind 开发人员与 AGIOne 管理员检查接口和数据。")
    return ("采集未完成，具体原因需要进一步排查。",
            "请 DevMind 管理员根据错误代码和任务编号检查日志。")


def possible_cause(code, diagnostic):
    status = diagnostic.get("http_status")
    if status == 404:
        return "连接地址不匹配，或 AGIOne 接口路径、版本发生变化。"
    if status == 401 or code == "SOURCE_AUTH_FAILED":
        return "凭据可能失效或配置有误，账号状态也可能发生变化。"
    if status == 403 or code == "SOURCE_FORBIDDEN":
        return "账号可能缺少访问权限，或被上游安全策略限制。"
    if status == 429 or code == "SOURCE_RATE_LIMITED":
        return "请求频率可能超过上游限制。"
    if status and 500 <= status <= 599:
        return "AGIOne 服务或中间网关可能发生异常。"
    if diagnostic.get("network") == "dns":
        return "域名、DNS 配置或解析服务可能存在问题。"
    if diagnostic.get("network") == "connection_refused":
        return "目标端口可能没有服务监听，或连接被中间网络设备拒绝。"
    if diagnostic.get("network") or code in {
        "SOURCE_UNREACHABLE", "SOURCE_TIMEOUT",
    }:
        return "网络链路、连接配置或 AGIOne 服务可能存在问题。"
    return "需要结合错误代码、任务状态和日志进一步确认。"

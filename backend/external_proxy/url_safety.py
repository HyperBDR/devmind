"""URL validation helpers for ExternalSite.

Blocks obvious SSRF targets by rejecting URLs that point at
loopback / private / link-local / metadata IP ranges, or at
hostnames that conventionally do. Resolving arbitrary hostnames
is intentionally NOT done here to keep the validator offline;
a determined attacker who controls DNS can still bypass this,
so this is a defense-in-depth check on top of admin-only writes
and a docker-network-only routing endpoint.
"""
import ipaddress
import socket
from urllib.parse import urlparse


_BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "kubernetes.default.svc",
}


def _ip_is_blocked(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def is_blocked_host(host: str) -> bool:
    """Return True if host looks like an internal/metadata target."""
    if not host:
        return True

    normalized = host.lower().strip(".")
    if normalized in _BLOCKED_HOSTNAMES:
        return True

    # Strip port and IPv6 brackets / zone IDs
    candidate = normalized
    if candidate.startswith("["):
        # IPv6 literal: [::1] or [::1%eth0]:443
        candidate = candidate[1:].split("]")[0]
    if ":" in candidate and not candidate.startswith("["):
        # `host:port` form — keep just the host portion. ipaddress rejects
        # `127.0.0.1:8080`, so split on the last colon only when it looks
        # like an IPv4+port. For naked IPv6 we already handled it above.
        if candidate.count(":") == 1:
            candidate = candidate.split(":")[0]

    try:
        ip = ipaddress.ip_address(candidate)
    except ValueError:
        # Not a literal IP. Try a DNS resolution; if it maps to a
        # blocked IP range, treat as blocked. Fail-open on lookup
        # error so we don't reject valid public domains that
        # temporarily fail to resolve.
        try:
            resolved = socket.gethostbyname(candidate)
            ip = ipaddress.ip_address(resolved)
        except (socket.gaierror, ValueError):
            return False
        return _ip_is_blocked(ip)

    return _ip_is_blocked(ip)

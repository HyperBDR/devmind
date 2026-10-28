"""Allowlisted request telemetry without source bodies or credentials."""

import json
import logging
import re
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID, uuid4

logger = logging.getLogger("agione_ops.performance")
_current = ContextVar("agione_query_observation", default=None)
STAGES = frozenset({
    "acl", "snapshot_metadata", "demo_operation", "finance",
    "response_projection", "cache", "native_collection", "dispatch",
})
COUNTERS = frozenset({
    "internal_http_requests", "internal_download_bytes", "upstream_pages",
    "upstream_authentications",
})


def safe_code(value, fallback="INTERNAL_ERROR"):
    """Only bounded symbolic codes may enter telemetry."""
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,79}", value):
        return value
    return fallback


class QueryObservation:
    """One request's numeric timings and opaque identifiers."""

    def __init__(self, connection_id=None, request_id=None):
        self.started = time.perf_counter()
        try:
            self.request_id = str(UUID(str(request_id)))
        except (ValueError, TypeError, AttributeError):
            self.request_id = str(uuid4())
        try:
            self.connection_id = str(UUID(str(connection_id)))
        except (ValueError, TypeError, AttributeError):
            self.connection_id = None
        self.operation = None
        self.data_version = None
        self.cache_hit = False
        self.cache_unavailable = False
        self.failed_stage = None
        self.error_code = None
        self.timings = {name: 0.0 for name in STAGES}
        self.counters = {name: 0 for name in COUNTERS}
        self.lock = threading.RLock()
        self.depth = {}

    def record(self, status_code):
        """Return a closed schema; never serialize request or exceptions."""
        with self.lock:
            return {
                "event": "agione_query",
                "request_id": self.request_id,
                "connection_id": self.connection_id,
                "operation": self.operation,
                "data_version": self.data_version,
                "cache_hit": self.cache_hit,
                "cache_unavailable": self.cache_unavailable,
                "status_code": int(status_code),
                "failed_stage": self.failed_stage,
                "safe_error_code": self.error_code,
                **{name + "_ms": round(value, 3)
                   for name, value in self.timings.items()},
                "total_ms": round(
                    (time.perf_counter() - self.started) * 1000, 3
                ),
                **self.counters,
            }

    def emit(self, status_code):
        """Emit one JSON event even for permission and integrity failures."""
        logger.info(json.dumps(self.record(status_code), separators=(",", ":")))


def begin(connection_id=None, request_id=None):
    """Attach request-local telemetry and return the context token."""
    observation = QueryObservation(connection_id, request_id)
    return observation, _current.set(observation)


def end(token):
    """Detach telemetry so reused worker threads never inherit old context."""
    _current.reset(token)


def current():
    return _current.get()


def set_fields(**fields):
    """Accept only non-sensitive, fixed-schema request measurements."""
    observation = current()
    if observation is None:
        return
    with observation.lock:
        for name, value in fields.items():
            if name == "operation":
                observation.operation = value if value in {
                    "dashboard", "trend", "analysis", "customers", "profile",
                    "finance", "schema", "requests", "evidence",
                } else "UNKNOWN"
            elif name == "data_version":
                try:
                    observation.data_version = str(UUID(str(value)))
                except (ValueError, TypeError, AttributeError):
                    observation.data_version = None
            elif name in {"cache_hit", "cache_unavailable"}:
                setattr(observation, name, value is True)


def error(exc, stage_name=None):
    """Preserve the first failed stage without exposing exception text."""
    observation = current()
    if observation is None:
        return
    with observation.lock:
        if observation.failed_stage is None:
            observation.failed_stage = (
                stage_name if stage_name in STAGES else "dispatch"
            )
        observation.error_code = safe_code(getattr(exc, "code", None))


def add_counter(name, amount=1):
    """Count IO, never URLs, headers, tokens or raw source records."""
    observation = current()
    if observation is not None and name in COUNTERS:
        with observation.lock:
            observation.counters[name] += max(0, int(amount))


@contextmanager
def stage(name):
    """Measure nested stages once per name, preserving the inner failure."""
    observation = current()
    if observation is None or name not in STAGES:
        yield
        return
    thread_key = (threading.get_ident(), name)
    started = time.perf_counter()
    with observation.lock:
        depth = observation.depth.get(thread_key, 0)
        observation.depth[thread_key] = depth + 1
    try:
        yield
    except BaseException as exc:
        error(exc, name)
        raise
    finally:
        with observation.lock:
            observation.depth[thread_key] -= 1
            if depth == 0:
                observation.timings[name] += (
                    time.perf_counter() - started
                ) * 1000
            if observation.depth[thread_key] == 0:
                del observation.depth[thread_key]


def measured(name):
    """Instrument a service without changing its callable contract."""
    from functools import wraps

    def decorate(function):
        @wraps(function)
        def invoke(*args, **kwargs):
            with stage(name):
                return function(*args, **kwargs)
        return invoke
    return decorate

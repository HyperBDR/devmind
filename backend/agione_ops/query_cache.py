"""Versioned query projections with fresh ACL and bounded single-flight."""

import copy
import hashlib
import json
import threading
import time
from concurrent.futures import Future
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.exceptions import NotFound

from agione_ops.client import AgioneOpsError
from agione_ops.models import SourceConnection
from agione_ops.observability import set_fields, stage
from agione_ops.permissions import get_connection_for

_flights = {}
_flights_lock = threading.Lock()
_CACHE_SCHEMA = 5


def _json_value(value):
    """Normalize validated query types, never connection configuration."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    raise TypeError("Unsupported query type")


def stable_json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False, default=_json_value,
    )


def _normalize_query(query):
    """Sort only set-valued fields; group/metric ordering is meaningful."""
    value = copy.deepcopy(query)
    if "customer_ids" in value:
        value["customer_ids"] = sorted(set(value["customer_ids"]))
    for filters in (value.get("filters", {}),):
        for name in ("model_ids", "statuses", "failure_types"):
            if name in filters:
                filters[name] = sorted(set(filters[name]))
    payload = value.get("payload", {})
    if "user_ids" in payload:
        payload["user_ids"] = sorted(set(payload["user_ids"]))
    return value


def make_cache_key(identity, query):
    """Expose only a SHA-256 digest of a closed, noncredential namespace."""
    serialized = stable_json({
        "schema": _CACHE_SCHEMA,
        "identity": identity,
        "query": _normalize_query(query),
    })
    return "agione:projection:v1:" + hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def _authorize(connection, user, operation):
    """Fresh account, main grant and independent finance grant on every read."""
    with stage("acl"):
        actor = get_user_model().objects.filter(
            pk=user.pk, is_active=True
        ).first()
        if actor is None:
            raise NotFound("Connection not found.")
        current = get_connection_for(actor, connection.pk, "view_business")
        identity = {
            "connection_id": str(current.pk),
            "config_version": current.config_version,
            "credential_version": current.credential_version,
            "source_kind": current.source_kind,
            "platform": current.platform,
            "principal_kind": current.principal_kind,
            "tenant_id": current.expected_tenant_id,
            "actor_id": str(actor.pk),
        }
        identity["source_id"] = "native:" + str(current.pk)
        if operation == "dashboard" and current.source_kind == "native":
            from agione_ops.native_sync_models import NativePublishedSnapshot

            latest = NativePublishedSnapshot.objects.filter(
                version__connection=current,
                version__run__status="succeeded",
                version__run__config_version=current.config_version,
                version__run__credential_version=current.credential_version,
            ).order_by("-version__published_at").values_list(
                "version_id", flat=True,
            ).first()
            identity["snapshot_catalog"] = str(latest) if latest else None
        if operation in {"dashboard", "finance", "profile"}:
            dependencies = []
            operators = SourceConnection.objects.filter(
                enabled=True, platform=current.platform,
                principal_kind="operator", source_kind=current.source_kind,
            )
            for operator in operators.order_by("pk"):
                try:
                    allowed = get_connection_for(
                        actor, operator.pk, "view_business"
                    )
                except NotFound:
                    continue
                dependency = [
                    str(allowed.pk), allowed.config_version,
                    allowed.credential_version,
                ]
                dependencies.append(dependency)
            identity["finance_acl"] = dependencies
            if current.source_kind == "native" and not getattr(
                settings, "AGIONE_OPS_FINANCE_REFRESH_ON_SYNC", True,
            ):
                from agione_ops.native_finance_refresh import finance_for

                _, identity["finance_version"] = finance_for(current, actor)
        return current, actor, identity


def _cache_get(key):
    try:
        with stage("cache"):
            value = cache.get(key)
        if isinstance(value, dict) and value.get("schema") == _CACHE_SCHEMA:
            return value
    except Exception:
        set_fields(cache_unavailable=True)
    return None


def _release(key, owner):
    """Release Redis locks atomically; never delete another owner's lease."""
    try:
        backend = getattr(cache, "_cache", None)
        if backend is not None and hasattr(backend, "get_client"):
            client = backend.get_client(key, write=True)
            raw_key = cache.make_and_validate_key(key)
            expected = backend._serializer.dumps(owner)
            client.eval(
                "if redis.call('get',KEYS[1]) == ARGV[1] then "
                "return redis.call('del',KEYS[1]) else return 0 end",
                1, raw_key, expected,
            )
        elif cache.get(key) == owner:
            cache.delete(key)
    except Exception:
        set_fields(cache_unavailable=True)


def _shared_compute(key, compute):
    """Coordinate processes with Redis; a failed cache never blocks querying."""
    owner, lock_key = str(uuid4()), key + ":flight"
    locked = False
    deadline = time.monotonic() + 25
    try:
        while not locked:
            try:
                locked = cache.add(lock_key, owner, timeout=120)
            except Exception:
                set_fields(cache_unavailable=True)
                return compute()
            if locked:
                result = _cache_get(key)
                if result is not None:
                    set_fields(cache_hit=True)
                    return result
                break
            result = _cache_get(key)
            if result is not None:
                set_fields(cache_hit=True)
                return result
            if time.monotonic() >= deadline:
                raise AgioneOpsError(
                    "QUERY_IN_PROGRESS", status_code=503, retryable=True
                )
            time.sleep(0.025)
        result = compute()
        try:
            cache.set(
                key, {"schema": _CACHE_SCHEMA, **result},
                timeout=int(getattr(
                    settings, "AGIONE_OPS_QUERY_CACHE_TTL", 6 * 60 * 60
                )),
            )
        except Exception:
            set_fields(cache_unavailable=True)
        return result
    finally:
        if locked:
            _release(lock_key, owner)


def cached_operation(connection, user, query, compute, validate=None):
    """Cache only successful projections, with fresh guards for every caller."""
    operation = query["operation"]
    current, actor, identity = _authorize(connection, user, operation)
    set_fields(operation=operation, data_version=query.get("data_version"))

    computed = False

    def finish(entry, check_signature=True):
        signature = entry.get("signature")
        if validate is not None:
            with stage("snapshot_metadata"):
                signature = validate(
                    current, actor, query,
                    expected=signature if check_signature else None,
                )
        _, _, after = _authorize(connection, user, operation)
        if {k: v for k, v in identity.items() if k != "finance_version"} != {
            k: v for k, v in after.items() if k != "finance_version"
        }:
            raise NotFound("Connection not found.")
        return {"result": entry["result"], "signature": signature}

    def calculate():
        nonlocal computed
        result = compute(current, actor, copy.deepcopy(query))
        if not isinstance(result, dict) or str(result.get("dataVersion")) != str(
            query.get("data_version")
        ):
            raise AgioneOpsError("SNAPSHOT_RESULT_INVALID", status_code=502)
        computed = True
        return finish({"result": result}, check_signature=False)

    if getattr(settings, "AGIONE_OPS_QUERY_CACHE_ENABLED", True) is not True:
        return copy.deepcopy(calculate()["result"])
    key = make_cache_key(identity, query)
    result = _cache_get(key)
    if result is not None:
        try:
            validated = finish(result)
        except AgioneOpsError as error:
            if getattr(error, "code", "") != "SNAPSHOT_CHANGED":
                raise
            try:
                cache.delete(key)
            except Exception:
                set_fields(cache_unavailable=True)
                return copy.deepcopy(calculate()["result"])
        else:
            set_fields(cache_hit=True)
            return copy.deepcopy(validated["result"])
    with _flights_lock:
        future = _flights.get(key)
        leader = future is None
        if leader:
            future = Future()
            _flights[key] = future
    if not leader:
        result = future.result(timeout=28)
        set_fields(cache_hit=True)
        return copy.deepcopy(finish(result)["result"])
    try:
        result = _shared_compute(key, calculate)
        if not computed:
            result = finish(result)
        future.set_result(result)
        return copy.deepcopy(result["result"])
    except BaseException as exc:
        future.set_exception(exc)
        raise
    finally:
        with _flights_lock:
            if _flights.get(key) is future:
                del _flights[key]

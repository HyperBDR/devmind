from __future__ import annotations

from dataclasses import dataclass
import re
import threading
from time import monotonic

from django.db import connection

from .models import MetaModel

META_MODEL_LOOKUP_CACHE_TTL_SECONDS = 30.0


@dataclass
class MetaModelLookupCache:
    """In-process lookup indexes for canonical meta model matching."""

    all_meta: list[MetaModel]
    alias_index: dict[str, MetaModel]
    connection_signature: tuple
    created_at: float
    name_index: dict[str, MetaModel]


_meta_model_cache = threading.local()


def invalidate_meta_model_lookup_cache() -> None:
    """Clear the current thread's cached meta model lookup indexes."""
    if hasattr(_meta_model_cache, "value"):
        delattr(_meta_model_cache, "value")


def register_meta_model_in_lookup_cache(meta_model: MetaModel) -> None:
    """Add or refresh one meta model in the current thread's cache."""
    cached = getattr(_meta_model_cache, "value", None)
    if cached is None:
        return
    if cached.connection_signature[0] != connection.alias:
        return
    if is_meta_model_lookup_cache_expired(cached):
        invalidate_meta_model_lookup_cache()
        return

    for index, cached_meta in enumerate(cached.all_meta):
        if cached_meta.pk == meta_model.pk:
            cached.all_meta[index] = meta_model
            break
    else:
        cached.all_meta.append(meta_model)

    alias_index, name_index = build_meta_model_lookup_indexes(cached.all_meta)
    cached.alias_index.clear()
    cached.alias_index.update(alias_index)
    cached.name_index.clear()
    cached.name_index.update(name_index)


def get_meta_model_lookup_cache() -> MetaModelLookupCache:
    """Return cached meta model lookup indexes for the current thread."""
    connection_signature = current_connection_signature()
    cached = getattr(_meta_model_cache, "value", None)
    if (
        cached is not None
        and is_meta_model_lookup_cache_current(
            cached,
            connection_signature,
        )
    ):
        return cached

    all_meta = list(MetaModel.objects.all())
    alias_index, name_index = build_meta_model_lookup_indexes(all_meta)

    cached = MetaModelLookupCache(
        all_meta=all_meta,
        alias_index=alias_index,
        connection_signature=connection_signature,
        created_at=monotonic(),
        name_index=name_index,
    )
    _meta_model_cache.value = cached
    return cached


def find_meta_model_by_alias_or_name(
    *,
    tokens: list[str],
    name: str,
) -> MetaModel | None:
    """Find a meta model through cached alias and normalized name indexes."""
    if not tokens and not name:
        return None

    cache = get_meta_model_lookup_cache()
    for token in tokens:
        value = str(token or "").strip()
        if not value:
            continue
        hit = cache.alias_index.get(value)
        if hit is not None:
            return hit

    normalized_name = normalize_meta_model_lookup_name(name)
    if not normalized_name:
        return None
    return cache.name_index.get(normalized_name)


def normalize_meta_model_lookup_name(value: str | None) -> str:
    """Normalize a model display name for loose matching."""
    return re.sub(r"[\s_\-]+", "", str(value or "").strip().lower())


def build_meta_model_lookup_indexes(
    all_meta: list[MetaModel],
) -> tuple[dict[str, MetaModel], dict[str, MetaModel]]:
    """Build alias and normalized-name indexes for meta models."""
    alias_index: dict[str, MetaModel] = {}
    name_index: dict[str, MetaModel] = {}
    for meta in all_meta:
        for alias in meta.aliases or []:
            value = str(alias or "").strip()
            if value:
                alias_index[value] = meta

        normalized_name = normalize_meta_model_lookup_name(meta.name)
        if normalized_name and normalized_name not in name_index:
            name_index[normalized_name] = meta
    return alias_index, name_index


def is_meta_model_lookup_cache_current(
    cached: MetaModelLookupCache,
    connection_signature: tuple,
) -> bool:
    """Return whether the cached indexes are still safe to reuse."""
    if cached.connection_signature != connection_signature:
        return False
    return not is_meta_model_lookup_cache_expired(cached)


def is_meta_model_lookup_cache_expired(
    cached: MetaModelLookupCache,
) -> bool:
    """Return whether the cached indexes are older than the TTL."""
    age = monotonic() - cached.created_at
    return age > META_MODEL_LOOKUP_CACHE_TTL_SECONDS


def current_connection_signature() -> tuple:
    """Return a cheap signature for the current database transaction scope."""
    savepoint_ids = tuple(str(value) for value in connection.savepoint_ids)
    return (connection.alias, connection.in_atomic_block, savepoint_ids)

"""Build owner metadata from Feishu person identities."""

from __future__ import annotations


_MULTI_OWNER_SPLITTERS = (",", "、", ";", "；", "/", " / ", "|")


def _split_owner_text(value: str | None) -> list[str]:
    if not value:
        return []
    cleaned = value.replace("\n", ",").replace("\r", "")
    for splitter in _MULTI_OWNER_SPLITTERS:
        cleaned = cleaned.replace(splitter, ",")
    return [item.strip() for item in cleaned.split(",") if item.strip()]


def owner_payload(
    value: str | None,
    identities: list[dict] | None = None,
) -> dict:
    """Return display metadata while using Feishu open IDs as identity."""
    aliases = _split_owner_text(value)
    safe_identities = identities or []
    open_ids = []
    display_names = []
    for identity in safe_identities:
        if not isinstance(identity, dict):
            continue
        open_id = str(identity.get("open_id") or "").strip()
        if open_id and open_id not in open_ids:
            open_ids.append(open_id)
        name = str(
            identity.get("name") or identity.get("en_name") or ""
        ).strip()
        if name and name not in display_names:
            display_names.append(name)
        for key in ("name", "en_name"):
            alias = str(identity.get(key) or "").strip()
            if alias and alias not in aliases:
                aliases.append(alias)
    if not aliases and not open_ids:
        return {}
    if not display_names:
        display_names = aliases.copy()
    return {
        "owner_open_ids": open_ids,
        "owner_canonical": display_names[0] if display_names else None,
        "owner_aliases": aliases,
        "owner_display": "、".join(display_names) or None,
    }


def owner_payload_from_record(record, field_name: str) -> dict:
    """Return owner metadata for one persisted source record field."""
    identities = getattr(record, "owner_identities", {}) or {}
    return owner_payload(
        getattr(record, field_name, ""),
        identities.get(field_name, []),
    )


__all__ = ("owner_payload", "owner_payload_from_record")

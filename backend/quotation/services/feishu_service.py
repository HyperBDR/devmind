from __future__ import annotations

from uuid import uuid4

from quotation.models import DocumentType
from quotation.services.feishu_client import FeishuAPIError


def guess_doc_type(file_name: str, mime_type: str | None) -> str:
    lower = (file_name or "").lower()
    mime = (mime_type or "").lower()
    if lower.endswith(".pdf") or "pdf" in mime:
        return DocumentType.PDF
    return DocumentType.EXCEL


def feishu_file_not_found(exc: FeishuAPIError) -> bool:
    """Best-effort detection for deleted or missing Feishu drive files."""
    if exc.code in {1061004, 1061045, 1061002, 1061021, 970005}:
        return True
    message = str(exc).lower()
    hints = (
        "not found",
        "不存在",
        "已删除",
        "deleted",
        "http 404",
        "record not found",
        "resource is not found",
        "970005",
        "no result",
    )
    return any(hint in message for hint in hints)


def is_folder_drive_item(item: dict) -> bool:
    item_type = str(item.get("type") or "").lower()
    if item_type in {"folder", "drive#folder"}:
        return True
    if item_type == "shortcut":
        target = str(
            (item.get("shortcut_info") or {}).get("target_type") or ""
        ).lower()
        return target in {"folder", "drive#folder"}
    return False


def folder_token_for_item(item: dict) -> str:
    """Resolve the token used to open a folder or folder shortcut."""
    item_type = str(item.get("type") or "").lower()
    if item_type == "shortcut":
        target = (item.get("shortcut_info") or {}).get("target_token")
        if target:
            return str(target)
    return str(item.get("token") or "")


def serialize_drive_file(item: dict) -> dict:
    shortcut = item.get("shortcut_info") or {}
    return {
        "token": item.get("token") or "",
        "name": item.get("name") or "",
        "type": item.get("type") or "",
        "parent_token": item.get("parent_token"),
        "url": item.get("url"),
        "created_time": (
            str(item.get("created_time"))
            if item.get("created_time") is not None
            else None
        ),
        "modified_time": (
            str(item.get("modified_time"))
            if item.get("modified_time") is not None
            else None
        ),
        "shortcut_info": (
            {
                "target_type": shortcut.get("target_type"),
                "target_token": shortcut.get("target_token"),
            }
            if shortcut
            else None
        ),
        "open_token": (
            folder_token_for_item(item)
            if is_folder_drive_item(item)
            else (item.get("token") or "")
        ),
    }


def item_size_bytes(item: dict) -> int | None:
    raw_size = item.get("size") or item.get("size_bytes")
    if raw_size in (None, ""):
        return None
    try:
        return int(raw_size)
    except (TypeError, ValueError):
        return None


def split_file_name(file_name: str) -> tuple[str, str]:
    if "." in file_name and not file_name.startswith("."):
        stem, ext = file_name.rsplit(".", 1)
        return stem, f".{ext}"
    return file_name, ""


def suggest_unique_file_name(file_name: str, existing_names: set[str]) -> str:
    if file_name not in existing_names:
        return file_name
    stem, ext = split_file_name(file_name)
    for index in range(1, 200):
        candidate = f"{stem} ({index}){ext}"
        if candidate not in existing_names:
            return candidate
    return f"{stem}-{uuid4().hex[:8]}{ext}"


def normalize_bookmarks(raw) -> list[dict]:
    bookmarks: list[dict] = []
    seen: set[str] = set()
    if not isinstance(raw, list):
        return bookmarks
    for item in raw:
        if not isinstance(item, dict):
            continue
        token = str(item.get("token") or "").strip()
        name = str(item.get("name") or token).strip() or token
        if not token or token in seen:
            continue
        seen.add(token)
        bookmarks.append({"token": token, "name": name, "type": "folder"})
    return bookmarks


def chunk_file_tokens(tokens: list[str], *, size: int = 50) -> list[list[str]]:
    """Split file tokens into fixed-size chunks for Feishu batch_query."""
    return [
        tokens[index : index + size] for index in range(0, len(tokens), size)
    ]


def classify_batch_query_results(
    metas: list[dict],
    failed_list: list[dict],
    requested_tokens: list[str] | None = None,
) -> tuple[set[str], set[str]]:
    """Return existing and missing tokens from a Feishu batch query."""
    existing_tokens = {
        str(meta.get("doc_token") or "").strip()
        for meta in metas
        if str(meta.get("doc_token") or "").strip()
    }
    missing_tokens: set[str] = set()
    for item in failed_list:
        token = str(item.get("token") or "").strip()
        if not token:
            continue
        error = FeishuAPIError(
            f"meta query failed code={item.get('code')}",
            code=item.get("code"),
            payload=item if isinstance(item, dict) else {},
        )
        if feishu_file_not_found(error):
            missing_tokens.add(token)
        else:
            existing_tokens.add(token)
    for token in requested_tokens or []:
        normalized = str(token or "").strip()
        if normalized and normalized not in existing_tokens:
            missing_tokens.add(normalized)
    return existing_tokens, missing_tokens

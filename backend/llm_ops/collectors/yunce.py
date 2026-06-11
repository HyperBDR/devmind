from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_YUNCE_BASE_URL = "https://llm.guohe-sh.com/admin/api"
MODEL_TYPE_LABELS = {
    "Text": "文本模型",
    "Image": "图片模型",
    "Video": "视频模型",
}


@dataclass(frozen=True)
class NormalizedPriceRow:
    """One normalized price row from Yunce model detail."""

    kind: str
    values: dict[str, Any]
    raw: dict[str, Any]


@dataclass(frozen=True)
class CollectedModelPricing:
    """Normalized pricing payload for one Yunce model."""

    model_source: str
    model_type: str
    source_model_type: str
    name: str
    model_id: str
    platform_id: int | str
    mode: str
    provider: str
    billing_type: str
    billing_unit: str
    currency: str
    unit: int | str | None
    billing_mode: str
    price_rows: list[NormalizedPriceRow]
    raw_price_info: dict[str, Any]
    raw_detail: dict[str, Any]


@dataclass(frozen=True)
class CollectedPricingCatalog:
    """Complete Yunce pricing catalog."""

    source_url: str
    total_models: int
    models: list[CollectedModelPricing]


class YuncePricingClient:
    """Client for Yunce token forwarding model pricing APIs."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_YUNCE_BASE_URL,
        timeout: int = 30,
        page_size: int = 100,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.page_size = page_size
        self.session = requests.Session()

    def login(self, *, username: str, password: str) -> str:
        """Log in and return an access token."""
        payload = self._request(
            "/users/login/",
            method="POST",
            json={"username": username, "password": password},
        )
        token = payload.get("access")
        if not token:
            raise ValueError(
                "Yunce login response did not include access token."
            )
        return str(token)

    def fetch_model_list(self, *, token: str) -> list[dict[str, Any]]:
        """Fetch all Yunce model list pages."""
        first_page = self._request(
            f"/llm_platform/llm_model_info/?page=1&size={self.page_size}",
            token=token,
        )
        total = first_page.get("total") or len(first_page.get("list") or [])
        pages = max(1, (int(total) + self.page_size - 1) // self.page_size)
        rows = list(first_page.get("list") or [])

        for page in range(2, pages + 1):
            data = self._request(
                (
                    "/llm_platform/llm_model_info/"
                    f"?page={page}&size={self.page_size}"
                ),
                token=token,
            )
            rows.extend(data.get("list") or [])

        return rows

    def fetch_model_detail(
        self,
        *,
        token: str,
        platform_id: int | str,
    ) -> dict[str, Any]:
        """Fetch one Yunce model detail payload."""
        return self._request(
            f"/llm_platform/llm_model_info/{platform_id}",
            token=token,
            timeout=self.timeout + 15,
        )

    def collect_catalog(
        self,
        *,
        username: str,
        password: str,
    ) -> CollectedPricingCatalog:
        """Login, fetch all model details, and normalize pricing."""
        token = self.login(username=username, password=password)
        rows = self.fetch_model_list(token=token)
        models = [
            self.normalize_model_detail(
                self.fetch_model_detail(token=token, platform_id=row["id"])
            )
            for row in rows
            if row.get("id") is not None
        ]
        models.sort(
            key=lambda item: (
                item.model_type,
                item.model_source,
                item.name,
            )
        )
        return CollectedPricingCatalog(
            source_url=self.base_url.replace("/admin/api", "/"),
            total_models=len(models),
            models=models,
        )

    def normalize_model_detail(
        self,
        detail: dict[str, Any],
    ) -> CollectedModelPricing:
        """Normalize one Yunce model detail response."""
        price_content = detail.get("price_content") or {}
        price_info = price_content.get("price_info") or {}
        model_info = detail.get("model_info") or {}
        source_model_type = price_content.get("type") or ""

        return CollectedModelPricing(
            model_source=(
                model_info.get("provider")
                or price_content.get("provider")
                or ""
            ),
            model_type=MODEL_TYPE_LABELS.get(
                source_model_type,
                source_model_type,
            ),
            source_model_type=source_model_type,
            name=detail.get("model_name") or "",
            model_id=(
                model_info.get("model_id")
                or price_content.get("name")
                or detail.get("model_name")
                or ""
            ),
            platform_id=detail.get("id") or "",
            mode=price_content.get("mode") or "",
            provider=price_content.get("provider") or "",
            billing_type=(
                price_info.get("unit_info")
                or price_info.get("billing_mode")
                or price_info.get("mode")
                or "按量计费"
            ),
            billing_unit=price_info.get("currency") or "-",
            currency=price_info.get("currency") or "",
            unit=price_info.get("unit"),
            billing_mode=(
                price_info.get("billing_mode")
                or price_info.get("mode")
                or ""
            ),
            price_rows=normalize_price_rows(price_content),
            raw_price_info=price_info,
            raw_detail=detail,
        )

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        token: str = "",
        timeout: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers.update(kwargs.pop("headers", {}) or {})

        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            timeout=timeout or self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200:
            message = payload.get("message") or payload.get("msg")
            raise ValueError(f"Yunce request failed: {message or path}")
        data = payload.get("data")
        return data if isinstance(data, dict) else {"list": data or []}


def scalar(value):
    """Normalize empty API values to None."""
    if value in (None, ""):
        return None
    return value


def token_range(start, end, fallback=None) -> str:
    """Format token range fields from Yunce tiered pricing."""
    if start is not None and end is not None:
        if start == 0 and end == 0:
            return "-"
        return f"{start}-{end}"
    if fallback is not None:
        return str(fallback)
    return "不限"


def first_present(*values):
    """Return the first value that is not None."""
    for value in values:
        if value is not None:
            return value
    return None


def is_tiered(value) -> bool:
    """Return whether Yunce marks this pricing block as tiered."""
    return value is True or value == "true"


def normalize_price_rows(
    price_content: dict[str, Any],
) -> list[NormalizedPriceRow]:
    """Normalize Yunce Text/Image/Video price rows."""
    price_info = price_content.get("price_info") or {}
    model_type = price_content.get("type")
    if model_type == "Image":
        return normalize_image_price_rows(price_info)
    if model_type == "Video":
        return normalize_video_price_rows(price_info)
    return normalize_text_price_rows(price_content, price_info)


def normalize_image_price_rows(
    price_info: dict[str, Any],
) -> list[NormalizedPriceRow]:
    """Normalize Yunce image pricing structures."""
    by_count = price_info.get("pricing_detail_by_count")
    if isinstance(by_count, list) and by_count:
        return [
            NormalizedPriceRow(
                kind="image_size",
                values={
                    "image_size": scalar(row.get("image_size")),
                    "unit_price": scalar(row.get("unit_price")),
                },
                raw=row,
            )
            for row in by_count
        ]

    by_token = price_info.get("pricing_detail_by_token")
    if isinstance(by_token, list) and by_token:
        return [
            NormalizedPriceRow(
                kind="image_token",
                values={
                    "input_price": scalar(
                        (row.get("input_price") or {}).get("non_cache")
                        or (row.get("input_price") or {}).get("hit_cache")
                    ),
                    "image_input_price": scalar(
                        (row.get("image_input_price") or {}).get("non_cache")
                        or (row.get("image_input_price") or {}).get(
                            "hit_cache"
                        )
                    ),
                    "output_price": scalar(
                        (row.get("output_price") or {}).get("non_thinking")
                        or (row.get("output_price") or {}).get("non_think")
                    ),
                    "image_output_price": scalar(
                        (row.get("image_output_price") or {}).get(
                            "non_thinking"
                        )
                        or (row.get("image_output_price") or {}).get(
                            "non_think"
                        )
                    ),
                },
                raw=row,
            )
            for row in by_token
        ]

    if price_info.get("unit_price") is not None:
        return [
            NormalizedPriceRow(
                kind="image_unit",
                values={"price": price_info.get("unit_price")},
                raw=price_info,
            )
        ]
    return []


def normalize_video_price_rows(
    price_info: dict[str, Any],
) -> list[NormalizedPriceRow]:
    """Normalize Yunce video pricing structures."""
    video_price = price_info.get("video_price")
    if not isinstance(video_price, list) or not video_price:
        return []

    if price_info.get("condition_video") is True:
        online = next(
            (row for row in video_price if row.get("mode") == "online"),
            None,
        )
        resolution_list = online.get("resolution_list") if online else None
        if isinstance(resolution_list, list) and resolution_list:
            return [
                NormalizedPriceRow(
                    kind="video_resolution_input",
                    values={
                        "resolution": scalar(row.get("resolution")),
                        "contains_video_price": scalar(
                            row.get("contains_video_price")
                        ),
                        "no_video_price": scalar(row.get("no_video_price")),
                    },
                    raw=row,
                )
                for row in resolution_list
            ]

    if any(row.get("mode") in ("online", "offline") for row in video_price):
        return [
            NormalizedPriceRow(
                kind="video_inference",
                values={
                    "inference_type": (
                        "在线推理"
                        if row.get("mode") == "online"
                        else "离线推理"
                        if row.get("mode") == "offline"
                        else scalar(row.get("mode"))
                    ),
                    "audible_price": scalar(
                        row.get("audible_price")
                        or row.get("contains_video_price")
                    ),
                    "silent_price": scalar(
                        row.get("silent_price") or row.get("no_video_price")
                    ),
                },
                raw=row,
            )
            for row in video_price
        ]

    if any(row.get("resolution") for row in video_price):
        return [
            NormalizedPriceRow(
                kind="video_resolution_output",
                values={
                    "resolution": scalar(row.get("resolution")),
                    "price": scalar(row.get("unit_price")),
                    "no_audio_price": scalar(row.get("no_audio_unit_price")),
                },
                raw=row,
            )
            for row in video_price
        ]

    first = video_price[0]
    if first.get("unit_price") is not None:
        return [
            NormalizedPriceRow(
                kind="video_unit",
                values={"price": first.get("unit_price")},
                raw=first,
            )
        ]
    return []


def normalize_text_price_rows(
    price_content: dict[str, Any],
    price_info: dict[str, Any],
) -> list[NormalizedPriceRow]:
    """Normalize Yunce text/token pricing structures."""
    rows = price_info.get("pricing_detail")
    tiered = is_tiered(price_info.get("tiered_pricing"))
    thinking = price_content.get("mode") == "thinking"

    if isinstance(rows, list) and rows:
        return [
            NormalizedPriceRow(
                kind="text_token",
                values={
                    "input_token_range": (
                        token_range(
                            first_present(
                                row.get("input_start"),
                                row.get("inputStart"),
                            ),
                            first_present(
                                row.get("input_end"),
                                row.get("inputEnd"),
                            ),
                            price_info.get("unit"),
                        )
                        if tiered
                        else str(price_info.get("unit"))
                        if price_info.get("unit") is not None
                        else "不限"
                    ),
                    "output_token_range": (
                        "-"
                        if thinking
                        else token_range(
                            first_present(
                                row.get("output_start"),
                                row.get("outputStart"),
                            ),
                            first_present(
                                row.get("output_end"),
                                row.get("outputEnd"),
                            ),
                        )
                        if tiered
                        else "不限"
                    ),
                    "input_price": scalar(
                        (row.get("input_price") or {}).get("non_cache")
                        or (row.get("input_price") or {}).get("non_think")
                        or (row.get("input_price") or {}).get("hit_cache")
                        or (row.get("input_price") or {}).get("think")
                    ),
                    "cache_input_price": scalar(
                        (row.get("input_price") or {}).get("hit_cache")
                    ),
                    "output_price": (
                        None
                        if thinking
                        else scalar(
                            (row.get("output_price") or {}).get(
                                "non_thinking"
                            )
                            or (row.get("output_price") or {}).get(
                                "non_think"
                            )
                        )
                    ),
                    "output_thinking_price": (
                        scalar(
                            (row.get("output_price") or {}).get("thinking")
                            or (row.get("output_price") or {}).get("think")
                        )
                        if thinking
                        else None
                    ),
                    "output_non_thinking_price": (
                        scalar(
                            (row.get("output_price") or {}).get(
                                "non_thinking"
                            )
                            or (row.get("output_price") or {}).get(
                                "non_think"
                            )
                        )
                        if thinking
                        else None
                    ),
                },
                raw=row,
            )
            for row in rows
        ]

    if price_info.get("unit_price") is not None or price_info.get("currency"):
        thinking_mode = price_info.get("mode") == "thinking"
        return [
            NormalizedPriceRow(
                kind="text_unit",
                values={
                    "input_token_range": (
                        str(price_info.get("unit"))
                        if price_info.get("unit") is not None
                        else "不限"
                    ),
                    "output_token_range": "不限",
                    "input_price": (
                        None
                        if thinking_mode
                        else scalar(price_info.get("unit_price"))
                    ),
                    "output_price": (
                        None
                        if thinking_mode
                        else scalar(price_info.get("unit_price"))
                    ),
                    "output_thinking_price": (
                        scalar(price_info.get("unit_price"))
                        if thinking_mode
                        else None
                    ),
                    "output_non_thinking_price": (
                        scalar(price_info.get("unit_price"))
                        if thinking_mode
                        else None
                    ),
                },
                raw=price_info,
            )
        ]

    return []

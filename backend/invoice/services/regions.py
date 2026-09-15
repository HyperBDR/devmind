"""Derive a reporting region from a customer's address."""

from __future__ import annotations

import re


_COUNTRY_PATTERNS = (
    ("Hong Kong", (r"\bhong\s+kong\b", r"\bHKG\b", "香港")),
    ("Mexico", (r"\bm[eé]xico\b", r"\bCDMX\b", "墨西哥")),
    ("United States", (r"\bunited\s+states\b", r"\bUSA\b", r"\bUS\b")),
    ("United Kingdom", (r"\bunited\s+kingdom\b", r"\bUK\b", r"\bGB\b")),
    ("South Korea", (r"\bsouth\s+korea\b", r"\bKorea,? Republic\b", "韩国")),
    ("Saudi Arabia", (r"\bsaudi\s+arabia\b", "沙特")),
    ("South Africa", (r"\bsouth\s+africa\b", "南非")),
    ("United Arab Emirates", (r"\bunited\s+arab\s+emirates\b", r"\bUAE\b", "阿联酋")),
    ("Malaysia", (r"\bmalaysia\b", "马来西亚")),
    ("Singapore", (r"\bsingapore\b", "新加坡")),
    ("Indonesia", (r"\bindonesia\b", "印度尼西亚")),
    ("Thailand", (r"\bthailand\b", "泰国")),
    ("Vietnam", (r"\bvietnam\b", "越南")),
    ("Philippines", (r"\bphilippines\b", "菲律宾")),
    ("China", (r"\bchina\b", r"\bPRC\b", "中国")),
    ("Taiwan", (r"\btaiwan\b", "台湾")),
    ("Japan", (r"\bjapan\b", "日本")),
    ("India", (r"\bindia\b", "印度")),
    ("Australia", (r"\baustralia\b", "澳大利亚")),
    ("New Zealand", (r"\bnew\s+zealand\b", "新西兰")),
    ("Canada", (r"\bcanada\b", "加拿大")),
    ("Germany", (r"\bgermany\b", "德国")),
    ("France", (r"\bfrance\b", "法国")),
    ("Netherlands", (r"\bnetherlands\b", "荷兰")),
    ("Brazil", (r"\bbrazil\b", "巴西")),
    ("Mexico", (r"\bmexico\b", "墨西哥")),
)

_CITY_PATTERNS = (
    (
        "Malaysia",
        (
            r"\bkuala\s+lumpur\b",
            r"\bselangor\b",
            r"\bpenang\b",
            r"\bjohor\b",
            "吉隆坡",
            "雪兰莪",
            "槟城",
        ),
    ),
    ("Singapore", (r"\bsingapore\b", "新加坡")),
    ("Indonesia", (r"\bjakarta\b", r"\bbali\b", r"\bsurabaya\b")),
    ("Thailand", (r"\bbangkok\b", r"\bphuket\b")),
    ("Vietnam", (r"\bho\s+chi\s+minh\b", r"\bhanoi\b")),
    ("Philippines", (r"\bmanila\b", r"\bcebu\b", r"\bmakati\b")),
    (
        "China",
        (
            r"\bshanghai\b",
            r"\bbeijing\b",
            r"\bshenzhen\b",
            r"\bguangzhou\b",
            "上海",
            "北京",
            "深圳",
            "广州",
        ),
    ),
    ("Japan", (r"\btokyo\b", r"\bosaka\b")),
    ("South Korea", (r"\bseoul\b", r"\bbusan\b")),
    ("India", (r"\bmumbai\b", r"\bdelhi\b", r"\bbangalore\b")),
    ("Australia", (r"\bsydney\b", r"\bmelbourne\b")),
    ("United Kingdom", (r"\blondon\b", r"\bmanchester\b")),
    (
        "United States",
        (r"\bnew\s+york\b", r"\blos\s+angeles\b", r"\bsan\s+francisco\b"),
    ),
    (
        "Hong Kong",
        (
            r"\bnathan\s+road\b",
            r"\bcheung\s+sha\s+wan\b",
            r"\bTST\b",
            r"\bkowloon\b",
        ),
    ),
    ("Saudi Arabia", (r"\bKSA\b", r"\bjeddah\b", r"\briyadh\b")),
    (
        "South Africa",
        (r"sandton", r"morningside", r"\bjohannesburg\b"),
    ),
)

_ADDRESS_MARKER_PATTERNS = (
    ("Malaysia", (r"\bsdn\.?\s+bhd\.?\b", r"\bberhad\b")),
    ("Indonesia", (r"\bpt\.?\s+[A-Z][\w.-]*", r"\btbk\.?\b")),
    ("Thailand", (r"ประเทศไทย", r"\bประเทศไทย\b")),
    ("Vietnam", (r"\bquận\b", r"\bphường\b", r"\bthành phố\b")),
)


def derive_customer_region(address: str | None) -> str:
    """Return a canonical country or territory parsed from an address."""
    normalized = re.sub(r"\s+", " ", str(address or "")).strip()
    if not normalized:
        return ""
    for region, patterns in _COUNTRY_PATTERNS:
        if any(
            re.search(pattern, normalized, re.IGNORECASE)
            for pattern in patterns
        ):
            return region
    for region, patterns in _CITY_PATTERNS:
        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns):
            return region
    for region, patterns in _ADDRESS_MARKER_PATTERNS:
        if any(
            re.search(pattern, normalized, re.IGNORECASE)
            for pattern in patterns
        ):
            return region
    return ""

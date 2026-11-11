"""Normalize quotation line-item description text."""

from __future__ import annotations

import re

DESCRIPTION_LABEL_PATTERN = re.compile(
    r"^\s*(?:license\s+type|description)\s*[:：]\s*",
    re.IGNORECASE,
)


def strip_description_label(value: str | None) -> str | None:
    """Drop a leading price-list label such as ``License Type:``.

    The legacy price sheet prefixed every line with a field label that
    must not reach customer-facing quotations. Text that is only a label
    is returned unchanged so nothing is silently blanked.
    """
    if not value:
        return value
    stripped = DESCRIPTION_LABEL_PATTERN.sub("", value, count=1)
    return stripped if stripped.strip() else value

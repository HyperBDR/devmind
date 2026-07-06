from __future__ import annotations

from llm_ops.collectors.official import OFFICIAL_PROVIDER_CONFIGS
from llm_ops.price_collectors import registered_vendor_price_collector_codes

SUPPORTED_OFFICIAL_PROVIDER_CODES = tuple(
    code
    for code in registered_vendor_price_collector_codes()
    if code in OFFICIAL_PROVIDER_CONFIGS
)

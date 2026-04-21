---
name: pricing-vendor-agent
description: Discover a vendor's pricing resources from only the vendor context, then extract the vendor's priced AI model catalog. Use when the caller provides a vendor name and optional pricing page hint, and the agent must decide which pages, JS bundles, JSON endpoints, or other assets to inspect.
---

# Pricing Vendor Agent

Read the vendor context first.

## Workflow

1. Call the vendor-context tool to learn the vendor name, slug, pricing URL, and any configured hints.
2. Call the vendor-specific Python skill tool first. It loads `scripts/vendor_pricing_<vendor_slug>.py` and returns a standard JSON structure.
3. If the Python skill result is incomplete, choose a promising starting URL. The configured pricing URL is only a hint, not a constraint.
4. Fetch candidate resources and inspect them incrementally.
5. Follow the evidence. If the pricing page is JS-rendered, inspect the page assets or referenced endpoints.
6. Return a structured priced-model catalog only when the evidence supports it.

## Rules

- Prefer primary vendor-owned sources over third-party mirrors.
- Prefer the vendor-specific deterministic Python skill result when it already provides sufficient evidence.
- Prefer current standard pricing over promotions, batch pricing, cached pricing, or historical pricing.
- Normalize prices to the vendor currency per 1M tokens.
- Keep model names concise and canonical.
- If you cannot substantiate a model price from the fetched resources, omit it.
- Keep `notes` short and factual.

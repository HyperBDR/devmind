# ADR-002: Bind resale approval and publication to price revisions

- Status: Accepted
- Date: 2026-08-04
- Related issues: #193, #194, #228, #232

## Context

The legacy resale workflow stores scalar retail prices directly on a listing.
It cannot prove which complete tier schedule, procurement costs, exchange rate,
fees, or policy result an operator approved and later published.

## Decision

The resale price revision is the immutable boundary for pricing decisions.

- A price draft is saved as one atomic, validated schedule.
- Submitting a revision stores a decision snapshot containing the retail and
  cost schedules, cost lineage and freshness, exchange-rate evidence, platform
  fees, interval profitability, and the server-side approval result.
- The snapshot receives a stable fingerprint and becomes immutable when the
  revision leaves `draft`.
- Automatic approval evaluates every aligned interval. A revision is eligible
  only when no interval is below `yield_warning` and every interval stays
  within `auto_approve_max_margin_rate`.
- Manual approval records the approver and timestamp on that exact revision.
- `confirm_publish` and `confirm_update` bind the listing's published pointer
  and audit log to the approved revision ID.
- Editing after submission or approval creates a new draft version. Approval
  evidence on the previous revision does not carry over.

The scalar fields on `ResaleListing` remain as a usage-zero compatibility
projection during migration. They are not approval evidence.

## API contract

- `PUT /resale-listings/{id}/price-draft/`
- `POST /resale-listings/{id}/price-preview/`
- `POST /resale-listings/{id}/submit-price-revision/`
- `GET /resale-listings/{id}/price-revisions/`

Errors use stable `resale_price.*` or `price_table_*` codes. Optimistic draft
conflicts return HTTP 409; invalid policy or state transitions return HTTP 400.

## Consequences

- Historical approval can be reconstructed without current upstream prices.
- A fixed procurement channel is currently required for tier preview. The
  automatic best-channel envelope remains a separate routing concern.
- Procurement evidence older than 30 days is previewable but cannot be
  submitted.
- Existing scalar CRUD and legacy workflow transitions remain compatible, but
  only revision-aware submissions provide immutable approval evidence.

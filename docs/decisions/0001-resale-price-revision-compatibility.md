# ADR-0001: Introduce resale price revisions behind flat compatibility

## Status

Accepted

## Date

2026-08-04

## Context

`ResaleListing` and `ResaleListingPriceHistory` store one value for each
retail price dimension. That representation cannot atomically store a tiered
price table or bind approval and publishing to an immutable price version.
Existing frontend and API consumers still read and write the three flat
`retail_*` text-price fields, so replacing those fields in one deployment
would break the current workbench.

## Decision

- `ResaleListingPriceRevision` is the approval and publishing identity for a
  complete price table. A listing has explicit read-only references to its
  current approved revision and pending draft or submitted revision.
- `ResaleListingPriceItem` stores `text_input`, `text_output`, and
  `cache_input` through one normalized structure. All items for a revision
  are created in the same database transaction.
- Draft revisions may be edited or replaced. Submitted, approved, and
  superseded revisions and their items are immutable through the model API.
- Existing listing endpoints continue accepting the flat fields. Their write
  paths dual-write normalized flat items and the revision pointer within the
  surrounding transaction. Editing a submitted price creates a new version
  and leaves the listing in an approval-required workflow state.
- Existing flat fields remain the compatibility read projection during this
  phase. `ResaleListingPriceHistory` remains a read-only compatibility API;
  it is not used as approval evidence.
- The data migration creates a pending version 1 for unpublished draft and
  pending-publish listings, and an approved current version 1 for stable
  published, offline, or deleted listings. Existing `update_draft` and
  `pending_update` listings receive both approved current version 1 and
  draft or submitted pending version 2. The legacy schema cannot distinguish
  the already-published price from its pending edit, so both backfilled
  revisions intentionally use the same flat compatibility projection. Legacy
  prices, currency fields, publish status, workflow status, and active state
  are not changed.

## Alternatives considered

### Replace flat fields immediately

Rejected because the frontend tier editor and revision API are tracked by
later issues. Removing the flat contract now would require an unsafe
coordinated deployment.

### Extend `ResaleListingPriceHistory` with child items

Rejected because history rows mix price changes with active-state changes and
do not model draft, submission, approval, or supersession explicitly.

## Consequences

- The compatibility period has intentional dual storage. All application
  writes must use the existing listing endpoints or the revision service;
  direct bulk database updates to flat prices bypass synchronization.
- Revision-native reads and writes can be added without another schema
  redesign. The legacy fields and history API can be removed only after those
  endpoints and all consumers have migrated.
- Rolling this migration back drops only derived revision data. The original
  flat fields and their business state remain available unchanged.

## References

- GitHub Issue #230
- Dependency #229 for shared tier validation semantics
- Follow-up #233 for revision-native APIs and approval/publish snapshots

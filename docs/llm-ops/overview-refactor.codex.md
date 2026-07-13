# LLM Ops Overview Refactor — Codex Brief

## Status: Aligned with repo reality (post-clarification)

This brief supersedes earlier drafts. It reflects the current
`ResalePlatform` schema (already has `fee_rate`, `service_fee_rate`)
and the operator decision that all newly added fee/yield fields are
nullable with no global fallback.

## Objective

Refactor the LLM Ops Monitor overview page into a single
"模型挂售决策表" worktable. Remove duplicate status views, drop the
drawer on the overview page, and route row clicks to the Resale
Publishing Workspace.

## Root Cause

The overview page is organized by data objects (KPI, provider
matrix, channel coverage, focus table, channel matrix, risk board)
instead of by operator decisions. Status, action and margin are
recomputed in multiple components with inconsistent ordering and no
recommended action. Margin thresholds are global (10%) instead of
per-platform fee configuration.

## Scope

- `backend/llm_ops/models.py` — `ResalePlatform` field additions
- `backend/llm_ops/migrations/0007_resaleplatform_fee_config.py` — new migration
- `backend/llm_ops/services.py` — `compute_model_decision` helper
- `backend/llm_ops/views.py` — `SummaryAPIView` canonical output
- `backend/llm_ops/tests/test_views.py` — decision field assertions
- `frontend/src/composables/useLLMOpsMonitor.js` — decision row factory
- `frontend/src/components/llm-ops/LLMOpsMonitorDashboard.vue` — collapsed page
- `frontend/src/pages/LLMOps.vue` — remove overview drawer reference
- `frontend/src/locales/zh-CN.json`, `frontend/src/locales/en.json` — i18n

Out of scope: changes to legacy management commands, new routes,
new engine or registry layer.

## Required Architecture / Logic

### 1. ResalePlatform schema addition

Add four DecimalFields, all `null=True, blank=True, default=None`,
matching `fee_rate` precision (`max_digits=8, decimal_places=4`):

- `tax_rate`
- `settlement_rate`
- `yield_warning`
- `yield_target`

`fee_rate` and `service_fee_rate` already exist; do not duplicate.

### 2. SummaryAPIView canonical output

For each model row emit:

- `recommended_channel` — `{channel_id, channel_name, currency, input_price_per_million, output_price_per_million, cache_input_price_per_million, estimated_cost}`
- `current_listing` — `{channel_id, channel_name, currency, retail_input_price_per_million, retail_output_price_per_million, retail_cache_input_price_per_million, is_listed}`
- `yield_metrics` — `{fee_rate, service_fee_rate, tax_rate, settlement_rate, yield_warning, yield_target, input_yield, output_yield, is_resolved}`
- `decision_status` (enum, see priority list)
- `decision_action` (string, see mapping)
- `last_data_event_at` (datetime)
- `data_event_type` (enum: `updated` | `collection_failed` | `source_disabled` | `reconciliation_anomaly` | `stale`)

### 3. Yield calculation

Per-platform, no global fallback. Implementation rule:

- If any of `fee_rate`, `service_fee_rate`, `tax_rate`, `settlement_rate`, `yield_warning` is null on the selected `ResalePlatform`, set `yield_metrics.is_resolved = false`, `input_yield = null`, `output_yield = null`, and `decision_status = platform_fee_unresolved`.
- When resolved, compute net yield per dimension:
  `net_yield = (retail * (1 - fee_rate - service_fee_rate - tax_rate) - cost * settlement_rate) / retail`
  `cost` here uses `recommended_channel.cost` or, when `current_listing.is_listed` is true, the actual listing channel cost.
- `low_yield` fires when `input_yield < yield_warning` or `output_yield < yield_warning`.

### 4. Decision status priority (highest to lowest)

1. `no_supply` — best_channel missing
2. `currency_unresolved` — best_channel present but display currency conversion failed
3. `platform_fee_unresolved` — `yield_metrics.is_resolved = false`
4. `low_yield` — listed and yield below warning
5. `not_lowest_channel` — listed but listing.channel_id != best_channel.channel_id
6. `unlisted` — best_channel present and not listed
7. `single_channel` — options.length == 1
8. `ready` — all checks pass

### 5. decision_action mapping

| status | action text (zh-CN) |
|---|---|
| `no_supply` | 去渠道配置 |
| `currency_unresolved` | 补汇率 |
| `platform_fee_unresolved` | 配置平台费用规则 |
| `low_yield` | 复核售价或切换渠道 |
| `not_lowest_channel` | 评估切换到最低渠道 |
| `unlisted` | 去挂售 |
| `single_channel` | 增加备选渠道 |
| `ready` | 保持 |

### 6. Sort order

1. decision_status priority asc
2. |input_yield| desc (lowest yield first; null treated as 0)
3. last_data_event_at asc (oldest first)
4. provider_name asc

### 7. KPI strip collapse to 4 cards

- `pending_listing` — count of `decision_status == unlisted`
- `missing_channel` — count of `decision_status == no_supply`
- `low_yield` — count of `decision_status == low_yield`
- `data_anomaly` — count where `data_event_type in {collection_failed, source_disabled, reconciliation_anomaly, stale}`

Remove cards for: total channels, total models, providers, active listings, channel coverage rate, ready_models percentage.

### 8. Overview page composition (LLMOpsMonitorDashboard.vue)

- Top: four KPI cards in one row.
- Body: decision table only.
- Removed from this page: provider matrix, channel coverage module, listing risk board, collection health panel, any drawer/modal trigger.

### 9. Row click navigation

- Row binds to `model_id`.
- Click navigates to `ResalePublishingWorkspace` scoped to that model.
- Workspace decides edit vs create mode based on `current_listing.is_listed`.
- `ResalePublishingDrawer` reference is removed from overview page only. Other call sites may keep it.

### 10. Locale keys (zh-CN + en)

- `decision.status.<status>` for all 8 statuses
- `decision.action.<key>` for all 8 actions
- `overview.kpi.{pendingListing,missingChannel,lowYield,dataAnomaly}.{label,hint}`
- `overview.table.columns.{model,provider,coverage,recommended,recommendedPrice,currentListing,currentPrice,inputYield,outputYield,status,action,lastUpdate,dataEventType}`

### 11. Data anomaly rule

- `data_event_type = updated` — never counted into data_anomaly
- `collection_failed` — count when latest CollectionRun for the price source feeding the model has status in {failed}
- `source_disabled` — count when PriceCollectionSource for the best_channel has is_enabled = false
- `reconciliation_anomaly` — count when UsageReconciliationRecord exists for this channel+model with status != STATUS_PERFECT
- `stale` — reserved for future source-level cadence support. Do not
  infer stale from a global fixed threshold; without a source cadence,
  avoid emitting this event to prevent false data anomaly KPI counts.

## Acceptance Tests

1. Overview page renders only KPI strip (4 cards) and decision table.
2. Each decision row contains all canonical fields.
3. no_supply rows appear first.
4. platform_fee_unresolved rows appear before low_yield.
5. low_yield rows appear after platform_fee_unresolved but before not_lowest_channel.
6. data_event_type=updated does NOT increase data_anomaly.
7. data_event_type in {collection_failed, source_disabled, reconciliation_anomaly} increases data_anomaly; stale is reserved until source cadence is modeled.
8. Clicking a decision row opens ResalePublishingWorkspace for that model; no drawer opens on overview.
9. i18n keys present in both locales.
10. SummaryAPIView returns canonical decision fields; backend test asserts presence.

## Attempt Rule

max 3 attempts per failure mode. Stop and report on fourth root cause.

## Completion Rule

- All acceptance tests pass.
- No duplicate riskRows/lowMarginRows computation in frontend.
- Overview page no longer references ResalePublishingDrawer.
- Decision status logic exists in one helper: `llm_ops.services.compute_model_decision`.
- i18n keys present in both locales.

## Boundary

- Do not modify ResalePlatform fields beyond the four additions.
- Do not introduce a new engine or registry.
- Do not modify legacy management commands.
- Do not change non-overview LLM Ops pages except ResalePublishingWorkspace (only to accept incoming model_id scope).

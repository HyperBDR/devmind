import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  isMonitorRowVisible,
  operationScopeForRow,
  summarizeMonitorRows
} from '../src/utils/llmOpsMonitor.js'

const monitorDashboardSource = readFileSync(
  new URL(
    '../src/components/llm-ops/LLMOpsMonitorDashboard.vue',
    import.meta.url
  ),
  'utf8'
)

const rows = [
  {
    model_id: 1,
    operation_scope: 'market_reference',
    decision_status: 'market_reference',
    decision_priority: 9
  },
  {
    model_id: 2,
    operation_scope: 'operational',
    decision_status: 'no_supply',
    decision_priority: 1
  },
  {
    model_id: 3,
    operation_scope: 'operational',
    decision_status: 'ready',
    decision_priority: 8
  },
  {
    model_id: 4,
    operation_scope: 'operational',
    decision_status: 'ready',
    decision_priority: 8,
    is_data_anomaly: true
  }
]

test('keeps market references out of the operational priority queue', () => {
  assert.deepEqual(
    rows.filter((row) => isMonitorRowVisible(row, 'priority')),
    [rows[1]]
  )
  assert.deepEqual(
    rows.filter((row) => isMonitorRowVisible(row, 'operational')),
    [rows[1], rows[2], rows[3]]
  )
  assert.deepEqual(
    rows.filter((row) => isMonitorRowVisible(row, 'market_reference')),
    [rows[0]]
  )
})

test('keeps data-health anomalies out of the resale decision queue', () => {
  assert.deepEqual(
    rows.filter((row) => isMonitorRowVisible(row, 'priority')),
    [rows[1]]
  )
  assert.deepEqual(
    rows.filter((row) => isMonitorRowVisible(row, 'all')),
    [rows[1], rows[2], rows[3]]
  )
})

test('calculates action KPIs from operational models only', () => {
  assert.deepEqual(summarizeMonitorRows(rows), {
    lowYield: 0,
    missingChannel: 1,
    needsAction: 1,
    operational: 3,
    pendingListing: 0,
    ready: 2
  })
})

test('infers scope for responses created before the scope contract', () => {
  assert.equal(operationScopeForRow({ coverage_count: 0 }), 'market_reference')
  assert.equal(operationScopeForRow({ coverage_count: 1 }), 'operational')
  assert.equal(
    operationScopeForRow({ current_listing: { is_listed: true } }),
    'operational'
  )
})

test('labels market references without implying a missing listing', () => {
  assert.match(
    monitorDashboardSource,
    /function currentListingText\(row\) \{\s*if \(!isOperationalRow\(row\)\) \{\s*return t\('llmOps\.decision\.status\.market_reference'\)/
  )
})

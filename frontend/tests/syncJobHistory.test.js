import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const syncJobHistory = readFileSync(
  new URL('../src/components/data-ops/SyncJobHistory.vue', import.meta.url),
  'utf8'
)
const syncSection = readFileSync(
  new URL('../src/components/data-ops/SyncSection.vue', import.meta.url),
  'utf8'
)

test('renders compact expandable sync records with change counts', () => {
  assert.match(syncSection, /<SyncJobHistory/)
  assert.doesNotMatch(syncSection, /<Panel title="同步任务">/)
  assert.match(syncJobHistory, /<details/)
  assert.match(syncJobHistory, /<summary/)
  assert.match(syncJobHistory, /dataOps\.sync\.records\.created/)
  assert.match(syncJobHistory, /dataOps\.sync\.records\.updated/)
  assert.match(syncJobHistory, /dataOps\.sync\.records\.deleted/)
  assert.match(syncJobHistory, /buildSyncJobSummary/)
  assert.match(syncJobHistory, /buildSyncResultRows/)
})

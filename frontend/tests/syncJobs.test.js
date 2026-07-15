import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildSyncJobSummary,
  buildSyncResultRows,
  formatSyncJobScope
} from '../src/utils/syncJobs.js'

const job = {
  source_key: 'domestic',
  table_key: '',
  results: {
    'domestic.table_a': {
      status: 'ok',
      source_records: 10,
      created: 2,
      updated: 3,
      deleted: 1,
      restored: 1,
      unchanged: 4,
      change_events: 5
    },
    'domestic.table_b': {
      status: 'ok',
      source_records: 5,
      created: 0,
      updated: 0,
      deleted: 0,
      restored: 0,
      skipped: true
    }
  }
}

const tables = [
  {
    source_key: 'domestic',
    table_key: 'table_a',
    table_name: '测试表 A'
  },
  {
    source_key: 'domestic',
    table_key: 'table_b',
    table_name: '测试表 B'
  }
]

test('aggregates added, modified and removed records for a sync job', () => {
  assert.deepEqual(buildSyncJobSummary(job), {
    sourceRecords: 15,
    created: 2,
    updated: 3,
    deleted: 1,
    restored: 1,
    unchanged: 9,
    changeEvents: 5,
    changed: 7,
    tableCount: 2,
    skippedTableCount: 1
  })
})

test('builds readable table details and a localized sync scope', () => {
  const rows = buildSyncResultRows(job, tables)
  const labels = {
    all: 'All Data',
    domestic: 'Domestic Data'
  }

  assert.equal(formatSyncJobScope(job, tables, labels), 'Domestic Data')
  assert.equal(rows[0].tableName, '测试表 A')
  assert.equal(rows[0].created, 2)
  assert.equal(rows[1].skipped, true)
})

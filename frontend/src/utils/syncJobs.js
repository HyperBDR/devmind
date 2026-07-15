export function buildSyncJobSummary(job) {
  const summary = {
    sourceRecords: 0,
    created: 0,
    updated: 0,
    deleted: 0,
    restored: 0,
    unchanged: 0,
    changeEvents: 0,
    changed: 0,
    tableCount: 0,
    skippedTableCount: 0
  }

  for (const result of Object.values(job?.results || {})) {
    if (!result || typeof result !== 'object') continue
    summary.sourceRecords += toCount(result.source_records)
    summary.created += toCount(result.created)
    summary.updated += toCount(result.updated)
    summary.deleted += toCount(result.deleted)
    summary.restored += toCount(result.restored)
    summary.unchanged += unchangedCount(result)
    summary.changeEvents += toCount(result.change_events)
    summary.tableCount += 1
    if (result.skipped) summary.skippedTableCount += 1
  }

  summary.changed =
    summary.created + summary.updated + summary.deleted + summary.restored
  return summary
}

export function buildSyncResultRows(job, tables = []) {
  const tableNames = new Map(
    tables.map((table) => [
      `${table.source_key}.${table.table_key}`,
      table.table_name
    ])
  )

  return Object.entries(job?.results || {}).map(([key, result = {}]) => {
    const [sourceKey, tableKey] = splitResultKey(key, job)
    return {
      key,
      sourceKey,
      tableKey,
      tableName:
        tableNames.get(`${sourceKey}.${tableKey}`) ||
        result.table_name ||
        tableKey ||
        key,
      status: result.status || 'pending',
      sourceRecords: toCount(result.source_records),
      created: toCount(result.created),
      updated: toCount(result.updated),
      deleted: toCount(result.deleted),
      restored: toCount(result.restored),
      unchanged: unchangedCount(result),
      changeEvents: toCount(result.change_events),
      skipped: Boolean(result.skipped),
      message: result.message || result.reason || ''
    }
  })
}

export function formatSyncJobScope(job, tables = [], labels = {}) {
  if (!job?.source_key) return labels.all || 'all'
  const sourceLabel = labels[job.source_key] || job.source_key
  if (!job.table_key) return sourceLabel

  const table = tables.find(
    (item) =>
      item.source_key === job.source_key && item.table_key === job.table_key
  )
  return `${sourceLabel} · ${table?.table_name || job.table_key}`
}

function splitResultKey(key, job) {
  const separatorIndex = key.indexOf('.')
  if (separatorIndex < 0) {
    return [job?.source_key || '', key || job?.table_key || '']
  }
  return [key.slice(0, separatorIndex), key.slice(separatorIndex + 1)]
}

function toCount(value) {
  const count = Number(value || 0)
  return Number.isFinite(count) ? count : 0
}

function unchangedCount(result) {
  if (result.skipped && result.unchanged == null) {
    return toCount(result.source_records)
  }
  return toCount(result.unchanged)
}

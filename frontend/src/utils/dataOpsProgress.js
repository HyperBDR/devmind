const localizedStages = new Set([
  'answer',
  'context',
  'plan',
  'question',
  'reasoning',
  'tool'
])

export function normalizeDataOpsProgressEvent(event) {
  return {
    detail: event?.detail || '',
    metadata: event?.metadata || {},
    stage: event?.stage || 'step',
    status: event?.status || 'done',
    timestamp: event?.timestamp || new Date().toISOString(),
    title: event?.title || ''
  }
}

export function localizeDataOpsProgressEvent(event, translate) {
  const normalized = normalizeDataOpsProgressEvent(event)
  if (
    !localizedStages.has(normalized.stage) ||
    typeof translate !== 'function'
  ) {
    return normalized
  }

  const metadata = normalized.metadata
  const result = metadata.result_summary || {}
  const values = {
    count: metadata.tool_count || result.row_count || 0,
    table: metadata.table || 'Data Ops'
  }

  return {
    ...normalized,
    detail: translate(
      `dataOps.feedback.progress.${normalized.stage}Detail`,
      values
    ),
    title: translate(
      `dataOps.feedback.progress.${normalized.stage}Title`,
      values
    )
  }
}

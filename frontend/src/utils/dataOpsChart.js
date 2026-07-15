const supportedChartTypes = new Set(['bar', 'line', 'pie', 'doughnut'])
const partToWholeChartTypes = new Set(['pie', 'doughnut'])

export function normalizeDataOpsChart(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null

  const type = String(value.type || 'bar').toLowerCase()
  if (!supportedChartTypes.has(type)) return null

  const rawSeries = Array.isArray(value.series) && value.series.length
    ? value.series
    : [
        {
          name: value.name,
          data: value.data || value.values
        }
      ]
  const series = rawSeries.map(normalizeSeries)
  if (series.some((item) => item === null)) return null
  if (partToWholeChartTypes.has(type) && series.length !== 1) return null

  const pointCount = series[0].data.length
  if (!pointCount || series.some((item) => item.data.length !== pointCount)) {
    return null
  }

  const labels = Array.isArray(value.labels)
    ? value.labels.map((label) => String(label ?? ''))
    : Array.from({ length: pointCount }, (_, index) => `#${index + 1}`)
  if (labels.length !== pointCount) return null

  if (partToWholeChartTypes.has(type)) {
    const values = series[0].data
    if (values.some((item) => item < 0)) return null
    if (values.reduce((total, item) => total + item, 0) <= 0) return null
  }

  return {
    type,
    title: String(value.title || ''),
    labels,
    series,
    unit: String(value.unit || '')
  }
}

function normalizeSeries(item, index) {
  if (!item || typeof item !== 'object') return null
  const values = item.data
  if (!Array.isArray(values) || !values.length) return null
  const data = values.map(normalizeNumber)
  if (data.some((value) => value === null)) return null
  return {
    name: String(item.name || `Series ${index + 1}`),
    data
  }
}

function normalizeNumber(value) {
  if (typeof value === 'string' && !value.trim()) return null
  if (!['number', 'string'].includes(typeof value)) return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

const supportedChartTypes = new Set(['bar', 'line', 'pie', 'doughnut'])
const partToWholeChartTypes = new Set(['pie', 'doughnut'])
const chartPointLimits = {
  bar: { min: 2, max: 12 },
  doughnut: { min: 2, max: 8 },
  line: { min: 3, max: 60 },
  pie: { min: 2, max: 8 }
}
const chartPalette = [
  '#5f4ecf',
  '#0284c7',
  '#059669',
  '#d97706',
  '#e11d48',
  '#7c3aed',
  '#0f766e',
  '#64748b'
]
const chartHoverPalette = [
  '#4a3eb0',
  '#0369a1',
  '#047857',
  '#b45309',
  '#be123c',
  '#6d28d9',
  '#115e59',
  '#475569'
]
const linePointStyles = [
  'circle',
  'rectRounded',
  'triangle',
  'rectRot',
  'crossRot',
  'star',
  'rect',
  'cross'
]

export function normalizeDataOpsChart(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null

  const type = String(value.type || 'bar').toLowerCase()
  if (!supportedChartTypes.has(type)) return null

  const rawSeries =
    Array.isArray(value.series) && value.series.length
      ? value.series
      : [
          {
            name: value.name,
            data: value.data || value.values
          }
        ]
  if (rawSeries.length > 8) return null
  const series = rawSeries.map(normalizeSeries)
  if (series.some((item) => item === null)) return null
  if (partToWholeChartTypes.has(type) && series.length !== 1) return null

  const pointCount = series[0].data.length
  if (!pointCount || series.some((item) => item.data.length !== pointCount)) {
    return null
  }
  const pointLimits = chartPointLimits[type]
  if (pointCount < pointLimits.min || pointCount > pointLimits.max) return null

  const labels = Array.isArray(value.labels)
    ? value.labels.map((label) => String(label ?? '').trim())
    : Array.from({ length: pointCount }, (_, index) => `#${index + 1}`)
  if (labels.length !== pointCount) return null
  if (labels.some((label) => !label)) return null

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

export function buildDataOpsChartDatasets(chart) {
  const type = String(chart?.type || 'bar').toLowerCase()
  const labels = Array.isArray(chart?.labels) ? chart.labels : []
  const series = Array.isArray(chart?.series) ? chart.series : []

  if (partToWholeChartTypes.has(type)) {
    const item = series[0]
    if (!item) return []
    return [
      {
        label: item.name,
        data: item.data,
        backgroundColor: categoryColors(labels, chartPalette),
        hoverBackgroundColor: categoryColors(labels, chartHoverPalette),
        borderColor: '#ffffff',
        borderWidth: 3,
        hoverBorderColor: '#ffffff',
        hoverBorderWidth: 3,
        hoverOffset: 8
      }
    ]
  }

  return series.map((item, index) => {
    const color = chartPalette[index % chartPalette.length]
    const hoverColor = chartHoverPalette[index % chartHoverPalette.length]
    if (type === 'line') {
      return {
        label: item.name,
        data: item.data,
        backgroundColor: hexToRgba(color, 0.12),
        borderColor: color,
        borderWidth: 2.5,
        fill: series.length === 1 ? 'origin' : false,
        pointBackgroundColor: '#ffffff',
        pointBorderColor: color,
        pointBorderWidth: 2,
        pointHitRadius: 10,
        pointHoverBackgroundColor: hoverColor,
        pointHoverBorderColor: '#ffffff',
        pointHoverBorderWidth: 2,
        pointHoverRadius: 6,
        pointRadius: 3.5,
        pointStyle: linePointStyles[index % linePointStyles.length],
        tension: 0.32
      }
    }

    const singleSeries = series.length === 1
    return {
      label: item.name,
      data: item.data,
      backgroundColor: singleSeries
        ? categoryColors(labels, chartPalette)
        : color,
      hoverBackgroundColor: singleSeries
        ? categoryColors(labels, chartHoverPalette)
        : hoverColor,
      borderColor: singleSeries
        ? categoryColors(labels, chartHoverPalette)
        : hoverColor,
      borderRadius: 5,
      borderSkipped: false,
      borderWidth: 1,
      maxBarThickness: 44
    }
  })
}

function categoryColors(labels, palette) {
  return labels.map((_, index) => palette[index % palette.length])
}

function hexToRgba(value, alpha) {
  const hex = String(value || '').replace('#', '')
  const red = Number.parseInt(hex.slice(0, 2), 16)
  const green = Number.parseInt(hex.slice(2, 4), 16)
  const blue = Number.parseInt(hex.slice(4, 6), 16)
  return `rgba(${red}, ${green}, ${blue}, ${alpha})`
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

export function exportTableFile({ columns, records, format, filenameBase }) {
  if (!Array.isArray(records) || !records.length) return
  if (format === 'excel') {
    downloadExcelExport(columns, records, exportFileName(filenameBase, 'xls'))
    return
  }
  downloadCsvExport(columns, records, exportFileName(filenameBase, 'csv'))
}

function downloadCsvExport(columns, records, filename) {
  const lines = [
    columns.map((column) => csvCell(column.label)).join(','),
    ...records.map((record) =>
      columns.map((column) => csvCell(record[column.key])).join(',')
    )
  ]
  downloadExportFile(
    ['\uFEFF', lines.join('\n')],
    filename,
    'text/csv;charset=utf-8;'
  )
}

function downloadExcelExport(columns, records, filename) {
  const thead = columns
    .map((column) => `<th>${htmlCell(column.label)}</th>`)
    .join('')
  const tbody = records
    .map((record) => {
      const cells = columns
        .map(
          (column) =>
            `<td style="mso-number-format:'\\@';">` +
            `${htmlCell(record[column.key])}</td>`
        )
        .join('')
      return `<tr>${cells}</tr>`
    })
    .join('')
  const html = [
    '<html><head><meta charset="UTF-8"></head><body>',
    '<table border="1">',
    `<thead><tr>${thead}</tr></thead>`,
    `<tbody>${tbody}</tbody>`,
    '</table></body></html>'
  ].join('')
  downloadExportFile(
    ['\uFEFF', html],
    filename,
    'application/vnd.ms-excel;charset=utf-8;'
  )
}

function exportFileName(filenameBase, extension) {
  const date = new Date().toISOString().slice(0, 10)
  return `${filenameBase}-${date}.${extension}`
}

function downloadExportFile(parts, filename, type) {
  const blob = new Blob(parts, { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function csvCell(value) {
  const text = spreadsheetSafeText(value)
  return `"${text.replace(/"/g, '""')}"`
}

function htmlCell(value) {
  const text = spreadsheetSafeText(value)
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function spreadsheetSafeText(value) {
  const text = value === null || value === undefined ? '' : String(value)
  return /^[=+\-@\t\r]/.test(text) ? `'${text}` : text
}

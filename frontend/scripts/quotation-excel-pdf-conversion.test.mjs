import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const excel = readFileSync(
  new URL('../src/modules/quotation/utils/excelGenerator.ts', import.meta.url),
  'utf8',
)
const pdf = readFileSync(
  new URL('../src/modules/quotation/utils/pdfExporter.ts', import.meta.url),
  'utf8',
)
const api = readFileSync(
  new URL('../src/modules/quotation/api/pdf.ts', import.meta.url),
  'utf8',
)
const compose = readFileSync(
  new URL('../../docker-compose.yml', import.meta.url),
  'utf8',
)
const devCompose = readFileSync(
  new URL('../../docker-compose.dev.yml', import.meta.url),
  'utf8',
)

test('PDF conversion uses the generated Excel workbook as its source', () => {
  assert.match(pdf, /buildQuotationExcelBlob\(quote, currentUser\)/)
  assert.match(pdf, /renderExcelToPdfBlob\(excelBlob, fileName\)/)
  assert.match(pdf, /printHtmlViaOffscreenFrame\(html, downloadBaseName\)/)
  assert.match(api, /\/pdf\/from-excel/)
  assert.match(api, /form\.append\('file', excelBlob, fileName\)/)
})

test('Excel print settings keep quotation output on A4 pages', () => {
  assert.match(excel, /paperSize: 9/)
  assert.match(excel, /orientation: 'portrait'/)
  assert.match(excel, /fitToWidth: 1/)
  assert.match(excel, /fitToHeight: 0/)
  assert.match(excel, /left: 0\.47/)
  assert.match(excel, /this\.sheet\.pageSetup\.printArea = `A1:G/)
})

test('PDF conversion uses the pinned LibreOffice-only image', () => {
  const digest = 'sha256:3c23aeb3a027a63d7c71745fc9d83724bd58cf9dfa470396ac82c0896028db2a'
  for (const source of [compose, devCompose]) {
    assert.match(source, /gotenberg\/gotenberg:8\.34\.0-libreoffice/)
    assert.match(source, new RegExp(digest))
    assert.doesNotMatch(source, /--chromium-/)
    assert.match(source, /--api-body-limit=8MB/)
    assert.match(source, /--libreoffice-auto-start=true/)
  }
})

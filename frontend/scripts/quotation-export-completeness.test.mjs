import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const renderer = readFileSync(
  new URL('../../backend/quotation/services/export_renderer.py', import.meta.url),
  'utf8',
)
const pipeline = readFileSync(
  new URL('../../backend/quotation/services/export_pipeline.py', import.meta.url),
  'utf8',
)

test('backend preview export keeps every item and uses one PDF layout', () => {
  assert.match(renderer, /items = list\(snapshot\.get\("items"\) or \[\]\)/)
  assert.match(renderer, /max\(minimum - len\(section_items\), 0\)/)
  assert.match(pipeline, /convert_xlsx_to_pdf\(\s*excel_bytes,/)
  assert.doesNotMatch(pipeline, /render_preview_pdf/)
})

import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const renderer = readFileSync(
  new URL('../../backend/quotation/services/export_renderer.py', import.meta.url),
  'utf8',
)

test('backend template rendering never truncates quotation line items', () => {
  assert.match(renderer, /items = list\(snapshot\.get\("items"\) or \[\]\)/)
  assert.match(renderer, /extra_rows = max\(len\(render_items\) - 1, 0\)/)
  assert.match(renderer, /insert_rows\(item_start_row \+ 1, amount=extra_rows\)/)
  assert.match(renderer, /for offset, item in enumerate\(render_items\)/)
})

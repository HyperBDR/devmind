import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const workspace = fs.readFileSync(
  new URL('../src/modules/quotation/config/workspace.ts', import.meta.url),
  'utf8',
)

test('Quote Desk keeps route ownership in one workspace contract', () => {
  assert.match(workspace, /QUOTE_DESK_ROUTES/)
  assert.match(workspace, /quotationTabFromPath/)
  assert.match(workspace, /\/quotation\/dashboard/)
  assert.match(workspace, /\/quotation\/permissions/)
})

test('legacy imports route remains mapped to the quotation list', () => {
  assert.match(workspace, /\/quotation\/imports/)
})

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const source = read(
  '../src/modules/quotation/components/QuotationPreview.vue',
)
const pagination = read(
  '../src/modules/quotation/utils/paginateQuotation.ts',
)
const acceptance = read(
  '../src/modules/quotation/components/QuotationAcceptanceRows.vue',
)

test('pagination measures DOM instead of guessing character heights', () => {
  assert.match(pagination, /getBoundingClientRect/)
  assert.doesNotMatch(source, /wrappedRowHeight|descriptionRowHeight|951/)
  assert.match(source, /ResizeObserver\(schedulePages\)/)
  assert.match(source, /cancelAnimationFrame\(frame\)/)
  assert.match(source, /observer\?\.disconnect\(\)/)
})

test('notes title is grouped with the first notes fragment', () => {
  assert.match(source, /<tr data-preview-notes-title>/)
  assert.match(source, /<tr data-preview-notes>/)
  assert.match(pagination, /place\(\[row, rows\[\+\+index\]\], undefined, 0\)/)
  assert.match(pagination, /offset \? \[\] : originals\.slice\(0, -1\)/)
})

test('notes use remaining space only when three rendered lines fit', () => {
  assert.match(pagination, /if \(!splitNotesHere\)/)
  assert.match(pagination, /range\.getClientRects\(\)/)
  assert.match(pagination, /if \(lines\.size < 3\)/)
})

test('measurement is inaccessible and cannot clip the visible preview', () => {
  assert.match(source, /aria-hidden="true"\s+inert/)
  assert.doesNotMatch(source, /overflow-hidden/)
  assert.match(source, /output\.value\.replaceChildren/)
  assert.match(source, /staging\.remove\(\)/)
})

test('signature keeps its PDF-like line width and clickable black email', () => {
  assert.equal((acceptance.match(/w-\[48%\]/g) || []).length, 2)
  assert.match(acceptance, /class="text-inherit no-underline"/)
  assert.match(acceptance, /mailto:\$\{signer\.email\}/)
})

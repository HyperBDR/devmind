import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const source = readFileSync(
  new URL('../src/modules/quotation/components/QuotationList.vue', import.meta.url),
  'utf8',
)

test('quotation filters render as a compact toolbar with a date-range group', () => {
  assert.match(source, /const hasActiveFilters = computed/)
  assert.match(source, /aria-label="Quote filters"/)
  assert.match(source, /data-filter-toolbar/)
  assert.match(source, /data-filter-date-range/)
  assert.match(source, /hasActiveFilters\s*\?/)
  assert.doesNotMatch(source, /grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-12/)
  assert.doesNotMatch(source, /selectedSalesperson/)
  assert.doesNotMatch(source, /salespersonFilterOptions/)
  assert.doesNotMatch(source, /salespersonLabel/)
  assert.doesNotMatch(source, /matchesSalesperson/)
  assert.doesNotMatch(source, /overflow-hidden rounded-lg bg-white shadow-xs ring-1 ring-dm-border-light sm:grid-cols-2/)
  assert.match(source, /grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2/)
})

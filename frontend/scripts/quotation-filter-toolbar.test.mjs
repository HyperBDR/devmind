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
  assert.match(source, /initialCreatedFrom/)
  assert.match(source, /initialCreatedTo/)
  assert.match(source, /ref\(props\.initialCreatedFrom \|\| ''\)/)
  assert.match(source, /ref\(props\.initialCreatedTo \|\| ''\)/)
  assert.match(source, /props\.initialCreatedFrom/)
  assert.match(source, /props\.initialCreatedTo/)
  assert.match(source, /suppressFilterWatch = true/)
  assert.match(source, /hasActiveFilters\s*\?/)
  assert.doesNotMatch(source, /grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-12/)
  assert.doesNotMatch(source, /selectedSalesperson/)
  assert.doesNotMatch(source, /selectedStatus/)
  assert.doesNotMatch(source, /salespersonFilterOptions/)
  assert.doesNotMatch(source, /salespersonLabel/)
  assert.doesNotMatch(source, /matchesSalesperson/)
  assert.doesNotMatch(source, /overflow-hidden rounded-lg bg-white shadow-xs ring-1 ring-dm-border-light sm:grid-cols-2/)
  assert.match(source, /grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2/)
  assert.match(source, /xl:grid-cols-\[minmax\(0,1\.35fr\)_repeat\(3,minmax\(0,\.7fr\)\)_minmax\(0,1\.4fr\)\]/)
  assert.doesNotMatch(source, /2xl:grid-cols-/)
  assert.match(source, /data-feishu-sync-button/)
  assert.match(source, /syncFeishuArchiveFolder\(\{ source: 'user' \}\)/)
  assert.match(source, /getFeishuSyncJob/)
  assert.match(source, /'animate-spin': syncingFeishu/)
})

import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const apiSource = readFileSync(
  new URL('../src/modules/quotation/api/catalog.ts', import.meta.url),
  'utf8',
)
const appSource = readFileSync(
  new URL('../src/modules/quotation/App.vue', import.meta.url),
  'utf8',
)

test('catalog API supports per-user load, save, and one-time legacy import', () => {
  assert.match(apiSource, /apiRequest<UserQuotationCatalog>\('\/catalog'\)/)
  assert.match(apiSource, /method: 'PUT'/)
  assert.match(apiSource, /'\/catalog\/import-legacy'/)
})

test('quotation app hydrates catalog after authentication and persists changes', () => {
  assert.match(appSource, /hydrateUserCatalog\(\)/)
  assert.match(appSource, /catalogReady\.value = true/)
  assert.match(appSource, /await nextTick\(\)/)
  assert.match(appSource, /queueCatalogSave\(\)/)
  assert.match(appSource, /qmp_catalog_migrated_v1/)
})

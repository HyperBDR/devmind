import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const source = readFileSync(
  new URL('../src/modules/quotation/components/ProductServiceManager.vue', import.meta.url),
  'utf8',
)

test('catalog uses an in-page parent and child hierarchy', () => {
  assert.match(source, /data-catalog-layout/)
  assert.match(source, /data-catalog-tree/)
  assert.match(source, /data-catalog-parent="quote-descriptions"/)
  assert.match(source, /data-catalog-child="products"/)
  assert.match(source, /data-catalog-child="services"/)
  assert.match(source, /data-catalog-parent="discount-settings"/)
  assert.match(source, /data-catalog-parent="system-settings"/)
  assert.match(source, /data-catalog-content/)
  assert.match(source, /data-catalog-add/)
  assert.match(source, /data-catalog-search/)
  assert.match(source, /data-catalog-form-modal/)
  assert.match(source, /const quoteDescriptionsExpanded = ref\(true\)/)
  assert.match(source, /const discountSettingsExpanded = ref\(true\)/)
  assert.match(source, /const systemSettingsExpanded = ref\(true\)/)
  assert.match(source, /@click="quoteDescriptionsExpanded = !quoteDescriptionsExpanded"/)
  assert.match(source, /v-show="quoteDescriptionsExpanded"/)
  assert.match(source, /v-show="discountSettingsExpanded"/)
  assert.match(source, /v-show="systemSettingsExpanded"/)
  assert.match(source, /:aria-current=/)
  assert.doesNotMatch(source, /class="flex gap-1 border-b border-dm-border-light text-xs"/)
  assert.doesNotMatch(source, /xl:grid-cols-3/)
})

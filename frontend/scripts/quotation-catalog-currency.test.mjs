import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const manager = readFileSync(
  new URL(
    '../src/modules/quotation/components/ProductServiceManager.vue',
    import.meta.url,
  ),
  'utf8',
)
const descriptions = readFileSync(
  new URL(
    '../src/modules/quotation/utils/descriptionCatalog.ts',
    import.meta.url,
  ),
  'utf8',
)
const quotationCreate = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationCreate.vue',
    import.meta.url,
  ),
  'utf8',
)
const templateCatalogs = readFileSync(
  new URL(
    '../src/modules/quotation/utils/templateCatalogs.ts',
    import.meta.url,
  ),
  'utf8',
)
const english = JSON.parse(
  readFileSync(
    new URL('../src/modules/quotation/locales/en.json', import.meta.url),
    'utf8',
  ),
)

test('catalog prices store an explicit CNY, USD, or EUR currency', () => {
  assert.match(manager, /const pCurrency = ref<CatalogCurrency>\('USD'\)/)
  assert.match(manager, /const sCurrency = ref<CatalogCurrency>\('USD'\)/)
  assert.match(manager, /currency: pCurrency\.value/)
  assert.match(manager, /currency: sCurrency\.value/)
  assert.match(manager, /\{ value: 'CNY', label: 'CNY' \}/)
  assert.match(manager, /\{ value: 'EUR', label: 'EUR' \}/)
  assert.equal(english.quotation.pages.catalog.productPrice, 'List price')
  assert.equal(english.quotation.pages.catalog.priceCurrency, 'Currency')
})

test('catalog prices only auto-fill quotes in the same currency', () => {
  assert.match(descriptions, /product\.currency \|\| 'USD'/)
  assert.match(descriptions, /quoteCurrency === currency/)
  assert.match(quotationCreate, /optionCurrency === currency\.value/)
  assert.match(templateCatalogs, /currency: 'USD'/)
})

test('automatic catalog sync skips matching names across currencies', () => {
  assert.match(descriptions, /const key = normalize\(text\)/)
  assert.doesNotMatch(
    descriptions,
    /`\$\{currency\}:\$\{normalize\(text\)\}`/,
  )
  assert.doesNotMatch(
    descriptions,
    /`\$\{item\.currency \|\| 'USD'\}:\$\{normalize/,
  )
})

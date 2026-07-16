import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const modalSource = readFileSync(
  new URL(
    '../src/components/cloud-billing/ProviderFormModal.vue',
    import.meta.url
  ),
  'utf8'
)
const providerDisplaySource = readFileSync(
  new URL('../src/utils/providerDisplay.js', import.meta.url),
  'utf8'
)
const en = JSON.parse(
  readFileSync(new URL('../src/locales/en.json', import.meta.url), 'utf8')
)
const zh = JSON.parse(
  readFileSync(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8')
)

test('cloud provider form supports DeepSeek API key configuration', () => {
  assert.match(modalSource, /<option value="deepseek">/)
  assert.match(modalSource, /formData\.provider_type === 'deepseek'/)
  assert.match(modalSource, /v-model="configFields\.deepseek_api_key"/)
  assert.match(
    modalSource,
    /config\.DEEPSEEK_API_KEY = configFields\.deepseek_api_key/
  )
  assert.match(modalSource, /config\.DEEPSEEK_TIMEOUT = preservedTimeout/)
})

test('DeepSeek provider labels are available in both locales', () => {
  assert.equal(en.cloudBilling.providers.types.deepseek, 'DeepSeek')
  assert.equal(zh.cloudBilling.providers.types.deepseek, 'DeepSeek')
  assert.equal(en.cloudBilling.providers.deepseekApiKey, 'API Key')
  assert.equal(zh.cloudBilling.providers.deepseekApiKey, 'API Key')
  assert.match(
    providerDisplaySource,
    /deepseek:\s*'cloudBilling\.providers\.types\.deepseek'/
  )
})

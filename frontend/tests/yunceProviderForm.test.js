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

test('cloud provider form supports Yunce credentials and optional API Key', () => {
  const yunceTemplate = modalSource.match(
    /<template v-if="formData\.provider_type === 'yunce'">([\s\S]*?)<\/template>/
  )?.[1]

  assert.ok(yunceTemplate)
  assert.match(modalSource, /<option value="yunce">/)
  assert.match(modalSource, /formData\.provider_type === 'yunce'/)
  assert.match(yunceTemplate, /v-model="configFields\.yunce_username"/)
  assert.match(yunceTemplate, /v-model="configFields\.yunce_password"/)
  assert.match(yunceTemplate, /v-model="configFields\.yunce_api_key"/)
  assert.match(
    modalSource,
    /config\.YUNCE_USERNAME = configFields\.yunce_username/
  )
  assert.match(
    modalSource,
    /config\.YUNCE_PASSWORD = configFields\.yunce_password/
  )
  assert.match(
    modalSource,
    /config\.YUNCE_API_KEY = configFields\.yunce_api_key/
  )
  assert.match(modalSource, /config\.YUNCE_TIMEOUT = preservedTimeout/)
  assert.doesNotMatch(modalSource, /Request data sent/)
})

test('Yunce provider labels are available in both locales', () => {
  assert.equal(en.cloudBilling.providers.types.yunce, 'Yunce')
  assert.equal(zh.cloudBilling.providers.types.yunce, '云策')
  assert.equal(en.cloudBilling.providers.yunceUsername, 'Username')
  assert.equal(zh.cloudBilling.providers.yunceUsername, '用户名')
  assert.equal(en.cloudBilling.providers.yuncePassword, 'Password')
  assert.equal(zh.cloudBilling.providers.yuncePassword, '密码')
  assert.equal(en.cloudBilling.providers.yunceApiKey, 'API Key (optional)')
  assert.equal(zh.cloudBilling.providers.yunceApiKey, 'API Key（可选）')
  assert.match(
    providerDisplaySource,
    /yunce:\s*'cloudBilling\.providers\.types\.yunce'/
  )
})

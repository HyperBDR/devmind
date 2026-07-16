import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const feishuApi = readFileSync(
  new URL('../src/modules/quotation/api/feishu.ts', import.meta.url),
  'utf8'
)

const driveModal = readFileSync(
  new URL('../src/modules/quotation/components/FeishuDriveModal.vue', import.meta.url),
  'utf8'
)

test('Feishu OAuth start accepts a Quote Desk return path', () => {
  assert.match(feishuApi, /startFeishuOAuth\([^)]*returnTo/)
  assert.match(feishuApi, /return_to/)
  assert.match(feishuApi, /URLSearchParams/)
})

test('Feishu drive modal sends the current Quote Desk path to OAuth start', () => {
  assert.match(driveModal, /useRoute/)
  assert.match(driveModal, /route\.fullPath/)
  assert.match(driveModal, /startFeishuOAuth\([^)]*route\.fullPath/)
})

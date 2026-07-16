import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const authStore = readFileSync(
  new URL('../src/modules/quotation/stores/auth.ts', import.meta.url),
  'utf8'
)

test('embedded Quote Desk trusts the authenticated DevMind user during view switches', () => {
  const isAuthenticatedBlock = authStore.match(
    /const isAuthenticated = computed\([^\n]+\)/
  )?.[0]

  assert.ok(isAuthenticatedBlock, 'embedded authentication getter is missing')
  assert.match(isAuthenticatedBlock, /!!currentUser\.value/)
  assert.doesNotMatch(isAuthenticatedBlock, /localStorage/)
})

import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const appLayout = readFileSync(
  new URL('../src/components/layout/AppLayout.vue', import.meta.url),
  'utf8',
)

test('sidebar collapse state stays independent in each browser tab', () => {
  assert.match(
    appLayout,
    /sessionStorage\.setItem\(\s*SIDEBAR_COLLAPSED_STORAGE_KEY/,
  )
  assert.match(
    appLayout,
    /sessionStorage\.getItem\(SIDEBAR_COLLAPSED_STORAGE_KEY\)/,
  )
  assert.doesNotMatch(
    appLayout,
    /localStorage\.(?:getItem|setItem)\(\s*SIDEBAR_COLLAPSED_STORAGE_KEY/,
  )
})

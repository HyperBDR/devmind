import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const sidebarSource = readFileSync(
  new URL('../src/components/layout/AppSidebar.vue', import.meta.url),
  'utf8'
)
const routerSource = readFileSync(
  new URL('../src/router/index.js', import.meta.url),
  'utf8'
)

test('keeps Data Ops available without showing it in the app sidebar', () => {
  assert.doesNotMatch(sidebarSource, /to="\/data-ops"/)
  assert.match(routerSource, /path:\s*'\/data-ops'/)
})

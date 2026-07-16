import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(
  new URL('../src/components/ui/BaseButton.vue', import.meta.url),
  'utf8'
)

test('small shared buttons keep a comfortable toolbar height', () => {
  assert.match(source, /sm:\s*'min-h-9 px-3\.5 py-2 text-sm'/)
  assert.doesNotMatch(source, /sm:\s*'[^']*text-xs[^']*'/)
})

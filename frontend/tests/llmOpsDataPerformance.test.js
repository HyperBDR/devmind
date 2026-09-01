import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(
  new URL('../src/composables/useLLMOpsData.js', import.meta.url),
  'utf8'
)

test('deduplicates concurrent LLM Ops data-group requests', () => {
  assert.match(source, /const inFlightGroups = new Map\(\)/)
  assert.match(
    source,
    /const existingRequest = inFlightGroups\.get\(requestKey\)/
  )
  assert.match(source, /loadDataGroupInternal\(group, section, options\)/)
})

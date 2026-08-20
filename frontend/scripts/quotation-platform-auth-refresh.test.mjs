import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const client = readFileSync(
  new URL('../src/modules/quotation/api/client.ts', import.meta.url),
  'utf8'
)

test('Quote Desk refreshes the platform token after a 401 response', () => {
  assert.match(client, /REFRESH_TOKEN_KEY = ['"]refresh_token['"]/
  )
  assert.match(client, /\/v1\/auth\/token\/refresh/)
  assert.match(client, /response\.status === 401/)
  assert.match(client, /Authorization.*newAccessToken/)
})

test('Quote Desk clears platform auth when refresh cannot recover the session', () => {
  assert.match(client, /localStorage\.removeItem\(REFRESH_TOKEN_KEY\)/)
  assert.match(client, /window\.location\.href = ['"]\/login['"]/
  )
})

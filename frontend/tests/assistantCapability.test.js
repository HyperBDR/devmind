import assert from 'node:assert/strict'
import test from 'node:test'

import {
  indexAssistantCapabilities,
  resolveAssistantCapability
} from '../src/utils/assistantCapability.js'

test('indexes capabilities by backend app key', () => {
  const capabilities = indexAssistantCapabilities([
    {
      app_key: 'data_ops',
      display_name: 'Data Ops Assistant',
      profile: { question_groups: [] }
    }
  ])

  assert.equal(capabilities.get('data_ops').displayName, 'Data Ops Assistant')
})

test('returns no capability for an app that did not register AI support', () => {
  const capabilities = indexAssistantCapabilities([
    { appKey: 'data_ops', displayName: 'Data Ops Assistant' }
  ])

  assert.equal(resolveAssistantCapability(capabilities, 'llm_ops'), null)
  assert.equal(resolveAssistantCapability(capabilities, ''), null)
})

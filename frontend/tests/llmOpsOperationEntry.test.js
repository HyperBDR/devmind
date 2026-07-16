import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { parseLLMOpsOperationTarget } from '../src/utils/llmOpsOperationEntry.js'

const llmOpsPageSource = readFileSync(
  new URL('../src/pages/LLMOps.vue', import.meta.url),
  'utf8'
)
const modelWorkbenchSource = readFileSync(
  new URL('../src/components/llm-ops/ModelWorkbenchPanel.vue', import.meta.url),
  'utf8'
)
const priceChangeSource = readFileSync(
  new URL('../src/components/llm-ops/PriceChangePanel.vue', import.meta.url),
  'utf8'
)

test('parses a model publishing operation entry from query params', () => {
  assert.deepEqual(
    parseLLMOpsOperationTarget('?section=reseller&model_id=42'),
    {
      modelId: 42,
      openPlatformConfig: false,
      platformId: null,
      sourceId: null,
      section: 'reseller'
    }
  )
})

test('ignores invalid model identifiers', () => {
  assert.deepEqual(
    parseLLMOpsOperationTarget('?section=providers&model_id=invalid'),
    {
      modelId: null,
      openPlatformConfig: false,
      platformId: null,
      sourceId: null,
      section: 'providers'
    }
  )
})

test('parses source and platform operation targets', () => {
  assert.deepEqual(
    parseLLMOpsOperationTarget(
      '?section=monitor&source_id=7&platform_id=9&open_platform_config=1'
    ),
    {
      modelId: null,
      openPlatformConfig: true,
      platformId: 9,
      sourceId: 7,
      section: 'monitor'
    }
  )
})

test('applies assistant model targets to model-scoped LLM Ops sections', () => {
  assert.match(
    llmOpsPageSource,
    /<ModelWorkbenchPanel[\s\S]*?:focus-model-id="operationTargetModelId"/
  )
  assert.match(
    llmOpsPageSource,
    /<PriceChangePanel[\s\S]*?:focus-model-id="operationTargetModelId"/
  )
  assert.match(
    llmOpsPageSource,
    /<ChannelManagement[\s\S]*?:focus-model-id="operationTargetModelId"/
  )
  assert.match(
    llmOpsPageSource,
    /<ReconciliationPanel[\s\S]*?:focus-model-id="operationTargetModelId"/
  )
  assert.match(
    llmOpsPageSource,
    /<ProviderManagement[\s\S]*?:focus-source-id="operationTargetSourceId"/
  )
  assert.match(modelWorkbenchSource, /focusModelId:/)
  assert.match(priceChangeSource, /focusModelId:/)
  assert.ok(
    priceChangeSource.indexOf('if (props.focusModelId)') <
      priceChangeSource.indexOf('return rows.slice(0, 120)')
  )
  assert.doesNotMatch(priceChangeSource, /priceItems\.slice\(0, 80\)/)
  assert.match(
    llmOpsPageSource,
    /refreshAll\(activeSection\.value,\s*\{\s*modelId:\s*operationTargetModelId\.value/
  )
})

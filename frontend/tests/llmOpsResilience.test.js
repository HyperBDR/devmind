import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import { userFacingApiError } from '../src/utils/llmOpsErrors.js'
import {
  dataGroupsForSection,
  toolbarForSection
} from '../src/utils/llmOpsSectionData.js'

const globalConfigSource = readFileSync(
  new URL('../src/components/llm-ops/GlobalConfigPanel.vue', import.meta.url),
  'utf8'
)
const llmOpsPageSource = readFileSync(
  new URL('../src/pages/LLMOps.vue', import.meta.url),
  'utf8'
)
const modelWorkbenchSource = readFileSync(
  new URL('../src/components/llm-ops/ModelWorkbenchPanel.vue', import.meta.url),
  'utf8'
)
const operationErrorSources = [
  '../src/components/llm-ops/AgioneListingStatusBoard.vue',
  '../src/components/llm-ops/ChannelManagement.vue',
  '../src/components/llm-ops/ManualPriceEntryModal.vue',
  '../src/components/llm-ops/MetaModelModal.vue',
  '../src/components/llm-ops/PriceSourceModal.vue',
  '../src/components/llm-ops/ProviderModal.vue',
  '../src/components/llm-ops/ResalePublishingDrawer.vue',
  '../src/components/llm-ops/ResaleWorkflowConfigPanel.vue',
  '../src/composables/useLLMOpsResalePublishing.js'
].map((path) => readFileSync(new URL(path, import.meta.url), 'utf8'))
const reconciliationSource = readFileSync(
  new URL('../src/components/llm-ops/ReconciliationPanel.vue', import.meta.url),
  'utf8'
)
const resalePublishingSource = readFileSync(
  new URL('../src/composables/useLLMOpsResalePublishing.js', import.meta.url),
  'utf8'
)

test('replaces server and HTML errors with a safe page message', () => {
  const htmlError = {
    response: {
      status: 502,
      data: '<html><title>502 Bad Gateway</title></html>'
    },
    message: 'Request failed with status code 502'
  }

  assert.equal(
    userFacingApiError(htmlError, '当前页面暂时不可用'),
    '当前页面暂时不可用'
  )
})

test('keeps concise validation messages returned by the API', () => {
  const validationError = {
    response: {
      status: 400,
      data: { detail: '执行周期不能为空' }
    }
  }

  assert.equal(
    userFacingApiError(validationError, '保存失败'),
    '执行周期不能为空'
  )
})

test('loads only the data groups required by each section', () => {
  assert.deepEqual(dataGroupsForSection('taskLogs'), ['sources', 'runs'])
  assert.deepEqual(dataGroupsForSection('globalConfig'), ['sources'])
  assert.deepEqual(dataGroupsForSection('audit'), ['channels'])
  assert.ok(dataGroupsForSection('modelWorkbench').includes('modelPrices'))
  assert.ok(dataGroupsForSection('modelWorkbench').includes('records'))
  assert.ok(!dataGroupsForSection('taskLogs').includes('summary'))
  assert.ok(!dataGroupsForSection('audit').includes('models'))
})

test('shows page toolbar controls only where they are meaningful', () => {
  assert.deepEqual(toolbarForSection('taskLogs'), {
    currency: false,
    refresh: false
  })
  assert.deepEqual(toolbarForSection('globalConfig'), {
    currency: false,
    refresh: false
  })
  assert.deepEqual(toolbarForSection('modelWorkbench'), {
    currency: true,
    refresh: true
  })
})

test('renders a persistent page error instead of business zero values', () => {
  assert.match(llmOpsPageSource, /<LLMOpsErrorState/)
  assert.match(llmOpsPageSource, /v-else-if="pageError"/)
  assert.match(
    llmOpsPageSource,
    /:actions-disabled="Boolean\(pageError\) \|\| loading"/
  )
})

test('keeps global configuration unavailable until a load succeeds', () => {
  assert.match(globalConfigSource, /v-else-if="configLoadError"/)
  assert.match(globalConfigSource, /v-else-if="config"/)
  assert.match(
    globalConfigSource,
    /:disabled="loading \|\| saving \|\| !config"/
  )
})

test('uses a guided empty state when no workbench models exist', () => {
  assert.match(modelWorkbenchSource, /v-if="!modelOptions\.length"/)
  assert.match(
    modelWorkbenchSource,
    /llmOps\.modelWorkbenchPanel\.emptyModelsTitle/
  )
})

test('sanitizes operation errors before showing them to users', () => {
  operationErrorSources.forEach((source) => {
    assert.doesNotMatch(source, /error\?\.response\?\.data\?\.detail/)
    assert.doesNotMatch(source, /showError\(error\?\.message/)
    assert.match(source, /userFacingApiError|errorMessage/)
  })
})

test('uses a recognizable create icon in the reconciliation action', () => {
  assert.doesNotMatch(reconciliationSource, /class="icon-mark"/)
  assert.match(reconciliationSource, /d="M12 5v14M5 12h14"/)
})

test('limits platform selection refreshes to platform-aware sections', () => {
  assert.match(
    resalePublishingSource,
    /if \(!\['monitor', 'reseller'\]\.includes\(activeSection\.value\)\) return/
  )
})

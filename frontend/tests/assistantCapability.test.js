import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  indexAssistantCapabilities,
  localizeAssistantCapability,
  resolveAssistantCapability
} from '../src/utils/assistantCapability.js'

const assistantSectionSource = readFileSync(
  new URL('../src/components/data-ops/AiAssistantSection.vue', import.meta.url),
  'utf8'
)
const en = JSON.parse(
  readFileSync(new URL('../src/locales/en.json', import.meta.url), 'utf8')
)
const zh = JSON.parse(
  readFileSync(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8')
)

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

test('localizes app-owned assistant copy from capability profile keys', () => {
  const translations = {
    'dataOps.ai.drawerLabel': 'AI data assistant',
    'dataOps.ai.openLabel': 'Open AI data assistant',
    'dataOps.ai.subtitle': 'Business insights from Data Ops context',
    'dataOps.ai.title': 'AI Data Assistant'
  }
  const capability = {
    description: '分析合同、回款、Pipeline 和数据质量。',
    displayName: 'Data Ops 助手',
    profile: {
      ui_i18n: {
        description_key: 'dataOps.ai.subtitle',
        drawer_label_key: 'dataOps.ai.drawerLabel',
        open_label_key: 'dataOps.ai.openLabel',
        title_key: 'dataOps.ai.title'
      }
    }
  }

  const copy = localizeAssistantCapability(
    capability,
    (key) => translations[key],
    (key) => Object.hasOwn(translations, key)
  )

  assert.deepEqual(copy, {
    description: 'Business insights from Data Ops context',
    drawerLabel: 'AI data assistant',
    openLabel: 'Open AI data assistant',
    title: 'AI Data Assistant'
  })
})

test('falls back to backend assistant copy without translation keys', () => {
  const copy = localizeAssistantCapability(
    {
      description: 'Query operational data.',
      displayName: 'Operations Assistant'
    },
    () => '',
    () => false
  )

  assert.deepEqual(copy, {
    description: 'Query operational data.',
    drawerLabel: 'Operations Assistant',
    openLabel: 'Operations Assistant',
    title: 'Operations Assistant'
  })
})

test('localizes assistant question groups through the app profile key', () => {
  assert.match(assistantSectionSource, /question_groups_key/)

  const englishGroups = Object.values(en.llmOps.assistant.questionGroups)
  const chineseGroups = Object.values(zh.llmOps.assistant.questionGroups)
  const englishText = englishGroups
    .flatMap((group) => [group.title, ...group.questions])
    .join(' ')

  assert.equal(englishGroups.length, 4)
  assert.equal(chineseGroups.length, 4)
  assert.equal(/[\u3400-\u9fff]/u.test(englishText), false)
})

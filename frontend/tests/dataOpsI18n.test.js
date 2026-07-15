import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import test from 'node:test'

const readJson = (path) =>
  JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'))
const readSource = (path) =>
  readFileSync(new URL(path, import.meta.url), 'utf8')

const zhCN = readJson('../src/locales/data-ops/zh-CN.json')
const en = readJson('../src/locales/data-ops/en.json')
const i18nSetup = readSource('../src/i18n/index.js')
const dataOpsPage = readSource('../src/pages/DataOps.vue')
const appHeader = readSource('../src/components/layout/AppHeader.vue')
const aiAssistant = readSource(
  '../src/components/data-ops/AiAssistantSection.vue'
)

test('keeps Data Ops English and Chinese locale keys in sync', () => {
  assert.deepEqual(flattenKeys(en), flattenKeys(zhCN))
})

test('provides English AI questions without Chinese fallback text', () => {
  const groups = Object.values(en.ai.questionGroups)
  const questions = groups.flatMap((group) => group.questions)

  assert.equal(groups.length, 5)
  assert.equal(questions.length, 15)
  assert.equal(
    questions.some((item) => /[\u3400-\u9fff]/u.test(item)),
    false
  )
  assert.match(questions[0], /risk/i)
})

test('wires Data Ops pages and AI prompts into vue-i18n', () => {
  assert.match(i18nSetup, /dataOpsEn/)
  assert.match(i18nSetup, /dataOpsZhCN/)
  assert.match(dataOpsPage, /useI18n/)
  assert.match(aiAssistant, /useI18n/)
  assert.match(aiAssistant, /localizedQuestionGroups/)
})

test('defines every literal Data Ops translation key used by the UI', () => {
  const sourceUrls = [
    new URL('../src/components/data-ops/', import.meta.url),
    new URL('../src/composables/useDataOpsConsole.js', import.meta.url),
    new URL('../src/pages/DataOps.vue', import.meta.url)
  ]
  const referencedKeys = sourceUrls.flatMap((url) => collectKeys(url))
  const missingKeys = [...new Set(referencedKeys)].filter(
    (key) => !hasPath(en, key.replace(/^dataOps\./, ''))
  )

  assert.deepEqual(missingKeys, [])
})

test('keeps the shared platform and language header on Data Ops', () => {
  assert.doesNotMatch(dataOpsPage, /:show-header="false"/u)
  assert.match(appHeader, /<LanguageSwitcher\s*\/>/u)
  assert.match(appHeader, /<PlatformSwitcher\s*\/>/u)
})

function flattenKeys(value, prefix = '') {
  return Object.entries(value)
    .flatMap(([key, item]) => {
      const path = prefix ? `${prefix}.${key}` : key
      if (item && typeof item === 'object' && !Array.isArray(item)) {
        return flattenKeys(item, path)
      }
      return [path]
    })
    .sort()
}

function collectKeys(url) {
  if (!url.pathname.endsWith('/')) {
    return extractKeys(readFileSync(url, 'utf8'))
  }
  return readdirSync(url, { withFileTypes: true }).flatMap((entry) => {
    if (!entry.isFile() || !/\.(js|vue)$/u.test(entry.name)) return []
    return extractKeys(readFileSync(new URL(entry.name, url), 'utf8'))
  })
}

function extractKeys(source) {
  return [...source.matchAll(/['"](dataOps\.[\w.-]+)['"]/gu)].map(
    (match) => match[1]
  )
}

function hasPath(value, path) {
  return path.split('.').every((part) => {
    if (!value || !Object.hasOwn(value, part)) return false
    value = value[part]
    return true
  })
}

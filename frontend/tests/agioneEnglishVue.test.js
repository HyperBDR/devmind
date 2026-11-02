import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = path => readFileSync(new URL(path, import.meta.url), 'utf8')
const en = JSON.parse(read('../src/locales/en.json')).agione
const zh = JSON.parse(read('../src/locales/zh-CN.json')).agione
const main = read('../src/pages/AgioneOps.vue')

function keys(value, prefix = '') {
  return Object.entries(value).flatMap(([key, item]) => {
    const name = prefix ? `${prefix}.${key}` : key
    return typeof item === 'object' ? keys(item, name) : [name]
  }).sort()
}

test('English and Chinese AGIOne dictionaries have matching keys', () => {
  assert.deepEqual(keys(en), keys(zh))
  assert.doesNotMatch(JSON.stringify(en), /\p{Script=Han}/u)
})

test('English navigation uses established customer operations terms', () => {
  assert.equal(en.demoCustomerOps, 'Customer Operations')
  assert.equal(en.demoDashboard, 'Overview')
  assert.equal(en.demoAnalysis, 'Usage Analytics')
  assert.equal(en.demoPortrait, 'Customer Insights')
  assert.equal(en.knownTokens, 'Reported tokens')
  assert.equal(en.requestLog, 'Request log')
  assert.equal(en.requestDetails, 'Request details')
  assert.equal(en.groupDetails, 'Group details')
})

test('direct-source status and errors provide clear, actionable English', () => {
  assert.equal(en.live.originalAsOf, 'Last fetched')
  assert.equal(en.live.refresh, 'Refresh data')
  assert.match(en.errors.networkError, /Try again/)
  assert.match(en.errors.accessDenied, /administrator/)
  assert.match(en.technicalFieldsHelp, /Prompts and raw responses are excluded/)
})

test('the page follows the global language without changing saved preferences', () => {
  assert.match(main, /useI18n\(\{ useScope: 'global' \}\)/)
  assert.doesNotMatch(main, /inheritLocale: false|locale: 'zh-CN'/)
  assert.doesNotMatch(main, /(?:localStorage|sessionStorage)[^\n]*(?:locale|language)|(?:locale|language)[^\n]*(?:localStorage|sessionStorage)/i)
  assert.match(main, /calendarMonth\(month, locale\)/)
  assert.match(main, /'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'/)
  assert.match(main, /locale\.value\.startsWith\('zh'\) \? 'zh-CN' : 'en-GB'/)
})

test('drawer, scope and financial Vue wrappers react to the portal language', () => {
  for (const name of ['RequestDrawer', 'ScopeDialog', 'FinancePanel']) {
    const code = read(`../src/components/agione-demo/${name}.vue`)
    assert.match(code, /useI18n\(\{useScope:'global'\}\)/)
    assert.match(code, /locale:locale\.value/)
  }
  const scope = read('../src/components/agione-demo/ScopeDialog.vue')
  assert.match(scope, /watch\(locale,update\)/)
  const drawer = read('../src/components/agione-demo/RequestDrawer.vue')
  assert.match(drawer, /backdrop\.onPointerDown/)
  assert.match(drawer, /backdrop\.onClick/)
  assert.match(drawer, /JSON\.stringify\(evidence,null,2\)/)
  assert.doesNotMatch(drawer.split('<script setup>')[0], /\p{Script=Han}/u)
})

test('all literal translation keys in these Vue templates exist in both languages', () => {
  for (const code of [main, ...['RequestDrawer', 'ScopeDialog'].map(name =>
    read(`../src/components/agione-demo/${name}.vue`))]) {
    for (const match of code.matchAll(/t\('agione\.([A-Za-z][A-Za-z.]+)'/g)) {
      for (const dictionary of [en, zh]) {
        const value = match[1].split('.').reduce((node, key) => node?.[key], dictionary)
        assert.notEqual(value, undefined, `Missing translation ${match[1]}`)
      }
    }
  }
})

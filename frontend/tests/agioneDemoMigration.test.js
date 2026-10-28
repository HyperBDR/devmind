import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const page = read('../src/pages/AgioneOps.vue')

test('original Demo shell and 8011 scope controls replace the former UI', () => {
  for (const name of [
    'shell',
    'sidebar',
    'workspace',
    'topbar',
    'main',
    'scope-filter-field',
    'scope-refresh-actions',
    'dashboard-columns',
    'dashboard-data',
    'dashboard-overview',
    'dashboard-trend',
    'dashboard-models',
    'event-column',
    'dashboard-finance',
    'calendar-months',
    'connection-menu'
  ]) {
    assert.ok(page.includes(name), `Original Demo structure missing: ${name}`)
  }
  assert.match(page, /id="scopeUpdatedAt"/)
  assert.match(page, /class="scope-filter-placeholder"/)
  assert.doesNotMatch(page.split('</header>')[0], /id="refresh"/)
  assert.ok(
    page.indexOf('id="scopeRefreshActions"') >
      page.indexOf('class="scope-toolbar"')
  )
  assert.doesNotMatch(page, /AppLayout|agione-kpi|llm-ops\/archive|LLMOps/)
})

test('workspace starts with controls without a repeated page heading', () => {
  const page = readFileSync(
    new URL('../src/pages/AgioneOps.vue', import.meta.url),
    'utf8'
  )
  assert.doesNotMatch(page, /<div class="heading">/)
  assert.match(page, /<main class="main">\s*<div v-if="connection/)
})

test('AGIOne follows the portal language while preserving Chinese copy', () => {
  assert.match(page, /useScope: 'global'/)
  assert.doesNotMatch(page, /inheritLocale: false|locale: 'zh-CN'/)
  assert.doesNotMatch(page, /localStorage|document\.body/)
  assert.match(page, /dateStorage = window\.sessionStorage/)
  const messages = JSON.parse(read('../src/locales/zh-CN.json')).agione
  assert.equal(messages.demoNavLabel, '以问题组织经营工作')
  assert.equal(messages.demoDashboard, '经营看板')
  assert.equal(messages.demoSubtitle, '先确认事实，再定位客户与下一步。')
  for (const match of page.matchAll(/t\('agione\.([^']+)'/g)) {
    assert.notEqual(
      match[1].split('.').reduce((value, key) => value?.[key], messages),
      undefined,
      `Undefined Demo translation: ${match[1]}`
    )
  }
})

test('copied original CSS is wrapper-scoped and bootstrap is not executed', () => {
  const css = read('../src/components/agione-demo/demo-scoped.css')
  assert.match(css, /\.agione-demo\.dashboard-home \.main/)
  assert.match(css, /\.agione-demo \.scope-refresh-actions/)
  assert.match(css, /\.agione-demo \.dashboard-finance/)
  assert.doesNotMatch(css, /(?:^|\n)(?:body|html|:root)[\s.#:{]/)
  for (const name of ['style.css', 'live.css', 'dashboard-finance.css']) {
    assert.ok(
      read(`../src/components/agione-demo/original-${name}`).length > 2000
    )
  }
  assert.doesNotMatch(
    page,
    /app\.mjs|connections\.mjs|FIXED_WINDOW|iframe|8011/
  )
  assert.match(page, /agioneOpsApi/)
  assert.match(page, /agione\.financeMissing/)
})

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const page = read('../src/pages/AgioneOps.vue')
const header = read('../src/components/layout/AppHeader.vue')
const layout = read('../src/components/layout/AppLayout.vue')
const quotation = read('../src/pages/Quotation.vue')

test('AGIOne embeds native controls in the business breadcrumb row', () => {
  assert.doesNotMatch(page, /AppLayout/)
  assert.equal((page.match(/<header\b/g) || []).length, 1)
  const topbar = page.match(/<header class="topbar">([\s\S]*?)<\/header>/)?.[1]
  assert.ok(topbar)
  assert.match(topbar, /class="header-context"/)
  assert.match(topbar, /class="crumb"/)
  assert.match(topbar, /ref="connectionControl"/)
  assert.match(topbar, /<AppHeader inline :show-menu-button="false"\s*\/>/)
  assert.ok(topbar.indexOf('class="crumb"') < topbar.indexOf('<AppHeader'))
})

test('AppHeader inline is opt-in and does not add a nested header', () => {
  assert.match(header, /inline:\s*\{\s*type: Boolean,\s*default: false/)
  assert.match(header, /:is="inline \? 'div' : 'header'"/)
  assert.match(header, /<\/component>\s*<\/template>/)
  assert.match(header, /v-if="!inline" class="flex items-center gap-3"/)
  assert.match(header, /flex justify-between items-center h-16/)
  assert.match(header, /bg-white shadow-sm border-b border-gray-200/)
})

test('Quote Desk and AGIOne use the same native controls and menu logic', () => {
  assert.match(quotation, /<AppLayout\b/)
  assert.match(layout, /<AppHeader\b/)
  assert.equal((header.match(/<LanguageSwitcher\s*\/>/g) || []).length, 1)
  assert.equal((header.match(/<PlatformSwitcher\s*\/>/g) || []).length, 1)
  assert.equal((header.match(/const toggleUserMenu =/g) || []).length, 1)
  assert.equal((header.match(/const handleLogout =/g) || []).length, 1)
  assert.match(header, /devmind-inline-header-controls flex items-center space-x-4/)
  assert.doesNotMatch(page, /<LanguageSwitcher|<PlatformSwitcher|handleLogout/)
})

test('inline isolation restores native utility values without global resets', () => {
  const style = header.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1]
  assert.ok(style)
  assert.match(style, /\.devmind-inline-header :deep\(button\.border\)/)
  assert.match(style, /\.devmind-inline-header :deep\(button\.rounded-lg\)/)
  assert.match(style, /\.devmind-inline-header :deep\(button\.px-3\)/)
  assert.match(style, /\.devmind-inline-header :deep\(button\.py-2\)/)
  assert.doesNotMatch(style, /(?:^|\n)\s*(?:button|svg|header|body|html)\s*\{/)
  assert.match(page, /\.topbar\s*\{\s*min-height: 55px;\s*flex-wrap: nowrap;/)
})

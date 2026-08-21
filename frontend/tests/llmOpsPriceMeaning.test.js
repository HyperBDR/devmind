import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const drawerSource = fs.readFileSync(
  new URL('../src/components/llm-ops/ChannelModelDrawer.vue', import.meta.url),
  'utf8'
)
const workbenchSource = fs.readFileSync(
  new URL('../src/components/llm-ops/ModelWorkbenchPanel.vue', import.meta.url),
  'utf8'
)
const guideSource = fs.readFileSync(
  new URL(
    '../src/components/llm-ops/PriceMeaningGuide.vue',
    import.meta.url
  ),
  'utf8'
)
const zhLocale = JSON.parse(
  fs.readFileSync(new URL('../src/locales/zh-CN.json', import.meta.url))
)
const enLocale = JSON.parse(
  fs.readFileSync(new URL('../src/locales/en.json', import.meta.url))
)

test('price meaning guide is available in channel configuration and workbench', () => {
  assert.match(drawerSource, /PriceMeaningGuide/)
  assert.match(workbenchSource, /PriceMeaningGuide/)
  assert.match(guideSource, /priceMeaningGuide/)
})

test('price meaning copy explains dimensions and calculation chain in both locales', () => {
  for (const locale of [zhLocale, enLocale]) {
    const guide = locale.llmOps.priceMeaningGuide
    assert.ok(guide.title)
    assert.ok(guide.description)
    assert.ok(guide.input)
    assert.ok(guide.output)
    assert.ok(guide.cache)
    assert.ok(guide.upstream)
    assert.ok(guide.channelCost)
    assert.ok(guide.listingPrice)
    assert.ok(guide.formula)
  }
})

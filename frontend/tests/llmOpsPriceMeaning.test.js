import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const drawerSource = fs.readFileSync(
  new URL('../src/components/llm-ops/ChannelModelDrawer.vue', import.meta.url),
  'utf8'
)
const drawerStyles = fs.readFileSync(
  new URL(
    '../src/components/llm-ops/channelModelDrawer.css',
    import.meta.url
  ),
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

test('price meaning guide is available in the workbench without using drawer space', () => {
  assert.doesNotMatch(drawerSource, /PriceMeaningGuide/)
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

test('batch price previews occupy a full row and wrap complete details', () => {
  const previewRule = drawerStyles.match(
    /\.channel-model-drawer \.batch-price-preview span,[\s\S]*?\n}\n/
  )?.[0]
  assert.ok(previewRule)
  assert.match(previewRule, /whitespace-normal/)
  assert.match(previewRule, /break-words/)
  assert.doesNotMatch(previewRule, /truncate/)
  assert.match(drawerSource, /class-name="batch-region-select"/)
  assert.match(drawerSource, /class-name="batch-upstream-select"/)
  assert.match(
    drawerStyles,
    /batch-selection-row[\s\S]*xl:grid-cols-\[minmax\(7\.5rem,0\.7fr\)/
  )
  assert.match(
    drawerStyles,
    /batch-price-preview[\s\S]*xl:col-span-3/
  )
})

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const popover = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationNotesPopover.vue',
    import.meta.url,
  ),
  'utf8',
)
const createPage = readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationCreate.vue',
    import.meta.url,
  ),
  'utf8',
)
const english = JSON.parse(
  readFileSync(
    new URL('../src/modules/quotation/locales/en.json', import.meta.url),
    'utf8',
  ),
)

test('quote notes introduces the floating trigger once per user', () => {
  assert.match(popover, /quotation-notes-trigger-guide-v1/)
  assert.match(popover, /props\.guideUserKey/)
  assert.match(popover, /localStorage\.setItem\(triggerGuideStorageKey\.value/)
  assert.match(popover, /data-testid="quotation-notes-trigger-guide"/)
  assert.match(createPage, /:guide-user-key="currentUser\?\.email/)
})

test('English quote-note copy is concise and localized', () => {
  const copy = english.quotation.pages.create

  assert.equal(copy.notesButton, 'Notes')
  assert.equal(copy.notesTriggerGuideTitle, 'New: Team notes')
  assert.match(copy.notesTriggerGuideSaveFirst, /^Save this quote/)
  assert.match(copy.notesVisibility, /^Visible to everyone on your team/)
  assert.match(copy.notesExportHint, /^Internal only/)
  assert.match(popover, /locale\.value\.startsWith\('en'\)/)
  assert.match(popover, /'en-US'/)
})

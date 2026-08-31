import assert from 'node:assert/strict'
import fs from 'node:fs'

const picker = fs.readFileSync(
  new URL(
    '../src/modules/quotation/components/PublicAttachmentPicker.vue',
    import.meta.url,
  ),
  'utf8',
)
const exportsSource = fs.readFileSync(
  new URL(
    '../src/modules/quotation/api/exports.ts',
    import.meta.url,
  ),
  'utf8',
)
const quotationList = fs.readFileSync(
  new URL(
    '../src/modules/quotation/components/QuotationList.vue',
    import.meta.url,
  ),
  'utf8',
)
const manager = fs.readFileSync(
  new URL('../src/modules/quotation/components/PublicAttachmentManager.vue', import.meta.url),
  'utf8',
)

assert.doesNotMatch(picker, />必选</)
assert.match(picker, /accent-blue-600/)
assert.match(picker, /未选择/)
assert.match(picker, /拖动调整顺序/)
assert.match(picker, /@dragend="stopDragging"/)
assert.match(picker, /data-attachment-row/)
assert.match(picker, /setDragImage\(row/)
assert.doesNotMatch(picker, /draggable="true"/)
assert.match(picker, /selected\.value = \[\]/)
assert.match(
  picker,
  /filter\(\s*\(item\) => item\.status === 'active',?\s*\)/,
)
assert.doesNotMatch(
  picker,
  /selected\.value = items\.value\.map/,
)
assert.match(picker, /overflow-hidden rounded-xl/)
assert.match(
  picker,
  /selected\.length \? '合并并下载' : '直接下载'/,
)
assert.match(manager, /accept="\.pdf,\.doc,\.docx,\.xls,\.xlsx"/)
assert.doesNotMatch(manager, /accept="[^"]*\.png/)
assert.match(quotationList, /attachmentSelection: ids/)
assert.match(exportsSource, /attachment_selection: options\.attachmentSelection \|\| \[\]/)

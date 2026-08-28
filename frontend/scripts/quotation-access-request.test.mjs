import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

const accessPage = read(
  '../src/modules/quotation/components/ViewPermissionPage.vue'
)
const accessApi = read('../src/modules/quotation/api/accessRequests.ts')
const uploadApi = read('../src/modules/quotation/api/uploadPermissions.ts')
const folderPicker = read(
  '../src/modules/quotation/components/FeishuFolderPickerModal.vue'
)
const quotationList = read(
  '../src/modules/quotation/components/QuotationList.vue'
)
const quotationApp = read('../src/modules/quotation/App.vue')
const sidebar = read('../src/components/layout/AppSidebar.vue')

test('Quote Desk keeps permission changes administrator-managed', () => {
  assert.match(accessApi, /\/access-requests/)
  assert.match(accessApi, /request_type/)
  assert.match(accessApi, /folder_upload/)
  assert.match(accessApi, /document_view/)
  assert.doesNotMatch(accessApi, /submitAccessRequest/)
  assert.doesNotMatch(accessPage, /submitAccessRequest/)
  assert.doesNotMatch(accessPage, /requestTypeOptions/)
  assert.match(accessPage, /decideAccessRequest/)
  assert.match(quotationApp, /currentTab === 'permissions'/)
  assert.doesNotMatch(
    quotationApp,
    /currentTab === 'permissions' && isViewPermissionAdmin/
  )
  assert.doesNotMatch(sidebar, /v-if="quotationViewPermissionAdmin"/)
})

test('administrators can manage upload permissions and decisions', () => {
  assert.match(uploadApi, /\/upload-permissions/)
  assert.match(uploadApi, /PATCH/)
  assert.match(accessApi, /\/decision/)
  assert.match(accessPage, /grantUploadPermission/)
  assert.match(accessPage, /decideAccessRequest/)
  assert.match(accessPage, /revokeUploadPermission/)
})

test('upload folder browsing and actions fail closed without access', () => {
  assert.match(folderPicker, /listFeishuFolder\(token, props\.intent\)/)
  assert.match(folderPicker, /uploadRoot/)
  assert.match(quotationList, /loadUploadAccess/)
  assert.match(quotationList, /hasUploadAccess/)
  assert.doesNotMatch(quotationList, /uploadAccessRequired/)
  assert.doesNotMatch(quotationList, /requestUploadAccess/)
  assert.doesNotMatch(quotationList, /data-feishu-sync-button/)
})

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

async function optionalSource(path) {
  try {
    return await readFile(new URL(path, import.meta.url), 'utf8')
  } catch {
    return ''
  }
}

const permissionPage = await optionalSource(
  '../src/modules/quotation/components/ViewPermissionPage.vue'
)
const userPermissionSection = await optionalSource(
  '../src/modules/quotation/components/UserPermissionSection.vue'
)
const viewGrantSection = await optionalSource(
  '../src/modules/quotation/components/ViewGrantSection.vue'
)
const viewGrantForm = await optionalSource(
  '../src/modules/quotation/components/ViewGrantForm.vue'
)
const viewGrantTable = await optionalSource(
  '../src/modules/quotation/components/ViewGrantTable.vue'
)
const permissionApi = await optionalSource(
  '../src/modules/quotation/api/viewPermissions.ts'
)
const quotationApp = await optionalSource('../src/modules/quotation/App.vue')
const sidebar = await optionalSource('../src/components/layout/AppSidebar.vue')
const english = JSON.parse(
  await optionalSource('../src/modules/quotation/locales/en.json')
)
const chinese = JSON.parse(
  await optionalSource('../src/modules/quotation/locales/zh-CN.json')
)

test('permission API supports role assignment and role changes', () => {
  assert.match(permissionApi, /getMembershipContext/)
  assert.match(permissionApi, /assignMembership/)
  assert.match(permissionApi, /updateMembershipRole/)
  assert.match(permissionApi, /'\/memberships'/)
  assert.match(permissionApi, /`\/memberships\/\$\{id\}`/)
  assert.match(permissionApi, /method: 'PATCH'/)
})

test('permission page exposes a dedicated user permission section', () => {
  assert.match(permissionPage, /UserPermissionSection/)
  assert.match(userPermissionSection, /userPermissionsTitle/)
  assert.match(userPermissionSection, /quotation_admin/)
  assert.match(userPermissionSection, /quotation_user/)
  assert.match(userPermissionSection, /@click="assignRole/)
  assert.match(userPermissionSection, /@click="changeRole/)
})

test('view grants support create, expiry edit, status, and revocation', () => {
  assert.match(permissionApi, /expires_at\?: string \| null/)
  assert.match(permissionApi, /updateViewPermissionExpiry/)
  assert.match(viewGrantSection, /ViewGrantForm/)
  assert.match(viewGrantSection, /ViewGrantTable/)
  assert.match(viewGrantForm, /type="datetime-local"/)
  assert.match(viewGrantTable, /permission\.status === 'expired'/)
  assert.match(viewGrantTable, /@click="saveExpiry/)
  assert.match(viewGrantTable, /@click="revoke/)
})

test('access requests stay visible while management remains admin-only', () => {
  assert.match(quotationApp, /currentTab === 'permissions'/)
  assert.doesNotMatch(
    quotationApp,
    /currentTab === 'permissions' && isViewPermissionAdmin/
  )
  assert.doesNotMatch(sidebar, /v-if="quotationViewPermissionAdmin"/)
  assert.match(permissionPage, /<template v-if="isAdmin">/)
  assert.doesNotMatch(userPermissionSection, /v-html/)
  assert.doesNotMatch(viewGrantSection, /v-html/)
  assert.doesNotMatch(viewGrantForm, /v-html/)
  assert.doesNotMatch(viewGrantTable, /v-html/)
})

test('permission lifecycle copy is complete in both languages', () => {
  for (const copy of [
    english.quotation.pages.permissions,
    chinese.quotation.pages.permissions
  ]) {
    for (const key of [
      'userPermissionsTitle',
      'assignRole',
      'changeRole',
      'expiryLabel',
      'neverExpires',
      'expired',
      'saveExpiry',
      'editFailed'
    ]) {
      assert.equal(typeof copy[key], 'string')
      assert.notEqual(copy[key].trim(), '')
    }
  }
})

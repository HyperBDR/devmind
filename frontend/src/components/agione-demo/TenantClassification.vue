<template>
  <section class="tenant-management" :class="{ 'tenant-default-page': limit === 10, 'tenant-full-page': limit === 10 && rows.length === 10 && !loading }">
    <section class="panel tenant-toolbar" data-panel="scope">
      <div class="scope-toolbar">
      <input v-model="search" :aria-label="t('agione.tenant.searchAria')" :placeholder="t('agione.tenant.searchPlaceholder')" @keyup.enter="load(0)">
      <Listbox v-for="filter in filters" :key="filter.key"
        :model-value="filter.key === 'classification' ? classification : source"
        @update:model-value="setFilter(filter.key, $event)">
        <div class="tenant-select">
          <ListboxButton class="ui-select-trigger" :aria-label="filter.aria">
            <span>{{ filter.options.find(option => option.value === (filter.key === 'classification' ? classification : source))?.label }}</span>
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m6 8 4 4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
          </ListboxButton>
          <ListboxOptions class="ui-select-menu tenant-select-menu">
            <ListboxOption v-for="option in filter.options" :key="option.value" v-slot="{ selected }" as="button" type="button" :value="option.value">
              <span>{{ option.label }}</span>
              <svg v-if="selected" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m5 10 3 3 7-7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>
            </ListboxOption>
          </ListboxOptions>
        </div>
      </Listbox>
      <button @click="load(0)">{{ t('agione.tenant.query') }}</button>
      <div class="scope-groups">
        <button :disabled="loading" @click="load(offset, true)">{{ t('agione.tenant.refresh') }}</button>
      </div>
      </div>
      <div class="scope-bottom"><span>{{ t('agione.tenant.note') }}</span></div>
    </section>
    <section class="panel tenant-table" :aria-busy="loading">
      <div class="tenant-count">
        <h2 class="tenant-sr-only">{{ t('agione.tenant.title') }}</h2>
        <small v-if="!loading || refreshing">{{ t('agione.tenant.count', { count: total }) }}</small>
      </div>
      <p v-if="error" role="alert">{{ error }}</p>
      <p v-if="notice" role="status">{{ notice }}</p>
      <p v-if="refreshing" role="status">{{ t('agione.tenant.refreshingPrevious') }}</p>
      <div v-if="loading && !refreshing" class="tenant-loading" role="status" aria-live="polite">
        <span class="tenant-spinner" aria-hidden="true"></span>
        <strong>{{ t('agione.tenant.loadingTitle') }}</strong>
        <span>{{ t('agione.tenant.loadingHint') }}</span>
      </div>
      <div class="tenant-list-wrap" :inert="refreshing || null">
        <table class="tenant-list">
          <thead><tr><th scope="col">{{ t('agione.tenant.colTenant') }}</th><th scope="col">{{ t('agione.tenant.colType') }}</th><th scope="col">{{ t('agione.tenant.colSource') }}</th><th scope="col">{{ t('agione.tenant.colMetrics') }}</th><th scope="col"><span class="tenant-sr-only">{{ t('agione.tenant.details') }}</span></th></tr></thead>
          <tbody v-if="loading && !refreshing" aria-hidden="true">
            <tr v-for="index in 4" :key="index"><td v-for="column in 5" :key="column"><span v-if="column < 5" class="tenant-skeleton" :class="`tenant-skeleton-${column}`"></span></td></tr>
          </tbody>
          <tbody v-else-if="rows.length">
            <tr v-for="row in rows" :key="row.tenantId" class="tenant-row" tabindex="0"
              aria-haspopup="dialog" :aria-label="t('agione.tenant.rowAria', { name: row.name, type: label(row.classification) })"
              @click="openDrawer(row, $event)" @keydown.enter.self.prevent="openDrawer(row, $event)" @keydown.space.self.prevent="openDrawer(row, $event)">
              <td><div class="tenant-identity"><strong class="tenant-name" :title="row.name">{{ row.name }}</strong><small v-if="row.name !== row.tenantId" class="tenant-id">ID · {{ row.tenantId }}</small></div></td>
              <td><span class="tenant-classification" :class="`is-${row.classification}`"><span class="tenant-dot" aria-hidden="true"></span>{{ label(row.classification) }}</span></td>
              <td><span class="tenant-source">{{ row.source === 'manual' ? t('agione.tenant.manual') : t('agione.tenant.automatic') }}</span></td>
              <td><span class="tenant-inclusion">{{ row.included ? t('agione.tenant.included') : t('agione.tenant.excluded') }}</span></td>
              <td class="tenant-chevron" aria-hidden="true">›</td>
            </tr>
          </tbody>
        </table>
        <p v-if="!loading && !rows.length && !error" class="tenant-empty">{{ t('agione.tenant.empty') }}</p>
      </div>
      <div v-if="!loading" class="tenant-pages">
        <Listbox :model-value="limit" @update:model-value="setLimit">
          <div class="tenant-select tenant-page-size">
            <ListboxButton class="ui-select-trigger" :aria-label="t('agione.tenant.pageSizeAria')">
              <span>{{ t('agione.tenant.pageSize', { size: limit }) }}</span>
              <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m6 8 4 4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
            </ListboxButton>
            <ListboxOptions class="ui-select-menu tenant-select-menu tenant-page-menu">
              <ListboxOption v-for="size in [10, 20, 50, 100]" :key="size" v-slot="{ selected }" as="button" type="button" :value="size">
                <span>{{ t('agione.tenant.pageSize', { size }) }}</span>
                <svg v-if="selected" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m5 10 3 3 7-7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>
              </ListboxOption>
            </ListboxOptions>
          </div>
        </Listbox>
        <button :disabled="offset === 0 || loading" @click="load(Math.max(0, offset - limit))">{{ t('agione.tenant.previous') }}</button>
        <span>{{ total ? offset + 1 : 0 }}–{{ Math.min(offset + limit, total) }} / {{ total }}</span>
        <button :disabled="offset + limit >= total || loading" @click="load(offset + limit)">{{ t('agione.tenant.next') }}</button></div>
    </section>
    <dialog ref="drawer" id="tenant-classification-dialog"
      data-agione-dialog-id="tenant-classification-dialog"
      class="requests-dialog request-drawer tenant-drawer"
      aria-labelledby="tenant-drawer-title" @cancel.prevent="closeDrawer"
      @close="afterDrawerClose" @pointerdown="backdrop.onPointerDown"
      @click="backdrop.onClick" @pointercancel="backdrop.reset">
      <div class="dialog-head">
        <h2 id="tenant-drawer-title">{{ t('agione.tenant.drawerTitle') }}</h2>
        <button type="button" :aria-label="t('agione.tenant.close')" @click="closeDrawer">×</button>
      </div>
      <div data-agione-dialog-body class="tenant-drawer-body">
        <div v-if="selectedRow" class="request-content">
          <div class="drawer-group-summary">
            <small>{{ t('agione.tenant.tenantLabel') }}</small>
            <h3>{{ selectedRow.name }}</h3>
            <p>{{ t('agione.tenant.tenantId', { id: selectedRow.tenantId }) }}</p>
          </div>
          <div class="tenant-current">
            <div><small>{{ t('agione.tenant.currentType') }}</small><strong>{{ label(selectedRow.classification) }}</strong></div>
            <div><small>{{ t('agione.tenant.colSource') }}</small><strong>{{ selectedRow.source === 'manual' ? t('agione.tenant.manual') : t('agione.tenant.automatic') }}</strong></div>
            <div><small>{{ t('agione.tenant.colMetrics') }}</small><strong>{{ selectedRow.included ? t('agione.tenant.included') : t('agione.tenant.excluded') }}</strong></div>
          </div>
          <fieldset class="tenant-classification-options">
            <legend>{{ t('agione.tenant.changeType') }}</legend>
            <label><input v-model="draft" type="radio" value="external"> {{ t('agione.tenant.external') }}</label>
            <label><input v-model="draft" type="radio" value="internal"> {{ t('agione.tenant.internal') }}</label>
            <label><input v-model="draft" type="radio" value="automatic"> {{ t('agione.tenant.restoreAutomatic') }}</label>
          </fieldset>
          <p class="tenant-drawer-hint">{{ t('agione.tenant.drawerHint') }}</p>
          <p v-if="drawerError" role="alert" class="tenant-drawer-error">{{ drawerError }}</p>
        </div>
        <div class="request-footer tenant-drawer-footer">
          <button type="button" @click="closeDrawer">{{ t('agione.tenant.cancel') }}</button>
          <button class="primary" type="button" :disabled="saving || !selectedRow" @click="save">{{ saving ? t('agione.tenant.saving') : t('agione.tenant.save') }}</button>
        </div>
      </div>
    </dialog>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Listbox, ListboxButton, ListboxOption, ListboxOptions } from '@headlessui/vue'
import { agioneOpsApi } from '@/api/agioneOps'
import { claimOriginalDialog, createDialogBackdropDismiss, releaseOriginalDialog } from '@/utils/agioneDialog'
const { t } = useI18n({ useScope: 'global' })
const props = defineProps({ connectionId: { type: String, default: '' } })
const emit = defineEmits(['changed'])
const rows = ref([]), total = ref(0), offset = ref(0), limit = ref(10)
const version = ref(''), search = ref(''), classification = ref(''), source = ref('')
const loading = ref(false), refreshing = ref(false), saving = ref(false), error = ref(''), notice = ref('')
const drawer = ref(null), selectedRow = ref(null), draft = ref('automatic')
const drawerError = ref(''), selectedVersion = ref('')
let returnFocus = null
const backdrop = createDialogBackdropDismiss(() => closeDrawer())
async function openDrawer(row, event) {
  if (saving.value) return
  returnFocus = event.currentTarget
  selectedRow.value = { ...row }
  selectedVersion.value = version.value
  draft.value = row.source === 'manual' ? row.classification : 'automatic'
  drawerError.value = ''
  await nextTick()
  if (!drawer.value || !selectedRow.value || drawer.value.open) return
  claimOriginalDialog(drawer.value)
  drawer.value.showModal()
}
function closeDrawer() {
  if (saving.value) return
  if (drawer.value?.open) drawer.value.close()
  else afterDrawerClose()
}
function afterDrawerClose() {
  backdrop.reset()
  releaseOriginalDialog(drawer.value)
  selectedRow.value = null
  drawerError.value = ''
  if (returnFocus?.isConnected) returnFocus.focus()
  returnFocus = null
}
onBeforeUnmount(() => {
  backdrop.reset()
  releaseOriginalDialog(drawer.value, { force: true })
})
const filters = computed(() => [
  { key: 'classification', aria: t('agione.tenant.filterTypeAria'), options: [
    { value: '', label: t('agione.tenant.allTypes') },
    { value: 'internal', label: t('agione.tenant.typeInternal') },
    { value: 'external', label: t('agione.tenant.typeExternal') },
    { value: 'unknown', label: t('agione.tenant.typeUnknown') }
  ] },
  { key: 'source', aria: t('agione.tenant.filterSourceAria'), options: [
    { value: '', label: t('agione.tenant.allSources') },
    { value: 'automatic', label: t('agione.tenant.automatic') },
    { value: 'manual', label: t('agione.tenant.manual') }
  ] }
])
function setFilter(key, value) {
  if (key === 'classification') classification.value = value
  else source.value = value
  load(0)
}
function setLimit(value) {
  limit.value = value
  load(0)
}
let sequence = 0
const label = (value) => ({
  internal: t('agione.tenant.typeInternal'),
  external: t('agione.tenant.typeExternal'),
  unknown: t('agione.tenant.typeUnknown')
})[value] || t('agione.tenant.typeUnknown')
async function load(next = 0, refresh = false) {
  const id = props.connectionId, current = ++sequence
  if (!id) { rows.value = []; total.value = 0; return }
  refreshing.value = refresh && rows.value.length > 0 && next === offset.value
  loading.value = true; error.value = ''
  try {
    const response = await agioneOpsApi.tenantClassifications(id, {
      search: search.value, classification: classification.value,
      source: source.value, limit: limit.value, offset: next, ...(refresh ? { refresh: 1 } : {})
    })
    if (current !== sequence) return
    const data = response.data.data
    rows.value = data.results; total.value = data.count; offset.value = data.offset
    version.value = data.version
  } catch (e) {
    if (current === sequence) {
      if ([401, 403, 404].includes(e?.response?.status)) {
        rows.value = []; total.value = 0; version.value = ''
      }
      error.value = t('agione.tenant.loadFailed')
    }
  } finally {
    if (current === sequence) { loading.value = false; refreshing.value = false }
  }
}
async function save() {
  const row = selectedRow.value
  if (!row || saving.value) return
  const id = props.connectionId
  saving.value = true; drawerError.value = ''; notice.value = ''
  try {
    const response = await agioneOpsApi.updateTenantClassification(id, {
      tenantId: row.tenantId, classification: draft.value, version: selectedVersion.value
    })
    if (id === props.connectionId) {
      const data = response.data.data
      version.value = data.version
      const next = {
        ...row,
        classification: data.classification,
        source: data.source,
        included: data.included
      }
      const matches = (
        !classification.value || classification.value === next.classification
      ) && (!source.value || source.value === next.source)
      if (matches)
        rows.value = rows.value.map((item) =>
          item.tenantId === next.tenantId ? next : item
        )
      else {
        rows.value = rows.value.filter(
          (item) => item.tenantId !== next.tenantId
        )
        total.value = Math.max(0, total.value - 1)
      }
      saving.value = false
      closeDrawer()
      emit('changed')
      notice.value = t('agione.tenant.saved')
    }
  } catch (e) {
    drawerError.value = e?.response?.status === 409
      ? t('agione.tenant.saveConflict') : t('agione.tenant.saveFailed')
  } finally { saving.value = false }
}
watch(() => props.connectionId, () => {
  if (drawer.value?.open) drawer.value.close()
  rows.value = []; total.value = 0; version.value = ''; notice.value = ''
  load(0)
}, { immediate: true })
</script>

<style scoped>
:global(.agione-demo.tenant-page .workspace){display:flex;flex-direction:column;min-height:100dvh}
:global(.agione-demo.tenant-page .main){display:flex;flex:1;flex-direction:column;width:100%;box-sizing:border-box}
.tenant-management{display:flex;flex:1;flex-direction:column;min-width:0}
.tenant-table{display:flex;flex:1;flex-direction:column;padding:18px 20px;margin-bottom:0}
.tenant-count{display:flex;justify-content:flex-end;align-items:center;min-height:20px;margin-bottom:8px;color:var(--muted);font-size:13px}
.tenant-toolbar input{width:240px;min-width:0;padding:7px 11px;font-size:14px}
.tenant-toolbar :deep(.ui-select-trigger){font-size:14px}
.tenant-toolbar .scope-toolbar button{font-size:14px}
.tenant-toolbar .scope-bottom{font-size:13px}
.tenant-toolbar input,.tenant-toolbar .scope-toolbar > button,.tenant-toolbar .scope-groups > button,.tenant-toolbar :deep(.ui-select-trigger){box-sizing:border-box;height:36px;min-height:36px;line-height:20px}
.tenant-select{position:relative;min-width:112px}
.tenant-management .tenant-select-menu{position:absolute;top:calc(100% + 6px);left:0;width:100%;max-height:260px}
.tenant-management .tenant-page-menu{top:auto;right:0;bottom:calc(100% + 6px);left:auto;min-width:150px}
.tenant-page-menu :deep([role=option] > span){white-space:nowrap}
.tenant-list-wrap{width:100%;overflow-x:auto}
.tenant-full-page .tenant-list-wrap{display:flex;flex:1;flex-direction:column}
.tenant-management.tenant-full-page .tenant-list{flex:1}
.tenant-management .tenant-list{width:100%;min-width:620px;table-layout:fixed;border-collapse:collapse}
.tenant-management .tenant-list th{padding:10px 14px;color:var(--muted);font-size:12px;font-weight:500;background:var(--bg)}
.tenant-list th:first-child{width:47%;border-radius:6px 0 0 6px}.tenant-list th:last-child{width:36px;border-radius:0 6px 6px 0}
.tenant-management .tenant-list td{padding:10px 14px;color:var(--ink);font-size:14px;border-bottom:1px solid var(--line)}
.tenant-row{cursor:pointer;transition:background-color .15s ease}.tenant-row:hover,.tenant-row:focus-visible{background:var(--soft)}
.tenant-row:focus-visible{outline:2px solid var(--blue);outline-offset:-2px}
.tenant-identity{display:flex;align-items:baseline;gap:12px;min-width:0}
.tenant-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px;font-weight:600}.tenant-id{flex:none;font-size:12px;color:var(--muted);white-space:nowrap}
.tenant-classification{display:inline-flex;align-items:center;gap:7px;font-size:13px;color:var(--muted)}
.tenant-dot{width:7px;height:7px;border-radius:50%;background:#a6b2c3}.tenant-classification.is-external{color:#19735b}.tenant-classification.is-external .tenant-dot{background:#36a17c}.tenant-classification.is-internal{color:#536781}.tenant-classification.is-internal .tenant-dot{background:#748aa4}
.tenant-source{color:var(--muted);font-size:13px}.tenant-inclusion{font-size:13px}
.tenant-management .tenant-list .tenant-chevron{text-align:right;color:#a1aec0;font-size:21px;line-height:1}.tenant-row:hover .tenant-chevron{color:var(--blue)}
.tenant-sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
.tenant-empty{padding:28px 0;text-align:center;color:var(--muted);font-size:13px}
.tenant-loading{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:2px 12px 22px;text-align:center;color:var(--muted);font-size:12px}
.tenant-loading strong{color:var(--ink);font-size:14px;font-weight:600}
.tenant-spinner{width:24px;height:24px;border:2px solid #d9e5fb;border-top-color:var(--blue);border-radius:50%;animation:tenant-spin .8s linear infinite}
.tenant-skeleton{display:block;height:14px;width:65%;max-width:150px;border-radius:4px;background:#e8edf3;animation:tenant-pulse 1.5s ease-in-out infinite}
.tenant-skeleton-1{width:75%;max-width:240px}
@keyframes tenant-spin{to{transform:rotate(360deg)}}
@keyframes tenant-pulse{50%{opacity:.45}}
@media(prefers-reduced-motion:reduce){.tenant-spinner,.tenant-skeleton{animation:none}}
.tenant-pages{display:flex;justify-content:flex-end;gap:8px;align-items:center;margin-top:auto;padding-top:14px;color:var(--muted);font-size:13px}
.tenant-pages > button{font-size:12px;padding:6px 10px}
.tenant-drawer .dialog-head button{width:34px;height:34px;padding:0;border:0;background:var(--bg);color:var(--muted);font-size:25px;line-height:1}
:global(.agione-demo #dialog.requests-dialog.request-drawer.tenant-drawer){width:min(520px,100vw);max-width:100vw}
.tenant-drawer-body{display:flex;flex:1;flex-direction:column;min-height:0}
.tenant-drawer .request-content{padding:24px;overflow:auto}
.tenant-drawer .drawer-group-summary h3{font-size:20px;font-weight:600;line-height:1.5}
:global(.agione-demo #dialog.request-drawer.tenant-drawer) .drawer-group-summary > small,:global(.agione-demo #dialog.request-drawer.tenant-drawer) .drawer-group-summary > p{font-size:13px;line-height:1.6}
.tenant-current{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;padding:16px;background:var(--bg);border-radius:8px}
.tenant-current div{display:flex;flex-direction:column;gap:7px}.tenant-current small{color:var(--muted);font-size:13px;line-height:1.5}.tenant-current strong{font-size:15px;font-weight:600;line-height:1.5}
.tenant-classification-options{border:0;margin:24px 0 0;padding:0}.tenant-classification-options legend{font-size:15px;font-weight:600;margin-bottom:14px}.tenant-classification-options label{display:flex;align-items:center;gap:12px;padding:10px 0;font-size:15px;line-height:1.7;cursor:pointer}.tenant-classification-options input{appearance:none;-webkit-appearance:none;box-sizing:border-box;width:18px;height:18px;aspect-ratio:1;flex:none;margin:0;border:1.5px solid #b6c2d2;border-radius:50%;background:#fff;cursor:pointer;transition:border-color .15s,box-shadow .15s}
.tenant-classification-options input:hover{border-color:#8fa3bd}
.tenant-classification-options input:checked{border:5px solid var(--blue);background:#fff}
.tenant-classification-options input:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.tenant-drawer-hint{font-size:13px;line-height:1.6;color:var(--muted);margin-top:14px}.tenant-drawer-error{color:var(--red);font-size:13px;margin-top:14px}
.tenant-drawer-footer{display:flex;justify-content:flex-end;gap:10px}
@media(max-width:650px){.tenant-toolbar input{flex:1 1 180px;max-width:100%}.tenant-toolbar .scope-groups{margin-left:0}.tenant-toolbar input,.tenant-toolbar .scope-toolbar > button,.tenant-toolbar .scope-groups > button,.tenant-toolbar :deep(.ui-select-trigger){height:38px;min-height:38px}}
@media(max-width:650px){.tenant-pages{flex-wrap:wrap}.tenant-current{gap:8px;padding:12px}.tenant-drawer .request-content{padding:16px}}
@media(max-height:850px) and (min-width:651px){.tenant-default-page .tenant-table{padding-top:12px;padding-bottom:12px}.tenant-default-page .tenant-list td{padding-top:6px;padding-bottom:6px}.tenant-default-page .tenant-pages{padding-top:8px}}
</style>

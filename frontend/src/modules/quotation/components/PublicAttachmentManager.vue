<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ArchiveRestore, FileText, Plus, UploadCloud, X } from 'lucide-vue-next'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import {
  listPublicAttachments,
  uploadPublicAttachment,
  updatePublicAttachmentStatus,
  type PublicAttachment,
} from '../api/publicAttachments'

const props = defineProps<{ isAdmin: boolean }>()
const { t } = useQuotationI18n()
const attachments = ref<PublicAttachment[]>([])
const loading = ref(true)
const uploading = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const uploadDialogOpen = ref(false)
const pendingFile = ref<File | null>(null)
const attachmentScope = ref('')
const attachmentProductLine = ref('')
const attachmentServiceName = ref('')
const uploadError = ref('')

async function load() {
  loading.value = true
  try {
    attachments.value = await listPublicAttachments()
  } finally {
    loading.value = false
  }
}

async function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  pendingFile.value = file
  attachmentScope.value = ''
  attachmentProductLine.value = ''
  attachmentServiceName.value = ''
  uploadError.value = ''
  uploadDialogOpen.value = true
}

function closeUploadDialog(force = false) {
  if (uploading.value && !force) return
  uploadDialogOpen.value = false
  pendingFile.value = null
  uploadError.value = ''
}

function requestCloseUploadDialog() {
  closeUploadDialog()
}

async function submitUpload() {
  const file = pendingFile.value
  const scope = attachmentScope.value.trim()
  if (!file) return
  if (!scope) {
    uploadError.value = t('quotation.pages.catalog.attachmentScopeRequired')
    return
  }

  uploadError.value = ''
  uploading.value = true
  try {
    await uploadPublicAttachment(file, {
      scope,
      productLine: attachmentProductLine.value.trim(),
      serviceName: attachmentServiceName.value.trim(),
    })
    closeUploadDialog(true)
    await load()
  } catch (error) {
    uploadError.value =
      error instanceof Error
        ? error.message
        : t('quotation.pages.catalog.attachmentUploadFailed')
  } finally {
    uploading.value = false
  }
}

async function toggleStatus(item: PublicAttachment) {
  const status = item.status === 'active' ? 'archived' : 'active'
  try {
    const updated = await updatePublicAttachmentStatus(item.id, status)
    item.status = updated.status
  } catch (error) {
    window.alert(error instanceof Error ? error.message : 'Update failed')
  }
}

function formatSize(size: number) {
  return size >= 1024 * 1024
    ? `${(size / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(size / 1024))} KB`
}

onMounted(load)
</script>

<template>
  <div class="min-w-0">
    <div class="flex flex-col gap-3 border-b border-dm-border-light px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h3 class="text-base font-bold text-dm-text">{{ t('quotation.pages.catalog.publicAttachmentsTitle') }}</h3>
        <p class="mt-0.5 text-sm text-dm-text-tertiary">{{ t('quotation.pages.catalog.publicAttachmentsSubtitle') }}</p>
      </div>
      <template v-if="props.isAdmin">
        <input
          ref="fileInput"
          type="file"
          accept=".pdf,.doc,.docx,.xls,.xlsx"
          class="hidden"
          @change="handleFileChange"
        />
        <button type="button" class="dm-btn-primary h-9 shrink-0 px-4 text-sm font-semibold" :disabled="uploading" @click="fileInput?.click()">
          <Plus class="h-4 w-4" />{{ uploading ? t('quotation.common.uploading') : t('quotation.pages.catalog.uploadAttachment') }}
        </button>
      </template>
    </div>
    <div v-if="loading" class="p-6 text-sm text-dm-text-tertiary">{{ t('quotation.common.loading') }}</div>
    <div v-else-if="!attachments.length" class="p-8 text-center text-sm text-dm-text-tertiary">{{ t('quotation.pages.catalog.noPublicAttachments') }}</div>
    <div v-else class="overflow-x-auto text-sm">
      <table class="w-full text-left">
        <thead><tr class="border-b border-dm-border-light bg-[#fafafa] text-xs font-bold uppercase text-dm-text-tertiary"><th class="px-4 py-2.5">{{ t('quotation.pages.catalog.attachmentFile') }}</th><th class="px-4 py-2.5">{{ t('quotation.pages.catalog.attachmentScope') }}</th><th class="px-4 py-2.5">{{ t('quotation.pages.catalog.attachmentUploadedBy') }}</th><th class="px-4 py-2.5">{{ t('quotation.pages.catalog.attachmentStatus') }}</th><th v-if="props.isAdmin" class="px-4 py-2.5 text-right">{{ t('quotation.pages.catalog.tableActions') }}</th></tr></thead>
        <tbody class="divide-y divide-slate-50">
          <tr v-for="item in attachments" :key="item.id" class="hover:bg-[#fafafa]/40">
            <td class="px-4 py-3"><div class="flex items-center gap-2"><FileText class="h-4 w-4 text-rose-500" /><div><p class="font-semibold text-dm-text">{{ item.file_name }}</p><p class="mt-0.5 text-xs text-dm-text-tertiary">{{ formatSize(item.size_bytes) }}</p></div></div></td>
            <td class="px-4 py-3 text-dm-text-secondary">{{ item.scope }}</td>
            <td class="px-4 py-3 text-xs text-dm-text-tertiary">{{ item.uploaded_by }}<br>{{ item.created_at.slice(0, 10) }}</td>
            <td class="px-4 py-3"><span class="rounded-full px-2 py-1 text-xs font-semibold" :class="item.status === 'active' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'">{{ item.status === 'active' ? t('quotation.pages.catalog.active') : t('quotation.pages.catalog.archived') }}</span></td>
            <td v-if="props.isAdmin" class="px-4 py-3 text-right"><button type="button" class="inline-flex items-center gap-1 text-xs font-semibold text-dm-primary" @click="toggleStatus(item)"><ArchiveRestore class="h-3.5 w-3.5" />{{ item.status === 'active' ? t('quotation.pages.catalog.archive') : t('quotation.pages.catalog.restore') }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <Teleport to="body">
      <div
        v-if="uploadDialogOpen"
        class="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-[2px]"
        role="presentation"
        @click.self="requestCloseUploadDialog"
      >
        <form
          class="w-full max-w-lg overflow-hidden rounded-xl border border-dm-border-light bg-white shadow-2xl"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="'public-attachment-upload-title'"
          @submit.prevent="submitUpload"
        >
          <div class="flex items-start justify-between border-b border-dm-border-light px-5 py-4">
            <div>
              <h2 id="public-attachment-upload-title" class="text-lg font-bold text-dm-text">
                {{ t('quotation.pages.catalog.publicAttachmentUploadTitle') }}
              </h2>
              <p class="mt-1 text-sm text-dm-text-tertiary">
                {{ t('quotation.pages.catalog.publicAttachmentUploadDescription') }}
              </p>
            </div>
            <button
              type="button"
              class="rounded-md p-1.5 text-dm-text-tertiary transition hover:bg-slate-100 hover:text-dm-text"
              :aria-label="t('quotation.common.close')"
              :disabled="uploading"
              @click="requestCloseUploadDialog"
            >
              <X class="h-5 w-5" />
            </button>
          </div>

          <div class="space-y-4 p-5">
            <div class="flex items-center gap-3 rounded-lg border border-blue-100 bg-blue-50/60 px-3.5 py-3">
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-dm-primary shadow-sm">
                <FileText class="h-5 w-5" />
              </div>
              <div class="min-w-0">
                <p class="truncate text-sm font-semibold text-dm-text">
                  {{ pendingFile?.name }}
                </p>
                <p class="mt-0.5 text-xs text-dm-text-tertiary">
                  {{ pendingFile ? formatSize(pendingFile.size) : '' }}
                </p>
              </div>
            </div>

            <label class="block">
              <span class="mb-1.5 block text-sm font-semibold text-dm-text">
                {{ t('quotation.pages.catalog.attachmentScopeLabel') }}
                <span class="text-rose-500">*</span>
              </span>
              <input
                v-model="attachmentScope"
                class="catalog-input"
                :placeholder="t('quotation.pages.catalog.attachmentScopePlaceholder')"
                maxlength="255"
                autofocus
              />
              <span class="mt-1.5 block text-xs text-dm-text-tertiary">
                {{ t('quotation.pages.catalog.attachmentScopeHint') }}
              </span>
            </label>

            <div class="grid gap-4 sm:grid-cols-2">
              <label class="block">
                <span class="mb-1.5 block text-sm font-semibold text-dm-text">
                  {{ t('quotation.pages.catalog.attachmentProductLineLabel') }}
                  <span class="font-normal text-dm-text-tertiary">({{ t('quotation.common.optional') }})</span>
                </span>
                <input
                  v-model="attachmentProductLine"
                  class="catalog-input"
                  :placeholder="t('quotation.pages.catalog.attachmentProductLinePlaceholder')"
                  maxlength="120"
                />
              </label>
              <label class="block">
                <span class="mb-1.5 block text-sm font-semibold text-dm-text">
                  {{ t('quotation.pages.catalog.attachmentServiceNameLabel') }}
                  <span class="font-normal text-dm-text-tertiary">({{ t('quotation.common.optional') }})</span>
                </span>
                <input
                  v-model="attachmentServiceName"
                  class="catalog-input"
                  :placeholder="t('quotation.pages.catalog.attachmentServiceNamePlaceholder')"
                  maxlength="255"
                />
              </label>
            </div>

            <p class="text-xs leading-5 text-dm-text-tertiary">
              <UploadCloud class="mr-1 inline h-3.5 w-3.5 align-text-bottom" />
              {{ t('quotation.pages.catalog.attachmentUploadHint') }}
            </p>
            <p
              v-if="uploadError"
              class="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700"
              role="alert"
            >
              {{ uploadError }}
            </p>
          </div>

          <div class="flex items-center justify-end gap-2 border-t border-dm-border-light bg-slate-50 px-5 py-4">
            <button
              type="button"
              class="rounded-lg border border-dm-border bg-white px-4 py-2 text-sm font-semibold text-dm-text transition hover:bg-slate-100"
              :disabled="uploading"
              @click="requestCloseUploadDialog"
            >
              {{ t('quotation.common.cancel') }}
            </button>
            <button
              type="submit"
              class="dm-btn-primary px-4 py-2 text-sm font-semibold"
              :disabled="uploading"
            >
              <UploadCloud class="h-4 w-4" />
              {{ uploading ? t('quotation.common.uploading') : t('quotation.pages.catalog.confirmUploadAttachment') }}
            </button>
          </div>
        </form>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.catalog-input {
  @apply h-9 w-full rounded-lg border border-dm-border bg-white px-3 text-sm text-dm-text outline-none transition focus:border-dm-primary focus:ring-2 focus:ring-blue-100;
}
</style>

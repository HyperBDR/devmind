<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { Download, FileSpreadsheet, FileText, Loader2 } from 'lucide-vue-next'
import {
  downloadImportedDocument,
  fetchImportedDocumentBlob,
  type ImportedDocument,
} from '../api/documents'

const props = defineProps<{
  doc: ImportedDocument | null
}>()

const emit = defineEmits<{
  toast: [message: string, type?: 'success' | 'info' | 'error']
}>()

const loading = ref(false)
const error = ref('')
const pdfUrl = ref<string | null>(null)
const downloading = ref(false)
let loadToken = 0

function isPdfDoc(doc: ImportedDocument): boolean {
  const type = (doc.doc_type || '').toLowerCase()
  const name = (doc.file_name || '').toLowerCase()
  const mime = (doc.mime_type || '').toLowerCase()
  return type === 'pdf' || name.endsWith('.pdf') || mime.includes('pdf')
}

function isExcelDoc(doc: ImportedDocument): boolean {
  const type = (doc.doc_type || '').toLowerCase()
  const name = (doc.file_name || '').toLowerCase()
  const mime = (doc.mime_type || '').toLowerCase()
  return (
    type === 'excel' ||
    name.endsWith('.xlsx') ||
    name.endsWith('.xls') ||
    mime.includes('spreadsheet') ||
    mime.includes('excel')
  )
}

function revokePdfUrl() {
  if (pdfUrl.value) {
    URL.revokeObjectURL(pdfUrl.value)
    pdfUrl.value = null
  }
}

watch(
  () => props.doc?.id,
  async (id) => {
    const token = ++loadToken
    error.value = ''
    revokePdfUrl()

    const doc = props.doc
    if (!id || !doc || !isPdfDoc(doc)) return

    loading.value = true
    try {
      const blob = await fetchImportedDocumentBlob(doc.id)
      if (token !== loadToken) return
      pdfUrl.value = URL.createObjectURL(blob)
    } catch (err: unknown) {
      if (token !== loadToken) return
      error.value = err instanceof Error ? err.message : 'PDF 预览加载失败'
    } finally {
      if (token === loadToken) loading.value = false
    }
  },
)

onBeforeUnmount(() => {
  loadToken += 1
  revokePdfUrl()
})

async function handleDownload() {
  if (!props.doc) return
  downloading.value = true
  try {
    await downloadImportedDocument(props.doc.id, props.doc.file_name)
    emit('toast', `已开始下载 ${props.doc.file_name}`, 'success')
  } catch (err: unknown) {
    emit('toast', err instanceof Error ? err.message : '下载失败', 'error')
  } finally {
    downloading.value = false
  }
}
</script>

<template>
  <div
    v-if="!doc"
    class="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 px-6 text-center"
  >
    <FileText class="h-8 w-8 text-slate-300" />
    <p class="mt-3 text-sm font-semibold text-slate-700">选择左侧文件</p>
    <p class="mt-1 text-[11px] text-slate-400">PDF 可在右侧全高预览；Excel 请下载后查看。</p>
  </div>

  <div
    v-else-if="isExcelDoc(doc) && !isPdfDoc(doc)"
    class="flex h-full flex-col overflow-hidden rounded-xl border border-slate-100 bg-white shadow-xs"
  >
    <div class="shrink-0 border-b border-slate-100 px-4 py-3">
      <div class="flex items-center gap-2">
        <FileSpreadsheet class="h-4 w-4 shrink-0 text-emerald-600" />
        <h3 class="truncate text-xs font-bold text-slate-800" :title="doc.file_name">
          {{ doc.file_name }}
        </h3>
      </div>
      <p class="mt-0.5 text-[10px] text-slate-400">Excel 不支持在线预览</p>
    </div>
    <div class="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
      <FileSpreadsheet class="h-10 w-10 text-slate-300" />
      <p class="text-sm font-semibold text-slate-700">请下载后用 Excel / WPS 打开</p>
      <p class="max-w-sm text-[11px] text-slate-400">Excel 仅提供下载，不在页面内预览。</p>
      <button
        type="button"
        class="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        :disabled="downloading"
        @click="handleDownload"
      >
        <Loader2 v-if="downloading" class="h-3.5 w-3.5 animate-spin" />
        <Download v-else class="h-3.5 w-3.5" />
        下载 Excel
      </button>
    </div>
  </div>

  <div
    v-else-if="!isPdfDoc(doc)"
    class="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 px-6 text-center"
  >
    <p class="text-sm font-semibold text-slate-700">暂不支持该类型预览</p>
    <button
      type="button"
      class="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
      @click="handleDownload"
    >
      <Download class="h-3.5 w-3.5" />
      下载文件
    </button>
  </div>

  <div
    v-else
    class="flex h-full flex-col overflow-hidden rounded-xl border border-slate-100 bg-white shadow-xs"
  >
    <div class="flex shrink-0 items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <FileText class="h-4 w-4 shrink-0 text-rose-500" />
          <h3 class="truncate text-xs font-bold text-slate-800" :title="doc.file_name">
            {{ doc.file_name }}
          </h3>
        </div>
        <p class="mt-0.5 text-[10px] text-slate-400">PDF 全高预览 · 只读</p>
      </div>
      <button
        type="button"
        class="inline-flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        :disabled="downloading"
        @click="handleDownload"
      >
        <Loader2 v-if="downloading" class="h-3.5 w-3.5 animate-spin" />
        <Download v-else class="h-3.5 w-3.5" />
        下载
      </button>
    </div>

    <div class="relative min-h-0 flex-1 bg-slate-100">
      <div
        v-if="loading"
        class="absolute inset-0 flex items-center justify-center gap-2 text-sm text-slate-500"
      >
        <Loader2 class="h-4 w-4 animate-spin" />
        正在加载 PDF…
      </div>
      <div
        v-else-if="error"
        class="m-4 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-[11px] text-red-600"
      >
        {{ error }}
      </div>
      <iframe
        v-else-if="pdfUrl"
        :title="`preview-${doc.id}`"
        :src="`${pdfUrl}#view=FitH`"
        class="absolute inset-0 h-full w-full border-0 bg-white"
      />
      <div
        v-else
        class="absolute inset-0 flex items-center justify-center text-[11px] text-slate-400"
      >
        暂无预览内容
      </div>
    </div>
  </div>
</template>

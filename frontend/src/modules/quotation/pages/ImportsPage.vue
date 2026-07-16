<script setup lang="ts">
import { ref } from 'vue'
import ImportedDocumentsPage from '../components/ImportedDocumentsPage.vue'

const toast = ref<{ message: string; type: string } | null>(null)
let toastTimer: number | undefined

function showToast(message: string, type: 'success' | 'info' | 'error' = 'info') {
  toast.value = { message, type }
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toast.value = null
  }, 4000)
}
</script>

<template>
  <div>
    <div
      v-if="toast"
      class="fixed right-6 top-6 z-50 rounded-lg px-4 py-2 text-sm font-medium shadow-lg"
      :class="{
        'bg-emerald-600 text-white': toast.type === 'success',
        'bg-slate-800 text-white': toast.type === 'info',
        'bg-red-600 text-white': toast.type === 'error',
      }"
    >
      {{ toast.message }}
    </div>

    <ImportedDocumentsPage @toast="showToast" />
  </div>
</template>

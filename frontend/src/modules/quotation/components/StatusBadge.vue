<script setup lang="ts">
import { quoteStatusBadgeClass } from '../utils/quoteStatus'
import { useQuotationI18n } from '../composables/useQuotationI18n'
import type { QuoteStatus } from '../types'

defineProps<{
  status: QuoteStatus
}>()

const { quoteStatusLabel } = useQuotationI18n()
</script>

<template>
  <span :class="quoteStatusBadgeClass(status)">
    {{ quoteStatusLabel(status) }}
  </span>
</template>

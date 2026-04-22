<template>
  <div
    class="bg-white rounded-lg border border-gray-200 shadow-sm active:bg-gray-50 transition-colors"
    @click="handleViewDetails"
  >
    <div class="p-4">
      <!-- Alert Time and Webhook Status -->
      <div class="flex items-center justify-between mb-3">
        <span
          :class="getWebhookStatusClass(alert.webhook_status)"
          class="px-2 py-1 text-xs font-semibold rounded-full"
        >
          {{ getWebhookStatusLabel(alert.webhook_status) }}
        </span>
        <span class="text-xs text-gray-500">
          {{ formatDate(alert.created_at) }}
        </span>
      </div>

      <!-- Provider and Cost Info -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-500">{{
            t('cloudBilling.alerts.provider')
          }}</span>
          <span class="text-sm font-medium text-gray-900">
            {{ alert.provider_label || alert.provider_name || alert.provider }}
          </span>
        </div>
        <div class="space-y-1 text-xs text-gray-600">
          <div>
            <span class="font-medium"
              >{{ t('cloudBilling.alerts.currentCost') }}:</span
            >
            {{ formatCurrency(alert.current_cost, alert.currency) }}
          </div>
          <div>
            <span class="font-medium"
              >{{ t('cloudBilling.alerts.increase') }}:</span
            >
            {{ formatCurrency(alert.increase_cost, alert.currency) }} ({{
              alert.increase_percent
            }}%)
          </div>
        </div>
        <div v-if="alert.alert_message" class="mt-2">
          <p class="text-sm text-gray-700 line-clamp-2">
            {{ alert.alert_message }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'

const props = defineProps({
  alert: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['view'])

const { t } = useI18n()

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
  } catch {
    return dateString
  }
}

const formatCurrency = (value, currency = 'CNY') => {
  if (!value && value !== 0) return '-'
  const currencySymbols = {
    CNY: '¥',
    USD: '$',
    EUR: '€'
  }
  const symbol = currencySymbols[currency] || currency
  return `${symbol}${Number(value).toFixed(2)}`
}

const getWebhookStatusClass = (status) => {
  const statusClasses = {
    pending: 'bg-yellow-100 text-yellow-800',
    success: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800'
  }
  return statusClasses[status] || 'bg-gray-100 text-gray-800'
}

const getWebhookStatusLabel = (status) => {
  const statusLabels = {
    pending: t('cloudBilling.alerts.webhookStatusLabels.pending'),
    success: t('cloudBilling.alerts.webhookStatusLabels.success'),
    failed: t('cloudBilling.alerts.webhookStatusLabels.failed')
  }
  return statusLabels[status] || status
}

const handleViewDetails = () => {
  emit('view', props.alert)
}
</script>

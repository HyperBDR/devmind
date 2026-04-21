<template>
  <div
    class="bg-white rounded-lg border border-gray-200 shadow-sm active:bg-gray-50 transition-colors"
    @click="handleViewDetails"
  >
    <div class="p-4">
      <!-- Provider and Collection Time -->
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-gray-900">
          {{ providerDisplayName }}
        </h3>
        <span class="text-xs text-gray-500">
          {{ formatDate(billing.collection_time) }}
        </span>
      </div>

      <!-- Cost and Change -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <span class="text-xs text-gray-500">{{
            t('cloudBilling.billing.cost')
          }}</span>
          <span class="text-lg font-semibold text-gray-900">
            {{ formatCost(billing.cost) }}
          </span>
        </div>
        <div
          v-if="
            billing.change_from_last_hour !== null &&
            billing.change_from_last_hour !== undefined
          "
          class="flex items-center justify-between"
        >
          <span class="text-xs text-gray-500">{{
            t('cloudBilling.billing.changeFromLastHour')
          }}</span>
          <span
            :class="getChangeClass(billing.change_from_last_hour)"
            class="text-sm font-medium"
          >
            {{ formatChange(billing.change_from_last_hour) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  formatCost,
  formatChange,
  formatDate,
  getChangeClass
} from '@/utils/formatting'
import { getLocalizedBillingProviderName } from '@/utils/providerDisplay'

const props = defineProps({
  billing: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['view'])

const { t } = useI18n()
const providerDisplayName = computed(() =>
  getLocalizedBillingProviderName(props.billing, t)
)

const handleViewDetails = () => {
  emit('view', props.billing)
}
</script>

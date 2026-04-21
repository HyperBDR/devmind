<template>
  <BaseModal
    :show="show"
    :title="t('cloudBilling.settings.alertRule.title')"
    @close="$emit('close')"
  >
    <form @submit.prevent="handleSubmit" class="space-y-4">
      <p class="text-xs text-gray-600 mb-4">
        {{
          t('cloudBilling.settings.alertRule.subtitle', {
            provider: providerName
          })
        }}
      </p>

      <!-- Enable Alert Rule -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
        <div class="md:col-span-1">
          <label
            for="isActive"
            class="block text-sm font-medium text-gray-700 mb-1"
          >
            {{ t('cloudBilling.settings.alertRule.enable') }}
          </label>
          <p class="text-xs text-gray-500 mb-2 md:mb-0">
            {{ t('cloudBilling.settings.alertRule.enableDesc') }}
          </p>
        </div>
        <div class="md:col-span-2">
          <label class="relative inline-flex items-center cursor-pointer">
            <input
              id="isActive"
              v-model="formData.is_active"
              type="checkbox"
              class="sr-only peer"
            />
            <div
              class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"
            ></div>
            <span class="ml-3 text-sm text-gray-700">
              {{
                formData.is_active ? t('common.enabled') : t('common.disabled')
              }}
            </span>
          </label>
        </div>
      </div>

      <!-- Alert Notification Channel (only when alert is enabled) -->
      <div
        v-if="formData.is_active"
        class="space-y-3 border-b border-gray-200 pb-4"
      >
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="alertChannelUuid"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('cloudBilling.providers.alertChannelLabel') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{ t('cloudBilling.providers.alertChannelDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <select
              id="alertChannelUuid"
              v-model="selectedChannelValue"
              required
              :disabled="channelsLoading"
              class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              <option value="" disabled>
                {{
                  channelsLoading
                    ? t('common.loading')
                    : t('cloudBilling.providers.alertChannelPlaceholder')
                }}
              </option>
              <option
                v-for="ch in allChannels"
                :key="`${resolveChannelType(ch)}:${ch.uuid}`"
                :value="`${resolveChannelType(ch)}:${ch.uuid}`"
              >
                {{ getChannelOptionLabel(ch) }}
              </option>
            </select>
            <p v-if="channelsLoading" class="text-xs text-gray-500 mt-1">
              {{ t('common.loading') }}
            </p>
            <p
              v-if="!channelsLoading && allChannels.length === 0"
              class="text-xs text-gray-500 mt-1"
            >
              {{ t('cloudBilling.providers.alertChannelEmptyHint') }}
            </p>
          </div>
        </div>

        <div
          v-if="isEmailChannelSelected"
          class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start"
        >
          <div class="md:col-span-1">
            <label class="block text-sm font-medium text-gray-700 mb-1">
              {{ t('cloudBilling.providers.alertEmailRecipients') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{ t('cloudBilling.providers.alertEmailRecipientsDesc3') }}
            </p>
          </div>
          <div class="md:col-span-2 space-y-2">
            <BaseInput
              v-for="i in 3"
              :key="i"
              v-model="emailToRecipients[i - 1]"
              type="email"
              :placeholder="
                t('cloudBilling.providers.alertEmailRecipientsPlaceholder')
              "
              class="w-full"
            />
          </div>
        </div>
      </div>

      <template v-if="formData.is_active">
        <!-- Cost Threshold -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="costThreshold"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('cloudBilling.settings.alertRule.costThreshold') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{ t('cloudBilling.settings.alertRule.costThresholdDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <BaseInput
              id="costThreshold"
              v-model="formData.cost_threshold"
              type="number"
              step="0.01"
              min="0"
              :placeholder="
                t('cloudBilling.settings.alertRule.costThresholdPlaceholder')
              "
              class="w-full"
            />
          </div>
        </div>

        <!-- Growth Threshold -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="growthThreshold"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('cloudBilling.settings.alertRule.growthThreshold') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{ t('cloudBilling.settings.alertRule.growthThresholdDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <BaseInput
              id="growthThreshold"
              v-model="formData.growth_threshold"
              type="number"
              step="0.01"
              min="0"
              max="100"
              :placeholder="
                t('cloudBilling.settings.alertRule.growthThresholdPlaceholder')
              "
              class="w-full"
            />
            <p class="text-xs text-gray-500 mt-1">
              {{ t('cloudBilling.settings.alertRule.growthThresholdNote') }}
            </p>
          </div>
        </div>

        <!-- Growth Amount Threshold -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="growthAmountThreshold"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('cloudBilling.settings.alertRule.growthAmountThreshold') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{
                t('cloudBilling.settings.alertRule.growthAmountThresholdDesc')
              }}
            </p>
          </div>
          <div class="md:col-span-2">
            <BaseInput
              id="growthAmountThreshold"
              v-model="formData.growth_amount_threshold"
              type="number"
              step="0.01"
              min="0"
              :placeholder="
                t(
                  'cloudBilling.settings.alertRule.growthAmountThresholdPlaceholder'
                )
              "
              class="w-full"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="balanceThreshold"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('cloudBilling.settings.alertRule.balanceThreshold') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{ t('cloudBilling.settings.alertRule.balanceThresholdDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <BaseInput
              id="balanceThreshold"
              v-model="formData.balance_threshold"
              type="number"
              step="0.01"
              min="0"
              :placeholder="
                t('cloudBilling.settings.alertRule.balanceThresholdPlaceholder')
              "
              class="w-full"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="daysRemainingThreshold"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('cloudBilling.settings.alertRule.daysRemainingThreshold') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{
                t('cloudBilling.settings.alertRule.daysRemainingThresholdDesc')
              }}
            </p>
          </div>
          <div class="md:col-span-2">
            <BaseInput
              id="daysRemainingThreshold"
              v-model="formData.days_remaining_threshold"
              type="number"
              step="1"
              min="1"
              :placeholder="
                t(
                  'cloudBilling.settings.alertRule.daysRemainingThresholdPlaceholder'
                )
              "
              class="w-full"
            />
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="autoSubmitRechargeApproval"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{
                t('cloudBilling.settings.alertRule.autoSubmitRechargeApproval')
              }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{
                t(
                  'cloudBilling.settings.alertRule.autoSubmitRechargeApprovalDesc'
                )
              }}
            </p>
          </div>
          <div class="md:col-span-2">
            <label
              class="relative inline-flex items-center"
              :class="
                canAutoSubmitRechargeApproval
                  ? 'cursor-pointer'
                  : 'cursor-not-allowed opacity-60'
              "
            >
              <input
                id="autoSubmitRechargeApproval"
                v-model="formData.auto_submit_recharge_approval"
                type="checkbox"
                class="sr-only peer"
                :disabled="!canAutoSubmitRechargeApproval"
              />
              <div
                class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"
              ></div>
              <span class="ml-3 text-sm text-gray-700">
                {{
                  formData.auto_submit_recharge_approval
                    ? t('common.enabled')
                    : t('common.disabled')
                }}
              </span>
            </label>
            <p
              v-if="!canAutoSubmitRechargeApproval"
              class="text-xs text-gray-500 mt-1"
            >
              {{
                t(
                  'cloudBilling.settings.alertRule.autoSubmitRechargeApprovalHint'
                )
              }}
            </p>
          </div>
        </div>

        <div class="rounded-md bg-blue-50 p-3 border border-blue-200">
          <p class="text-xs text-blue-800">
            {{ t('cloudBilling.settings.alertRule.note') }}
          </p>
        </div>
      </template>
    </form>

    <template #footer>
      <div class="flex flex-col-reverse sm:flex-row justify-end gap-3">
        <BaseButton
          variant="outline"
          @click="$emit('close')"
          class="w-full sm:w-auto"
        >
          {{ t('common.cancel') }}
        </BaseButton>
        <BaseButton
          :loading="saving"
          @click="handleSubmit"
          :disabled="!canSave"
          class="w-full sm:w-auto"
        >
          {{ saving ? t('common.saving') : t('common.save') }}
        </BaseButton>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { extractResponseData } from '@/utils/api'
import { cloudBillingApi } from '@/api/cloudBilling'
import { notificationsAdminApi } from '@/admin/api'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import { getLocalizedProviderDisplayName } from '@/utils/providerDisplay'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  provider: {
    type: Object,
    default: null
  },
  alertRule: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'saved'])

const { t } = useI18n()
const { showSuccess, showError } = useToast()
const saving = ref(false)

const providerName = computed(
  () => getLocalizedProviderDisplayName(props.provider, t) || ''
)
const resolvedProviderId = computed(
  () =>
    props.provider?.id ||
    props.provider?.provider_id ||
    props.alertRule?.provider ||
    null
)

const formData = ref({
  is_active: true,
  cost_threshold: null,
  growth_threshold: null,
  growth_amount_threshold: null,
  balance_threshold: null,
  days_remaining_threshold: null,
  auto_submit_recharge_approval: false
})

const allChannels = ref([])
const channelsLoading = ref(false)
const selectedChannelValue = ref('')
const emailToRecipients = ref(['', '', ''])
const pendingChannelUuid = ref('')

const canSave = computed(() => {
  return true
})

function normalizeThresholdValue(value) {
  if (value === null || value === undefined || value === '') {
    return null
  }
  const text = String(value).trim()
  return text === '' ? null : text
}

const isEmailChannelSelected = computed(() =>
  (selectedChannelValue.value || '').startsWith('email:')
)

const canAutoSubmitRechargeApproval = computed(
  () =>
    normalizeThresholdValue(formData.value.balance_threshold) !== null ||
    normalizeThresholdValue(formData.value.days_remaining_threshold) !== null
)

watch(canAutoSubmitRechargeApproval, (canSubmit) => {
  if (!canSubmit) {
    formData.value.auto_submit_recharge_approval = false
  }
})

function normalizeChannelType(value) {
  const type = String(value || '')
    .trim()
    .toLowerCase()
  if (type === 'email' || type === 'webhook') {
    return type
  }
  return ''
}

function resolveChannelType(channel) {
  const direct = normalizeChannelType(channel?.channel_type || channel?.type)
  if (direct) {
    return direct
  }
  const cfg = channel?.config || {}
  if (cfg.smtp_host || cfg.from_email || cfg.smtp_user) {
    return 'email'
  }
  return 'webhook'
}

function applyNotificationSelection(notification) {
  const n = notification && typeof notification === 'object' ? notification : {}
  const channelUuid = getNotificationChannelUuid(n)
  const channelType = normalizeChannelType(
    n.type || n.channel_type || n.notification_type
  )

  if (!channelUuid) {
    selectedChannelValue.value = ''
    pendingChannelUuid.value = ''
    return
  }

  if (channelType) {
    selectedChannelValue.value = `${channelType}:${channelUuid}`
    pendingChannelUuid.value = ''
    return
  }

  const matched = allChannels.value.find(
    (ch) => String(ch?.uuid || '') === channelUuid
  )
  if (matched) {
    selectedChannelValue.value = `${resolveChannelType(matched)}:${channelUuid}`
    pendingChannelUuid.value = ''
    return
  }

  selectedChannelValue.value = ''
  pendingChannelUuid.value = channelUuid
}

function getNotificationChannelUuid(notification) {
  const n = notification && typeof notification === 'object' ? notification : {}
  return String(
    n.channel_uuid ||
      n.channelUuid ||
      n.channel_id ||
      n.channelId ||
      n.uuid ||
      n.id ||
      ''
  ).trim()
}

function getChannelOptionLabel(ch) {
  const name =
    (ch.name || '').trim() || t('cloudBilling.providers.channelUnnamed')
  const channelType = resolveChannelType(ch)
  const typeLabel =
    channelType === 'email'
      ? t('cloudBilling.providers.channelTypeEmail')
      : t('cloudBilling.providers.channelTypeWebhook')
  const cfg = ch.config || {}
  if (channelType === 'email') {
    const host = (cfg.smtp_host || '').trim()
    const hint = host ? ` · ${host}` : ''
    return `${name} (${typeLabel})${hint}`
  }
  const provider = (
    cfg.provider ||
    cfg.provider_type ||
    'webhook'
  ).toLowerCase()
  const url = (cfg.url || '').trim()
  const urlHint = url ? (url.length > 40 ? url.slice(0, 37) + '...' : url) : ''
  if (urlHint) {
    return `${name} (${typeLabel} · ${provider}) · ${urlHint}`
  }
  return `${name} (${typeLabel} · ${provider})`
}

async function loadChannels() {
  channelsLoading.value = true
  try {
    const channelRes = await notificationsAdminApi.getChannels()
    let rawList = []
    if (Array.isArray(channelRes)) {
      rawList = channelRes
    } else if (Array.isArray(channelRes?.results)) {
      rawList = channelRes.results
    } else if (Array.isArray(channelRes?.list)) {
      rawList = channelRes.list
    } else if (Array.isArray(channelRes?.items)) {
      rawList = channelRes.items
    } else if (Array.isArray(channelRes?.data)) {
      rawList = channelRes.data
    } else if (Array.isArray(channelRes?.data?.results)) {
      rawList = channelRes.data.results
    } else if (Array.isArray(channelRes?.data?.list)) {
      rawList = channelRes.data.list
    } else if (Array.isArray(channelRes?.data?.items)) {
      rawList = channelRes.data.items
    }
    allChannels.value = rawList.filter((ch) => {
      const type = resolveChannelType(ch)
      return type === 'webhook' || type === 'email'
    })
    if (pendingChannelUuid.value) {
      const matched = allChannels.value.find(
        (ch) => String(ch?.uuid || '') === pendingChannelUuid.value
      )
      if (matched) {
        selectedChannelValue.value = `${resolveChannelType(matched)}:${pendingChannelUuid.value}`
        pendingChannelUuid.value = ''
      }
    }
  } catch (err) {
    console.error('Failed to load channels:', err)
    allChannels.value = []
  } finally {
    channelsLoading.value = false
  }
}

async function hydrateNotificationSelection(providerId) {
  if (!providerId) {
    selectedChannelValue.value = ''
    pendingChannelUuid.value = ''
    emailToRecipients.value = ['', '', '']
    return
  }

  try {
    const res = await cloudBillingApi.getProvider(providerId)
    const full = extractResponseData(res)
    const notification = full?.config?.notification
    const channelUuid = getNotificationChannelUuid(notification)
    if (channelUuid) {
      applyNotificationSelection(notification)
      const to = notification.email_to
      if (Array.isArray(to) && to.length) {
        emailToRecipients.value = [
          (to[0] || '').trim(),
          (to[1] || '').trim(),
          (to[2] || '').trim()
        ]
      } else {
        emailToRecipients.value = ['', '', '']
      }
      return
    }
  } catch (e) {
    // Keep fallback values below.
  }

  selectedChannelValue.value = ''
  pendingChannelUuid.value = ''
  emailToRecipients.value = ['', '', '']
}

async function fetchExistingAlertRule(providerId) {
  if (!providerId) {
    return null
  }

  try {
    const response = await cloudBillingApi.getAlertRules({
      provider_id: providerId,
      page_size: 1
    })
    const data = extractResponseData(response)
    const rules = Array.isArray(data) ? data : data?.results || data?.list || []
    return rules[0] || null
  } catch (error) {
    console.error('Failed to fetch existing alert rule:', error)
    return null
  }
}

watch(
  () => [props.show, resolvedProviderId.value],
  async ([visible, providerId]) => {
    if (!visible) {
      return
    }
    await loadChannels()
    await hydrateNotificationSelection(providerId)
  }
)
onMounted(() => {
  if (props.show) {
    loadChannels().then(() =>
      hydrateNotificationSelection(resolvedProviderId.value)
    )
  }
})

watch(
  () => props.alertRule,
  (newRule) => {
    if (newRule) {
      formData.value = {
        is_active: newRule.is_active ?? true,
        cost_threshold:
          newRule.cost_threshold != null
            ? String(newRule.cost_threshold)
            : null,
        growth_threshold:
          newRule.growth_threshold != null
            ? String(newRule.growth_threshold)
            : null,
        growth_amount_threshold:
          newRule.growth_amount_threshold != null
            ? String(newRule.growth_amount_threshold)
            : null,
        balance_threshold:
          newRule.balance_threshold != null
            ? String(newRule.balance_threshold)
            : null,
        days_remaining_threshold:
          newRule.days_remaining_threshold != null
            ? String(newRule.days_remaining_threshold)
            : null,
        auto_submit_recharge_approval:
          newRule.auto_submit_recharge_approval ?? false
      }
    } else {
      formData.value = {
        is_active: true,
        cost_threshold: null,
        growth_threshold: null,
        growth_amount_threshold: null,
        balance_threshold: null,
        days_remaining_threshold: null,
        auto_submit_recharge_approval: false
      }
    }
  },
  { immediate: true }
)

const handleSubmit = async () => {
  // Check if any threshold has a value (handle both null and empty string)
  const costThreshold = normalizeThresholdValue(formData.value.cost_threshold)
  const growthThreshold = normalizeThresholdValue(
    formData.value.growth_threshold
  )
  const growthAmountThreshold = normalizeThresholdValue(
    formData.value.growth_amount_threshold
  )
  const balanceThreshold = normalizeThresholdValue(
    formData.value.balance_threshold
  )
  const daysRemainingThreshold = normalizeThresholdValue(
    formData.value.days_remaining_threshold
  )
  const hasAnyThreshold = [
    costThreshold,
    growthThreshold,
    growthAmountThreshold,
    balanceThreshold,
    daysRemainingThreshold
  ].some((value) => value !== null)

  saving.value = true
  try {
    const providerId = resolvedProviderId.value
    if (!providerId) {
      showError(t('cloudBilling.settings.alertRule.saveError'))
      saving.value = false
      return
    }

    const existingRule =
      props.alertRule || (await fetchExistingAlertRule(providerId))
    const existingRuleId = existingRule?.id || null

    // If all thresholds are empty and rule exists, delete it
    if (!hasAnyThreshold && existingRuleId) {
      await cloudBillingApi.deleteAlertRule(existingRuleId)
      showSuccess(t('cloudBilling.settings.alertRule.deleteSuccess'))
      emit('saved')
      return
    }

    // If all thresholds are empty and no rule exists, cannot create
    if (!hasAnyThreshold && !props.alertRule) {
      showError(t('cloudBilling.settings.alertRule.atLeastOneThreshold'))
      saving.value = false
      return
    }

    if (
      formData.value.is_active &&
      !(selectedChannelValue.value || '').trim()
    ) {
      showError(t('cloudBilling.providers.alertChannelRequired'))
      saving.value = false
      return
    }

    if (isEmailChannelSelected.value) {
      const list = (emailToRecipients.value || [])
        .map((s) => (s || '').trim())
        .filter(Boolean)
      if (list.length === 0) {
        showError(t('cloudBilling.providers.alertEmailRecipientsRequired'))
        saving.value = false
        return
      }
      const invalid = list.find((e) => !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e))
      if (invalid) {
        showError(
          t('cloudBilling.providers.alertEmailRecipientsInvalid', {
            email: invalid
          })
        )
        saving.value = false
        return
      }
    }

    const data = {
      provider: providerId,
      is_active: formData.value.is_active,
      cost_threshold: costThreshold !== null ? parseFloat(costThreshold) : null,
      growth_threshold:
        growthThreshold !== null ? parseFloat(growthThreshold) : null,
      growth_amount_threshold:
        growthAmountThreshold !== null
          ? parseFloat(growthAmountThreshold)
          : null,
      balance_threshold:
        balanceThreshold !== null ? parseFloat(balanceThreshold) : null,
      days_remaining_threshold:
        daysRemainingThreshold !== null
          ? parseInt(daysRemainingThreshold, 10)
          : null,
      auto_submit_recharge_approval:
        canAutoSubmitRechargeApproval.value &&
        formData.value.auto_submit_recharge_approval
    }

    const successMessage = existingRuleId
      ? t('cloudBilling.settings.alertRule.updateSuccess')
      : t('cloudBilling.settings.alertRule.createSuccess')
    if (existingRuleId) {
      await cloudBillingApi.updateAlertRule(existingRuleId, data)
    } else {
      await cloudBillingApi.createAlertRule(data)
    }

    const providerRes = await cloudBillingApi.getProvider(providerId)
    const fullProvider = extractResponseData(providerRes)
    const providerConfig = { ...(fullProvider?.config || {}) }
    const raw = (selectedChannelValue.value || '').trim()
    if (raw) {
      const colonIndex = raw.indexOf(':')
      const notifType = colonIndex >= 0 ? raw.slice(0, colonIndex) : 'webhook'
      const notifUuid = colonIndex >= 0 ? raw.slice(colonIndex + 1) : raw
      providerConfig.notification = {
        type: notifType,
        channel_uuid: notifUuid
      }
      if (notifType === 'email') {
        const list = (emailToRecipients.value || [])
          .map((s) => (s || '').trim())
          .filter(Boolean)
        if (list.length) {
          providerConfig.notification.email_to = list
        }
      }
    } else {
      delete providerConfig.notification
    }
    await cloudBillingApi.patchProvider(providerId, { config: providerConfig })

    showSuccess(successMessage)
    emit('saved')
  } catch (error) {
    console.error('Failed to save alert rule:', error)
    showError(t('cloudBilling.settings.alertRule.saveError'))
  } finally {
    saving.value = false
  }
}
</script>

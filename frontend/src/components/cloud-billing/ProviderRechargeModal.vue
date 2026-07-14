<template>
  <BaseModal
    :show="show"
    :title="t('cloudBilling.providers.rechargeModalTitle')"
    @close="$emit('close')"
  >
    <div class="space-y-5">
      <div class="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3">
        <p class="text-sm font-medium text-blue-900">
          {{ providerDisplayName }}
        </p>
        <p class="mt-1 text-xs text-blue-700">
          {{ t('cloudBilling.providers.rechargeModalDesc') }}
        </p>
      </div>

      <div class="space-y-2">
        <label
          for="providerRechargeInfo"
          class="block text-sm font-medium text-gray-700"
        >
          {{ t('cloudBilling.providers.rechargeInfo') }}
        </label>
        <p class="text-xs text-gray-500">
          {{ t('cloudBilling.providers.rechargeInfoInputModeHint') }}
        </p>
        <textarea
          id="providerRechargeInfo"
          v-model="form.recharge_info"
          rows="10"
          :placeholder="t('cloudBilling.providers.rechargeInfoPlaceholder')"
          class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono shadow-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
          style="height: 290px"
        />
      </div>

      <div class="space-y-2">
        <label class="block text-sm font-medium text-gray-700">
          <span class="text-red-500">*</span>
          {{ t('cloudBilling.providers.submitterIdentifier') }}
        </label>
        <div class="flex gap-2">
          <BaseSearchableSelect
            v-model="form.submitter_user_id"
            :options="feishuUserOptions"
            :loading="loadingFeishuUsers"
            :disabled="loadingFeishuUsers"
            allow-custom
            class="min-w-0 flex-1"
            :placeholder="t('cloudBilling.providers.selectUserPlaceholder')"
            :loading-text="t('cloudBilling.providers.loadingUsers')"
            :empty-text="t('cloudBilling.providers.noMatchingUsers')"
            @change="handleSubmitterUserChange"
          />
          <BaseButton
            variant="outline"
            size="sm"
            class="shrink-0"
            :loading="loadingFeishuUsers"
            @click="refreshFeishuUsers"
          >
            {{ t('common.refresh') }}
          </BaseButton>
        </div>
        <p class="text-xs text-gray-500">
          {{ t('cloudBilling.providers.submitterIdentifierRequiredHint') }}
        </p>
      </div>

      <div
        class="flex flex-col gap-3 rounded-lg border border-gray-200 p-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div>
          <p class="text-sm font-medium text-gray-900">
            {{ t('cloudBilling.providers.manualApprovalTitle') }}
          </p>
          <p class="mt-1 text-xs text-gray-500">
            {{ t('cloudBilling.providers.manualApprovalDesc') }}
          </p>
        </div>
        <BaseButton
          :loading="submitting"
          :disabled="!canOpenSubmitApprovalDialog"
          @click="openSubmitApprovalDialog"
        >
          {{ t('cloudBilling.providers.submitRechargeApproval') }}
        </BaseButton>
      </div>

      <div class="space-y-3">
        <div class="flex items-center justify-between gap-3">
          <div>
            <h4 class="text-sm font-semibold text-gray-900">
              {{ t('cloudBilling.providers.rechargeApprovals') }}
            </h4>
            <p class="text-xs text-gray-500">
              {{ t('cloudBilling.providers.rechargeApprovalsDesc') }}
            </p>
          </div>
          <BaseButton
            variant="outline"
            size="sm"
            :loading="loadingRecords"
            @click="loadApprovals"
          >
            {{ t('common.refresh') }}
          </BaseButton>
        </div>

        <BaseLoading v-if="loadingRecords" size="md" variant="primary" />
        <div
          v-else-if="approvals.length === 0"
          class="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-8 text-center text-sm text-gray-500"
        >
          {{ t('cloudBilling.providers.noRechargeApprovals') }}
        </div>
        <div v-else class="space-y-3">
          <div
            v-for="item in approvals"
            :key="item.id"
            class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
          >
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p class="text-sm font-medium text-gray-900">
                  {{ item.feishu_instance_code || `#${item.id}` }}
                </p>
                <p class="mt-1 text-xs text-gray-500">
                  {{
                    t('cloudBilling.providers.rechargeApprovalMeta', {
                      source: formatTriggerSource(item.trigger_source),
                      stage: item.latest_stage || '-'
                    })
                  }}
                </p>
              </div>
              <span
                class="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium"
                :class="statusClass(item.status)"
              >
                {{ formatStatus(item.status) }}
              </span>
            </div>

            <div class="mt-3 grid gap-2 text-xs text-gray-600 sm:grid-cols-2">
              <div>
                <span class="font-medium text-gray-700">
                  {{ t('cloudBilling.providers.triggeredBy') }}:
                </span>
                {{
                  item.triggered_by_username ||
                  item.triggered_by_username_snapshot ||
                  '-'
                }}
              </div>
              <div>
                <span class="font-medium text-gray-700">
                  {{ t('cloudBilling.providers.submitterIdentifier') }}:
                </span>
                {{
                  item.submitter_user_label ||
                  item.resolved_submitter_user_id ||
                  '-'
                }}
              </div>
              <div>
                <span class="font-medium text-gray-700">
                  {{ t('cloudBilling.providers.submittedAt') }}:
                </span>
                {{ formatDate(item.submitted_at) || '-' }}
              </div>
              <div>
                <span class="font-medium text-gray-700">
                  {{ t('cloudBilling.providers.submittedBalance') }}:
                </span>
                {{ approvalSnapshot(item).submittedBalance }}
              </div>
              <div>
                <span class="font-medium text-gray-700">
                  {{ t('cloudBilling.providers.alertThreshold') }}:
                </span>
                {{ approvalSnapshot(item).threshold }}
              </div>
              <div>
                <span class="font-medium text-gray-700">
                  {{ t('cloudBilling.providers.rechargeApprovalAmount') }}:
                </span>
                {{ approvalSnapshot(item).rechargeAmount }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <BaseModal
      :show="showSubmitDialog"
      :title="t('cloudBilling.providers.submitRechargeApproval')"
      @close="closeSubmitApprovalDialog"
    >
      <div class="space-y-4">
        <div class="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3">
          <p class="text-sm font-medium text-blue-900">
            {{ providerDisplayName }}
          </p>
          <p class="mt-1 text-xs text-blue-700">
            {{ t('cloudBilling.providers.manualApprovalDialogDesc') }}
          </p>
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-2">
            <label class="block text-sm font-medium text-gray-700">
              <span class="text-red-500">*</span>
              {{ t('cloudBilling.providers.rechargeApprovalAmount') }}
            </label>
            <BaseInput
              v-model="submitApprovalForm.amount"
              type="number"
              min="0"
              step="0.01"
              :placeholder="
                t('cloudBilling.providers.rechargeApprovalAmountPlaceholder')
              "
            />
          </div>
          <div class="space-y-2">
            <label class="block text-sm font-medium text-gray-700">
              <span class="text-red-500">*</span>
              {{ t('cloudBilling.providers.rechargeApprovalExpectedDate') }}
            </label>
            <BaseInput
              v-model="submitApprovalForm.expected_date"
              type="date"
              :placeholder="
                t(
                  'cloudBilling.providers.rechargeApprovalExpectedDatePlaceholder'
                )
              "
            />
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex flex-col-reverse justify-end gap-3 sm:flex-row">
          <BaseButton
            variant="outline"
            :disabled="submitting"
            @click="closeSubmitApprovalDialog"
          >
            {{ t('common.cancel') }}
          </BaseButton>
          <BaseButton :loading="submitting" @click="submitApprovalFromDialog">
            {{ t('cloudBilling.providers.submitRechargeApproval') }}
          </BaseButton>
        </div>
      </template>
    </BaseModal>

    <template #footer>
      <div class="flex flex-col-reverse justify-end gap-3 sm:flex-row">
        <BaseButton variant="outline" @click="$emit('close')">
          {{ t('common.close') }}
        </BaseButton>
        <BaseButton :loading="saving" @click="handleSave">
          {{ saving ? t('common.saving') : t('common.save') }}
        </BaseButton>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { format } from 'date-fns'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { extractResponseData } from '@/utils/api'
import {
  getRechargeApprovalSubmitErrorContext,
  getRechargeInfoSaveErrorContext
} from './rechargeApprovalErrors'
import { getRechargeApprovalSnapshot } from './rechargeApprovalDisplay'
import { cloudBillingApi } from '@/api/cloudBilling'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import { getLocalizedProviderDisplayName } from '@/utils/providerDisplay'
import BaseSearchableSelect from '@/components/ui/BaseSearchableSelect.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  provider: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'saved'])

const { t } = useI18n()
const { showSuccess, showError, showWarning } = useToast()

const saving = ref(false)
const submitting = ref(false)
const loadingRecords = ref(false)
const loadingFeishuUsers = ref(false)
const showSubmitDialog = ref(false)
const approvals = ref([])
const feishuUsers = ref([])
const form = reactive({
  recharge_info: '',
  submitter_identifier: '',
  submitter_user_id: '',
  submitter_user_label: ''
})
const submitApprovalForm = reactive({
  amount: '',
  expected_date: ''
})

const RECHARGE_INFO_FIELD_ORDER = [
  'cloud_type',
  'recharge_customer_name',
  'recharge_account',
  'payment_company',
  'payment_way',
  'payment_type',
  'remit_method',
  'amount',
  'expected_date',
  'payment_note',
  'remark',
  'payee.type',
  'payee.account_name',
  'payee.account_number',
  'payee.bank_name',
  'payee.bank_region',
  'payee.bank_branch'
]

const RECHARGE_INFO_SYNC_FIELD_ORDER = RECHARGE_INFO_FIELD_ORDER.filter(
  (field) => field !== 'amount'
)

const RECHARGE_INFO_FIELD_LABELS = {
  cloud_type: '公有云类型',
  recharge_customer_name: '充值客户名称',
  recharge_account: '充值云账号',
  payment_company: '付款公司',
  payment_way: '支付方式',
  payment_type: '付款类型',
  remit_method: '付款方式',
  amount: '付款金额',
  expected_date: '期望到账时间',
  payment_note: '付款说明',
  remark: '备注',
  'payee.type': '账户类型',
  'payee.account_name': '户名',
  'payee.account_number': '账号',
  'payee.bank_name': '银行',
  'payee.bank_region': '银行地区',
  'payee.bank_branch': '支行'
}

const RECHARGE_INFO_TEXT_KEY_MAP = {
  cloud_type: 'cloud_type',
  公有云类型: 'cloud_type',
  recharge_customer_name: 'recharge_customer_name',
  充值客户名称: 'recharge_customer_name',
  recharge_account: 'recharge_account',
  充值云账号: 'recharge_account',
  payment_company: 'payment_company',
  付款公司: 'payment_company',
  payment_way: 'payment_way',
  支付方式: 'payment_way',
  payment_type: 'payment_type',
  付款类型: 'payment_type',
  remit_method: 'remit_method',
  付款方式: 'remit_method',
  amount: 'amount',
  付款金额: 'amount',
  expected_date: 'expected_date',
  期望到账时间: 'expected_date',
  payment_note: 'payment_note',
  付款说明: 'payment_note',
  remark: 'remark',
  备注: 'remark',
  'payee.type': 'payee.type',
  账户类型: 'payee.type',
  'payee.account_name': 'payee.account_name',
  户名: 'payee.account_name',
  'payee.account_number': 'payee.account_number',
  账号: 'payee.account_number',
  'payee.bank_name': 'payee.bank_name',
  银行: 'payee.bank_name',
  'payee.bank_region': 'payee.bank_region',
  银行地区: 'payee.bank_region',
  银行所在地区: 'payee.bank_region',
  'payee.bank_branch': 'payee.bank_branch',
  支行: 'payee.bank_branch',
  银行支行: 'payee.bank_branch'
}

const PAYEE_DETAIL_PREFIXES = [
  '账户类型',
  '收款账户类型',
  '账户类型',
  '户名',
  '账号',
  '银行',
  '银行地区',
  '银行所在地区',
  '支行',
  '银行支行'
]

const providerDisplayName = computed(() =>
  getLocalizedProviderDisplayName(props.provider, t)
)
const canOpenSubmitApprovalDialog = computed(() => {
  return (
    Boolean(String(form.recharge_info || '').trim()) &&
    Boolean(String(form.submitter_user_id || '').trim())
  )
})

const selectedSubmitterUser = computed(() => {
  const selectedId = String(form.submitter_user_id || '').trim()
  if (!selectedId) return null
  return (
    feishuUsers.value.find((user) => {
      return getFeishuUserOptionValue(user) === selectedId
    }) || null
  )
})

const feishuUserOptions = computed(() => {
  return feishuUsers.value
    .map((user) => {
      const value = getFeishuUserOptionValue(user)
      if (!value) return null
      const label = formatFeishuUserOption(user) || value
      return {
        value,
        label,
        description: '',
        searchText: [
          label,
          user?.display_name,
          user?.name,
          user?.email,
          user?.mobile,
          user?.user_id
        ]
          .filter(Boolean)
          .join(' ')
      }
    })
    .filter(Boolean)
})

const formatDate = (value) => {
  if (!value) return ''
  return format(new Date(value), 'yyyy-MM-dd HH:mm')
}

const formatStatus = (value) => {
  const key = `cloudBilling.providers.approvalStatuses.${value || 'pending'}`
  return t(key)
}

const formatTriggerSource = (value) => {
  const key = `cloudBilling.providers.triggerSources.${value || 'manual'}`
  return t(key)
}

const approvalSnapshot = (item) =>
  getRechargeApprovalSnapshot(item, {
    daysUnit: t('cloudBilling.providers.daysUnit')
  })

const statusClass = (status) => {
  const classes = {
    submitted: 'bg-blue-50 text-blue-700',
    approved: 'bg-green-50 text-green-700',
    rejected: 'bg-red-50 text-red-700',
    canceled: 'bg-gray-100 text-gray-700',
    failed: 'bg-amber-50 text-amber-700',
    pending: 'bg-slate-100 text-slate-700'
  }
  return classes[status] || classes.pending
}

function formatRechargeInfoValue(value) {
  const text = String(value ?? '').trim()
  return text || ''
}

function getSubmitterIdentifier() {
  return String(form.submitter_user_id || '').trim()
}

function looksLikeLegacySubmitterIdentifier(value) {
  const text = String(value || '').trim()
  return text.includes('@') || /^\+?\d[\d\s-]{5,}$/.test(text)
}

function getFeishuUserOptionValue(user) {
  return String(
    user?.user_id || user?.open_id || user?.union_id || user?.email ||
      user?.mobile || ''
  ).trim()
}

function getFeishuUserLabel(user) {
  return String(user?.display_name || user?.name || user?.user_id || '').trim()
}

function formatFeishuUserOption(user) {
  const label = getFeishuUserLabel(user) || getFeishuUserOptionValue(user)
  return label
}

function applySubmitterUser(user) {
  if (!user) return
  form.submitter_user_id = getFeishuUserOptionValue(user)
  form.submitter_identifier = ''
  form.submitter_user_label = getFeishuUserLabel(user)
}

function buildRechargeInfoSaveErrorMessage(errorContext) {
  const baseKey = 'cloudBilling.providers.rechargeInfoSaveError'
  const status = Number(errorContext?.status) || 0
  const reason = String(errorContext?.reason || '').toLowerCase()
  const missingFields = Array.isArray(errorContext?.missingFields)
    ? errorContext.missingFields
    : []
  const rawMessage = String(errorContext?.rawMessage || '').trim()
  const code = String(errorContext?.code || '').trim()

  if (missingFields.length > 0) {
    const fieldLabels = missingFields
      .map((f) => RECHARGE_INFO_FIELD_LABELS[f] || f)
      .filter(Boolean)
      .join('、')
    if (fieldLabels) {
      return (
        t(baseKey) +
        '，缺少以下必填字段：' +
        fieldLabels
      )
    }
  }

  const reasonKey = `cloudBilling.providers.rechargeInfoSaveErrorReason.${reason}`
  let reasonText = t(reasonKey, { status, code }, '')
  if (!reasonText) {
    if (reason === 'validation' && rawMessage) {
      reasonText = t(
        'cloudBilling.providers.rechargeInfoSaveErrorReason.validationWithDetail',
        { detail: rawMessage },
        ''
      )
    } else if (reason === 'server' && rawMessage) {
      reasonText = t(
        'cloudBilling.providers.rechargeInfoSaveErrorReason.serverWithDetail',
        { detail: rawMessage },
        ''
      )
    } else if (rawMessage) {
      reasonText = rawMessage
    }
  }

  if (reasonText) {
    return `${t(baseKey)}：${reasonText}`
  }
  return t(baseKey)
}

function handleSubmitterUserChange(value) {
  const selectedId = String(value || form.submitter_user_id || '').trim()
  const user =
    feishuUsers.value.find((item) => {
      return getFeishuUserOptionValue(item) === selectedId
    }) || null
  if (!user) {
    form.submitter_identifier = ''
    form.submitter_user_label = ''
    return
  }
  applySubmitterUser(user)
}

function applySubmitterUserId(userId) {
  const text = String(userId || '').trim()
  if (!text) {
    form.submitter_identifier = ''
    form.submitter_user_id = ''
    form.submitter_user_label = ''
    return
  }
  const user = feishuUsers.value.find((item) => {
    return getFeishuUserOptionValue(item) === text
  })
  if (user) {
    applySubmitterUser(user)
    return
  }
  // Accept the legacy email/手机号 form so historical configs still hydrate.
  // Anything else is treated as a stale free-text value (e.g. a typed name
  // during search) and is cleared to avoid leaking arbitrary strings into
  // the submitter_user_id field.
  if (looksLikeLegacySubmitterIdentifier(text)) {
    form.submitter_identifier = text
    form.submitter_user_id = text
    form.submitter_user_label = ''
    return
  }
  form.submitter_identifier = ''
  form.submitter_user_id = ''
  form.submitter_user_label = ''
}

function getSubmitterPayload() {
  const user = selectedSubmitterUser.value
  if (user) {
    return {
      submitter_user_id: getFeishuUserOptionValue(user),
      submitter_user_label: getFeishuUserLabel(user)
    }
  }
  const value = getSubmitterIdentifier()
  if (looksLikeLegacySubmitterIdentifier(value)) {
    return {
      submitter_identifier: value,
      submitter_user_id: '',
      submitter_user_label: String(form.submitter_user_label || '').trim()
    }
  }
  return {
    submitter_user_id: value,
    submitter_user_label: String(form.submitter_user_label || '').trim()
  }
}

function hasSubmitterPayload(payload) {
  return Boolean(
    String(payload?.submitter_user_id || payload?.submitter_identifier || '')
      .trim()
  )
}

function validateRechargeInfoBeforeSave() {
  if (!String(form.recharge_info || '').trim()) {
    showWarning(t('cloudBilling.providers.rechargeInfoEmpty'))
    return false
  }

  if (!hasSubmitterPayload(getSubmitterPayload())) {
    showWarning(t('cloudBilling.providers.submitterIdentifierRequiredWarning'))
    return false
  }

  const parsedPayload = parseRechargeInfoForStorage(form.recharge_info || '')
  const paymentType = String(parsedPayload.payment_type || '').trim()
  if (paymentType && paymentType !== '仅充值') {
    showWarning(
      t('cloudBilling.providers.rechargeInfoPaymentTypeNotSupported', {
        type: paymentType
      })
    )
    return false
  }

  return true
}

function formatRechargeInfoSaveError(errorContext) {
  if (errorContext.missingFields.length > 0) {
    const fieldLabels = errorContext.missingFields
      .map((field) => RECHARGE_INFO_FIELD_LABELS[field] || field)
      .filter(Boolean)
      .join('、')
    if (fieldLabels) {
      return t('cloudBilling.providers.rechargeInfoSaveErrorMissingFields', {
        fields: fieldLabels
      })
    }
  }

  const reason = String(errorContext.reason || '').trim()
  if (reason) {
    return t('cloudBilling.providers.rechargeInfoSaveErrorWithReason', {
      reason
    })
  }

  if (errorContext.status) {
    return t('cloudBilling.providers.rechargeInfoSaveErrorWithReason', {
      reason: `HTTP ${errorContext.status}`
    })
  }

  return t('cloudBilling.providers.rechargeInfoSaveErrorWithReason', {
    reason: t('cloudBilling.providers.rechargeInfoSaveErrorUnknownReason')
  })
}

function parseRechargeInfoObject(source) {
  const payload = {}
  if (!source || typeof source !== 'object') return payload
  payload.cloud_type = formatRechargeInfoValue(source.cloud_type)
  payload.recharge_customer_name = formatRechargeInfoValue(
    source.recharge_customer_name
  )
  payload.recharge_account = formatRechargeInfoValue(source.recharge_account)
  payload.payment_company = formatRechargeInfoValue(source.payment_company)
  payload.payment_way = formatRechargeInfoValue(source.payment_way)
  payload.payment_type = formatRechargeInfoValue(source.payment_type)
  payload.remit_method = formatRechargeInfoValue(source.remit_method)
  const amountText = formatRechargeInfoValue(source.amount)
  const currencyText = formatRechargeInfoValue(source.currency)
  payload.amount = currencyText
    ? [amountText, currencyText].filter(Boolean).join(' ')
    : amountText
  payload.expected_date = formatRechargeInfoValue(source.expected_date)
  payload.payment_note = formatRechargeInfoValue(source.payment_note)
  payload.remark = formatRechargeInfoValue(source.remark)
  const payee =
    source.payee && typeof source.payee === 'object' ? source.payee : {}
  payload['payee.type'] = formatRechargeInfoValue(payee.type)
  payload['payee.account_name'] = formatRechargeInfoValue(payee.account_name)
  payload['payee.account_number'] = formatRechargeInfoValue(
    payee.account_number
  )
  payload['payee.bank_name'] = formatRechargeInfoValue(payee.bank_name)
  payload['payee.bank_region'] = formatRechargeInfoValue(payee.bank_region)
  payload['payee.bank_branch'] = formatRechargeInfoValue(payee.bank_branch)
  return payload
}

function parseRechargeInfoText(source) {
  const payload = {}
  const lines = String(source || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const separatorIndex = Math.max(line.indexOf('：'), line.indexOf(':'))
    let key = ''
    let value = ''
    if (separatorIndex !== -1) {
      key = line.slice(0, separatorIndex).trim()
      value = line.slice(separatorIndex + 1).trim()
    } else if (RECHARGE_INFO_TEXT_KEY_MAP[line]) {
      key = line
      value = lines[index + 1] || ''
      index += 1
    } else {
      continue
    }

    const normalizedKey = RECHARGE_INFO_TEXT_KEY_MAP[key]
    if (!normalizedKey) continue
    if (normalizedKey === 'amount') {
      payload.amount = payload.amount
        ? [payload.amount, value].filter(Boolean).join(' ')
        : value
      continue
    }
    if (normalizedKey === 'remark') {
      if (looksLikePayeeDetails(value)) {
        continue
      }
      payload.remark = payload.remark ? `${payload.remark}\n${value}` : value
      continue
    }
    if (normalizedKey.startsWith('payee.')) {
      payload[normalizedKey] = value
      continue
    }
    payload[normalizedKey] = value
  }

  return payload
}

function parseRechargeInfoForStorage(source) {
  if (!source) return {}
  if (typeof source === 'string') {
    const trimmed = source.trim()
    if (!trimmed) return {}
    try {
      const parsed = JSON.parse(trimmed)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed
      }
    } catch {
      // fall through to text parsing
    }
    return parseRechargeInfoText(trimmed)
  }
  if (typeof source === 'object' && !Array.isArray(source)) {
    return { ...source }
  }
  return {}
}

function buildRechargeInfoStorageObject(source) {
  const payload = parseRechargeInfoForStorage(source)
  const nested = { ...payload }
  const payee = {
    type: formatRechargeInfoValue(payload['payee.type'] ?? payload.payee?.type),
    account_name: formatRechargeInfoValue(
      payload['payee.account_name'] ?? payload.payee?.account_name
    ),
    account_number: formatRechargeInfoValue(
      payload['payee.account_number'] ?? payload.payee?.account_number
    ),
    bank_name: formatRechargeInfoValue(
      payload['payee.bank_name'] ?? payload.payee?.bank_name
    ),
    bank_region: formatRechargeInfoValue(
      payload['payee.bank_region'] ?? payload.payee?.bank_region
    ),
    bank_branch: formatRechargeInfoValue(
      payload['payee.bank_branch'] ?? payload.payee?.bank_branch
    )
  }

  delete nested['payee.type']
  delete nested['payee.account_name']
  delete nested['payee.account_number']
  delete nested['payee.bank_name']
  delete nested['payee.bank_region']
  delete nested['payee.bank_branch']

  if (Object.values(payee).some((value) => String(value || '').trim())) {
    nested.payee = payee
  } else {
    delete nested.payee
  }

  return nested
}

function extractRechargeApprovalFromSource(source) {
  const approval = extractRechargeApprovalObjectFromSource(source)
  return {
    submitter_user_id: formatRechargeInfoValue(
      approval.submitter_user_id ||
        approval.resolved_submitter_user_id ||
        approval.submitter_identifier ||
        approval.submitter_email ||
        approval.submitter_mobile ||
        approval.submitter_contact
    )
  }
}

function extractRechargeApprovalObjectFromSource(source) {
  const payload = parseRechargeInfoForStorage(source)
  const approval =
    payload && typeof payload.recharge_approval === 'object'
      ? { ...payload.recharge_approval }
      : {}
  const legacySubmitterUserId = formatRechargeInfoValue(
    approval.submitter_user_id ||
      payload.submitter_user_id ||
      payload.submitter_identifier ||
      payload.submitter_email ||
      payload.submitter_mobile ||
      payload.submitter_contact ||
      payload['审批发起人'] ||
      payload['提交名义'] ||
      payload['发起人邮箱或手机号']
  )
  if (legacySubmitterUserId && !approval.submitter_user_id) {
    approval.submitter_user_id = legacySubmitterUserId
  }
  const resolvedSubmitterUserId = formatRechargeInfoValue(
    approval.resolved_submitter_user_id || payload.resolved_submitter_user_id
  )
  if (resolvedSubmitterUserId && !approval.resolved_submitter_user_id) {
    approval.resolved_submitter_user_id = resolvedSubmitterUserId
  }
  const submitterUserLabel = formatRechargeInfoValue(
    approval.submitter_user_label || payload.submitter_user_label
  )
  if (submitterUserLabel && !approval.submitter_user_label) {
    approval.submitter_user_label = submitterUserLabel
  }
  return approval
}

function looksLikePayeeDetails(value) {
  const lines = String(value || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  if (!lines.length) return false
  return lines.every((line) =>
    PAYEE_DETAIL_PREFIXES.some(
      (prefix) =>
        line.startsWith(`${prefix}：`) || line.startsWith(`${prefix}:`)
    )
  )
}

function renderRechargeInfoText(payload, { includeAmount = true } = {}) {
  const lines = []
  const fields = includeAmount
    ? RECHARGE_INFO_FIELD_ORDER
    : RECHARGE_INFO_SYNC_FIELD_ORDER
  for (const field of fields) {
    const value = formatRechargeInfoValue(payload[field])
    if (!value) continue
    lines.push(`${RECHARGE_INFO_FIELD_LABELS[field]}： ${value}`)
  }
  return lines.join('\n')
}

function formatRechargeInfoText(source, options = {}) {
  if (!source) return ''
  if (typeof source === 'string') {
    const trimmed = source.trim()
    if (!trimmed) return ''
    try {
      const parsed = JSON.parse(trimmed)
      if (parsed && typeof parsed === 'object') {
        return renderRechargeInfoText(parseRechargeInfoObject(parsed), options)
      }
    } catch {
      // fall through to key/value parsing or raw text
    }
    const parsedText = parseRechargeInfoText(trimmed)
    if (Object.keys(parsedText).length > 0) {
      return renderRechargeInfoText(parsedText, options)
    }
    if (looksLikePayeeDetails(trimmed)) {
      return ''
    }
    return trimmed
  }
  if (typeof source === 'object') {
    return renderRechargeInfoText(parseRechargeInfoObject(source), options)
  }
  return String(source).trim()
}

const syncForm = () => {
  form.recharge_info = formatRechargeInfoText(
    props.provider?.recharge_info || ''
  )
  const approvalConfig = extractRechargeApprovalFromSource(
    props.provider?.recharge_info || props.provider?.config || {}
  )
  applySubmitterUserId(
    approvalConfig.submitter_user_id ||
      props.provider?.config?.recharge_approval?.submitter_user_id ||
      ''
  )
}

function addDaysToDateString(dateString, days) {
  const parsed = new Date(`${dateString}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) {
    return ''
  }
  parsed.setDate(parsed.getDate() + days)
  const year = parsed.getFullYear()
  const month = String(parsed.getMonth() + 1).padStart(2, '0')
  const day = String(parsed.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function getTodayDateString() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const loadApprovals = async () => {
  if (!props.provider?.id) {
    approvals.value = []
    return
  }
  loadingRecords.value = true
  try {
    const response = await cloudBillingApi.getRechargeApprovals({
      provider: props.provider.id,
      page_size: 5
    })
    const data = extractResponseData(response)
    approvals.value = Array.isArray(data) ? data : data?.results || []
  } catch (error) {
    console.error('Failed to load recharge approvals:', error)
    approvals.value = []
    showError(t('cloudBilling.providers.loadRechargeApprovalsError'))
  } finally {
    loadingRecords.value = false
  }
}

const hydrateProviderDetail = async () => {
  if (!props.provider?.id) return
  try {
    const response = await cloudBillingApi.getProvider(props.provider.id)
    const provider = extractResponseData(response)
    form.recharge_info = formatRechargeInfoText(provider?.recharge_info || '')
    const approvalConfig = extractRechargeApprovalFromSource(
      provider?.recharge_info || provider?.config || {}
    )
    applySubmitterUserId(
      approvalConfig.submitter_user_id ||
        provider?.config?.recharge_approval?.submitter_user_id ||
        ''
    )
  } catch (error) {
    console.error('Failed to load provider detail for recharge modal:', error)
    syncForm()
  }
}

const loadFeishuUsers = async () => {
  if (feishuUsers.value.length > 0 || loadingFeishuUsers.value) return
  loadingFeishuUsers.value = true
  try {
    const response = await cloudBillingApi.getFeishuUsers()
    const data = extractResponseData(response)
    feishuUsers.value = Array.isArray(data?.users) ? data.users : []
    if (form.submitter_user_id) {
      applySubmitterUserId(form.submitter_user_id)
    }
  } catch (error) {
    console.error('Failed to load Feishu users:', error)
    feishuUsers.value = []
    showError(t('cloudBilling.providers.loadFeishuUsersError'))
  } finally {
    loadingFeishuUsers.value = false
  }
}

const refreshFeishuUsers = async () => {
  if (loadingFeishuUsers.value) return
  loadingFeishuUsers.value = true
  try {
    const response = await cloudBillingApi.refreshFeishuUsers()
    const data = extractResponseData(response)
    feishuUsers.value = Array.isArray(data?.users) ? data.users : []
    if (form.submitter_user_id) {
      applySubmitterUserId(form.submitter_user_id)
    }
  } catch (error) {
    console.error('Failed to refresh Feishu users:', error)
    showError(t('cloudBilling.providers.loadFeishuUsersError'))
  } finally {
    loadingFeishuUsers.value = false
  }
}

const handleSave = async ({ emitSaved = true } = {}) => {
  if (!props.provider?.id) return false
  if (!validateRechargeInfoBeforeSave()) {
    return false
  }
  saving.value = true
  try {
    const rechargeInfoPayload = buildRechargeInfoStorageObject(
      form.recharge_info || ''
    )
    delete rechargeInfoPayload.amount
    delete rechargeInfoPayload.currency
    const existingApproval = extractRechargeApprovalObjectFromSource(
      props.provider?.recharge_info || props.provider?.config || {}
    )
    const approvalPayload = {
      ...existingApproval
    }
    delete approvalPayload.submitter_identifier
    delete approvalPayload.submitter_email
    delete approvalPayload.submitter_mobile
    delete approvalPayload.submitter_contact
    Object.assign(approvalPayload, getSubmitterPayload())
    if (!approvalPayload.submitter_user_label) {
      delete approvalPayload.submitter_user_label
    }
    if (
      Object.values(approvalPayload).some((value) => String(value || '').trim())
    ) {
      rechargeInfoPayload.recharge_approval = approvalPayload
    } else {
      delete rechargeInfoPayload.recharge_approval
    }

    const response = await cloudBillingApi.patchProvider(props.provider.id, {
      recharge_info: JSON.stringify(rechargeInfoPayload, null, 2)
    })
    const savedProvider = extractResponseData(response)
    showSuccess(t('cloudBilling.providers.rechargeInfoSaveSuccess'))
    if (emitSaved) {
      emit('saved', savedProvider)
    }
    return savedProvider || true
  } catch (error) {
    console.error('Failed to save recharge info:', error)
    const errorContext = getRechargeInfoSaveErrorContext(error)
    showError(buildRechargeInfoSaveErrorMessage(errorContext))
    return false
  } finally {
    saving.value = false
  }
}
const openSubmitApprovalDialog = () => {
  if (!props.provider?.id) return
  if (!String(form.recharge_info || '').trim()) {
    showWarning(t('cloudBilling.providers.rechargeInfoEmpty'))
    return
  }
  if (!String(form.submitter_user_id || '').trim()) {
    showWarning(t('cloudBilling.providers.submitterIdentifierRequiredWarning'))
    return
  }
  submitApprovalForm.amount = ''
  submitApprovalForm.expected_date = addDaysToDateString(
    getTodayDateString(),
    7
  )
  showSubmitDialog.value = true
}

const closeSubmitApprovalDialog = () => {
  if (submitting.value) return
  showSubmitDialog.value = false
  submitApprovalForm.amount = ''
  submitApprovalForm.expected_date = ''
}

const submitApprovalFromDialog = async () => {
  if (!props.provider?.id) return
  const submitterPayload = getSubmitterPayload()
  const amount = String(submitApprovalForm.amount || '').trim()
  const expectedDate = String(submitApprovalForm.expected_date || '').trim()
  if (!hasSubmitterPayload(submitterPayload)) {
    showWarning(t('cloudBilling.providers.submitterIdentifierRequiredWarning'))
    return
  }
  if (!amount || !expectedDate) {
    showWarning(t('cloudBilling.providers.rechargeApprovalRequiredFields'))
    return
  }

  submitting.value = true
  try {
    const savedProvider = await handleSave({ emitSaved: false })
    if (!savedProvider) return
    const response = await cloudBillingApi.submitProviderRechargeApproval(
      props.provider.id,
      {
        ...submitterPayload,
        amount,
        expected_date: expectedDate
      }
    )
    const data = extractResponseData(response)
    showSuccess(
      data?.message || t('cloudBilling.providers.submitRechargeApprovalSuccess')
    )
    showSubmitDialog.value = false
    submitApprovalForm.amount = ''
    submitApprovalForm.expected_date = ''
    await loadApprovals()
    emit('saved', savedProvider === true ? props.provider : savedProvider)
  } catch (error) {
    console.error('Failed to submit recharge approval:', error)
    const errorContext = getRechargeApprovalSubmitErrorContext(error)
    if (errorContext.existingApproval) {
      showWarning(
        t('cloudBilling.providers.rechargeApprovalAlreadyExists', {
          instanceCode: errorContext.instanceCode || '-',
          recordId: errorContext.recordId || '-'
        })
      )
      return
    }
    showError(
      errorContext.message ||
        t('cloudBilling.providers.submitRechargeApprovalError')
    )
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.show,
  (visible) => {
    if (!visible) {
      closeSubmitApprovalDialog()
      return
    }
    syncForm()
    loadFeishuUsers()
    hydrateProviderDetail()
    loadApprovals()
  },
  { immediate: true }
)
</script>

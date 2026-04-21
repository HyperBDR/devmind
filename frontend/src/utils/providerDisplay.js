import en from '@/locales/en.json'
import zhCN from '@/locales/zh-CN.json'

const PROVIDER_TYPE_LABEL_KEYS = {
  aws: 'cloudBilling.providers.types.aws',
  huawei: 'cloudBilling.providers.types.huawei',
  'huawei-intl': 'cloudBilling.providers.types.huaweiIntl',
  tencentcloud: 'cloudBilling.providers.types.tencentcloud',
  alibaba: 'cloudBilling.providers.types.alibaba',
  azure: 'cloudBilling.providers.types.azure',
  volcengine: 'cloudBilling.providers.types.volcengine',
  baidu: 'cloudBilling.providers.types.baidu',
  zhipu: 'cloudBilling.providers.types.zhipu'
}

const LOCALE_MESSAGES = [en, zhCN]

function getMessageByPath(messages, path) {
  return path.split('.').reduce((current, key) => current?.[key], messages)
}

function normalizeValue(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
}

export function getProviderTypeLabel(type, t) {
  const key = PROVIDER_TYPE_LABEL_KEYS[type]
  return key ? t(key) : type
}

export function appendProviderNotesLabel(baseLabel, notes) {
  const label = String(baseLabel || '').trim()
  const noteText = String(notes || '').trim()
  if (!noteText) {
    return label
  }
  return label ? `${label} - ${noteText}` : noteText
}

export function getLocalizedProviderDisplayName(provider, t) {
  const providerType = String(provider?.provider_type || '').trim()
  const rawDisplayName = String(provider?.display_name || '').trim()
  if (!providerType) {
    return rawDisplayName
  }

  const localizedLabel = getProviderTypeLabel(providerType, t)
  if (!rawDisplayName) {
    return localizedLabel
  }

  const aliases = new Set([
    normalizeValue(providerType),
    normalizeValue(localizedLabel)
  ])
  const labelKey = PROVIDER_TYPE_LABEL_KEYS[providerType]
  if (labelKey) {
    LOCALE_MESSAGES.forEach((messages) => {
      const candidate = getMessageByPath(messages, labelKey)
      if (candidate) {
        aliases.add(normalizeValue(candidate))
      }
    })
  }

  return aliases.has(normalizeValue(rawDisplayName))
    ? localizedLabel
    : rawDisplayName
}

export function getLocalizedBillingProviderName(billing, t) {
  const baseLabel = getLocalizedProviderDisplayName(
    {
      provider_type: billing?.provider_type,
      display_name:
        billing?.provider_display_name ||
        billing?.provider_name ||
        billing?.provider
    },
    t
  )
  return appendProviderNotesLabel(
    baseLabel,
    billing?.provider_notes || billing?.notes
  )
}

export function getProviderAuthIdentifierLabel(provider, t) {
  const kind = String(provider?.auth_identifier_kind || '').trim()
  const labelKeys = {
    access_key_id: 'cloudBilling.providers.authIdentifierKinds.accessKeyId',
    username: 'cloudBilling.providers.authIdentifierKinds.username',
    client_id: 'cloudBilling.providers.authIdentifierKinds.clientId',
    identifier: 'cloudBilling.providers.authIdentifierKinds.identifier'
  }

  const key = labelKeys[kind] || labelKeys.identifier
  return t(key)
}

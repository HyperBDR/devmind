export const FEATURE_DEFINITIONS = [
  {
    key: 'workspace',
    labelKey: 'platforms.workspace',
    defaultPath: '/dashboard',
    matchers: ['/dashboard', '/settings', '/cloud-billing', '/data-collector']
  },
  {
    key: 'operations_console',
    labelKey: 'platforms.operationsConsole',
    defaultPath: '/operations/dashboard',
    matchers: ['/operations']
  },
  {
    key: 'hyperbdr_dashboard',
    labelKey: 'platforms.hyperbdrDashboard',
    defaultPath: '/hyperbdr-dashboard',
    matchers: ['/hyperbdr-dashboard']
  },
  {
    key: 'llm_ops',
    labelKey: 'platforms.llmOps',
    defaultPath: '/llm-ops',
    matchers: ['/llm-ops']
  },
  {
    key: 'data_ops',
    labelKey: 'platforms.dataOps',
    defaultPath: '/data-ops',
    matchers: ['/data-ops']
  },
  {
    key: 'sales_work_orders',
    labelKey: 'platforms.salesWorkOrders',
    defaultPath: '/sals/dashboard',
    matchers: ['/sals']
  },
  {
    key: 'quotation_management',
    labelKey: 'platforms.quotationManagement',
    defaultPath: '/quotation/dashboard',
    matchers: ['/quotation']
  },
  {
    key: 'admin_console',
    labelKey: 'platforms.adminConsole',
    defaultPath: '/management/users',
    matchers: ['/management', '/llm', '/task-management', '/notifier']
  }
]

export const FEATURE_KEY_SET = new Set(
  FEATURE_DEFINITIONS.map((item) => item.key)
)

const FEATURE_MAP = new Map(FEATURE_DEFINITIONS.map((item) => [item.key, item]))

const FEATURE_ALIASES = {
  cloud_billing: 'operations_console',
  data_collector: 'operations_console',
  data_operations: 'data_ops',
  sals: 'sales_work_orders',
  llm_operations: 'llm_ops',
  llm_ops_management: 'llm_ops',
  llm_console: 'admin_console',
  task_management_console: 'admin_console',
  notification_console: 'admin_console',
  sales_management: 'quotation_management'
}

export function normalizeFeatureKeys(values) {
  if (!Array.isArray(values)) return []

  const seen = new Set()
  return FEATURE_DEFINITIONS.map((item) => item.key).filter((key) => {
    const matches = values.some((value) => {
      const normalized = FEATURE_ALIASES[value] || value
      return normalized === key
    })
    return matches && !seen.has(key) && seen.add(key)
  })
}

export function normalizePlatformKey(value) {
  const normalized = FEATURE_ALIASES[value] || value
  return FEATURE_KEY_SET.has(normalized) ? normalized : ''
}

export function getAccessProfile(user) {
  return (
    user?.access_profile || {
      visible_features: [],
      available_platforms: [],
      preferred_platform: '',
      landing_path: '/dashboard',
      invoice_access: {
        enabled: false,
        role: null,
        capabilities: []
      }
    }
  )
}

function hasAdminAccess(user) {
  if (user?.is_staff === true) return true
  return (user?.roles || []).some((role) =>
    normalizeFeatureKeys(role?.visible_features).includes('admin_console')
  )
}

export function hasFeature(user, featureKey) {
  const normalizedFeatureKey = FEATURE_ALIASES[featureKey] || featureKey
  if (hasAdminAccess(user)) {
    return FEATURE_KEY_SET.has(normalizedFeatureKey)
  }
  const visibleFeatures = normalizeFeatureKeys(
    getAccessProfile(user).visible_features
  )
  return visibleFeatures.includes(normalizedFeatureKey)
}

export function hasQuotationAdminAccess(user) {
  return Boolean(
    user?.is_staff === true
    || user?.is_superuser === true
    || user?.access_profile?.quotation_role === 'quotation_admin'
  )
}

const INVOICE_CAPABILITIES = new Set(['view', 'edit', 'import', 'issue'])

export function hasInvoiceCapability(user, capability) {
  if (!INVOICE_CAPABILITIES.has(capability)) return false
  if (hasAdminAccess(user)) return true
  const invoiceAccess = getAccessProfile(user).invoice_access
  return Boolean(
    invoiceAccess?.enabled &&
    invoiceAccess.capabilities?.includes(capability)
  )
}

export function getAvailablePlatforms(user, t) {
  if (hasAdminAccess(user)) {
    return FEATURE_DEFINITIONS.filter(
      (item) => item.platformVisible !== false
    ).map((item) => ({
      key: item.key,
      label: t ? t(item.labelKey) : item.key,
      defaultPath: item.defaultPath
    }))
  }

  const accessProfile = getAccessProfile(user)
  const platformMap = new Map(
    (accessProfile.available_platforms || []).map((item) => [
      FEATURE_ALIASES[item.key] || item.key,
      item
    ])
  )
  normalizeFeatureKeys(accessProfile.visible_features).forEach((key) => {
    if (!platformMap.has(key)) {
      platformMap.set(key, { key })
    }
  })
  if (!platformMap.has('workspace')) {
    platformMap.set('workspace', { key: 'workspace' })
  }
  return FEATURE_DEFINITIONS.filter(
    (item) => platformMap.has(item.key)
  ).map((item) => {
    const resolved = platformMap.get(item.key)
    return {
      key: item.key,
      label: t ? t(item.labelKey) : item.key,
      defaultPath: resolved?.default_path || item.defaultPath
    }
  })
}

export function getLandingPath(user) {
  const platforms = getAvailablePlatforms(user)
  const hasQuotation = platforms.some(
    (platform) => platform.key === 'quotation_management'
  )
  if (!hasQuotation && hasInvoiceCapability(user, 'view')) {
    return '/quotation/sales/dashboard'
  }

  const preferredPlatform = getAccessProfile(user).preferred_platform
  const preferred = platforms.find(
    (platform) => platform.key === preferredPlatform
  )
  if (preferred) return preferred.defaultPath

  return platforms[0]?.defaultPath || '/dashboard'
}

export function getCurrentPlatformKey(path) {
  const matched = FEATURE_DEFINITIONS
    .flatMap((item) => item.matchers.map((matcher) => ({ item, matcher })))
    .filter(({ matcher }) => path.startsWith(matcher))
    .sort((left, right) => right.matcher.length - left.matcher.length)[0]
  return matched?.item.key || 'workspace'
}

export function getPlatformByKey(platformKey, t) {
  const definition = FEATURE_MAP.get(platformKey)
  if (!definition) return null
  return {
    key: definition.key,
    label: t ? t(definition.labelKey) : definition.key,
    defaultPath: definition.defaultPath
  }
}

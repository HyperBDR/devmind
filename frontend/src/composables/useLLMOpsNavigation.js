import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

export const LIGHT_CORE_SECTIONS = new Set(['metaModels', 'providers'])

export const DATA_HEAVY_SECTIONS = new Set([
  'channels',
  'channelMatrix',
  'collectionHealth',
  'listingRisk',
  'metaModels',
  'modelWorkbench',
  'priceChanges',
  'providers',
  'reconciler',
  'reseller'
])

export const SECTION_KEYS = new Set([
  'monitor',
  'collectionHealth',
  'channelMatrix',
  'modelWorkbench',
  'listingRisk',
  'priceChanges',
  'metaModels',
  'providers',
  'taskLogs',
  'channels',
  'globalConfig',
  'reseller',
  'workflow',
  'reconciler',
  'audit'
])

const NAV_GROUP_STORAGE_KEY = 'llm_ops_expanded_nav_groups'
const SIDEBAR_STORAGE_KEY = 'llm_ops_sidebar_collapsed'
const SECTION_STORAGE_KEY = 'llm_ops_active_section'

const navIcons = {
  audit: ['M4 5h16', 'M4 12h16', 'M4 19h10'],
  channelMatrix: ['M4 6h16', 'M4 12h16', 'M4 18h16', 'M8 6v12', 'M16 6v12'],
  channels: ['M4 7h16', 'M7 7v10', 'M17 7v10', 'M4 17h16'],
  collectionHealth: ['M4 13l4 4L20 5', 'M4 19h16'],
  globalConfig: ['M4 7h16', 'M7 7v10', 'M17 7v10', 'M4 17h16', 'M9 12h6'],
  listingRisk: ['M12 4l8 14H4L12 4Z', 'M12 9v4', 'M12 16h.01'],
  metaModels: ['M12 3l8 4-8 4-8-4 8-4Z', 'M4 12l8 4 8-4', 'M4 17l8 4 8-4'],
  modelWorkbench: ['M5 5h14v14H5Z', 'M8 9h8', 'M8 13h8', 'M8 17h5'],
  monitor: ['M4 19V5', 'M8 19v-6', 'M12 19v-9', 'M16 19v-4', 'M20 19V8'],
  priceChanges: ['M4 16l5-5 4 4 7-8', 'M4 20h16'],
  providers: ['M5 5h14v14H5Z', 'M9 9h6', 'M9 13h6', 'M9 17h3'],
  reconciler: [
    'M4 7h16',
    'M7 7v12',
    'M17 7v12',
    'M4 13h16',
    'M9 17h1',
    'M14 17h1'
  ],
  reseller: ['M6 8h12l-1 12H7L6 8Z', 'M9 8a3 3 0 0 1 6 0'],
  taskLogs: ['M5 4h14v16H5Z', 'M8 8h8', 'M8 12h8', 'M8 16h5'],
  workflow: [
    'M4 6h7',
    'M13 6h7',
    'M11 6l2 2-2 2',
    'M4 18h7',
    'M13 18h7',
    'M11 18l2-2-2-2',
    'M6 8v8',
    'M18 8v8'
  ]
}

export function useLLMOpsNavigation() {
  const { t } = useI18n()
  const activeSection = ref(initialActiveSection())
  const sidebarCollapsed = ref(readStorage(SIDEBAR_STORAGE_KEY) === 'true')
  const expandedNavGroupKeys = ref(readExpandedNavGroupKeys())

  const sidebarToggleLabel = computed(() =>
    sidebarCollapsed.value
      ? t('llmOps.toolbar.expandSidebar')
      : t('llmOps.toolbar.collapseSidebar')
  )

  const navItems = computed(() => [
    createNavItem('monitor', 'Monitor'),
    createNavItem('collectionHealth', 'Health'),
    createNavItem('modelWorkbench', 'Workbench'),
    createNavItem('priceChanges', 'Changes'),
    createNavItem('metaModels', 'Meta Models'),
    createNavItem('providers', 'Sources'),
    createNavItem('taskLogs', 'Task Logs'),
    createNavItem('channels', 'Channels'),
    createNavItem('channelMatrix', 'Matrix'),
    createNavItem('reseller', 'Reseller'),
    createNavItem('workflow', 'Workflow'),
    createNavItem('listingRisk', 'Risk'),
    createNavItem('globalConfig', 'Global Config'),
    createNavItem('reconciler', 'Reconciliation'),
    createNavItem('audit', 'Audit')
  ])

  const navGroups = computed(() =>
    [
      createNavGroup('overview', 'llmOps.navGroups.overview', ['monitor']),
      createNavGroup('catalog', 'llmOps.navGroups.catalog', [
        'metaModels',
        'providers'
      ]),
      createNavGroup('distribution', 'llmOps.navGroups.distribution', [
        'channels',
        'reseller',
        'workflow'
      ]),
      createNavGroup('dashboards', 'llmOps.navGroups.dashboards', [
        'collectionHealth',
        'channelMatrix',
        'modelWorkbench',
        'listingRisk',
        'priceChanges'
      ]),
      createNavGroup('governance', 'llmOps.navGroups.governance', [
        'reconciler',
        'audit',
        'globalConfig',
        'taskLogs'
      ])
    ].filter((group) => group.items.length > 0)
  )

  const activeNav = computed(
    () =>
      navItems.value.find((item) => item.key === activeSection.value) ||
      navItems.value[0]
  )

  watch(activeSection, (section) => {
    if (!SECTION_KEYS.has(section)) return
    writeStorage(SECTION_STORAGE_KEY, section)
    if (typeof window === 'undefined') return
    const url = new URL(window.location.href)
    url.searchParams.set('section', section)
    window.history.replaceState({}, '', `${url.pathname}${url.search}`)
  })

  function createNavItem(key, eyebrow) {
    return {
      key,
      label: t(`llmOps.nav.${key}.label`),
      eyebrow,
      description: t(`llmOps.nav.${key}.description`),
      icon: navIcons[key] || []
    }
  }

  function findNavItem(key) {
    return navItems.value.find((item) => item.key === key)
  }

  function createNavGroup(key, labelKey, itemKeys) {
    const items = itemKeys.map(findNavItem).filter(Boolean)

    return {
      key,
      label: t(labelKey),
      icon: items[0]?.icon || [],
      items
    }
  }

  function isNavGroupExpanded(key) {
    return expandedNavGroupKeys.value.includes(key)
  }

  function setExpandedNavGroupKeys(keys) {
    expandedNavGroupKeys.value = keys
    writeStorage(NAV_GROUP_STORAGE_KEY, JSON.stringify(keys))
  }

  function toggleNavGroup(key) {
    const expandedKeys = new Set(expandedNavGroupKeys.value)
    const shouldExpand = sidebarCollapsed.value || !isNavGroupExpanded(key)

    if (sidebarCollapsed.value) {
      sidebarCollapsed.value = false
      writeStorage(SIDEBAR_STORAGE_KEY, 'false')
    }

    if (shouldExpand) {
      expandedKeys.add(key)
    } else {
      expandedKeys.delete(key)
    }

    setExpandedNavGroupKeys(Array.from(expandedKeys))
  }

  function selectNavItem(groupKey, itemKey) {
    activeSection.value = itemKey
    setExpandedNavGroupKeys([groupKey])
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    writeStorage(SIDEBAR_STORAGE_KEY, sidebarCollapsed.value ? 'true' : 'false')
  }

  function setActiveSection(section) {
    activeSection.value = section
  }

  return {
    activeNav,
    activeSection,
    expandedNavGroupKeys,
    isNavGroupExpanded,
    navGroups,
    navItems,
    selectNavItem,
    setActiveSection,
    sidebarCollapsed,
    sidebarToggleLabel,
    toggleNavGroup,
    toggleSidebar
  }
}

function initialActiveSection() {
  if (typeof window !== 'undefined') {
    const querySection = new URLSearchParams(window.location.search).get(
      'section'
    )
    if (SECTION_KEYS.has(querySection)) return querySection
  }
  const storedSection = readStorage(SECTION_STORAGE_KEY)
  if (SECTION_KEYS.has(storedSection)) return storedSection
  return 'monitor'
}

function readExpandedNavGroupKeys() {
  try {
    const parsedValue = JSON.parse(readStorage(NAV_GROUP_STORAGE_KEY) || '[]')

    if (!Array.isArray(parsedValue)) return []

    return parsedValue.filter((item) => typeof item === 'string')
  } catch {
    return []
  }
}

function readStorage(key) {
  if (typeof localStorage === 'undefined') return ''
  return localStorage.getItem(key) || ''
}

function writeStorage(key, value) {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(key, value)
}

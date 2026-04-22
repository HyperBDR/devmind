/**
 * Mock data for HyperBDR Dashboard
 * Mirrors the data structure from HyperBDRHub React constants
 */

export const KPIS = [
  {
    key: 'total_tenants',
    labelKey: 'hyperbdrDashboard.totalTenants',
    value: '1,050',
    trend: 'up',
    trendPercent: '+12.5%',
    type: 'default'
  },
  {
    key: 'poc',
    labelKey: 'hyperbdrDashboard.poc',
    value: '780',
    trend: 'up',
    trendPercent: '+10%',
    progress: 74,
    progressLabelKey: 'hyperbdrDashboard.pocProgress',
    type: 'primary'
  },
  {
    key: 'official',
    labelKey: 'hyperbdrDashboard.official',
    value: '270',
    trend: 'up',
    trendPercent: '+10%',
    progress: 78,
    progressLabelKey: 'hyperbdrDashboard.officialProgress',
    type: 'secondary'
  },
  {
    key: 'conversion_rate',
    labelKey: 'hyperbdrDashboard.conversionRate',
    value: '34.6%',
    trend: 'up',
    trendPercent: '+5.4%',
    type: 'gradient'
  }
]

export const FOCUS_CARDS = [
  {
    key: 'expiring_soon',
    titleKey: 'hyperbdrDashboard.expiringSoon',
    value: 12,
    color: '#ef4444',
    colorBg: 'bg-red-50',
    colorText: 'text-red-600',
    icon: 'calendar',
    statsKey: 'hyperbdrDashboard.expiringSoonDesc',
    statsValueKey: 'hyperbdrDashboard.statsDays',
    statsValueDays: 30
  },
  {
    key: 'high_potential',
    titleKey: 'hyperbdrDashboard.highPotential',
    value: 8,
    color: '#f97316',
    colorBg: 'bg-orange-50',
    colorText: 'text-orange-600',
    icon: 'trending',
    statsKey: 'hyperbdrDashboard.highPotentialDesc',
    statsValueKey: 'hyperbdrDashboard.statsUtil',
    statsValueThreshold: 60
  },
  {
    key: 'poc_expiring',
    titleKey: 'hyperbdrDashboard.pocExpiring',
    value: 5,
    color: '#eab308',
    colorBg: 'bg-yellow-50',
    colorText: 'text-yellow-600',
    icon: 'calendar',
    statsKey: 'hyperbdrDashboard.pocExpiringDesc',
    statsValueKey: 'hyperbdrDashboard.statsDays',
    statsValueDays: 7
  },
  {
    key: 'low_activity',
    titleKey: 'hyperbdrDashboard.lowActivity',
    value: 2,
    color: '#64748b',
    colorBg: 'bg-slate-50',
    colorText: 'text-slate-500',
    icon: 'users',
    statsKey: 'hyperbdrDashboard.lowActivityDesc',
    statsValueKey: 'hyperbdrDashboard.statsUtil',
    statsValueThreshold: 30
  }
]

// Trend data generator
function getTrendData(filterKey) {
  let dayKeys = []
  let pocBase = 65
  let pocRange = 20
  const officialBaseRatio = 0.346

  switch (filterKey) {
    case 'filterWeek':
    case 'filterMonth':
      dayKeys = Array.from(
        { length: filterKey === 'filterWeek' ? 7 : 30 },
        (_, i) => `${i + 1}`
      )
      pocBase = 25
      pocRange = 10
      break
    case 'filterHalfYear':
      dayKeys = ['10', '11', '12', '1', '2', '3']
      pocBase = 60
      pocRange = 15
      break
    case 'filterYear':
    default:
      dayKeys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
      pocBase = 65
      pocRange = 20
      break
  }

  return dayKeys.map((key, index) => {
    const trend = Math.sin(index / (dayKeys.length / 3)) * (pocRange / 2)
    const poc = Math.max(
      1,
      Math.floor(pocBase + trend + (Math.random() - 0.5) * pocRange)
    )
    const noise = (Math.random() - 0.5) * 0.08
    const official = Math.max(0, Math.floor(poc * (officialBaseRatio + noise)))
    const rate = poc > 0 ? Number(((official / poc) * 100).toFixed(1)) : 0
    return { key, poc, official, rate }
  })
}

export { getTrendData }

export const FUNNEL_DATA = [
  {
    name: '全部租户',
    value: 1050,
    labelKey: 'hyperbdrDashboard.allTenants',
    subLabel: '100% 基数',
    color: '#f1f5f9'
  },
  {
    name: 'PoC 租户',
    value: 780,
    labelKey: 'hyperbdrDashboard.pocTenant',
    subLabel: '占总比 74.3%',
    color: '#dbeafe'
  },
  {
    name: '正式',
    value: 270,
    labelKey: 'hyperbdrDashboard.officialTenant',
    subLabel: '转化率 34.6%',
    color: '#ede9fe'
  }
]

export const UTILIZATION_STRUCTURE = [
  {
    type: 'PoC',
    labelKey: 'hyperbdrDashboard.pocTenants',
    segments: [
      {
        label: '高使用 (>80%)',
        labelKey: 'hyperbdrDashboard.highUtil',
        value: 45,
        count: 351,
        color: '#2563eb'
      },
      {
        label: '中使用 (50~80%)',
        labelKey: 'hyperbdrDashboard.mediumUtil',
        value: 35,
        count: 273,
        color: '#60a5fa'
      },
      {
        label: '低使用 (<50%)',
        labelKey: 'hyperbdrDashboard.lowUtil',
        value: 20,
        count: 156,
        color: '#dbeafe'
      }
    ]
  },
  {
    type: 'Official',
    labelKey: 'hyperbdrDashboard.officialTenants',
    segments: [
      {
        label: '高使用 (>80%)',
        labelKey: 'hyperbdrDashboard.highUtil',
        value: 65,
        count: 175,
        color: '#8a4cfc'
      },
      {
        label: '中使用 (50~80%)',
        labelKey: 'hyperbdrDashboard.mediumUtil',
        value: 25,
        count: 68,
        color: '#a78bfa'
      },
      {
        label: '低使用 (<50%)',
        labelKey: 'hyperbdrDashboard.lowUtil',
        value: 10,
        count: 27,
        color: '#ddd6fe'
      }
    ]
  }
]

export const TENANTS = [
  {
    id: '1',
    name: '泰和科技云',
    type: 'migration',
    sceneLabelKey: 'hyperbdrDashboard.sceneTypeMigration',
    cloudPlatform: 'AWS',
    authType: 'PoC',
    validAuth: 15000,
    used: 12600,
    utilization: 84,
    remainingDays: 3,
    status: '联系跟进'
  },
  {
    id: '2',
    name: '远瞻科技',
    type: 'disaster',
    sceneLabelKey: 'hyperbdrDashboard.sceneTypeDisaster',
    cloudPlatform: '华为云',
    authType: 'PoC',
    validAuth: 10000,
    used: 7800,
    utilization: 78,
    remainingDays: 12,
    status: '联系跟进'
  },
  {
    id: '3',
    name: '北极星数据',
    type: 'migration',
    sceneLabelKey: 'hyperbdrDashboard.sceneTypeMigration',
    cloudPlatform: 'AWS',
    authType: 'Official',
    validAuth: 50000,
    used: 46000,
    utilization: 92,
    remainingDays: 284,
    status: '联系跟进'
  },
  {
    id: '4',
    name: '幻影传媒',
    type: 'disaster',
    sceneLabelKey: 'hyperbdrDashboard.sceneTypeDisaster',
    cloudPlatform: '华为云',
    authType: 'Official',
    validAuth: 20000,
    used: 3000,
    utilization: 15,
    remainingDays: 192,
    status: '联系跟进'
  },
  {
    id: '5',
    name: '星辰重工',
    type: 'migration',
    sceneLabelKey: 'hyperbdrDashboard.sceneTypeMigration',
    cloudPlatform: 'AWS',
    authType: 'PoC',
    validAuth: 5000,
    used: 4500,
    utilization: 90,
    remainingDays: 5,
    status: '联系跟进'
  },
  {
    id: '6',
    name: '云海物流',
    type: 'disaster',
    sceneLabelKey: 'hyperbdrDashboard.sceneTypeDisaster',
    cloudPlatform: '华为云',
    authType: 'PoC',
    validAuth: 8000,
    used: 2000,
    utilization: 25,
    remainingDays: 45,
    status: '联系跟进'
  },
  {
    id: '7',
    name: '极光软件',
    type: 'migration',
    sceneLabelKey: 'hyperbdrDashboard.sceneTypeMigration',
    cloudPlatform: 'AWS',
    authType: 'Official',
    validAuth: 100000,
    used: 85000,
    utilization: 85,
    remainingDays: 150,
    status: '联系跟进'
  },
  {
    id: '8',
    name: '蓝天航空',
    type: 'disaster',
    sceneLabelKey: 'hyperbdrDashboard.sceneTypeDisaster',
    cloudPlatform: '华为云',
    authType: 'Official',
    validAuth: 30000,
    used: 28000,
    utilization: 93,
    remainingDays: 10,
    status: '联系跟进'
  }
]

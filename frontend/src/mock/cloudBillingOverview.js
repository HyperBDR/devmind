export const cloudBillingOverviewSummary = {
  estimatedTotal: 482360.5,
  currentConsumed: 318245.2,
  dailyAverage: 10608.17,
  peakCost: 26890.35,
  peakDate: '2026-03-18',
  trend: [
    { date: '03-20', cny: 9200, usd: 1280 },
    { date: '03-21', cny: 10150, usd: 1360 },
    { date: '03-22', cny: 10890, usd: 1425 },
    { date: '03-23', cny: 11240, usd: 1490 },
    { date: '03-24', cny: 11860, usd: 1535 },
    { date: '03-25', cny: 12120, usd: 1590 },
    { date: '03-26', cny: 12680, usd: 1645 }
  ]
}

export const cloudBillingOverviewCurrencyBreakdown = [
  {
    code: 'CNY',
    name: 'Chinese Yuan',
    value: 286540.22,
    original_value: 286540.22,
    percentage: 61,
    color: '#2563eb'
  },
  {
    code: 'USD',
    name: 'US Dollar',
    value: 182350.41,
    original_value: 25503.55,
    percentage: 39,
    color: '#10b981'
  }
]

export const cloudBillingOverviewFinancialHealth = {
  totalFunds: 96320.8,
  totalDays: 12,
  bottleneck: 'Huawei Intl - Global Production',
  rechargeAlerts: [
    {
      name: 'Huawei Intl - Global Production',
      category: 'Cloud',
      days_remaining: 6
    },
    { name: 'AWS - Main Settlement', category: 'Cloud', days_remaining: 9 },
    { name: 'Zhipu AI', category: 'LLM', days_remaining: 14 },
    { name: 'Azure - Europe', category: 'Cloud', days_remaining: 18 }
  ]
}

export const cloudBillingOverviewAccounts = [
  {
    id: 'acct-hw-intl-1',
    name: 'Huawei Intl - Global Production',
    provider: '华为云（国际）',
    providerType: 'huawei-intl',
    notes: '核心生产账号',
    category: 'Cloud',
    cost: 85690.25,
    percentage: 18.6,
    change: 12.4,
    risk: 'high',
    balance: 0,
    balanceCurrency: 'USD',
    creditLimit: 12000,
    creditLimitCurrency: 'USD',
    displayFunds: 12000,
    displayFundsCurrency: 'USD',
    daysRemaining: 6,
    type: 'postpaid',
    usageRate: 78,
    accountId: 'hw-intl-prod',
    trend: [
      { date: '03-20', value: 16800 },
      { date: '03-21', value: 15950 },
      { date: '03-22', value: 15100 },
      { date: '03-23', value: 14320 },
      { date: '03-24', value: 13680 },
      { date: '03-25', value: 12940 },
      { date: '03-26', value: 12000 }
    ]
  },
  {
    id: 'acct-aws-1',
    name: 'AWS Main Settlement',
    provider: 'AWS',
    providerType: 'aws',
    notes: '北美核心业务',
    category: 'Cloud',
    cost: 124500.4,
    percentage: 26.8,
    change: 8.1,
    risk: 'high',
    balance: 0,
    balanceCurrency: 'USD',
    creditLimit: 18500,
    creditLimitCurrency: 'USD',
    displayFunds: 18500,
    displayFundsCurrency: 'USD',
    daysRemaining: 9,
    type: 'postpaid',
    usageRate: 64,
    accountId: 'aws-main',
    trend: [
      { date: '03-20', value: 24300 },
      { date: '03-21', value: 23150 },
      { date: '03-22', value: 22520 },
      { date: '03-23', value: 21480 },
      { date: '03-24', value: 20520 },
      { date: '03-25', value: 19460 },
      { date: '03-26', value: 18500 }
    ]
  },
  {
    id: 'acct-azure-1',
    name: 'Azure Europe',
    provider: 'Azure',
    providerType: 'azure',
    notes: '欧洲区域订阅',
    category: 'Cloud',
    cost: 76380.18,
    percentage: 16.2,
    change: 5.6,
    risk: 'medium',
    balance: 0,
    balanceCurrency: 'USD',
    creditLimit: 8600,
    creditLimitCurrency: 'USD',
    displayFunds: 8600,
    displayFundsCurrency: 'USD',
    daysRemaining: 18,
    type: 'postpaid',
    usageRate: 52,
    accountId: 'azure-eu',
    trend: [
      { date: '03-20', value: 11200 },
      { date: '03-21', value: 10850 },
      { date: '03-22', value: 10220 },
      { date: '03-23', value: 9780 },
      { date: '03-24', value: 9310 },
      { date: '03-25', value: 8960 },
      { date: '03-26', value: 8600 }
    ]
  },
  {
    id: 'acct-zhipu-1',
    name: '智谱 AI',
    provider: '智谱 AI',
    providerType: 'zhipu',
    notes: '郑伟自用',
    category: 'LLM',
    cost: 38950.66,
    percentage: 8.4,
    change: 14.2,
    risk: 'medium',
    balance: 6840.2,
    balanceCurrency: 'CNY',
    creditLimit: null,
    creditLimitCurrency: '',
    displayFunds: 6840.2,
    displayFundsCurrency: 'CNY',
    daysRemaining: 14,
    type: 'prepaid',
    usageRate: 41,
    accountId: 'zhipu-self',
    trend: [
      { date: '03-20', value: 9120 },
      { date: '03-21', value: 8740 },
      { date: '03-22', value: 8360 },
      { date: '03-23', value: 7950 },
      { date: '03-24', value: 7540 },
      { date: '03-25', value: 7180 },
      { date: '03-26', value: 6840 }
    ]
  },
  {
    id: 'acct-alibaba-1',
    name: 'Alibaba Shanghai',
    provider: '阿里云',
    providerType: 'alibaba',
    notes: '国内推理服务',
    category: 'Cloud',
    cost: 55820.37,
    percentage: 11.9,
    change: 4.3,
    risk: 'low',
    balance: 22880.6,
    balanceCurrency: 'CNY',
    creditLimit: null,
    creditLimitCurrency: '',
    displayFunds: 22880.6,
    displayFundsCurrency: 'CNY',
    daysRemaining: 35,
    type: 'prepaid',
    usageRate: 27,
    accountId: 'ali-sh-prod',
    trend: [
      { date: '03-20', value: 24600 },
      { date: '03-21', value: 24280 },
      { date: '03-22', value: 23920 },
      { date: '03-23', value: 23510 },
      { date: '03-24', value: 23280 },
      { date: '03-25', value: 23060 },
      { date: '03-26', value: 22880 }
    ]
  },
  {
    id: 'acct-baidu-1',
    name: 'Baidu AI Cloud',
    provider: '百度智能云',
    providerType: 'baidu',
    notes: '向量检索业务',
    category: 'Cloud',
    cost: 27018.54,
    percentage: 5.8,
    change: 3.2,
    risk: 'low',
    balance: 11420.0,
    balanceCurrency: 'CNY',
    creditLimit: null,
    creditLimitCurrency: '',
    displayFunds: 11420.0,
    displayFundsCurrency: 'CNY',
    daysRemaining: 28,
    type: 'prepaid',
    usageRate: 33,
    accountId: 'baidu-vec',
    trend: [
      { date: '03-20', value: 12880 },
      { date: '03-21', value: 12540 },
      { date: '03-22', value: 12230 },
      { date: '03-23', value: 11980 },
      { date: '03-24', value: 11750 },
      { date: '03-25', value: 11590 },
      { date: '03-26', value: 11420 }
    ]
  }
]

/**
 * i18n — English / Chinese translation texts for SALs Dashboard.
 * All UI copy used in App.tsx and StatCard.tsx is keyed here.
 */

export type Language = "en" | "zh";

export const translations: Record<Language, Record<string, string>> = {
  en: {
    // ── Header ─────────────────────────────────────────────────
    title: "Sales Operations Console",
    subtitle: "Sales Work Order Analytics",
    recordsFound: "records",
    refresh: "Refresh",

    // ── KPI Cards ───────────────────────────────────────────────
    totalVolume: "Total Opportunities",
    totalVolumeSub: "All-time work orders",
    slaCompliance: "Win Rate",
    slaTarget: "vs target",
    resolved: "Won",
    resolvedRate: "Win rate",
    pending: "Active",
    pendingRatio: "Active ratio",
    avgResolve: "Avg Quote",
    mttrTrend: "Quote trend",
    p1Overdue: "In Negotiation",
    criticalAttention: "Needs attention",

    // ── Monthly Trend Chart ─────────────────────────────────────
    monthlyTrend: "Monthly Trend",
    trendSub: "Volume & Won Amount",
    volume: "Volume",
    avgHours: "Won Amount",

    // ── Distribution Charts ──────────────────────────────────────
    priorityDist: "Stage Distribution",
    stateBreakdown: "State Breakdown",

    // ── Efficiency Analysis ──────────────────────────────────────
    efficiencyAnalysis: "Sales Rep Performance",
    efficiencySub: "Win rate and deal amount by sales rep",
    groups: "Teams",
    resolvers: "Sales Reps",

    // ── Client Health ───────────────────────────────────────────
    clientHealth: "Account Overview",
    bubbleSub: "Won amount vs deal count (bubble size = deal count)",
    productExposure: "Product Mix",
    slaByTier: "Win Rate by Stage",

    // ── Work Order Registry ──────────────────────────────────────
    incidentRegistry: "Work Order Registry",
    tier: "Stage",
    all: "All",
    state: "State",
    group: "Sales Rep",
    reset: "Reset",
    id: "WO #",
    status: "Stage",
    company: "Account",
    requestor: "Contact",
    summary: "Product",
    assignee: "Sales Rep",
    logged: "Created",
    duration: "Quote",
  },

  zh: {
    // ── Header ─────────────────────────────────────────────────
    title: "销售运营控制台",
    subtitle: "销售工单数据分析",
    recordsFound: "条记录",
    refresh: "刷新",

    // ── KPI Cards ───────────────────────────────────────────────
    totalVolume: "商机总数",
    totalVolumeSub: "全部工单数",
    slaCompliance: "赢单率",
    slaTarget: "目标",
    resolved: "已成交",
    resolvedRate: "成交率",
    pending: "进行中",
    pendingRatio: "活跃占比",
    avgResolve: "平均报价",
    mttrTrend: "报价趋势",
    p1Overdue: "谈判中",
    criticalAttention: "需重点关注",

    // ── Monthly Trend Chart ─────────────────────────────────────
    monthlyTrend: "月度趋势",
    trendSub: "工单量与成交金额",
    volume: "工单量",
    avgHours: "成交金额",

    // ── Distribution Charts ─────────────────────────────────────
    priorityDist: "阶段分布",
    stateBreakdown: "状态分布",

    // ── Efficiency Analysis ─────────────────────────────────────
    efficiencyAnalysis: "销售业绩",
    efficiencySub: "按销售统计成交率和成交金额",
    groups: "团队",
    resolvers: "销售",

    // ── Client Health ───────────────────────────────────────────
    clientHealth: "客户概览",
    bubbleSub: "成交金额 vs 工单数（气泡大小 = 工单数）",
    productExposure: "产品分布",
    slaByTier: "各阶段赢单率",

    // ── Work Order Registry ──────────────────────────────────────
    incidentRegistry: "工单列表",
    tier: "阶段",
    all: "全部",
    state: "状态",
    group: "销售",
    reset: "重置",
    id: "工单号",
    status: "阶段",
    company: "客户",
    requestor: "联系人",
    summary: "产品",
    assignee: "销售",
    logged: "创建时间",
    duration: "报价",
  },
};

/**
 * mockData.ts — Sales Work Order mock dataset.
 * Replaces the previous Incident mock data with sales opportunity data.
 */

import type { WorkOrder, SaleStage, OrderState } from './types';

export { type SaleStage, type OrderState, type WorkOrder } from './types';
export { STAGE_COLORS, STAGE_ORDER } from './types';

const STAGES: SaleStage[] = ['Prospect', 'Qualified', 'Proposal Sent', 'Negotiation', 'Won', 'Lost'];
const STATES: OrderState[] = ['New', 'In Progress', 'On Hold', 'Closed Won', 'Closed Lost', 'Canceled'];

const COMPANIES = [
  '华星科技', '鹏程电子', '恒通机械', '明远软件', '中科智云',
  '云帆数据', '蓝海工业', '天工智造', '智联供应链', '博创科技',
  '凌云系统', '盛世光电', '锐捷网络', '深视科技', '新锐医疗',
  '安恒信息', '航天云网', '华腾数据', '赛乐奇生物', '睿智教育',
];

const PRODUCTS = [
  'CRM 企业版', 'ERP 专业版', '数据分析平台', 'AI 智能助手',
  '云存储服务', '安全网关', '低代码平台', '流程自动化',
  '营销云', '客服系统',
];

const SALES_REPS = [
  '张伟', '李娜', '王强', '陈静', '刘洋',
  '赵敏', '黄磊', '周涛', '吴霞', '郑凯',
];

const SOURCES = [
  '官网表单', '展会获客', '客户推荐', '线上广告',
  '电话营销', '合作伙伴', '公众号', '行业论坛',
];

function rand<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randAmount(): number {
  const bases = [5, 8, 10, 15, 20, 30, 50, 80, 100, 150, 200];
  const base = rand(bases) * 10000;
  return base + Math.floor(Math.random() * base * 0.5);
}

function dateStr(daysAgo: number): string {
  const d = new Date('2026-05-02');
  d.setDate(d.getDate() - daysAgo);
  return d.toISOString().split('T')[0];
}

function makeWorkOrder(index: number): WorkOrder {
  const stage = rand(STAGES);
  const state = stage === 'Won' ? 'Closed Won'
              : stage === 'Lost' ? 'Closed Lost'
              : rand(STATES.filter(s => !s.startsWith('Closed')));
  const quote = randAmount();
  const dealAmount = stage === 'Won' ? Math.round(quote * (0.85 + Math.random() * 0.2)) : null;
  const createdDaysAgo = Math.floor(Math.random() * 120) + 1;
  const closedAt = state.startsWith('Closed') || state === 'Canceled'
    ? dateStr(Math.max(0, createdDaysAgo - Math.floor(Math.random() * 20)))
    : null;

  return {
    id: `wo-${index.toString().padStart(3, '0')}`,
    number: `WO-2026-${(1000 + index).toString()}`,
    stage,
    state,
    company: rand(COMPANIES),
    contact: rand(['李', '王', '张', '陈', '刘', '周', '吴', '徐', '孙', '马']) + '经理',
    product_name: rand(PRODUCTS),
    quote_amount: quote,
    deal_amount: dealAmount,
    sales_rep: rand(SALES_REPS),
    created_at: dateStr(createdDaysAgo),
    expected_close_date: dateStr(createdDaysAgo - 30),
    closed_at: closedAt,
    source: rand(SOURCES),
    notes: '',
  };
}

export const MOCK_WORK_ORDERS: WorkOrder[] = Array.from({ length: 50 }, (_, i) => makeWorkOrder(i + 1));

export type Priority = 'P1' | 'P2' | 'P3' | 'P4'; // kept for SLA-compat chart

// ── Statistics helpers ──────────────────────────────────────────

export function getStats(orders: WorkOrder[]) {
  const total = orders.length;
  const won = orders.filter(o => o.stage === 'Won').length;
  const lost = orders.filter(o => o.stage === 'Lost').length;
  const active = orders.filter(o => !['Won', 'Lost'].includes(o.stage)).length;
  const totalQuote = orders.reduce((s, o) => s + o.quote_amount, 0);
  const wonAmount = orders.filter(o => o.deal_amount != null).reduce((s, o) => s + (o.deal_amount ?? 0), 0);
  const avgQuote = total > 0 ? totalQuote / total : 0;
  const winRate = (won + lost) > 0 ? won / (won + lost) : 0;
  const inNegotiation = orders.filter(o => o.stage === 'Negotiation').length;

  return {
    total,
    won,
    lost,
    active,
    totalQuote,
    wonAmount,
    avgQuote,
    winRate,
    inNegotiation,
    quoteRate: totalQuote > 0 ? wonAmount / totalQuote : 0,
  };
}

export function getTrendData(orders: WorkOrder[]) {
  const months = ['Jan', 'Feb', 'Mar', 'Apr'];
  return months.map((month, i) => {
    const monthOrders = orders.filter(o => {
      const m = new Date(o.created_at).getMonth();
      return m === i;
    });
    return {
      month,
      count: monthOrders.length,
      wonAmount: monthOrders
        .filter(o => o.deal_amount != null)
        .reduce((s, o) => s + (o.deal_amount ?? 0), 0),
    };
  });
}

export function getStageData(orders: WorkOrder[]) {
  return STAGES.map(stage => ({
    name: stage,
    value: orders.filter(o => o.stage === stage).length,
  }));
}

export function getStateData(orders: WorkOrder[]) {
  return STATES.map(state => ({
    name: state,
    value: orders.filter(o => o.state === state).length,
  }));
}

export function getRepStats(orders: WorkOrder[]) {
  const map: Record<string, { won: number; total: number; amount: number }> = {};
  for (const o of orders) {
    if (!map[o.sales_rep]) map[o.sales_rep] = { won: 0, total: 0, amount: 0 };
    map[o.sales_rep].total++;
    if (o.stage === 'Won') {
      map[o.sales_rep].won++;
      map[o.sales_rep].amount += o.deal_amount ?? 0;
    }
  }
  return Object.entries(map).map(([name, v]) => ({
    name,
    ...v,
    winRate: v.total > 0 ? v.won / v.total : 0,
    avgAmount: v.won > 0 ? v.amount / v.won : 0,
  }));
}

export function getCompanyStats(orders: WorkOrder[]) {
  const map: Record<string, { volume: number; wonAmount: number; stages: SaleStage[] }> = {};
  for (const o of orders) {
    if (!map[o.company]) map[o.company] = { volume: 0, wonAmount: 0, stages: [] };
    map[o.company].volume++;
    if (o.deal_amount != null) map[o.company].wonAmount += o.deal_amount;
    if (!map[o.company].stages.includes(o.stage)) map[o.company].stages.push(o.stage);
  }
  return Object.entries(map)
    .map(([name, v]) => ({ name, volume: v.volume, wonAmount: v.wonAmount, stages: v.stages }))
    .sort((a, b) => b.wonAmount - a.wonAmount)
    .slice(0, 15);
}

export function getProductData(orders: WorkOrder[]) {
  const map: Record<string, { total: number; wonAmount: number }> = {};
  for (const o of orders) {
    if (!map[o.product_name]) map[o.product_name] = { total: 0, wonAmount: 0 };
    map[o.product_name].total++;
    if (o.deal_amount != null) map[o.product_name].wonAmount += o.deal_amount;
  }
  return Object.entries(map)
    .map(([name, v]) => ({ name, total: v.total, value: v.wonAmount }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);
}

export function getStageConversionData(orders: WorkOrder[]) {
  return STAGES.map((stage, i) => ({
    name: stage,
    count: orders.filter(o => o.stage === stage).length,
    // cumulative conversion rate
    conversionRate: orders.filter(o => {
      const idx = STAGES.indexOf(o.stage);
      return idx <= i;
    }).length / orders.length,
  }));
}

// ── Backward-compatible aliases for App.tsx (still uses old API names) ──

/** @deprecated use MOCK_WORK_ORDERS */
export const MOCK_INCIDENTS = MOCK_WORK_ORDERS;

/** @deprecated use getStageData */
export const getPriorityData = getStageData;

/** @deprecated use getRepStats */
export const getGroupStats = getRepStats;
export { getRepStats as getUserStats };

/** @deprecated use getCompanyStats */
export const getClientHealthData = getCompanyStats;

/** @deprecated use getStageData for stage breakdown */
export const getSlaByPriority = getStageData;

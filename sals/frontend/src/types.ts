/**
 * types.ts — Sales Work Order domain types.
 * Replaces the previous Incident / Priority / IncidentState model.
 */

export type SaleStage =
  | 'Prospect'      // 潜在客户
  | 'Qualified'     // 已qualify
  | 'Proposal Sent' // 已发报价
  | 'Negotiation'  // 谈判中
  | 'Won'          // 赢单
  | 'Lost';        // 输单

export type OrderState =
  | 'New'          // 新建
  | 'In Progress'  // 处理中
  | 'On Hold'     // 暂停
  | 'Closed Won'  // 已成交
  | 'Closed Lost' // 已流失
  | 'Canceled';   // 已取消

/** 销售工单 / 销售机会 */
export interface WorkOrder {
  id: string;
  /** 展示编号，如 "WO-2026-0001" */
  number: string;
  /** 销售阶段 */
  stage: SaleStage;
  /** 工单状态 */
  state: OrderState;
  /** 客户公司名 */
  company: string;
  /** 联系人姓名 */
  contact: string;
  /** 产品名称 */
  product_name: string;
  /** 报价金额（人民币） */
  quote_amount: number;
  /** 实际成交金额 */
  deal_amount: number | null;
  /** 负责销售 */
  sales_rep: string;
  /** 创建时间 */
  created_at: string;
  /** 预计成交日期 */
  expected_close_date: string;
  /** 实际关闭时间（赢单/输单时） */
  closed_at: string | null;
  /** 商机来源 */
  source: string;
  /** 备注 */
  notes: string;
}

/** 阶段颜色映射 */
export const STAGE_COLORS: Record<SaleStage, string> = {
  'Prospect':      '#94a3b8', // slate-400
  'Qualified':      '#3b82f6', // blue-500
  'Proposal Sent':  '#f59e0b', // amber-500
  'Negotiation':    '#8b5cf6', // violet-500
  'Won':            '#10b981', // emerald-500
  'Lost':           '#f43f5e', // rose-500
};

export const STAGE_ORDER: SaleStage[] = [
  'Prospect',
  'Qualified',
  'Proposal Sent',
  'Negotiation',
  'Won',
  'Lost',
];

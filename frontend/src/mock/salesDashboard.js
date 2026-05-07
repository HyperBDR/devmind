/**
 * 售后工单 Dashboard 模拟数据
 * 用于前端独立开发/调试，无需启动后端服务
 */
export const mockDashboard = {
  kpi: {
    total: 486,
    pending: 72,
    in_progress: 38,
    resolved: 218,
    closed: 124,
    canceled: 34,
    resolved_rate: 70.4,
    sla_rate: 82.3,
    avg_resolve_hours: 18.6,
    p1_total: 52,
    p1_overdue: 8,
    p2_total: 128
  },

  priority_dist: [
    { priority: 'P1', count: 52 },
    { priority: 'P2', count: 128 },
    { priority: 'P3', count: 186 },
    { priority: 'P4', count: 120 }
  ],

  state_dist: [
    { state: 'New', count: 28 },
    { state: 'In Progress', count: 38 },
    { state: 'On Hold', count: 12 },
    { state: 'Resolved', count: 218 },
    { state: 'Closed', count: 124 },
    { state: 'Canceled', count: 34 },
    { state: 'Pending', count: 32 }
  ],

  monthly_trend: [
    { month: '2025-11', total: 62, avg_hours: 22.4 },
    { month: '2025-12', total: 78, avg_hours: 19.8 },
    { month: '2026-01', total: 84, avg_hours: 17.2 },
    { month: '2026-02', total: 71, avg_hours: 21.6 },
    { month: '2026-03', total: 95, avg_hours: 15.9 },
    { month: '2026-04', total: 96, avg_hours: 14.7 }
  ],

  group_stats: [
    { group: '一线运维A组', count: 142, avg_hours: 16.2, resolved_rate: 74.6 },
    { group: '一线运维B组', count: 118, avg_hours: 12.8, resolved_rate: 81.4 },
    { group: '二线运维团队', count: 96, avg_hours: 24.6, resolved_rate: 62.5 }
  ],

  assignee_stats: [
    { assignee: '张明', count: 48, avg_hours: 14.2, pending_count: 6 },
    { assignee: '李娜', count: 42, avg_hours: 16.8, pending_count: 5 },
    { assignee: '王强', count: 38, avg_hours: 18.4, pending_count: 7 }
  ],

  customer_stats: [
    { company: '华润集团', count: 28, resolved_count: 22, resolve_rate: 78.6, avg_hours: 14.2, category: '企业版' },
    { company: '招商银行', count: 24, resolved_count: 20, resolve_rate: 83.3, avg_hours: 12.8, category: '金融版' },
    { company: '中国电信', count: 21, resolved_count: 16, resolve_rate: 76.2, avg_hours: 18.4, category: '企业版' },
    { company: '平安科技', count: 18, resolved_count: 14, resolve_rate: 77.8, avg_hours: 15.6, category: '企业版' },
    { company: '万科地产', count: 16, resolved_count: 12, resolve_rate: 75.0, avg_hours: 20.1, category: '企业版' },
    { company: '比亚迪', count: 15, resolved_count: 11, resolve_rate: 73.3, avg_hours: 16.8, category: '企业版' },
    { company: '京东科技', count: 14, resolved_count: 10, resolve_rate: 71.4, avg_hours: 17.2, category: '企业版' },
    { company: '小米集团', count: 13, resolved_count: 9, resolve_rate: 69.2, avg_hours: 19.5, category: '企业版' },
    { company: '美团', count: 12, resolved_count: 8, resolve_rate: 66.7, avg_hours: 21.3, category: '企业版' },
    { company: '字节跳动', count: 11, resolved_count: 7, resolve_rate: 63.6, avg_hours: 22.8, category: '企业版' }
  ],

  sla_stats: [
    { priority: 'P1', count: 52, sla_met: 44, sla_rate: 84.6, avg_hours: 3.2, sla_limit: 4 },
    { priority: 'P2', count: 128, sla_met: 108, sla_rate: 84.4, avg_hours: 8.6, sla_limit: 12 },
    { priority: 'P3', count: 186, sla_met: 152, sla_rate: 81.7, avg_hours: 18.4, sla_limit: 24 },
    { priority: 'P4', count: 120, sla_met: 96, sla_rate: 80.0, avg_hours: 32.1, sla_limit: 48 }
  ],

  escalation_stats: {
    summary: {
      l1_count: 260,
      l2_count: 226,
      escalation_rate: 46.5
    },
    priority_dist: [
      { priority: 'P1', l1: 20, l2: 32 },
      { priority: 'P2', l1: 68, l2: 60 },
      { priority: 'P3', l1: 108, l2: 78 },
      { priority: 'P4', l1: 64, l2: 56 }
    ],
    monthly_trend: [
      { month: '2025-11', l1: 38, l2: 24 },
      { month: '2025-12', l1: 42, l2: 36 },
      { month: '2026-01', l1: 46, l2: 38 },
      { month: '2026-02', l1: 40, l2: 31 },
      { month: '2026-03', l1: 48, l2: 47 },
      { month: '2026-04', l1: 46, l2: 50 }
    ]
  },

  recent_incidents: [
    {
      number: 'WO-2026-0428',
      priority: 'P2',
      state: 'In Progress',
      company: '华润集团',
      short_description: '企业版系统登录异常',
      category: '企业版',
      assignment_group: '一线运维A组',
      assigned_to: '张明',
      created_at: '2026-04-28T10:24:00',
      resolve_hours: 12.4
    },
    {
      number: 'WO-2026-0427',
      priority: 'P3',
      state: 'New',
      company: '招商银行',
      short_description: '金融版报表导出失败',
      category: '金融版',
      assignment_group: '一线运维B组',
      assigned_to: '李娜',
      created_at: '2026-04-27T14:18:00',
      resolve_hours: 6.2
    },
    {
      number: 'WO-2026-0426',
      priority: 'P1',
      state: 'Resolved',
      company: '中国电信',
      short_description: '生产环境数据库连接超时',
      category: '企业版',
      assignment_group: '二线运维团队',
      assigned_to: '王强',
      created_at: '2026-04-26T09:05:00',
      resolve_hours: 3.8
    },
    {
      number: 'WO-2026-0425',
      priority: 'P3',
      state: 'Closed',
      company: '万科地产',
      short_description: '权限配置变更申请',
      category: '企业版',
      assignment_group: '二线运维团队',
      assigned_to: '刘芳',
      created_at: '2026-04-25T16:42:00',
      resolve_hours: 48.6
    },
    {
      number: 'WO-2026-0424',
      priority: 'P4',
      state: 'New',
      company: '比亚迪',
      short_description: '界面显示优化建议',
      category: '企业版',
      assignment_group: '二线运维团队',
      assigned_to: '陈伟',
      created_at: '2026-04-24T11:30:00',
      resolve_hours: 2.1
    },
    {
      number: 'WO-2026-0423',
      priority: 'P2',
      state: 'In Progress',
      company: '京东科技',
      short_description: 'API 接口返回数据异常',
      category: '企业版',
      assignment_group: '一线运维A组',
      assigned_to: '张明',
      created_at: '2026-04-23T15:08:00',
      resolve_hours: 18.5
    },
    {
      number: 'WO-2026-0422',
      priority: 'P3',
      state: 'Resolved',
      company: '平安科技',
      short_description: '安全证书更新',
      category: '企业版',
      assignment_group: '一线运维B组',
      assigned_to: '李娜',
      created_at: '2026-04-22T10:15:00',
      resolve_hours: 15.3
    },
    {
      number: 'WO-2026-0421',
      priority: 'P2',
      state: 'On Hold',
      company: '小米集团',
      short_description: '批量数据迁移问题',
      category: '企业版',
      assignment_group: '二线运维团队',
      assigned_to: '刘芳',
      created_at: '2026-04-21T13:44:00',
      resolve_hours: 24.7
    },
    {
      number: 'WO-2026-0420',
      priority: 'P1',
      state: 'Resolved',
      company: '美团',
      short_description: '紧急故障修复',
      category: '企业版',
      assignment_group: '二线运维团队',
      assigned_to: '陈伟',
      created_at: '2026-04-20T08:32:00',
      resolve_hours: 2.9
    },
    {
      number: 'WO-2026-0419',
      priority: 'P3',
      state: 'Pending',
      company: '字节跳动',
      short_description: '大规模部署配置问题',
      category: '企业版',
      assignment_group: '一线运维A组',
      assigned_to: '王强',
      created_at: '2026-04-19T14:20:00',
      resolve_hours: 32.4
    },
    {
      number: 'WO-2026-0418',
      priority: 'P4',
      state: 'New',
      company: '顺丰速运',
      short_description: '物流接口对接咨询',
      category: '行业版',
      assignment_group: '二线运维团队',
      assigned_to: '刘芳',
      created_at: '2026-04-18T16:05:00',
      resolve_hours: 1.8
    },
    {
      number: 'WO-2026-0417',
      priority: 'P2',
      state: 'Closed',
      company: '华润集团',
      short_description: '功能模块升级确认',
      category: '企业版',
      assignment_group: '一线运维A组',
      assigned_to: '张明',
      created_at: '2026-04-17T09:48:00',
      resolve_hours: 8.6
    },
    {
      number: 'WO-2026-0416',
      priority: 'P3',
      state: 'Closed',
      company: '万科地产',
      short_description: '重复问题合并处理',
      category: '企业版',
      assignment_group: '二线运维团队',
      assigned_to: '刘芳',
      created_at: '2026-04-16T11:22:00',
      resolve_hours: 56.2
    },
    {
      number: 'WO-2026-0415',
      priority: 'P2',
      state: 'In Progress',
      company: '招商银行',
      short_description: '私有化部署环境排查',
      category: '金融版',
      assignment_group: '二线运维团队',
      assigned_to: '王强',
      created_at: '2026-04-15T10:36:00',
      resolve_hours: 14.8
    },
    {
      number: 'WO-2026-0414',
      priority: 'P3',
      state: 'Resolved',
      company: '比亚迪',
      short_description: '生产管理系统部署',
      category: '企业版',
      assignment_group: '二线运维团队',
      assigned_to: '陈伟',
      created_at: '2026-04-14T13:15:00',
      resolve_hours: 20.4
    }
  ]
}

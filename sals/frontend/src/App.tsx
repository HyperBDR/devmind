/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useMemo, useState } from 'react';
import { 
  Ticket, 
  CheckCircle2, 
  Clock, 
  AlertCircle,
  BarChart3,
  ArrowUpRight,
  Filter,
  XCircle,
  TrendingUp,
  Activity,
  Layers,
  CircleDot,
  FileText,
  RefreshCw,
  Calendar,
  Layers2
} from 'lucide-react';
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Legend,
  ComposedChart,
  Line,
  ScatterChart,
  Scatter,
  ZAxis
} from 'recharts';
import { motion } from 'motion/react';
import {
  MOCK_WORK_ORDERS,
  getStats,
  getTrendData,
  getStageData as getPriorityData,
  getStateData,
  getRepStats as getGroupStats,
  getRepStats as getUserStats,
  getCompanyStats as getClientHealthData,
  getProductData,
  getStageData as getSlaByPriority,
  STAGE_COLORS,
} from './mockData';
import type { SaleStage } from './mockData';
import { StatCard } from './components/StatCard';
import { cn } from './lib/utils';
import { format } from 'date-fns';
import { translations, Language } from './i18n';

const PRIORITY_COLORS = {
  P1: '#f43f5e', // rose-500
  P2: '#f59e0b', // amber-500
  P3: '#3b82f6', // blue-500
  P4: '#94a3b8', // slate-400
};

const STATE_COLORS = ['#3b82f6', '#4f46e5', '#34d399', '#f59e0b', '#f43f5e'];

export default function App() {
  const [lang, setLang] = useState<Language>('zh');
  const [priorityFilter, setPriorityFilter] = useState<string>('all');
  const [stateFilter, setStateFilter] = useState<string>('all');
  const [groupFilter, setGroupFilter] = useState<string>('all');
  const [efficiencyMode, setEfficiencyMode] = useState<'group' | 'user'>('group');

  const t = translations[lang];

  const getStateLabel = (state: string) => {
    if (lang === 'en') return state;
    const stateMap: Record<string, string> = {
      'New': '新建',
      'In Progress': '处理中',
      'On Hold': '挂起',
      'Resolved': '已解决',
      'Closed': '已关闭',
      'Canceled': '已取消'
    };
    return stateMap[state] || state;
  };

  const stats = useMemo(() => getStats(MOCK_WORK_ORDERS), []);
  const trendData = useMemo(() => getTrendData(MOCK_WORK_ORDERS), []);
  const priorityData = useMemo(() => getPriorityData(MOCK_WORK_ORDERS), []);
  const stateData = useMemo(() => getStateData(MOCK_WORK_ORDERS), []);
  const groupStats = useMemo(() => getGroupStats(MOCK_WORK_ORDERS), []);
  const userStats = useMemo(() => getUserStats(MOCK_WORK_ORDERS), []);
  const healthData = useMemo(() => getClientHealthData(MOCK_WORK_ORDERS), []);
  const productData = useMemo(() => getProductData(MOCK_WORK_ORDERS), []);
  const slaByPriority = useMemo(() => getSlaByPriority(MOCK_WORK_ORDERS), []);

  const filteredOrders = useMemo(() => {
    return MOCK_WORK_ORDERS.filter(order => {
      const matchPriority = priorityFilter === 'all' || order.stage === priorityFilter;
      const matchState = stateFilter === 'all' || order.state === stateFilter;
      const matchGroup = groupFilter === 'all' || order.sales_rep === groupFilter;
      return matchPriority && matchState && matchGroup;
    }).sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [priorityFilter, stateFilter, groupFilter]);

  const recentOrders = useMemo(() => filteredOrders.slice(0, 15), [filteredOrders]);

  const resetFilters = () => {
    setPriorityFilter('all');
    setStateFilter('all');
    setGroupFilter('all');
  };

  return (
    <div className="min-h-screen bg-[#f8fbff] text-slate-900 font-sans selection:bg-indigo-100">
      {/* Universal Header */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-slate-200/60 px-8 py-4">
        <div className="max-w-screen-2xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center text-white shadow-lg shadow-indigo-200">
              <Activity className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold tracking-tight">{t.title}</h1>
                <span className="text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">v2.4.0</span>
              </div>
              <p className="text-xs text-slate-500 font-medium">{t.subtitle}</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden lg:flex items-center gap-1 p-1 bg-slate-100 rounded-xl mr-2">
              <button 
                onClick={() => setLang('en')}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all",
                  lang === 'en' ? "bg-white text-indigo-600 shadow-sm" : "text-slate-400 hover:text-slate-600"
                )}
              >
                EN
              </button>
              <button 
                onClick={() => setLang('zh')}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all",
                  lang === 'zh' ? "bg-white text-indigo-600 shadow-sm" : "text-slate-400 hover:text-slate-600"
                )}
              >
                中文
              </button>
            </div>
            <div className="flex items-center gap-6 px-4 py-2 bg-slate-50 rounded-xl border border-slate-200/50">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-slate-400" />
                <span className="text-xs font-bold text-slate-600">2026-01 ~ 2026-04</span>
              </div>
              <div className="flex items-center gap-2 border-l border-slate-200 pl-4">
                <FileText className="w-4 h-4 text-slate-400" />
                <span className="text-xs font-bold text-slate-600 font-mono">{MOCK_WORK_ORDERS.length} {t.recordsFound}</span>
              </div>
            </div>
            <button className="flex items-center gap-2 bg-indigo-600 px-4 py-2.5 rounded-xl text-white text-xs font-bold shadow-lg shadow-indigo-100 hover:bg-indigo-700 transition-all active:scale-95">
              <RefreshCw className="w-4 h-4" />
              {t.refresh}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-screen-2xl mx-auto p-8 flex flex-col gap-8 pb-20">
        
        {/* Section 1: Summary Metrics */}
        <section>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
            <StatCard title={t.totalVolume} value={stats.total} icon={Ticket} iconClassName="bg-blue-50 text-blue-600" subtitle={t.totalVolumeSub} />
            <StatCard 
              title={t.slaCompliance} 
              value={`${stats.slaRate.toFixed(1)}`} 
              icon={CheckCircle2} 
              iconClassName="bg-indigo-600 text-white" 
              className="bg-indigo-600 text-white border-none shadow-indigo-200"
              subtitle={t.slaTarget}
            />
            <StatCard title={t.resolved} value={stats.resolved} icon={TrendingUp} iconClassName="bg-emerald-50 text-emerald-600" subtitle={`${t.resolvedRate}: ${Math.round((stats.resolved/stats.total)*100)}%`} />
            <StatCard title={t.pending} value={stats.pending} icon={Clock} iconClassName="bg-amber-50 text-amber-600" subtitle={`${t.pendingRatio}: ${Math.round((stats.pending/stats.total)*100)}%`} />
            <StatCard title={t.avgResolve} value={`${stats.avgResolve.toFixed(1)}h`} icon={TrendingUp} iconClassName="bg-purple-50 text-purple-600" subtitle={t.mttrTrend} />
            <StatCard 
              title={t.p1Overdue} 
              value={`${stats.p1Overdue}/${stats.p1Total}`} 
              icon={AlertCircle} 
              iconClassName="bg-rose-50 text-rose-600" 
              subtitle={t.criticalAttention}
            />
          </div>
        </section>

        {/* Section 2: Distribution Dashboard */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Main Trend Chart */}
          <div className="lg:col-span-8 bg-white p-6 rounded-2xl border border-slate-200/60 shadow-sm flex flex-col">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h3 className="font-bold text-slate-800">{t.monthlyTrend}</h3>
                <p className="text-[11px] text-slate-400 font-medium">{t.trendSub}</p>
              </div>
              <div className="flex gap-4">
                <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-500">
                  <div className="w-2.5 h-2.5 bg-indigo-500 rounded-sm"></div> {t.volume}
                </div>
                <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-500">
                  <div className="w-2.5 h-2.5 bg-indigo-500 h-0.5 mt-1 border-t-2 border-indigo-500"></div> {t.avgHours}
                </div>
              </div>
            </div>
            <div className="flex-1 min-h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#94a3b8', fontWeight: 600 }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#94a3b8' }} />
                  <Tooltip cursor={{ fill: '#f8fafc' }} contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} />
                  <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={40} />
                  <Line type="monotone" dataKey="avgHours" stroke="#6366f1" strokeWidth={3} dot={{ r: 4, fill: '#6366f1', strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 6 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="lg:col-span-4 flex flex-col gap-6">
            {/* Priority Pie */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200/60 shadow-sm flex flex-col items-center">
              <h3 className="w-full font-bold text-slate-800 mb-4">{t.priorityDist}</h3>
              <div className="h-[200px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={priorityData} innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value">
                      {priorityData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={PRIORITY_COLORS[entry.name as keyof typeof PRIORITY_COLORS]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend iconType="circle" wrapperStyle={{ fontSize: '11px', fontWeight: 600 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
            {/* State Bar */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200/60 shadow-sm flex flex-col">
              <h3 className="font-bold text-slate-800 mb-4">{t.stateBreakdown}</h3>
              <div className="h-[150px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stateData} layout="vertical">
                    <XAxis type="number" hide />
                    <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 600 }} width={80} tickFormatter={getStateLabel} />
                    <Tooltip cursor={{ fill: 'transparent' }} formatter={(val: any, name: any, props: any) => [val, getStateLabel(props.payload.name)]} />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      {stateData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={STATE_COLORS[index % STATE_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </section>

        {/* Section 3: Efficiency Analysis */}
        <section className="bg-white p-8 rounded-2xl border border-slate-200/60 shadow-sm">
          <div className="flex flex-col md:flex-row md:items-center justify-between mb-10 gap-4">
            <div>
              <h3 className="text-xl font-bold text-slate-800">{t.efficiencyAnalysis}</h3>
              <p className="text-xs text-slate-400 font-medium mt-1">{t.efficiencySub}</p>
            </div>
            <div className="bg-slate-100 p-1 rounded-lg flex">
              <button 
                onClick={() => setEfficiencyMode('group')}
                className={cn(
                  "px-4 py-1.5 rounded-md text-[11px] font-bold transition-all",
                  efficiencyMode === 'group' ? "bg-white text-indigo-600 shadow-sm" : "text-slate-400 hover:text-slate-600"
                )}
              >
                {t.groups}
              </button>
              <button 
                onClick={() => setEfficiencyMode('user')}
                className={cn(
                  "px-4 py-1.5 rounded-md text-[11px] font-bold transition-all",
                  efficiencyMode === 'user' ? "bg-white text-indigo-600 shadow-sm" : "text-slate-400 hover:text-slate-600"
                )}
              >
                {t.resolvers}
              </button>
            </div>
          </div>

          <div className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={efficiencyMode === 'group' ? groupStats : userStats} layout="vertical" margin={{ left: 40, right: 40 }}>
                <XAxis type="number" hide />
                <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#475569', fontWeight: 600 }} width={140} />
                <Tooltip 
                  cursor={{ fill: '#f8fafc' }}
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      return (
                        <div className="bg-slate-900 text-white p-3 rounded-lg shadow-xl text-[11px]">
                          <p className="font-bold border-b border-white/10 pb-1 mb-1">{payload[0].payload.name}</p>
                          <p>Won: <span className="font-bold text-emerald-400">{payload[0].value} deals</span></p>
                          <p>Amount: <span className="font-bold text-sky-400">¥{(payload[0].payload.amount / 10000).toFixed(0)}w</span></p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="won" radius={[0, 6, 6, 0]} barSize={24}>
                  {(efficiencyMode === 'group' ? groupStats : userStats).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.won > 3 ? '#10b981' : entry.won > 1 ? '#f59e0b' : '#f43f5e'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* Section 4: Client Health Analysis */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          <div className="lg:col-span-12">
            <div className="bg-white rounded-2xl border border-slate-200/60 shadow-sm overflow-hidden flex flex-col lg:flex-row">
              {/* Left Side: Bubble Chart */}
              <div className="lg:w-2/3 p-8 border-r border-slate-100">
                <header className="mb-8">
                  <h3 className="text-xl font-bold text-slate-800">{t.clientHealth}</h3>
                  <p className="text-xs text-slate-400 mt-1">{t.bubbleSub}</p>
                </header>
                <div className="h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                      <XAxis type="number" dataKey="volume" name="Deals" unit=" deals" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                      <YAxis type="number" dataKey="wonAmount" name="Won Amount" unit="w" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                      <ZAxis type="number" dataKey="volume" range={[100, 1500]} />
                      <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                      <Scatter name="Clients" data={healthData.slice(0, 15)}>
                        {healthData.slice(0, 15).map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.wonAmount > 500000 ? '#10b981' : entry.wonAmount > 100000 ? '#f59e0b' : '#f43f5e'} opacity={0.6} />
                        ))}
                      </Scatter>
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              </div>
              
              {/* Right Side: Client List + Product Distribution */}
              <div className="lg:w-1/3 flex flex-col divide-y divide-slate-100">
                <div className="p-8">
                  <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-6">{t.productExposure}</h4>
                  <div className="h-[200px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={productData.slice(0, 4)}>
                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fontWeight: 700 }} />
                        <Tooltip />
                        <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={50} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <div className="p-8 space-y-6">
                  <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-4">{t.slaByTier}</h4>
                  <div className="space-y-4">
                    {slaByPriority.map((item) => (
                      <div key={item.name} className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className="w-1.5 h-6 rounded-full" style={{ backgroundColor: STAGE_COLORS[item.name as SaleStage] }}></div>
                          <span className="text-xs font-bold text-slate-600">{item.name}</span>
                        </div>
                        <span className="text-sm font-mono font-bold text-slate-900">{item.value} deals</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 5: Incident Detail Table */}
        <section className="bg-white rounded-2xl border border-slate-200/60 shadow-sm overflow-hidden flex flex-col">
          <div className="px-8 py-5 border-b border-slate-100 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="flex items-center gap-4">
              <h3 className="font-bold text-slate-800">{t.incidentRegistry}</h3>
              <span className="text-[10px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-lg font-bold font-mono">{filteredOrders.length} {t.recordsFound}</span>
            </div>
            
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 bg-slate-50 border border-slate-200/60 rounded-xl px-3 py-1.5 transition-all focus-within:border-indigo-400/50 focus-within:ring-4 focus-within:ring-indigo-500/5">
                <Filter className="w-3.5 h-3.5 text-slate-400" />
                <select 
                  value={priorityFilter}
                  onChange={(e) => setPriorityFilter(e.target.value)}
                  className="text-[11px] font-bold text-slate-600 bg-transparent border-none focus:ring-0 cursor-pointer outline-none min-w-[80px]"
                >
                  <option value="all">{t.tier}: {t.all}</option>
                  {['Prospect', 'Qualified', 'Proposal Sent', 'Negotiation', 'Won', 'Lost'].map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>

              <div className="flex items-center gap-2 bg-slate-50 border border-slate-200/60 rounded-xl px-3 py-1.5 transition-all">
                <select 
                  value={stateFilter}
                  onChange={(e) => setStateFilter(e.target.value)}
                  className="text-[11px] font-bold text-slate-600 bg-transparent border-none focus:ring-0 cursor-pointer outline-none min-w-[100px]"
                >
                  <option value="all">{t.state}: {t.all}</option>
                  {MOCK_WORK_ORDERS.map(i => i.state).filter((v, i, a) => a.indexOf(v) === i).map(s => <option key={s} value={s}>{getStateLabel(s)}</option>)}
                </select>
              </div>

              <div className="flex items-center gap-2 bg-slate-50 border border-slate-200/60 rounded-xl px-3 py-1.5 transition-all">
                <select 
                  value={groupFilter}
                  onChange={(e) => setGroupFilter(e.target.value)}
                  className="text-[11px] font-bold text-slate-600 bg-transparent border-none focus:ring-0 cursor-pointer outline-none min-w-[120px]"
                >
                  <option value="all">{t.group}: {t.all}</option>
                  {[...new Set(MOCK_WORK_ORDERS.map(i => i.sales_rep))].map(g => <option key={g} value={g}>{g}</option>)}
                </select>
              </div>

              {(priorityFilter !== 'all' || stateFilter !== 'all' || groupFilter !== 'all') && (
                <button 
                  onClick={resetFilters}
                  className="px-3 py-1.5 text-[11px] font-bold text-rose-500 hover:bg-rose-50 rounded-xl transition-all flex items-center gap-1.5"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  {t.reset}
                </button>
              )}
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[10px] text-slate-400 font-bold uppercase tracking-widest border-b border-slate-100">
                  <th className="px-8 py-4">{t.id}</th>
                  <th className="px-4 py-4">{t.tier}</th>
                  <th className="px-4 py-4">{t.status}</th>
                  <th className="px-4 py-4">{t.company}</th>
                  <th className="px-4 py-4">{t.requestor}</th>
                  <th className="px-4 py-4 max-w-[200px]">{t.summary}</th>
                  <th className="px-4 py-4">{t.group}</th>
                  <th className="px-4 py-4">{t.assignee}</th>
                  <th className="px-4 py-4">{t.logged}</th>
                  <th className="px-8 py-4 text-right">{t.duration}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100/50">
                {recentOrders.map((order) => (
                  <tr key={order.id} className="hover:bg-slate-50/50 transition-colors group cursor-default">
                    <td className="px-8 py-4">
                      <span className="text-[13px] font-bold text-indigo-600 font-mono tracking-tighter">#{order.number.replace('WO-2026-', '')}</span>
                    </td>
                    <td className="px-4 py-4">
                      <span className="text-[11px] font-bold" style={{ color: STAGE_COLORS[order.stage] }}>{order.stage}</span>
                    </td>
                    <td className="px-4 py-4">
                      <span className={cn(
                        "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide",
                        order.state === 'Closed Won' || order.state === 'Closed Lost' ? "bg-emerald-50 text-emerald-600" :
                        order.state === 'New' ? "bg-indigo-50 text-indigo-600" :
                        "bg-amber-50 text-amber-600"
                      )}>
                        {getStateLabel(order.state)}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-[13px] font-medium text-slate-700">{order.company}</td>
                    <td className="px-4 py-4 text-[13px] text-slate-500">{order.contact}</td>
                    <td className="px-4 py-4 text-[13px] max-w-[200px] truncate text-slate-600 font-medium">{order.product_name}</td>
                    <td className="px-4 py-4 text-[12px] text-slate-500 font-medium">{order.sales_rep}</td>
                    <td className="px-4 py-4 text-[12px] text-slate-500">{order.sales_rep}</td>
                    <td className="px-4 py-4 text-[12px] text-slate-400 font-medium font-mono">{format(new Date(order.created_at), 'MM-dd HH:mm')}</td>
                    <td className="px-8 py-4 text-right">
                      <span className={cn(
                        "text-[13px] font-bold font-mono",
                        order.deal_amount != null ? "text-emerald-600" : "text-slate-900"
                      )}>
                        ¥{(order.quote_amount / 10000).toFixed(0)}w
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}


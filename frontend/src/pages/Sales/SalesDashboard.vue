<template>
  <AppLayout :show-sidebar="false">
    <div class="mx-auto w-full max-w-[1440px]">
      <!-- Page Header -->
      <div class="mb-6 rounded-xl border border-gray-200 bg-white shadow-sm">
        <div
          class="flex flex-col gap-5 p-6 lg:flex-row lg:items-end lg:justify-between"
        >
          <div class="max-w-3xl">
            <div
              class="inline-flex items-center gap-2 rounded-full border border-primary-100 bg-primary-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary-700"
            >
              <span class="h-2 w-2 rounded-full bg-primary-500" />
              {{ t('sals.dashboard.badge') }}
            </div>
            <h1
              class="mt-4 text-2xl font-semibold tracking-tight text-gray-900"
            >
              {{ t('sals.dashboard.title') }}
            </h1>
            <p class="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
              {{ t('sals.dashboard.subtitle') }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <BaseButton
              variant="outline"
              size="sm"
              :loading="loading"
              @click="loadDashboard"
            >
              {{ t('common.refresh') }}
            </BaseButton>
            <BaseButton
              variant="outline"
              size="sm"
              :loading="syncing"
              @click="syncDb"
            >
              {{ t('sals.dashboard.sync') }}
            </BaseButton>
          </div>
        </div>
      </div>

      <!-- Error Banner -->
      <div
        v-if="error"
        class="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
      >
        {{ error }}
      </div>

      <!-- Loading State -->
      <BaseLoading v-if="loading && !dashboardLoaded" />

      <template v-else>
        <!-- ── Section 1: KPI Cards ── -->
        <div class="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <!-- Total -->
          <article
            class="flex items-center gap-4 rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
          >
            <div class="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-gray-100">
              <svg class="h-5 w-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </div>
            <div>
              <div class="text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                {{ t('sals.dashboard.kpiTotal') }}
              </div>
              <div class="mt-1 text-2xl font-bold tracking-tight text-gray-900">
                {{ kpi.total ?? 0 }}
              </div>
            </div>
          </article>

          <!-- Resolved -->
          <article
            class="flex items-center gap-4 rounded-xl border border-emerald-200 bg-emerald-50 p-5 shadow-sm"
          >
            <div class="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-emerald-100">
              <svg class="h-5 w-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <div class="text-[11px] font-semibold uppercase tracking-wider text-emerald-500">
                {{ t('sals.dashboard.kpiResolvedCount') }}
              </div>
              <div class="mt-1 text-2xl font-bold tracking-tight text-emerald-700">
                {{ resolvedCount }}
              </div>
            </div>
          </article>

          <!-- Active (Pending + In Progress) -->
          <article
            class="flex items-center gap-4 rounded-xl border border-amber-200 bg-amber-50 p-5 shadow-sm"
          >
            <div class="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-amber-100">
              <svg class="h-5 w-5 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <div class="text-[11px] font-semibold uppercase tracking-wider text-amber-500">
                {{ t('sals.dashboard.kpiActive') }}
              </div>
              <div class="mt-1 text-2xl font-bold tracking-tight text-amber-700">
                {{ activeCount }}
              </div>
            </div>
          </article>

          <!-- Resolution Rate -->
          <article
            class="flex items-center gap-4 rounded-xl border border-primary-200 bg-primary-50 p-5 shadow-sm"
          >
            <div class="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-primary-100">
              <svg class="h-5 w-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <div>
              <div class="text-[11px] font-semibold uppercase tracking-wider text-primary-500">
                {{ t('sals.dashboard.kpiWinRate') }}
              </div>
              <div class="mt-1 text-2xl font-bold tracking-tight text-primary-700">
                {{ resolutionRate }}%
              </div>
            </div>
          </article>

          <!-- Avg Hours -->
          <article
            class="flex items-center gap-4 rounded-xl border border-purple-200 bg-purple-50 p-5 shadow-sm"
          >
            <div class="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-purple-100">
              <svg class="h-5 w-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <div class="text-[11px] font-semibold uppercase tracking-wider text-purple-500">
                {{ t('sals.dashboard.kpiAvgHours') }}
              </div>
              <div class="mt-1 text-2xl font-bold tracking-tight text-purple-700">
                {{ kpi.avg_resolve_hours ?? 0 }}<span class="text-sm font-normal text-purple-400">h</span>
              </div>
            </div>
          </article>
        </div>

        <!-- ── Section 2: Charts Row ── -->
        <div class="mb-6 grid items-stretch gap-6 lg:grid-cols-12">
          <!-- Monthly Trend -->
          <div
            class="lg:col-span-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
          >
            <h3 class="mb-5 text-sm font-semibold text-gray-900">
              {{ t('sals.dashboard.salesTrend') }}
            </h3>
            <div class="h-[300px]">
              <Bar
                v-if="trendChartData"
                :data="trendChartData"
                :options="barOptions"
              />
            </div>
          </div>

          <!-- Stage Distribution + State Breakdown -->
          <div class="lg:col-span-4 flex flex-col gap-6">
            <!-- Stage Distribution (Pie) -->
            <div
              class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
            >
              <h3 class="mb-4 text-sm font-semibold text-gray-900">
                {{ t('sals.dashboard.stageDistribution') }}
              </h3>
              <div class="mx-auto h-[160px] w-full max-w-[180px]">
                <Doughnut
                  v-if="priorityChartData"
                  :data="priorityChartData"
                  :options="doughnutOptions"
                />
              </div>
              <div class="mt-3 space-y-1.5">
                <div
                  v-for="(item, idx) in data.priority_dist || []"
                  :key="item.priority"
                  class="flex items-center justify-between text-xs"
                >
                  <div class="flex items-center gap-1.5">
                    <span
                      class="h-2 w-2 rounded-full"
                      :style="{
                        backgroundColor: priorityChartColors[idx % priorityChartColors.length]
                      }"
                    />
                    <span class="font-medium text-gray-600">{{
                      getPriorityLabel(item.priority)
                    }}</span>
                  </div>
                  <span class="font-mono font-semibold text-gray-900">{{
                    item.count
                  }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ── Section 2b: Escalation Panel ── -->
        <div
          v-if="escalation.summary"
          class="mb-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
        >
          <h3 class="mb-5 text-sm font-semibold text-gray-900">
            {{ t('sals.dashboard.escalationTitle') }}
          </h3>
          <div class="grid gap-6 lg:grid-cols-12">
            <!-- Funnel Visualization -->
            <div class="lg:col-span-4 flex flex-col items-center justify-center">
              <!-- L1 Label -->
              <div class="mb-2 text-center">
                <div class="text-[11px] font-semibold text-blue-500 uppercase tracking-wider">
                  {{ t('sals.dashboard.l1Count') }}
                </div>
                <div class="text-2xl font-bold text-blue-700">
                  {{ escalation.summary.l1_count }}
                </div>
              </div>
              <!-- Funnel SVG -->
              <svg
                width="100%"
                viewBox="0 0 200 100"
                class="max-w-[220px]"
                preserveAspectRatio="xMidYMid meet"
              >
                <defs>
                  <linearGradient id="funnelGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#3b82f6" />
                    <stop offset="100%" stop-color="#f59e0b" />
                  </linearGradient>
                </defs>
                <!-- 倒梯形 -->
                <polygon
                  points="20,0 180,0 150,70 50,70"
                  fill="url(#funnelGrad)"
                  opacity="0.85"
                />
                <!-- 转化率文字 -->
                <text
                  x="100"
                  y="42"
                  text-anchor="middle"
                  fill="white"
                  font-size="14"
                  font-weight="bold"
                >
                  {{ escalation.summary.escalation_rate }}%
                </text>
              </svg>
              <!-- L2 Label -->
              <div class="mt-2 text-center">
                <div class="text-[11px] font-semibold text-amber-500 uppercase tracking-wider">
                  {{ t('sals.dashboard.l2Count') }}
                </div>
                <div class="text-2xl font-bold text-amber-700">
                  {{ escalation.summary.l2_count }}
                </div>
              </div>
            </div>

            <!-- Priority Distribution -->
            <div class="lg:col-span-4 flex flex-col">
              <div class="text-xs font-semibold text-gray-500 mb-3">
                {{ t('sals.dashboard.priorityDistribution') }}
              </div>
              <div class="flex flex-1 flex-col justify-between">
                <div
                  v-for="row in escalation.priority_dist || []"
                  :key="row.priority"
                  class="space-y-1"
                >
                  <div class="flex items-center justify-between text-xs">
                    <span class="font-medium text-gray-600">
                      {{ getPriorityLabel(row.priority) }}
                    </span>
                    <span class="font-mono text-gray-500">
                      {{ row.l1 }} / {{ row.l2 }}
                    </span>
                  </div>
                  <div class="flex h-2 overflow-hidden rounded-full bg-gray-100">
                    <div
                      class="bg-blue-500"
                      :style="{
                        width: `${(row.l1 + row.l2) ? (row.l1 / (row.l1 + row.l2) * 100) : 0}%`
                      }"
                    />
                    <div
                      class="bg-amber-500"
                      :style="{
                        width: `${(row.l1 + row.l2) ? (row.l2 / (row.l1 + row.l2) * 100) : 0}%`
                      }"
                    />
                  </div>
                </div>
              </div>
            </div>

            <!-- Monthly Trend -->
            <div class="lg:col-span-4">
              <div class="text-xs font-semibold text-gray-500 mb-3">
                {{ t('sals.dashboard.escalationTrend') }}
              </div>
              <div class="h-[160px]">
                <Bar
                  v-if="escalationTrendData"
                  :data="escalationTrendData"
                  :options="escalationBarOptions"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- ── Section 3: SLA + Team Performance ── -->
        <div class="mb-6 grid gap-6 lg:grid-cols-2">
          <!-- Win Rate by Stage -->
          <div class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h3 class="mb-5 text-sm font-semibold text-gray-900">
              {{ t('sals.dashboard.slaOverview') }}
            </h3>
            <div class="space-y-4">
              <div
                v-for="row in data.sla_stats || []"
                :key="row.priority"
                class="flex items-center justify-between"
              >
                <div class="flex items-center gap-2">
                  <div
                    class="h-2 w-2 rounded-full"
                    :style="{
                      backgroundColor: priorityColorMap[row.priority] || '#6366f1'
                    }"
                  />
                  <span class="text-xs font-medium text-gray-700">{{
                    getPriorityLabel(row.priority)
                  }}</span>
                </div>
                <div class="flex items-center gap-3">
                  <div
                    class="h-1.5 w-24 overflow-hidden rounded-full bg-gray-100"
                  >
                    <div
                      class="h-full rounded-full"
                      :class="
                        row.sla_rate >= 80
                          ? 'bg-emerald-500'
                          : row.sla_rate >= 50
                            ? 'bg-amber-500'
                            : 'bg-red-400'
                      "
                      :style="{ width: `${Math.min(row.sla_rate ?? 0, 100)}%` }"
                    />
                  </div>
                  <span
                    class="w-10 text-right font-mono text-xs font-semibold text-gray-700"
                    >{{ row.sla_rate ?? 0 }}%</span
                  >
                </div>
              </div>
            </div>
          </div>

          <!-- Team Performance -->
          <div class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <div class="mb-5 flex items-center justify-between">
              <h3 class="text-sm font-semibold text-gray-900">
                {{ t('sals.dashboard.teamPerformance') }}
              </h3>
              <div class="flex gap-1 rounded-lg bg-gray-100 p-1">
                <button
                  v-for="mode in ['group', 'rep']"
                  :key="mode"
                  class="rounded-md px-3 py-1 text-[11px] font-bold transition-all"
                  :class="
                    perfMode === mode
                      ? 'bg-white text-primary-600 shadow-sm'
                      : 'text-gray-400'
                  "
                  @click="perfMode = mode"
                >
                  {{
                    mode === 'group'
                      ? t('sals.dashboard.group')
                      : t('sals.dashboard.assignee')
                  }}
                </button>
              </div>
            </div>
            <div class="space-y-3">
              <div
                v-for="row in performanceRows"
                :key="row.name"
                class="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2"
              >
                <div>
                  <div class="text-xs font-semibold text-gray-800">
                    {{ row.name }}
                  </div>
                  <div class="text-[10px] text-gray-400">
                    {{ row.count }}
                    {{ t('sals.dashboard.total').toLowerCase() }}
                  </div>
                </div>
                <div class="text-right">
                  <div class="text-xs font-bold text-gray-900">
                    {{ row.avg_hours }}h
                  </div>
                  <div class="text-[10px] text-gray-400">
                    {{ t('sals.dashboard.winRate') }}: {{ row.resolved_rate }}%
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ── Section 4: Customer Stats ── -->
        <div
          class="mb-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
        >
          <h3 class="mb-5 text-sm font-semibold text-gray-900">
            {{ t('sals.dashboard.customerStats') }}
          </h3>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-gray-100">
                  <th
                    class="pb-3 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                  >
                    {{ t('sals.dashboard.company') }}
                  </th>
                  <th
                    class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                  >
                    {{ t('sals.dashboard.total') }}
                  </th>
                  <th
                    class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                  >
                    {{ t('sals.dashboard.wins') }}
                  </th>
                  <th
                    class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                  >
                    {{ t('sals.dashboard.winRate') }}
                  </th>
                  <th
                    class="pb-3 text-right text-[11px] font-semibold uppercase tracking-wider text-gray-400"
                  >
                    {{ t('sals.dashboard.avgHours') }}
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-50">
                <tr
                  v-for="row in (data.customer_stats || []).slice(0, 10)"
                  :key="row.company"
                  class="hover:bg-gray-50"
                >
                  <td class="py-3 font-medium text-gray-700">
                    {{ row.company }}
                  </td>
                  <td class="py-3 text-right font-mono text-gray-900">
                    {{ row.count }}
                  </td>
                  <td class="py-3 text-right font-mono text-gray-900">
                    {{ row.resolved_count ?? '—' }}
                  </td>
                  <td class="py-3 text-right">
                    <span
                      class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold"
                      :class="
                        row.resolve_rate >= 80
                          ? 'bg-emerald-100 text-emerald-700'
                          : row.resolve_rate >= 50
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-red-100 text-red-700'
                      "
                    >
                      {{ row.resolve_rate ?? 0 }}%
                    </span>
                  </td>
                  <td class="py-3 text-right font-mono text-xs text-gray-500">
                    {{ row.avg_hours != null ? `${Math.round(row.avg_hours)}h` : '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- ── Section 5: Order Registry ── -->
        <div class="rounded-xl border border-gray-200 bg-white shadow-sm">
          <!-- Table Header -->
          <div
            class="flex flex-col gap-4 border-b border-gray-100 px-6 py-4 md:flex-row md:items-center md:justify-between"
          >
            <div class="flex items-center gap-3">
              <h3 class="font-semibold text-gray-900">
                {{ t('sals.dashboard.orderRegistry') }}
              </h3>
              <span
                class="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-mono font-bold text-gray-500"
              >
                {{ incidentsTotal }}
                {{ t('sals.dashboard.recordsFound') }}
              </span>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <!-- Priority filter -->
              <div
                class="flex items-center gap-1.5 rounded-xl border border-gray-200 bg-gray-50 px-3 py-1.5"
              >
                <span
                  class="text-[10px] font-semibold text-gray-400 uppercase tracking-wider"
                  >{{ t('sals.dashboard.filterStage') }}</span
                >
                <select
                  v-model="filterPriority"
                  class="bg-transparent text-[11px] font-bold text-gray-600 outline-none cursor-pointer"
                >
                  <option value="all">{{ t('sals.dashboard.all') }}</option>
                  <option v-for="p in priorityOptions" :key="p" :value="p">
                    {{ getPriorityLabel(p) }}
                  </option>
                </select>
              </div>
              <!-- State filter -->
              <div
                class="flex items-center gap-1.5 rounded-xl border border-gray-200 bg-gray-50 px-3 py-1.5"
              >
                <span
                  class="text-[10px] font-semibold text-gray-400 uppercase tracking-wider"
                  >{{ t('sals.dashboard.filterState') }}</span
                >
                <select
                  v-model="filterState"
                  class="bg-transparent text-[11px] font-bold text-gray-600 outline-none cursor-pointer"
                >
                  <option value="all">{{ t('sals.dashboard.all') }}</option>
                  <option v-for="s in stateOptions" :key="s" :value="s">
                    {{ getStateLabel(s) }}
                  </option>
                </select>
              </div>
              <!-- Group filter -->
              <div
                class="flex items-center gap-1.5 rounded-xl border border-gray-200 bg-gray-50 px-3 py-1.5"
              >
                <span
                  class="text-[10px] font-semibold text-gray-400 uppercase tracking-wider"
                  >{{ t('sals.dashboard.filterGroup') }}</span
                >
                <select
                  v-model="filterGroup"
                  class="bg-transparent text-[11px] font-bold text-gray-600 outline-none cursor-pointer"
                >
                  <option value="all">{{ t('sals.dashboard.all') }}</option>
                  <option v-for="g in groupOptions" :key="g" :value="g">
                    {{ g }}
                  </option>
                </select>
              </div>
              <!-- Reset -->
              <button
                v-if="
                  filterPriority !== 'all' ||
                  filterState !== 'all' ||
                  filterGroup !== 'all'
                "
                class="flex items-center gap-1 rounded-xl px-2.5 py-1.5 text-[11px] font-bold text-red-500 hover:bg-red-50 transition-all"
                @click="resetFilters"
              >
                <svg
                  class="h-3.5 w-3.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
                {{ t('sals.dashboard.resetFilters') }}
              </button>
            </div>
          </div>

          <!-- Table -->
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead>
                <tr
                  class="bg-gray-50 text-[10px] font-bold uppercase tracking-widest text-gray-400"
                >
                  <th class="px-6 py-3">{{ t('sals.dashboard.orderNo') }}</th>
                  <th class="px-4 py-3">
                    {{ t('sals.dashboard.filterStage') }}
                  </th>
                  <th class="px-4 py-3">
                    {{ t('sals.dashboard.filterState') }}
                  </th>
                  <th class="px-4 py-3">{{ t('sals.dashboard.company') }}</th>
                  <th class="px-4 py-3">{{ t('sals.dashboard.product') }}</th>
                  <th class="px-4 py-3">{{ t('sals.dashboard.group') }}</th>
                  <th class="px-4 py-3">{{ t('sals.dashboard.salesRep') }}</th>
                  <th class="px-4 py-3">{{ t('sals.dashboard.createdAt') }}</th>
                  <th class="px-6 py-3 text-right">
                    {{ t('sals.dashboard.cycleDays') }}
                  </th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-50">
                <tr
                  v-for="row in incidents"
                  :key="row.number"
                  class="hover:bg-gray-50 transition-colors"
                >
                  <td
                    class="px-6 py-3 font-mono text-[13px] font-bold text-primary-600"
                  >
                    {{ row.number }}
                  </td>
                  <td class="px-4 py-3">
                    <span
                      class="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
                      :style="{
                        color:
                          priorityColorMap[row.priority] || '#6366f1',
                        backgroundColor:
                          (priorityColorMap[row.priority] ||
                            '#6366f1') + '15'
                      }"
                    >
                      {{ getPriorityLabel(row.priority) }}
                    </span>
                  </td>
                  <td class="px-4 py-3">
                    <span
                      class="rounded-full px-1.5 py-0.5 text-[10px] font-bold"
                      :class="stateClass(row.state)"
                    >
                      {{ getStateLabel(row.state) }}
                    </span>
                  </td>
                  <td class="px-4 py-3 font-medium text-gray-700">
                    {{ row.company }}
                  </td>
                  <td class="px-4 py-3 text-gray-600">
                    {{ row.category || row.product || '—' }}
                  </td>
                  <td class="px-4 py-3 text-gray-600">
                    {{ row.assignment_group || row.group || '—' }}
                  </td>
                  <td class="px-4 py-3 text-gray-600">
                    {{ row.assigned_to || row.assignee || '—' }}
                  </td>
                  <td class="px-4 py-3 font-mono text-gray-400">
                    {{ formatDate(row.created_at) }}
                  </td>
                  <td
                    class="px-6 py-3 text-right font-mono font-semibold"
                    :class="
                      (row.resolve_hours || 0) > 24
                        ? 'text-red-500'
                        : 'text-gray-900'
                    "
                  >
                    {{ Math.round(row.resolve_hours || 0) }}h
                  </td>
                </tr>
                <tr v-if="incidents.length === 0">
                  <td
                    colspan="9"
                    class="py-12 text-center text-sm text-gray-400"
                  >
                    <span v-if="incidentsLoading">{{ t('common.loading') }}</span>
                    <span v-else>{{ t('sals.dashboard.noResults') || 'No matching records' }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <!-- Pagination -->
          <div
            class="flex flex-col gap-3 border-t border-gray-100 px-6 py-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <!-- Left: info -->
            <div class="text-xs text-gray-500">
              {{ t('sals.dashboard.showing') }}
              <span class="font-semibold text-gray-700">
                {{ incidentsTotal > 0 ? (incidentsPage - 1) * incidentsPageSize + 1 : 0 }}–{{ Math.min(incidentsPage * incidentsPageSize, incidentsTotal) }}
              </span>
              {{ t('sals.dashboard.of') }}
              <span class="font-semibold text-gray-700">{{ incidentsTotal }}</span>
              {{ t('sals.dashboard.records') }}
            </div>
            <!-- Center: page buttons -->
            <div class="flex items-center gap-0.5">
              <button
                class="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-semibold transition-colors"
                :class="incidentsPage > 1 ? 'text-gray-600 hover:bg-gray-100' : 'cursor-default text-gray-300'"
                :disabled="incidentsPage <= 1"
                @click="incidentsPage--"
              >
                ‹
              </button>
              <template v-for="(p, idx) in paginationRange">
                <span
                  v-if="p === '...'"
                  :key="`e${idx}`"
                  class="flex h-8 w-8 items-center justify-center text-xs text-gray-400"
                >…</span>
                <button
                  v-else
                  :key="`p${p}`"
                  class="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-semibold transition-colors"
                  :class="p === incidentsPage ? 'bg-primary-600 text-white shadow-sm' : 'text-gray-600 hover:bg-gray-100'"
                  @click="incidentsPage = p"
                >
                  {{ p }}
                </button>
              </template>
              <button
                class="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-semibold transition-colors"
                :class="incidentsPage < incidentsTotalPages ? 'text-gray-600 hover:bg-gray-100' : 'cursor-default text-gray-300'"
                :disabled="incidentsPage >= incidentsTotalPages"
                @click="incidentsPage++"
              >
                ›
              </button>
            </div>
            <!-- Right: page size -->
            <div class="flex items-center gap-1.5 text-xs text-gray-500">
              <select
                v-model.number="incidentsPageSize"
                class="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs font-semibold text-gray-600 outline-none cursor-pointer"
              >
                <option :value="10">10</option>
                <option :value="20">20</option>
                <option :value="50">50</option>
                <option :value="100">100</option>
              </select>
              <span>{{ t('sals.dashboard.perPage') }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend
} from 'chart.js'
import { Bar, Doughnut } from 'vue-chartjs'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import { salsApi } from '@/api/sals'

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend
)

const { t } = useI18n()

const loading = ref(false)
const syncing = ref(false)
const error = ref('')
const dashboardLoaded = ref(false)
const perfMode = ref('group')
const filterPriority = ref('all')
const filterState = ref('all')
const filterGroup = ref('all')

const incidents = ref([])
const incidentsTotal = ref(0)
const incidentsPage = ref(1)
const incidentsPageSize = ref(20)
const incidentsLoading = ref(false)

const data = ref({
  kpi: {},
  state_dist: [],
  priority_dist: [],
  monthly_trend: [],
  group_stats: [],
  assignee_stats: [],
  customer_stats: [],
  sla_stats: [],
  escalation_stats: {},
  recent_incidents: []
})

// ── Priority & State options ───────────────────────
const priorityOptions = ['P1', 'P2', 'P3', 'P4']
const stateOptions = [
  'New',
  'In Progress',
  'On Hold',
  'Resolved',
  'Closed',
  'Canceled',
  'Pending'
]
const groupOptions = computed(() =>
  (data.value.group_stats || [])
    .map((r) => r.group)
    .filter(Boolean)
)

// ── Colors ─────────────────────────────────────────
const priorityChartColors = [
  '#ef4444',
  '#f97316',
  '#eab308',
  '#22c55e'
]
const priorityColorMap = {
  P1: '#ef4444',
  P2: '#f97316',
  P3: '#eab308',
  P4: '#22c55e'
}

// ── API ────────────────────────────────────────────
async function loadDashboard() {
  loading.value = true
  error.value = ''
  try {
    const res = await salsApi.getDashboard()
    data.value = res.data.data ?? res.data
    dashboardLoaded.value = true
  } catch (e) {
    error.value =
      e.response?.data?.message ||
      e.response?.data?.detail ||
      e.message ||
      'Failed to load dashboard'
  } finally {
    loading.value = false
  }
}

async function syncDb() {
  syncing.value = true
  try {
    await salsApi.syncDb('api', true)
    await loadDashboard()
  } catch (e) {
    error.value =
      e.response?.data?.message ||
      e.response?.data?.detail ||
      e.message ||
      'Sync failed'
  } finally {
    syncing.value = false
  }
}

async function loadIncidents() {
  incidentsLoading.value = true
  try {
    const params = {
      page: incidentsPage.value,
      page_size: incidentsPageSize.value
    }
    if (filterPriority.value !== 'all') params.priority = filterPriority.value
    if (filterState.value !== 'all') params.state = filterState.value
    if (filterGroup.value !== 'all') params.group = filterGroup.value

    const res = await salsApi.getIncidents(params)
    const body = res.data?.data ?? res.data
    incidents.value = Array.isArray(body?.results)
      ? body.results
      : []
    incidentsTotal.value = body?.count ?? 0
  } catch (e) {
    console.error('[loadIncidents]', e.response?.status, e.response?.data || e.message)
    incidents.value = []
    incidentsTotal.value = 0
  } finally {
    incidentsLoading.value = false
  }
}

const incidentsTotalPages = computed(() =>
  Math.max(1, Math.ceil(incidentsTotal.value / incidentsPageSize.value))
)

const paginationRange = computed(() => {
  const total = incidentsTotalPages.value
  const current = incidentsPage.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages = []
  pages.push(1)
  if (current > 3) pages.push('...')
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
    pages.push(i)
  }
  if (current < total - 2) pages.push('...')
  pages.push(total)
  return pages
})

watch([filterPriority, filterState, filterGroup], () => {
  incidentsPage.value = 1
  loadIncidents()
})

watch([incidentsPage, incidentsPageSize], loadIncidents)

onMounted(() => {
  loadDashboard()
  loadIncidents()
})

// ── KPI ────────────────────────────────────────────
const kpi = computed(() => data.value.kpi || {})
const resolvedCount = computed(() => kpi.value.resolved ?? 0)
const activeCount = computed(
  () => (kpi.value.pending ?? 0) + (kpi.value.in_progress ?? 0)
)
const resolutionRate = computed(() =>
  (kpi.value.resolved_rate ?? 0).toFixed(1)
)

// ── Chart Data ─────────────────────────────────────
const trendChartData = computed(() => {
  const trend = data.value.monthly_trend || []
  return {
    labels: trend.map((d) => d.month),
    datasets: [
      {
        label: t('sals.dashboard.count'),
        data: trend.map((d) => d.total || 0),
        backgroundColor: '#6366f1',
        borderRadius: 6,
        borderWidth: 0
      }
    ]
  }
})

const priorityChartData = computed(() => {
  const dist = data.value.priority_dist || []
  return {
    labels: dist.map((d) => getPriorityLabel(d.priority)),
    datasets: [
      {
        data: dist.map((d) => d.count),
        backgroundColor: priorityChartColors,
        borderWidth: 0
      }
    ]
  }
})

// ── Escalation Chart ──────────────────────────────
const escalation = computed(
  () => data.value.escalation_stats || {}
)
const escalationTrendData = computed(() => {
  const trend = escalation.value.monthly_trend || []
  return {
    labels: trend.map((d) => d.month),
    datasets: [
      {
        label: t('sals.dashboard.l1Label'),
        data: trend.map((d) => d.l1 || 0),
        backgroundColor: '#3b82f6',
        borderRadius: 4,
        borderWidth: 0
      },
      {
        label: t('sals.dashboard.l2Label'),
        data: trend.map((d) => d.l2 || 0),
        backgroundColor: '#f59e0b',
        borderRadius: 4,
        borderWidth: 0
      }
    ]
  }
})
const escalationBarOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      position: 'top',
      labels: { font: { size: 11 }, boxWidth: 12, padding: 12 }
    },
    tooltip: {
      callbacks: {
        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}`
      }
    }
  },
  scales: {
    x: {
      stacked: true,
      grid: { display: false },
      ticks: { font: { size: 11 }, color: '#9ca3af' }
    },
    y: {
      stacked: true,
      grid: { color: '#f3f4f6' },
      ticks: { font: { size: 11 }, color: '#9ca3af' }
    }
  }
}

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: true,
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed}` } }
  },
  cutout: '65%'
}

const barOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}` }
    }
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { font: { size: 11 }, color: '#9ca3af' }
    },
    y: {
      grid: { color: '#f3f4f6' },
      ticks: { font: { size: 11 }, color: '#9ca3af' }
    }
  }
}

// ── Performance Rows ───────────────────────────────
const performanceRows = computed(() => {
  const stats =
    perfMode.value === 'group'
      ? (data.value.group_stats || []).slice(0, 5)
      : (data.value.assignee_stats || []).slice(0, 5)
  return stats.map((r) => ({
    name: r.group || r.assignee,
    count: r.count,
    avg_hours: Math.round(r.avg_hours || 0),
    resolved_rate: r.resolved_rate ?? 0
  }))
})

function resetFilters() {
  filterPriority.value = 'all'
  filterState.value = 'all'
  filterGroup.value = 'all'
}

// ── Helpers ────────────────────────────────────────
function getPriorityLabel(priority) {
  return t(`sals.dashboard.${priority}`) !== `sals.dashboard.${priority}`
    ? t(`sals.dashboard.${priority}`)
    : priority
}

function getStateLabel(state) {
  return t(`sals.dashboard.${state}`) !== `sals.dashboard.${state}`
    ? t(`sals.dashboard.${state}`)
    : state
}

function stateClass(state) {
  if (state === 'Resolved') return 'bg-emerald-100 text-emerald-700'
  if (state === 'Closed') return 'bg-gray-100 text-gray-600'
  if (state === 'In Progress') return 'bg-blue-100 text-blue-700'
  if (state === 'On Hold') return 'bg-amber-100 text-amber-700'
  if (state === 'Canceled') return 'bg-gray-100 text-gray-500'
  if (state === 'Pending') return 'bg-purple-100 text-purple-700'
  return 'bg-indigo-100 text-indigo-700'
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
</script>

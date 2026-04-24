<template>
  <AppLayout :show-sidebar="false">
    <div
      class="mx-auto w-full max-w-[1600px] space-y-4 bg-[#f8fafc] text-slate-900 selection:bg-blue-100 selection:text-blue-900"
    >
      <!-- Filters -->
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div
          class="flex items-center gap-3 rounded-lg border border-slate-100 bg-white px-4 py-1.5 shadow-sm"
        >
          <div class="flex items-center gap-2">
            <span
              class="text-[10px] font-black uppercase tracking-widest text-slate-400"
              >{{ t('hyperbdrDashboard.year') }}</span
            >
            <select
              v-model="selectedYear"
              class="cursor-pointer rounded-lg border-none bg-slate-50 px-3 py-1.5 text-xs font-bold text-slate-600 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option v-for="year in years" :key="year" :value="year">
                {{ year === 'all' ? t('common.all') : year }}
              </option>
            </select>
          </div>
          <div class="h-4 w-px bg-slate-200" />
          <div class="flex items-center gap-2">
            <span
              class="text-[10px] font-black uppercase tracking-widest text-slate-400"
              >{{ t('hyperbdrDashboard.month') }}</span
            >
            <select
              v-model="selectedMonth"
              class="cursor-pointer rounded-lg border-none bg-slate-50 px-3 py-1.5 text-xs font-bold text-slate-600 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="all">
                {{ t('hyperbdrDashboard.allMonths') }}
              </option>
              <option v-for="m in 12" :key="m" :value="String(m)">
                {{ m }}{{ t('hyperbdrDashboard.month') }}
              </option>
            </select>
          </div>
        </div>

        <div
          class="flex items-center gap-1 rounded-lg border border-slate-100 bg-white p-1.5 shadow-sm"
        >
          <span
            class="px-2 text-[10px] font-black uppercase tracking-widest text-slate-400"
            >{{ t('hyperbdrDashboard.scenario') }}</span
          >
          <button
            v-for="scene in sceneOptions"
            :key="scene.value"
            type="button"
            class="whitespace-nowrap rounded-lg px-4 py-1.5 text-xs font-bold transition-all"
            :class="
              sceneFilter === scene.value
                ? 'bg-blue-600 text-white shadow-md shadow-blue-200'
                : 'text-slate-500 hover:bg-slate-50'
            "
            @click="sceneFilter = scene.value"
          >
            {{ t(scene.labelKey) }}
          </button>
        </div>
      </div>

      <!-- KPI Cards -->
      <div class="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <div
          v-for="kpi in dynamicKPIS"
          :key="kpi.key"
          class="flex flex-col justify-between rounded-lg border p-6 shadow-sm transition-all hover:shadow-md"
          :class="
            kpi.type === 'gradient'
              ? 'border-none bg-gradient-to-br from-blue-600 to-indigo-600 text-white'
              : kpi.type === 'accent'
                ? 'border-purple-100 bg-white shadow-purple-50'
                : 'border-slate-100 bg-white'
          "
        >
          <div class="flex items-start justify-between">
            <div class="flex flex-col">
              <div class="flex items-center gap-1.5">
                <p
                  class="text-[11px] font-bold tracking-wider uppercase"
                  :class="
                    kpi.type === 'gradient' ? 'text-white/80' : 'text-slate-500'
                  "
                >
                  {{ t(kpi.labelKey) }}
                </p>
                <!-- Help icon tooltip -->
                <div
                  v-if="kpi.descriptionKey"
                  class="relative cursor-help group"
                >
                  <svg
                    class="h-3 w-3"
                    :class="
                      kpi.type === 'gradient'
                        ? 'text-white/40'
                        : 'text-slate-300'
                    "
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <div
                    class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-50 pointer-events-none"
                  >
                    <div
                      class="w-48 p-2 bg-slate-800 text-white text-[10px] rounded shadow-xl text-center font-medium leading-relaxed"
                    >
                      {{ t(kpi.descriptionKey) }}
                      <div
                        class="absolute top-full left-1/2 -translate-x-1/2 border-8 border-transparent border-t-slate-800"
                      />
                    </div>
                  </div>
                </div>
              </div>
              <p
                class="mt-3 text-3xl font-bold"
                :class="
                  kpi.type === 'gradient' ? 'text-white' : 'text-slate-800'
                "
              >
                {{ kpi.value }}
                <span
                  v-if="kpi.unit"
                  class="text-sm font-medium"
                  :class="
                    kpi.type === 'gradient' ? 'text-white/70' : 'text-slate-400'
                  "
                  >{{ kpi.unit }}</span
                >
              </p>
            </div>
            <div
              v-if="kpi.type !== 'gradient'"
              class="p-2 rounded-lg"
              :class="
                kpi.type === 'primary'
                  ? 'bg-blue-50 text-blue-600'
                  : kpi.type === 'secondary'
                    ? 'bg-slate-50 text-slate-500'
                    : kpi.type === 'accent'
                      ? 'bg-purple-50 text-purple-600 shadow-sm shadow-purple-100'
                      : 'bg-slate-50 text-slate-400'
              "
            >
              <!-- Total Tenants Icon -->
              <svg
                v-if="kpi.key === 'totalTenants'"
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
              <!-- POC Icon -->
              <svg
                v-else-if="kpi.key === 'pocTenants'"
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"
                />
              </svg>
              <!-- Official Icon -->
              <svg
                v-else-if="kpi.key === 'officialTenants'"
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                />
              </svg>
              <!-- Others Icon -->
              <svg
                v-else-if="kpi.key === 'otherTenants'"
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <!-- Cycle Icon -->
              <svg
                v-else
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
          </div>

          <!-- Progress bar for gradient KPI (Conversion Rate) -->
          <div
            v-if="
              kpi.progress != null &&
              (kpi.type === 'gradient' || kpi.type === 'accent')
            "
            class="mt-4"
          >
            <div
              class="flex justify-between text-[10px] font-medium mb-1.5"
              :class="
                kpi.type === 'gradient' ? 'text-white/70' : 'text-slate-400'
              "
            >
              <span>{{
                kpi.progressLabelKey
                  ? t(kpi.progressLabelKey)
                  : kpi.progressLabel
              }}</span>
              <span>{{ kpi.progress }}%{{ kpi.progressSuffix || '' }}</span>
            </div>
            <div
              class="w-full overflow-hidden rounded-full h-1.5"
              :class="kpi.type === 'gradient' ? 'bg-white/20' : 'bg-slate-100'"
            >
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="
                  kpi.type === 'primary'
                    ? 'bg-blue-600'
                    : kpi.type === 'secondary'
                      ? 'bg-green-500'
                      : kpi.type === 'accent'
                        ? 'bg-purple-500'
                        : 'bg-white'
                "
                :style="{ width: kpi.progress + '%' }"
              />
            </div>
          </div>

          <!-- Trend badge -->
          <div v-if="kpi.trendValue" class="mt-3">
            <span
              class="inline-flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded"
              :class="
                kpi.type === 'gradient'
                  ? 'bg-white/20 text-white'
                  : kpi.type === 'accent'
                    ? 'text-purple-600 bg-purple-50'
                    : 'text-green-600 bg-green-50'
              "
            >
              <svg
                class="h-3 w-3"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                />
              </svg>
              {{ kpi.trendValue }}
            </span>
          </div>
        </div>
      </div>

      <!-- Funnel, Trend Chart & Churn Chart Row -->
      <div class="mb-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- Conversion Funnel - Trapezoid Style -->
        <div
          class="overflow-hidden rounded-lg border border-slate-100 bg-white p-6 shadow-sm"
        >
          <div class="mb-8">
            <div class="flex items-center gap-2">
              <h2 class="text-base font-bold text-slate-800">
                {{ t('hyperbdrDashboard.conversionFunnel') }}
              </h2>
              <span
                class="rounded bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-400"
                >{{ timeFilterLabel }}</span
              >
            </div>
            <p class="mt-1 text-xs text-slate-400">
              {{ t('hyperbdrDashboard.funnelDesc') }}
            </p>
          </div>

          <!-- Trapezoid Funnel Visualization -->
          <div
            class="flex flex-col items-center justify-center space-y-1 flex-1"
          >
            <div
              v-for="(level, index) in trapezoidLevels"
              :key="level.labelKey"
              class="relative flex items-center justify-between px-8 py-4 transition-all hover:scale-[1.02]"
              :style="{
                width: level.width + '%',
                backgroundColor: level.color,
                clipPath: level.clipPath,
                borderRadius: index === 0 ? '12px 12px 0 0' : '0'
              }"
            >
              <div class="flex flex-col">
                <span class="text-[11px] font-bold text-slate-600">{{
                  t(level.labelKey)
                }}</span>
                <span class="text-[10px] text-slate-400">{{
                  level.subLabel
                }}</span>
              </div>
              <span class="text-2xl font-black text-slate-800">{{
                level.count.toLocaleString()
              }}</span>
              <div class="absolute -right-28 flex flex-col items-start">
                <span
                  class="text-[10px] font-black text-slate-400 tracking-widest uppercase"
                  >{{ level.tag }}</span
                >
              </div>
            </div>
          </div>
        </div>

        <!-- Trend Chart -->
        <div
          class="overflow-hidden rounded-lg border border-slate-100 bg-white p-6 shadow-sm"
        >
          <div class="mb-6 flex items-start justify-between">
            <div>
              <div class="flex items-center gap-2">
                <h2 class="text-base font-bold text-slate-800">
                  {{ t('hyperbdrDashboard.trendChart') }}
                </h2>
                <span
                  class="rounded bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-400"
                  >{{ timeFilterLabel }}</span
                >
              </div>
              <p class="mt-1 text-xs text-slate-400">
                {{ t('hyperbdrDashboard.trendDescCumulative') }}
              </p>
            </div>
            <div class="flex flex-col items-end gap-2">
              <div class="flex gap-1 bg-slate-50 p-1 rounded-lg">
                <button
                  v-for="type in ['累计']"
                  :key="type"
                  @click="trendChartType = type"
                  class="px-2.5 py-1 text-[10px] font-bold rounded-md transition-all"
                  :class="
                    trendChartType === type
                      ? 'bg-white shadow-sm text-blue-600'
                      : 'text-slate-400 hover:text-slate-600'
                  "
                >
                  {{ type }}
                </button>
              </div>
              <div class="flex gap-3 text-[9px] font-bold">
                <div class="flex items-center gap-1">
                  <div class="h-2 w-2 rounded-full bg-purple-600" />
                  <span class="text-slate-500">{{
                    t('hyperbdrDashboard.poc')
                  }}</span>
                </div>
                <div class="flex items-center gap-1">
                  <div class="h-2 w-2 rounded-full bg-blue-600" />
                  <span class="text-slate-500">{{
                    t('hyperbdrDashboard.official')
                  }}</span>
                </div>
                <div class="flex items-center gap-1">
                  <div class="h-0.5 w-2.5 bg-amber-400" />
                  <span class="text-slate-500">{{
                    t('hyperbdrDashboard.conversionRate')
                  }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="h-[250px] w-full">
            <Chart type="bar" :data="chartData" :options="chartOptions" />
          </div>
        </div>

        <!-- Churn Chart -->
        <div
          class="overflow-hidden rounded-lg border border-slate-100 bg-white p-6 shadow-sm"
        >
          <div class="mb-6">
            <div class="flex items-center gap-2">
              <h2 class="text-base font-bold text-slate-800">
                {{ t('hyperbdrDashboard.churnChart') }}
              </h2>
              <span
                class="rounded bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-400"
                >{{ timeFilterLabel }}</span
              >
            </div>
            <p class="mt-1 text-xs text-slate-400">
              {{ t('hyperbdrDashboard.churnDesc') }}
            </p>
          </div>
          <div class="h-[250px] w-full">
            <Chart
              type="line"
              :data="churnChartData"
              :options="churnChartOptions"
            />
          </div>
        </div>
      </div>

      <!-- Focus Cards, License Status, Utilization Structure Row -->
      <div class="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <!-- Focus Cards - Horizontal Layout -->
        <div
          class="overflow-hidden rounded-lg border border-slate-100 bg-white p-6 shadow-sm"
        >
          <div class="mb-8">
            <div class="flex items-center gap-2">
              <h2 class="text-base font-bold text-slate-800">
                {{ t('hyperbdrDashboard.focusCards') }}
              </h2>
              <span
                class="rounded bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-400"
                >({{ focusCardsTotal }})</span
              >
            </div>
            <p class="mt-1 text-xs text-slate-400">
              {{ t('hyperbdrDashboard.focusDesc') }}
            </p>
          </div>
          <div class="flex flex-col gap-0 flex-1">
            <div
              v-for="card in focusCards"
              :key="card.key"
              @click="(openDrawer(card), (tableFilter = card.key))"
              class="flex items-center justify-between rounded-xl p-2.5 transition-all duration-300 cursor-pointer group hover:bg-slate-50 border border-transparent"
            >
              <div class="flex items-center gap-4">
                <div
                  class="w-10 h-10 rounded-xl flex items-center justify-center transition-transform group-hover:scale-110"
                  :style="{
                    backgroundColor: card.color + '15',
                    color: card.color
                  }"
                >
                  <svg
                    v-if="card.icon === 'calendar'"
                    class="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                  <svg
                    v-else-if="card.icon === 'trending'"
                    class="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                    />
                  </svg>
                  <svg
                    v-else
                    class="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                  </svg>
                </div>
                <div class="flex flex-col">
                  <span
                    class="text-sm font-bold text-slate-700 group-hover:text-blue-600 transition-colors"
                    >{{ card.label }}</span
                  >
                  <div class="flex items-center gap-3 mt-0.5">
                    <span
                      class="text-[10px] font-medium text-slate-400 flex items-center gap-1"
                    >
                      <span class="w-1 h-1 rounded-full bg-slate-300" />
                      {{
                        card.descriptionKey
                          ? t(card.descriptionKey)
                          : card.description
                      }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="flex items-center gap-4">
                <div class="flex flex-col items-end">
                  <div class="flex items-baseline gap-1">
                    <span
                      class="text-xl font-black transition-colors text-slate-900 group-hover:text-blue-600"
                      >{{ card.count }}</span
                    >
                    <span
                      class="text-[10px] font-bold text-slate-400 uppercase tracking-tighter"
                      >{{ t('hyperbdrDashboard.units') }}</span
                    >
                  </div>
                </div>
                <div
                  class="w-6 h-6 rounded-full flex items-center justify-center transition-all bg-slate-100 text-slate-400 group-hover:bg-blue-600 group-hover:text-white group-hover:rotate-90"
                >
                  <svg
                    class="h-3 w-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- License Status Distribution -->
        <div class="overflow-hidden rounded-lg border border-slate-100 bg-white p-6 shadow-sm">
          <div class="mb-6">
            <div class="flex items-center gap-2">
              <h2 class="text-base font-bold text-slate-800">
                {{ t('hyperbdrDashboard.licenseStatus') }}
              </h2>
            </div>
            <p class="mt-1 text-xs text-slate-400">
              {{ t('hyperbdrDashboard.licenseStatusDesc') }}
            </p>
          </div>

          <div class="flex items-center gap-6">
            <div class="w-40 h-40 flex-shrink-0 relative">
              <Doughnut :data="licenseStatusChartData" :options="licenseStatusChartOptions" />
              <div class="absolute inset-0 flex flex-col items-center justify-center">
                <span class="text-2xl font-black text-slate-800">{{ licenseStats.total }}</span>
                <span class="text-[10px] text-slate-400">Total</span>
              </div>
            </div>
            <div class="flex flex-col gap-3 flex-1">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <div class="h-3 w-3 rounded-full bg-emerald-500" />
                  <span class="text-xs font-medium text-slate-600">{{ t('hyperbdrDashboard.validLicense') }}</span>
                </div>
                <span class="text-sm font-bold text-slate-800">{{ licenseStats.valid }}</span>
              </div>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <div class="h-3 w-3 rounded-full bg-red-500" />
                  <span class="text-xs font-medium text-slate-600">{{ t('hyperbdrDashboard.exhaustedLicense') }}</span>
                </div>
                <span class="text-sm font-bold text-slate-800">{{ licenseStats.exhausted }}</span>
              </div>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <div class="h-3 w-3 rounded-full bg-slate-400" />
                  <span class="text-xs font-medium text-slate-600">{{ t('hyperbdrDashboard.inactiveLicense') }}</span>
                </div>
                <span class="text-sm font-bold text-slate-800">{{ licenseStats.inactive }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Utilization Structure -->
        <div
          class="overflow-hidden rounded-lg border border-slate-100 bg-white p-6 shadow-sm"
        >
          <div class="mb-8">
            <div class="flex items-center gap-2">
              <h2 class="text-base font-bold text-slate-800">
                {{ t('hyperbdrDashboard.utilizationStructure') }}
              </h2>
              <span
                class="rounded bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-400"
                >{{ timeFilterLabel }}</span
              >
            </div>
            <p class="mt-1 text-xs text-slate-400">
              {{ t('hyperbdrDashboard.utilizationDesc') }}
            </p>
          </div>
          <div class="flex flex-col justify-center flex-1 gap-8">
            <div
              v-for="item in utilizationStructure"
              :key="item.type"
              class="flex flex-col gap-2"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="text-xs font-bold text-slate-700">{{
                  t(item.labelKey)
                }}</span>
                <span class="text-[10px] text-slate-400 font-medium">{{
                  t('hyperbdrDashboard.utilizationDistribution')
                }}</span>
              </div>
              <div
                class="flex h-8 w-full overflow-hidden rounded-lg border border-slate-100 shadow-sm"
              >
                <div
                  v-for="(segment, sIdx) in item.segments"
                  :key="sIdx"
                  class="group relative flex h-full items-center justify-center transition-all hover:brightness-95"
                  :style="{
                    width: segment.value + '%',
                    backgroundColor: segment.color
                  }"
                >
                  <span
                    class="text-[10px] font-bold text-white drop-shadow-sm truncate px-1"
                  >
                    {{ segment.value }}%
                  </span>
                  <!-- Tooltip -->
                  <div
                    class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-20"
                  >
                    <div
                      class="rounded bg-slate-800 py-1 px-2 text-[10px] text-white shadow-lg whitespace-nowrap"
                    >
                      {{
                        segment.labelKey ? t(segment.labelKey) : segment.label
                      }}: {{ segment.count }}
                    </div>
                    <div
                      class="absolute -bottom-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 bg-slate-800"
                    />
                  </div>
                </div>
              </div>
              <div class="flex justify-between mt-1">
                <div
                  v-for="(segment, sIdx) in item.segments"
                  :key="sIdx"
                  class="flex items-center gap-1.5"
                >
                  <div
                    class="h-2 w-2 rounded-full"
                    :style="{ backgroundColor: segment.color }"
                  />
                  <span class="text-[10px] font-medium text-slate-500">{{
                    t(segment.labelKey)
                  }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Tenant Table -->
      <div
        class="mb-6 overflow-hidden rounded-lg border border-slate-100 bg-white shadow-sm"
      >
        <div
          class="flex items-center justify-between border-b border-slate-50 bg-slate-50/60 px-8 py-5"
        >
          <div class="flex items-center gap-3">
            <h2 class="text-base font-bold text-slate-800">
              {{ tableFilterTitle }}
            </h2>
            <span
              class="rounded bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-400"
              >{{ t('hyperbdrDashboard.currentData') }}</span
            >
          </div>
          <div class="flex items-center gap-2">
            <span class="mr-1 text-xs font-bold text-slate-400"
              >{{ t('common.filter') }}:</span
            >
            <select
              v-model="tableFilter"
              class="rounded-lg border-none bg-slate-50 px-3 py-1.5 text-xs font-bold text-slate-600 focus:ring-2 focus:ring-blue-500 focus:outline-none cursor-pointer"
            >
              <option value="all">{{ t('common.all') || 'All' }}</option>
              <option
                v-for="card in focusCards"
                :key="card.key"
                :value="card.key"
              >
                {{ t(card.labelKey) }}
              </option>
            </select>
          </div>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full min-w-[1000px] text-left border-collapse">
            <thead class="bg-slate-50/50">
              <tr
                class="text-[10px] uppercase tracking-widest font-black text-slate-400"
              >
                <th class="px-8 py-4">
                  {{ t('hyperbdrDashboard.tenantName') }}
                </th>
                <th class="px-4 py-4">{{ t('hyperbdrDashboard.scenario') }}</th>
                <th class="px-4 py-4">
                  {{ t('hyperbdrDashboard.cloudPlatform') }}
                </th>
                <th class="px-4 py-4">{{ t('hyperbdrDashboard.authType') }}</th>
                <th class="px-4 py-4">
                  {{ t('hyperbdrDashboard.validAuth') }}
                </th>
                <th class="px-4 py-4">{{ t('hyperbdrDashboard.usedAuth') }}</th>
                <th class="px-4 py-4">
                  {{ t('hyperbdrDashboard.utilization') }}
                </th>
                                <th class="px-4 py-4">
                  {{ t('hyperbdrDashboard.remainingDays') }}
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-50">
              <tr
                v-for="tenant in paginatedTenants"
                :key="tenant.id"
                class="group transition-colors hover:bg-slate-50/50"
              >
                <td class="px-8 py-5">
                  <div class="flex flex-col">
                    <span class="text-sm font-bold text-slate-800">{{
                      tenant.name
                    }}</span>
                    <span class="text-[10px] text-slate-400"
                      >ID: {{ tenant.id }}</span
                    >
                  </div>
                </td>
                <td class="px-4 py-5 text-xs font-medium text-slate-500">
                  {{ translateScenario(tenant.scenario) }}
                </td>
                <td class="px-4 py-5">
                  <span
                    class="rounded px-2 py-0.5 text-[10px] font-bold"
                    :class="
                      tenant.data_source
                        ? 'bg-orange-50 text-orange-600'
                        : 'bg-red-50 text-red-600'
                    "
                  >
                    {{ tenant.data_source || '-' }}
                  </span>
                </td>
                <td class="px-4 py-5">
                  <span
                    class="rounded px-2 py-0.5 text-[10px] font-bold"
                    :class="
                      tenant.tenant_type === 'poc'
                        ? 'bg-blue-50 text-blue-600'
                        : 'bg-indigo-50 text-indigo-600'
                    "
                  >
                    {{
                      tenant.tenant_type === 'official'
                        ? t('hyperbdrDashboard.official')
                        : t('hyperbdrDashboard.poc')
                    }}
                  </span>
                </td>
                <td class="px-4 py-5 text-xs font-bold text-slate-700">
                  {{ (tenant.total_authorization || 0).toLocaleString() }}
                </td>
                <td class="px-4 py-5 text-xs font-medium text-slate-500">
                  {{ (tenant.used_authorization || 0).toLocaleString() }}
                </td>
                <td class="px-4 py-5">
                  <div class="flex items-center gap-3">
                    <div
                      class="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100"
                    >
                      <div
                        class="h-full rounded-full"
                        :class="utilizationClass(tenant.utilization)"
                        :style="{ width: tenant.utilization + '%' }"
                      />
                    </div>
                    <span class="text-[10px] font-bold text-slate-700"
                      >{{ tenant.utilization }}%</span
                    >
                  </div>
                </td>
                <td class="px-4 py-5">
                  <span
                    class="text-xs font-bold"
                    :class="remainingDaysClass(tenant.remaining_days)"
                  >
                    {{ formatRemainingDays(tenant.remaining_days) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div
          class="flex items-center justify-between border-t border-slate-50 bg-slate-50/30 px-8 py-4"
        >
          <span class="text-[11px] text-slate-400 font-medium">
            {{
              t('common.pagination.showing', {
                from: paginatedFrom,
                to: paginatedTo,
                total: filteredTenants.length
              })
            }}
          </span>
          <div class="flex items-center gap-1">
            <button
              class="rounded-lg p-1.5 text-slate-400 transition-all hover:bg-white hover:shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="currentPage === 1"
              @click="currentPage -= 1"
            >
              <svg
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </button>
            <button
              v-for="p in visiblePages"
              :key="p"
              class="h-8 w-8 rounded-lg text-[11px] font-bold transition-all"
              :class="
                p === currentPage
                  ? 'border border-slate-200 bg-white text-blue-600 shadow-sm'
                  : 'text-slate-400 hover:bg-white hover:shadow-sm'
              "
              @click="currentPage = p"
            >
              {{ p }}
            </button>
            <button
              class="rounded-lg p-1.5 text-slate-400 transition-all hover:bg-white hover:shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
              :disabled="currentPage === totalPages"
              @click="currentPage += 1"
            >
              <svg
                class="h-4 w-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Top 5 Ranking Table -->
      <div
        class="mb-6 overflow-hidden rounded-lg border border-slate-100 bg-white shadow-sm"
      >
        <div
          class="flex items-center justify-between border-b border-slate-50 bg-slate-50/60 px-8 py-5"
        >
          <div class="flex items-center gap-3">
            <h2 class="text-base font-bold text-slate-800">
              {{ t('hyperbdrDashboard.top5Ranking') }}
            </h2>
            <span
              class="rounded bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-400"
              >{{ timeFilterLabel }}</span
            >
          </div>
          <div class="flex items-center gap-2 bg-slate-50 p-1 rounded-lg">
            <button
              class="rounded-md px-3 py-1.5 text-[10px] font-bold transition-all"
              :class="
                topSortBy === 'auth'
                  ? 'bg-white shadow-sm text-blue-600'
                  : 'text-slate-400 hover:text-slate-600'
              "
              @click="topSortBy = 'auth'"
            >
              {{ t('hyperbdrDashboard.sortByAuth') }}
            </button>
            <button
              class="rounded-md px-3 py-1.5 text-[10px] font-bold transition-all"
              :class="
                topSortBy === 'growth'
                  ? 'bg-white shadow-sm text-blue-600'
                  : 'text-slate-400 hover:text-slate-600'
              "
              @click="topSortBy = 'growth'"
            >
              {{ t('hyperbdrDashboard.sortByGrowth') }}
            </button>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr
                class="bg-slate-50/50 text-[10px] uppercase tracking-widest font-black text-slate-400"
              >
                <th class="px-8 py-4 w-16">
                  {{ t('hyperbdrDashboard.rank') }}
                </th>
                <th class="px-4 py-4">
                  {{ t('hyperbdrDashboard.tenantName') }}
                </th>
                <th class="px-4 py-4">
                  {{ t('hyperbdrDashboard.authTotal') }}
                </th>
                <th class="px-4 py-4">
                  {{ t('hyperbdrDashboard.top5Share') }}
                </th>
                <th class="px-4 py-4">
                  {{ t('hyperbdrDashboard.growthRate') }}
                </th>
                <th class="px-8 py-4 text-right">
                  {{ t('hyperbdrDashboard.authShare') }}
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-50">
              <tr
                v-for="(tenant, idx) in top5Tenants"
                :key="tenant.id"
                class="group transition-colors hover:bg-slate-50/50"
              >
                <td class="px-8 py-5">
                  <span
                    class="flex h-6 w-6 items-center justify-center rounded-lg text-xs font-black"
                    :class="
                      idx === 0
                        ? 'bg-amber-100 text-amber-600'
                        : idx === 1
                          ? 'bg-slate-100 text-slate-500'
                          : idx === 2
                            ? 'bg-orange-50 text-orange-600'
                            : 'bg-slate-50 text-slate-400'
                    "
                  >
                    {{ idx + 1 }}
                  </span>
                </td>
                <td class="px-4 py-5">
                  <span class="text-sm font-bold text-slate-800">{{
                    tenant.name
                  }}</span>
                </td>
                <td class="px-4 py-5">
                  <span class="text-sm font-black text-slate-700">{{
                    (tenant.total_authorization || 0).toLocaleString()
                  }}</span>
                </td>
                <td class="px-4 py-5">
                  <span class="text-xs font-bold text-slate-500"
                    >{{ top5Share(tenant) }}%</span
                  >
                </td>
                <td class="px-4 py-5">
                  <span class="text-xs font-black text-emerald-500"
                    >+{{ top5Growth(tenant) }}%</span
                  >
                </td>
                <td class="px-8 py-5 text-right">
                  <div class="flex items-center justify-end gap-3">
                    <div
                      class="h-2 w-32 overflow-hidden rounded-full bg-slate-100"
                    >
                      <div
                        class="h-full rounded-full transition-all"
                        :style="{
                          width: top5BarWidth(tenant) + '%',
                          backgroundColor:
                            tenantColors[idx % tenantColors.length]
                        }"
                      />
                    </div>
                    <span class="text-[10px] font-black text-slate-400 w-8"
                      >{{ Math.round(top5BarWidth(tenant)) }}%</span
                    >
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </AppLayout>

  <!-- Focus Card Drawer -->
  <Transition name="drawer">
    <div
      v-if="drawerOpen"
      class="fixed inset-0 z-[100]"
      @keydown.esc="drawerOpen = false"
    >
      <!-- Backdrop -->
      <div
        class="fixed inset-0 bg-slate-900/40 backdrop-blur-sm"
        @click="drawerOpen = false"
      />
      <!-- Drawer Panel -->
      <div
        class="fixed top-0 right-0 h-full w-full max-w-4xl bg-white shadow-2xl z-[101] flex flex-col overflow-hidden"
      >
        <div
          class="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white px-8 py-6"
        >
          <div class="flex items-center gap-3">
            <div
              class="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600"
            >
              <svg
                class="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            </div>
            <div>
              <h2 class="text-xl font-black text-slate-800">
                {{ drawerTitle }}
              </h2>
              <p class="text-xs text-slate-400 font-medium">
                {{
                  t('hyperbdrDashboard.focusTenantCount', {
                    count: drawerTenants.length
                  })
                }}
              </p>
            </div>
          </div>
          <button
            @click="drawerOpen = false"
            class="flex h-10 w-10 items-center justify-center rounded-full text-slate-400 transition-all hover:bg-slate-100 hover:text-slate-600"
          >
            <svg
              class="h-6 w-6"
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
          </button>
        </div>
        <div class="flex-1 overflow-y-auto p-0">
          <table class="w-full text-left border-collapse">
            <thead class="bg-slate-50/50 sticky top-0">
              <tr
                class="text-[10px] uppercase tracking-widest font-black text-slate-400"
              >
                <th class="px-8 py-4">
                  {{ t('hyperbdrDashboard.tenantName') }}
                </th>
                <th class="px-4 py-4">{{ t('hyperbdrDashboard.scenario') }}</th>
                <th class="px-4 py-4">{{ t('hyperbdrDashboard.authType') }}</th>
                <th class="px-4 py-4">
                  {{ t('hyperbdrDashboard.validAuth') }}
                </th>
                <th class="px-4 py-4">{{ t('hyperbdrDashboard.usedAuth') }}</th>
                <th class="px-4 py-4">
                  {{ t('hyperbdrDashboard.utilization') }}
                </th>
                <th class="px-4 py-4">
                  {{ t('hyperbdrDashboard.remainingDays') }}
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-50">
              <tr
                v-for="tenant in drawerTenants"
                :key="tenant.id"
                class="transition-colors hover:bg-slate-50/50"
              >
                <td class="px-8 py-5">
                  <div class="flex flex-col">
                    <span class="text-sm font-bold text-slate-800">{{
                      tenant.name
                    }}</span>
                    <span class="text-[10px] text-slate-400"
                      >ID: {{ tenant.id }}</span
                    >
                  </div>
                </td>
                <td class="px-4 py-5 text-xs font-medium text-slate-500">
                  {{ translateScenario(tenant.scenario) }}
                </td>
                <td class="px-4 py-5">
                  <span
                    class="rounded px-2 py-0.5 text-[10px] font-bold"
                    :class="
                      tenant.tenant_type === 'poc'
                        ? 'bg-blue-50 text-blue-600'
                        : 'bg-indigo-50 text-indigo-600'
                    "
                  >
                    {{
                      tenant.tenant_type === 'official'
                        ? t('hyperbdrDashboard.official')
                        : t('hyperbdrDashboard.poc')
                    }}
                  </span>
                </td>
                <td class="px-4 py-5 text-xs font-bold text-slate-700">
                  {{ (tenant.total_authorization || 0).toLocaleString() }}
                </td>
                <td class="px-4 py-5 text-xs font-medium text-slate-500">
                  {{ (tenant.used_authorization || 0).toLocaleString() }}
                </td>
                <td class="px-4 py-5">
                  <div class="flex items-center gap-3">
                    <div
                      class="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100"
                    >
                      <div
                        class="h-full rounded-full"
                        :class="utilizationClass(tenant.utilization)"
                        :style="{ width: tenant.utilization + '%' }"
                      />
                    </div>
                    <span class="text-[10px] font-bold text-slate-700"
                      >{{ tenant.utilization }}%</span
                    >
                  </div>
                </td>
                <td class="px-4 py-5">
                  <span
                    class="text-xs font-bold"
                    :class="remainingDaysClass(tenant.remaining_days)"
                  >
                    {{ formatRemainingDays(tenant.remaining_days) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div
          class="flex items-center justify-between border-t border-slate-100 bg-slate-50 px-8 py-4"
        >
          <span class="text-[11px] text-slate-400 font-medium">{{
            t('hyperbdrDashboard.realTimeUpdate')
          }}</span>
          <button
            @click="drawerOpen = false"
            class="rounded-lg bg-slate-800 px-6 py-2 text-xs font-bold text-white transition-all hover:bg-slate-900"
          >
            {{ t('hyperbdrDashboard.close') }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import { Chart, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ArcElement,
  DoughnutController
} from 'chart.js'
import { hyperbdrDashboardApi } from '@/api/hyperbdrDashboard'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ArcElement,
  DoughnutController
)

const { t } = useI18n()

// ─── API State ────────────────────────────────────────────────────────────────
const loading = ref(false)
const loadError = ref(null)
const overviewData = ref(null)
const trendsData = ref(null)

// ─── Filters ──────────────────────────────────────────────────────────────────
const currentYear = new Date().getFullYear()
const years = ['all', currentYear - 1, currentYear]

const selectedYear = ref('all')
const selectedMonth = ref('all')
const sceneOptions = [
  { value: 'all', labelKey: 'common.all' },
  { value: 'migration', labelKey: 'hyperbdrDashboard.migration' },
  { value: 'disaster', labelKey: 'hyperbdrDashboard.disasterRecovery' }
]

const sceneFilter = ref('all')
const tableFilter = ref('all')
const trendChartType = ref('累计')

// Time filter label
const timeFilterLabel = computed(() => {
  if (selectedYear.value === 'all') {
    return t('hyperbdrDashboard.allTime')
  }
  if (selectedMonth.value === 'all') {
    return `${selectedYear.value}${t('hyperbdrDashboard.yearFull')}`
  }
  return `${selectedYear.value}${t('hyperbdrDashboard.yearShort')}${selectedMonth.value}${t('hyperbdrDashboard.monthShort')}`
})

// Table filter title
const tableFilterTitle = computed(() => {
  if (tableFilter.value === 'all') return t('hyperbdrDashboard.focusTenants')
  const card = focusCards.value.find((c) => c.key === tableFilter.value)
  return card ? t(card.labelKey) : t('hyperbdrDashboard.focusTenants')
})

// ─── Data Fetching ────────────────────────────────────────────────────────────
function extractData(res) {
  return res?.data?.data ?? res?.data ?? res
}

async function fetchOverview() {
  loading.value = true
  loadError.value = null
  try {
    const params = {}
    if (selectedYear.value !== 'all') {
      params.year = selectedYear.value
      if (selectedMonth.value !== 'all') {
        params.month = parseInt(selectedMonth.value)
      }
    }
    const res = await hyperbdrDashboardApi.overview(params)
    overviewData.value = extractData(res)
  } catch (err) {
    loadError.value = err.message || t('hyperbdrDashboard.loadError')
  } finally {
    loading.value = false
  }
}

async function fetchTrends() {
  try {
    const params = {}
    if (selectedYear.value !== 'all') {
      params.year = selectedYear.value
    }
    const res = await hyperbdrDashboardApi.monthlyTrends(params)
    trendsData.value = extractData(res)
  } catch (err) {
    trendsData.value = null
  }
}

async function refresh() {
  await Promise.all([fetchOverview(), fetchTrends()])
}

onMounted(() => {
  refresh()
})

watch([selectedYear, selectedMonth], () => {
  fetchOverview()
  fetchTrends()
})

// ─── License Stats ─────────────────────────────────────────────────────────────
const licenseStats = computed(() => {
  const stats = overviewData.value?.license_stats ?? {}
  return {
    valid: stats.valid_amount ?? 0,
    exhausted: stats.exhausted_amount ?? 0,
    inactive: stats.inactive_amount ?? 0,
    total: (stats.valid_amount ?? 0) + (stats.exhausted_amount ?? 0) + (stats.inactive_amount ?? 0)
  }
})

const licenseStatusChartData = computed(() => {
  return {
    labels: [
      t('hyperbdrDashboard.validLicense'),
      t('hyperbdrDashboard.exhaustedLicense'),
      t('hyperbdrDashboard.inactiveLicense')
    ],
    datasets: [
      {
        data: [licenseStats.value.valid, licenseStats.value.exhausted, licenseStats.value.inactive],
        backgroundColor: ['#10b981', '#ef4444', '#94a3b8'],
        borderColor: ['#10b981', '#ef4444', '#94a3b8'],
        borderWidth: 1
      }
    ]
  }
})

const licenseStatusChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '70%',
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      backgroundColor: 'white',
      titleColor: '#334155',
      bodyColor: '#64748b',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: 12,
      cornerRadius: 12,
      boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'
    }
  }
}

// ─── KPI ──────────────────────────────────────────────────────────────────────
const dynamicKPIS = computed(() => {
  const tenants = sceneFilteredTenants.value
  const total = tenants.length
  const pocCount = tenants.filter((t) => t.tenant_type === 'poc').length
  const officialCount = total - pocCount
  const convRate =
    total > 0 ? ((officialCount / total) * 100).toFixed(1) : '0.0'
  const conversionCycleDays = tenants
    .map((t) => t.conversion_cycle_days)
    .filter((days) => Number.isFinite(days) && days >= 0)
  const avgConversionCycle =
    conversionCycleDays.length > 0
      ? Math.round(
          conversionCycleDays.reduce((sum, days) => sum + days, 0) /
            conversionCycleDays.length
        )
      : 0
  const conversionTarget = 20
  const conversionProgress = Math.min(
    100,
    Number(((avgConversionCycle / conversionTarget) * 100).toFixed(1))
  )
  const conversionDiff = avgConversionCycle - conversionTarget
  const conversionDiffText =
    conversionDiff > 0
      ? `+${conversionDiff}`
      : conversionDiff < 0
        ? `${conversionDiff}`
        : '0'
  const otherCount = Math.max(0, tenants.length - pocCount - officialCount)
  const compareLabel = getCompareLabel()

  return [
    {
      key: 'totalTenants',
      labelKey: 'hyperbdrDashboard.totalTenants',
      value: total,
      type: 'default',
      trend: null,
      trendValue: null,
      descriptionKey: 'hyperbdrDashboard.totalTenantsDesc'
    },
    {
      key: 'pocTenants',
      labelKey: 'hyperbdrDashboard.pocTenants',
      value: pocCount,
      type: 'primary',
      trend: null,
      trendValue: null,
      descriptionKey: 'hyperbdrDashboard.pocTenantsDesc'
    },
    {
      key: 'officialTenants',
      labelKey: 'hyperbdrDashboard.officialTenants',
      value: officialCount,
      type: 'secondary',
      trend: null,
      trendValue: null,
      descriptionKey: 'hyperbdrDashboard.officialTenantsDesc'
    },
    {
      key: 'otherTenants',
      labelKey: 'hyperbdrDashboard.otherTenants',
      value: otherCount,
      type: 'default',
      trend: null,
      trendValue: null,
      descriptionKey: 'hyperbdrDashboard.otherTenantsDesc'
    },
    {
      key: 'conversionRate',
      labelKey: 'hyperbdrDashboard.conversionRate',
      value: `${convRate}%`,
      type: 'accent',
      progress: parseFloat(convRate),
      progressLabelKey: 'hyperbdrDashboard.conversionRate',
      trend: convRate > 0 ? `+${convRate}%` : null,
      trendValue: convRate > 0 ? compareLabel + ' +' + convRate + '%' : null,
      descriptionKey: 'hyperbdrDashboard.conversionRateDesc'
    },
    {
      key: 'conversionCycle',
      labelKey: 'hyperbdrDashboard.conversionCycle',
      value: avgConversionCycle,
      unit: t('hyperbdrDashboard.days'),
      type: 'accent',
      progress: conversionProgress,
      progressLabel: t('hyperbdrDashboard.target20days'),
      progressSuffix: ')',
      trendValue: `${compareLabel} ${conversionDiffText}${t('hyperbdrDashboard.days')}`,
      descriptionKey: 'hyperbdrDashboard.conversionCycleDesc'
    }
  ]
})

// ─── Focus Cards ──────────────────────────────────────────────────────────────
const FOCUS_CARD_KEY_MAP = {
  expiring_soon: {
    labelKey: 'hyperbdrDashboard.expiringSoon',
    descriptionKey: 'hyperbdrDashboard.expiringSoonDesc',
    color: '#ef4444',
    icon: 'calendar'
  },
  high_potential: {
    labelKey: 'hyperbdrDashboard.highPotential',
    descriptionKey: 'hyperbdrDashboard.highPotentialDesc',
    color: '#f97316',
    icon: 'trending'
  },
  poc_expiring: {
    labelKey: 'hyperbdrDashboard.pocExpiring',
    descriptionKey: 'hyperbdrDashboard.pocExpiringDesc',
    color: '#eab308',
    icon: 'calendar'
  },
  low_activity: {
    labelKey: 'hyperbdrDashboard.lowActivity',
    descriptionKey: 'hyperbdrDashboard.lowActivityDesc',
    color: '#64748b',
    icon: 'users'
  }
}

const focusCards = computed(() => {
  const tenants = sceneFilteredTenants.value
  const expiringSoon = tenants.filter(
    (t) =>
      t.remaining_days != null &&
      t.remaining_days >= 0 &&
      t.remaining_days <= 30
  )
  const highPotential = tenants.filter(
    (t) =>
      t.tenant_type === 'poc' &&
      t.utilization >= 60 &&
      t.remaining_days != null &&
      t.remaining_days >= 0 &&
      t.remaining_days <= 30
  )
  const pocExpiring = tenants.filter(
    (t) =>
      t.tenant_type === 'poc' &&
      t.remaining_days != null &&
      t.remaining_days >= 0 &&
      t.remaining_days <= 7
  )
  const lowActivity = tenants.filter((t) => t.utilization < 30)

  const counts = {
    expiring_soon: expiringSoon.length,
    high_potential: highPotential.length,
    poc_expiring: pocExpiring.length,
    low_activity: lowActivity.length
  }

  return Object.entries(FOCUS_CARD_KEY_MAP).map(([key, meta]) => ({
    key,
    count: counts[key] || 0,
    labelKey: meta.labelKey,
    descriptionKey: meta.descriptionKey,
    color: meta.color,
    icon: meta.icon
  }))
})

const focusCardsTotal = computed(() =>
  focusCards.value.reduce((sum, card) => sum + card.count, 0)
)

// ─── Funnel / Retention ───────────────────────────────────────────────────────
const trapezoidLevels = computed(() => {
  const tenants = sceneFilteredTenants.value
  const total = tenants.length
  const pocCount = tenants.filter((t) => t.tenant_type === 'poc').length
  const officialCount = total - pocCount
  if (total === 0) return []

  const pocPercent = ((pocCount / total) * 100).toFixed(1)
  const convRate =
    pocCount > 0 ? ((officialCount / pocCount) * 100).toFixed(1) : '0.0'

  const levels = [
    {
      labelKey: 'hyperbdrDashboard.allTenants',
      count: total,
      percent: 100,
      proportion: 1,
      color: '#8b5cf6',
      subLabel: `${t('hyperbdrDashboard.totalRatio')} 100%`,
      tag: 'TOTAL'
    },
    {
      labelKey: 'hyperbdrDashboard.pocTenant',
      count: pocCount,
      percent: parseFloat(pocPercent),
      proportion: total > 0 ? pocCount / total : 0,
      color: '#a78bfa',
      subLabel: `${t('hyperbdrDashboard.pocRatio')} ${pocPercent}%`,
      tag: 'POC'
    },
    {
      labelKey: 'hyperbdrDashboard.officialTenant',
      count: officialCount,
      percent: parseFloat(convRate),
      proportion: total > 0 ? officialCount / total : 0,
      color: '#c4b5fd',
      subLabel: `${t('hyperbdrDashboard.convRate')} ${convRate}%`,
      tag: 'OFFICIAL'
    }
  ]

  return levels.map((level) => {
    const proportion = level.proportion
    const displayWidth = 45 + 55 * Math.pow(proportion, 0.4)
    const taper = (1 - proportion) * 10
    const clipPath = `polygon(0% 0%, 100% 0%, calc(100% - ${taper}%) 100%, ${taper}% 100%)`
    return { ...level, width: displayWidth, clipPath }
  })
})

// ─── Utilization Structure ─────────────────────────────────────────────────────
const utilizationStructure = computed(() => {
  const tenants = sceneFilteredTenants.value
  const pocTenants = tenants.filter((t) => t.tenant_type === 'poc')
  const officialTenants = tenants.filter((t) => t.tenant_type !== 'poc')

  const buildSegments = (group) => {
    if (group.length === 0) {
      return [
        {
          labelKey: 'hyperbdrDashboard.highUtil',
          value: '0.0',
          count: 0,
          color: '#2563eb'
        },
        {
          labelKey: 'hyperbdrDashboard.mediumUtil',
          value: '0.0',
          count: 0,
          color: '#60a5fa'
        },
        {
          labelKey: 'hyperbdrDashboard.lowUtil',
          value: '0.0',
          count: 0,
          color: '#dbeafe'
        }
      ]
    }
    const high = group.filter((t) => t.utilization >= 60)
    const medium = group.filter(
      (t) => t.utilization >= 30 && t.utilization < 60
    )
    const low = group.filter((t) => t.utilization < 30)
    const total = group.length
    return [
      {
        labelKey: 'hyperbdrDashboard.highUtil',
        value: ((high.length / total) * 100).toFixed(1),
        count: high.length,
        color: '#2563eb'
      },
      {
        labelKey: 'hyperbdrDashboard.mediumUtil',
        value: ((medium.length / total) * 100).toFixed(1),
        count: medium.length,
        color: '#60a5fa'
      },
      {
        labelKey: 'hyperbdrDashboard.lowUtil',
        value: ((low.length / total) * 100).toFixed(1),
        count: low.length,
        color: '#dbeafe'
      }
    ]
  }

  const pocSegs = buildSegments(pocTenants)
  const offSegs = buildSegments(officialTenants)

  return [
    {
      type: 'PoC',
      labelKey: 'hyperbdrDashboard.pocTenants',
      segments: pocSegs
    },
    {
      type: 'Official',
      labelKey: 'hyperbdrDashboard.officialTenants',
      segments: offSegs
    }
  ]
})

// ─── Trend Chart ───────────────────────────────────────────────────────────────
const chartLabels = computed(() => ({
  poc: t('hyperbdrDashboard.poc'),
  official: t('hyperbdrDashboard.official'),
  conversionRate: t('hyperbdrDashboard.conversionRate')
}))

// Build trend chart from monthly data via trends/monthly/ API
const chartData = computed(() => {
  const months = trendsData.value?.months

  if (!months || months.length === 0) {
    return {
      labels: [],
      datasets: [
        {
          label: t('hyperbdrDashboard.poc'),
          data: [],
          backgroundColor: '#8a4cfc',
          borderRadius: 4,
          borderSkipped: false,
          barPercentage: 0.6,
          categoryPercentage: 0.8,
          stack: 'stack0'
        },
        {
          label: t('hyperbdrDashboard.official'),
          data: [],
          backgroundColor: '#2563eb',
          borderRadius: 4,
          borderSkipped: false,
          barPercentage: 0.6,
          categoryPercentage: 0.8,
          stack: 'stack0'
        },
        {
          label: t('hyperbdrDashboard.conversionRate'),
          data: [],
          type: 'line',
          borderColor: '#f59e0b',
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: '#f59e0b',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          tension: 0.3,
          yAxisID: 'y1'
        }
      ]
    }
  }

  // Use month labels (e.g. "2025-01")
  const labels = months.map((m) => m.label)
  const convRate = trendsData.value.conversion_rate || 0

  const pocData = months.map((m) => {
    const total = m.total_tenants || 0
    const official = Math.round((total * convRate) / 100)
    return total - official
  })
  const officialData = months.map((m) => {
    const total = m.total_tenants || 0
    return Math.round((total * convRate) / 100)
  })
  const conversionData = months.map((m) => m.conversion_rate || 0)

  return {
    labels,
    datasets: [
      {
        label: t('hyperbdrDashboard.poc'),
        data: pocData,
        backgroundColor: '#8a4cfc',
        borderRadius: 4,
        borderSkipped: false,
        barPercentage: 0.6,
        categoryPercentage: 0.8,
        stack: 'stack0'
      },
      {
        label: t('hyperbdrDashboard.official'),
        data: officialData,
        backgroundColor: '#2563eb',
        borderRadius: 4,
        borderSkipped: false,
        barPercentage: 0.6,
        categoryPercentage: 0.8,
        stack: 'stack0'
      },
      {
        label: t('hyperbdrDashboard.conversionRate'),
        data: conversionData,
        type: 'line',
        borderColor: '#f59e0b',
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: '#f59e0b',
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        tension: 0.3,
        yAxisID: 'y1'
      }
    ]
  }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'index',
    intersect: false
  },
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      backgroundColor: 'white',
      titleColor: '#334155',
      bodyColor: '#64748b',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: 12,
      cornerRadius: 12,
      boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'
    }
  },
  scales: {
    x: {
      stacked: trendChartType.value === '累计',
      grid: {
        display: false
      },
      border: {
        display: false
      },
      ticks: {
        font: {
          size: 10,
          weight: 600,
          color: '#94a3b8'
        },
        maxRotation: 0,
        maxTicksLimit: 12
      }
    },
    y: {
      stacked: trendChartType.value === '累计',
      grid: {
        color: '#f1f5f9'
      },
      border: {
        display: false
      },
      ticks: {
        font: {
          size: 10,
          color: '#94a3b8'
        }
      }
    },
    y1: {
      position: 'right',
      grid: {
        display: false
      },
      border: {
        display: false
      },
      ticks: {
        font: {
          size: 10,
          color: '#94a3b8'
        },
        callback: (value) => value + '%'
      }
    }
  }
}))

// ─── Churn Chart ──────────────────────────────────────────────────────────────
const churnChartData = computed(() => {
  const months = trendsData.value?.months || []
  const labels = months.map((m) => m.label)
  const churnData = months.map((m) => m.churned_tenants || 0)

  return {
    labels,
    datasets: [
      {
        label: t('hyperbdrDashboard.churnedTenants'),
        data: churnData.length > 0 ? churnData : [],
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        borderWidth: 3,
        pointRadius: 4,
        pointBackgroundColor: '#ef4444',
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        tension: 0.3,
        fill: true
      }
    ]
  }
})

const churnChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: {
    mode: 'index',
    intersect: false
  },
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      backgroundColor: 'white',
      titleColor: '#334155',
      bodyColor: '#64748b',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: 12,
      cornerRadius: 12,
      boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)',
      callbacks: {
        label: (context) =>
          `${t('hyperbdrDashboard.churnedTenants')}: ${context.raw}`
      }
    }
  },
  scales: {
    x: {
      grid: {
        display: false
      },
      border: {
        display: false
      },
      ticks: {
        font: {
          size: 10,
          weight: 600,
          color: '#94a3b8'
        },
        maxRotation: 0,
        maxTicksLimit: 12
      }
    },
    y: {
      grid: {
        color: '#f1f5f9'
      },
      border: {
        display: false
      },
      ticks: {
        font: {
          size: 10,
          color: '#94a3b8'
        }
      }
    }
  }
}

// ─── Tenant Table ──────────────────────────────────────────────────────────────
const allTenants = computed(() => overviewData.value?.tenant_table || [])

// Scene filter applied globally to KPIs, focus cards, funnel, distribution
const sceneFilteredTenants = computed(() => {
  if (sceneFilter.value === 'all') return allTenants.value
  if (sceneFilter.value === 'migration') {
    return allTenants.value.filter((t) => t.scenario && t.scenario !== 'dr')
  }
  // disaster / dr
  return allTenants.value.filter((t) => t.scenario === 'dr')
})

// Table filter applied on top of scene filter (for tenant table display)
const filteredTenants = computed(() => {
  let result = [...sceneFilteredTenants.value]

  if (tableFilter.value !== 'all') {
    switch (tableFilter.value) {
      case 'expiring_soon':
        result = result.filter(
          (t) =>
            t.remaining_days != null &&
            t.remaining_days >= 0 &&
            t.remaining_days <= 30
        )
        break
      case 'high_potential':
        result = result.filter(
          (t) =>
            t.tenant_type === 'poc' &&
            t.utilization >= 60 &&
            t.remaining_days != null &&
            t.remaining_days >= 0 &&
            t.remaining_days <= 30
        )
        break
      case 'poc_expiring':
        result = result.filter(
          (t) =>
            t.tenant_type === 'poc' &&
            t.remaining_days != null &&
            t.remaining_days >= 0 &&
            t.remaining_days <= 7
        )
        break
      case 'low_activity':
        result = result.filter((t) => t.utilization < 30)
        break
    }
  }

  return result
})

const PAGE_SIZE = 10
const currentPage = ref(1)

watch(filteredTenants, () => {
  currentPage.value = 1
})

const totalPages = computed(
  () => Math.ceil(filteredTenants.value.length / PAGE_SIZE) || 1
)

const paginatedTenants = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return filteredTenants.value.slice(start, start + PAGE_SIZE)
})

const paginatedFrom = computed(() => {
  if (filteredTenants.value.length === 0) return 0
  return (currentPage.value - 1) * PAGE_SIZE + 1
})

const paginatedTo = computed(() => {
  return Math.min(currentPage.value * PAGE_SIZE, filteredTenants.value.length)
})

const visiblePages = computed(() => {
  const total = totalPages.value
  const cur = currentPage.value
  if (total <= 5) return Array.from({ length: total }, (_, i) => i + 1)
  if (cur <= 3) return [1, 2, 3, 4, 5]
  if (cur >= total - 2)
    return [total - 4, total - 3, total - 2, total - 1, total]
  return [cur - 2, cur - 1, cur, cur + 1, cur + 2]
})

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getCompareLabel() {
  return selectedMonth.value === 'all'
    ? t('hyperbdrDashboard.compYear')
    : t('hyperbdrDashboard.compMonth')
}

function translateScenario(scenario) {
  if (!scenario) return '-'
  if (scenario === 'dr') return t('hyperbdrDashboard.sceneTypeDisaster')
  return t('hyperbdrDashboard.sceneTypeMigration')
}

// ─── Drawer State ─────────────────────────────────────────────────────────────
const drawerOpen = ref(false)
const drawerTitle = ref('')
const drawerTenants = ref([])

function openDrawer(card) {
  drawerTitle.value = t(card.labelKey)
  const source = sceneFilteredTenants.value
  if (card.key === 'expiring_soon') {
    drawerTenants.value = source.filter(
      (t) =>
        t.remaining_days != null &&
        t.remaining_days >= 0 &&
        t.remaining_days <= 30
    )
  } else if (card.key === 'high_potential') {
    drawerTenants.value = source.filter(
      (t) =>
        t.tenant_type === 'poc' &&
        t.utilization >= 60 &&
        t.remaining_days != null &&
        t.remaining_days >= 0 &&
        t.remaining_days <= 30
    )
  } else if (card.key === 'poc_expiring') {
    drawerTenants.value = source.filter(
      (t) =>
        t.tenant_type === 'poc' &&
        t.remaining_days != null &&
        t.remaining_days >= 0 &&
        t.remaining_days <= 7
    )
  } else if (card.key === 'low_activity') {
    drawerTenants.value = source.filter((t) => t.utilization < 30)
  } else {
    drawerTenants.value = filteredTenants.value
  }
  drawerOpen.value = true
}

// ─── Top 5 Ranking ───────────────────────────────────────────────────────────
const topSortBy = ref('auth')
const tenantColors = ['#2563eb', '#8a4cfc', '#f97316', '#22c55e', '#06b6d4']

const top5Tenants = computed(() => {
  const sorted = [...allTenants.value]
    .map((t, idx) => {
      // Mock growth based on index
      const growthBase = [8.4, 5.2, 12.1, 3.5, 7.8, 4.2, 9.1, 6.3][idx % 8]
      const growthValue = growthBase * 1.0
      return { ...t, growth: growthValue }
    })
    .sort((a, b) => {
      if (topSortBy.value === 'auth')
        return (b.total_authorization || 0) - (a.total_authorization || 0)
      return b.growth - a.growth
    })
  return sorted.slice(0, 5)
})

const top5MaxAuth = computed(() => {
  return top5Tenants.value[0]?.total_authorization || 1
})

const top5TotalAuth = computed(() => {
  return top5Tenants.value.reduce(
    (acc, t) => acc + (t.total_authorization || 0),
    0
  )
})

function top5Share(tenant) {
  return top5TotalAuth.value > 0
    ? (((tenant.total_authorization || 0) / top5TotalAuth.value) * 100).toFixed(
        1
      )
    : '0.0'
}

function top5Growth(tenant) {
  return tenant.growth?.toFixed(1) || '0.0'
}

function top5BarWidth(tenant) {
  return top5MaxAuth.value > 0
    ? ((tenant.total_authorization || 0) / top5MaxAuth.value) * 100
    : 0
}

function utilizationClass(util) {
  const v = parseFloat(util) || 0
  if (v >= 60) return 'bg-blue-600'
  if (v >= 30) return 'bg-slate-400'
  return 'bg-red-400'
}

function remainingDaysClass(days) {
  if (days === null || days === undefined) return 'text-slate-400'
  if (days < 0) return 'text-red-400 line-through'
  if (days <= 7) return 'text-red-500'
  if (days <= 30) return 'text-amber-500'
  return 'text-slate-700'
}

function formatRemainingDays(days) {
  if (days === null || days === undefined) return '-'
  if (days < 0) return t('hyperbdrDashboard.expired') || 'Expired'
  return days
}
</script>

<style scoped>
/* Drawer transition */
.drawer-enter-active,
.drawer-leave-active {
  transition: opacity 0.3s ease;
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
</style>

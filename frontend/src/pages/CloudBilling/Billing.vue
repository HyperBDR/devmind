<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h1 class="text-lg font-semibold text-gray-900">
            {{ t('cloudBilling.billing.title') }}
          </h1>
          <p class="mt-1 text-sm text-gray-500">
            {{ t('cloudBilling.billing.subtitle') }}
          </p>
        </div>
        <BaseButton
          variant="outline"
          size="sm"
          :loading="
            activeTab === 'statistics'
              ? statsLoading
              : activeTab === 'details'
                ? detailsLoading
                : false
          "
          @click="handleRefresh"
          :title="t('common.refresh')"
          class="flex items-center gap-1 transition-shadow shadow-sm hover:shadow-md"
        >
          <svg
            v-if="
              !(activeTab === 'statistics'
                ? statsLoading
                : activeTab === 'details'
                  ? detailsLoading
                  : false)
            "
            class="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          <span class="sr-only">{{ t('common.refresh') }}</span>
        </BaseButton>
      </div>

      <div class="bg-white border border-gray-200 rounded shadow-sm">
        <div class="p-6">
          <!-- Tabs -->
          <div>
            <div class="border-b border-gray-200">
              <nav class="flex -mb-px space-x-4 overflow-x-auto">
                <button
                  v-for="tab in tabs"
                  :key="tab.id"
                  :class="[
                    activeTab === tab.id
                      ? 'border-primary-500 text-primary-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
                    'whitespace-nowrap py-3 px-4 border-b-2 font-semibold text-sm transition-colors'
                  ]"
                  @click="activeTab = tab.id"
                >
                  {{ tab.label }}
                </button>
              </nav>
            </div>

            <div class="mt-6">
              <!-- Statistics Tab -->
              <div v-if="activeTab === 'statistics'">
                <!-- Statistics Filters -->
                <div
                  class="p-4 mb-6 bg-white border border-gray-200 rounded-lg shadow-sm"
                >
                  <div class="flex flex-wrap items-end gap-4">
                    <!-- Period Type Selection -->
                    <div class="flex-1 min-w-[140px]">
                      <label
                        class="block mb-1 text-sm font-medium text-gray-700"
                      >
                        {{ t('cloudBilling.billing.periodType') }}:
                      </label>
                      <select
                        v-model="statsPeriodType"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                      >
                        <option value="month">
                          {{ t('cloudBilling.billing.byMonth') }}
                        </option>
                        <option value="year">
                          {{ t('cloudBilling.billing.byYear') }}
                        </option>
                      </select>
                    </div>

                    <!-- Period Selection (Month or Year) -->
                    <div
                      v-if="statsPeriodType === 'month'"
                      class="flex-1 min-w-[180px]"
                    >
                      <label
                        class="block mb-1 text-sm font-medium text-gray-700"
                      >
                        {{ t('cloudBilling.billing.month') }}:
                      </label>
                      <BaseMonthPicker
                        v-model="statsSelectedPeriod"
                        :placeholder="t('cloudBilling.billing.month')"
                      />
                    </div>
                    <div
                      v-if="statsPeriodType === 'year'"
                      class="flex-1 min-w-[140px]"
                    >
                      <label
                        class="block mb-1 text-sm font-medium text-gray-700"
                      >
                        {{ t('cloudBilling.billing.year') }}:
                      </label>
                      <input
                        type="number"
                        v-model="statsSelectedYear"
                        :min="2020"
                        :max="2099"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>

                    <!-- Provider Filter -->
                    <div class="flex-1 min-w-[180px]">
                      <label
                        class="block mb-1 text-sm font-medium text-gray-700"
                      >
                        {{ t('cloudBilling.billing.provider') }}
                      </label>
                      <select
                        v-model="statsProviderId"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                        @change="statsAccountId = ''"
                      >
                        <option value="">
                          {{ t('cloudBilling.billing.allProviders') }}
                        </option>
                        <option
                          v-for="provider in providers"
                          :key="provider.id"
                          :value="provider.id"
                        >
                          {{ getProviderSelectLabel(provider) }}
                        </option>
                      </select>
                    </div>

                    <!-- Account ID Filter -->
                    <div class="flex-1 min-w-[180px]">
                      <label
                        class="block mb-1 text-sm font-medium text-gray-700"
                      >
                        {{ t('cloudBilling.billing.accountId') }}
                      </label>
                      <select
                        v-model="statsAccountId"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                        :disabled="!statsProviderId"
                      >
                        <option value="">
                          {{ t('cloudBilling.billing.allAccounts') }}
                        </option>
                        <option
                          v-for="account in availableAccounts"
                          :key="account"
                          :value="account"
                        >
                          {{
                            account || t('cloudBilling.billing.defaultAccount')
                          }}
                        </option>
                      </select>
                    </div>
                  </div>
                </div>

                <!-- Statistics Content -->
                <BaseLoading v-if="statsLoading && !statistics" />

                <div v-if="!statsLoading && statistics" class="space-y-6">
                  <!-- Summary Cards and Pie Chart Row -->
                  <div
                    v-if="statsPeriodType === 'month'"
                    class="grid items-start grid-cols-1 gap-6 lg:grid-cols-2"
                  >
                    <!-- Left Column: Summary Cards -->
                    <div class="flex flex-col h-full space-y-3">
                      <div
                        class="flex items-center flex-1 gap-3 p-4 bg-white border border-gray-200 rounded-lg"
                      >
                        <div
                          class="flex items-center justify-center flex-shrink-0 w-10 h-10 bg-blue-100 rounded-lg"
                        >
                          <svg
                            class="w-6 h-6 text-blue-600"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              stroke-linecap="round"
                              stroke-linejoin="round"
                              stroke-width="2"
                              d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                        </div>
                        <div class="flex-1 min-w-0">
                          <div class="mb-1 text-xs font-medium text-gray-500">
                            {{ t('cloudBilling.billing.totalCost') }}
                          </div>
                          <div class="text-xl font-bold text-gray-900">
                            {{
                              formatStatsSummaryAmount(
                                statistics.total_cost,
                                'total_cost'
                              )
                            }}
                          </div>
                          <div
                            v-if="statsSummaryHasMixedCurrencies"
                            class="mt-1 text-xs font-medium text-gray-500"
                          >
                            {{
                              t('cloudBilling.billing.overviewMixedCurrency')
                            }}
                          </div>
                        </div>
                      </div>
                      <div
                        class="flex items-center flex-1 gap-3 p-4 bg-white border border-gray-200 rounded-lg"
                      >
                        <div
                          class="flex items-center justify-center flex-shrink-0 w-10 h-10 bg-green-100 rounded-lg"
                        >
                          <svg
                            class="w-6 h-6 text-green-600"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              stroke-linecap="round"
                              stroke-linejoin="round"
                              stroke-width="2"
                              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                            />
                          </svg>
                        </div>
                        <div class="flex-1 min-w-0">
                          <div class="mb-1 text-xs font-medium text-gray-500">
                            {{ t('cloudBilling.billing.averageCost') }}
                          </div>
                          <div class="text-xl font-bold text-gray-900">
                            {{
                              formatStatsSummaryAmount(
                                statistics.average_cost,
                                'average_cost'
                              )
                            }}
                          </div>
                          <div
                            v-if="statsSummaryHasMixedCurrencies"
                            class="mt-1 text-xs font-medium text-gray-500"
                          >
                            {{
                              t('cloudBilling.billing.overviewMixedCurrency')
                            }}
                          </div>
                        </div>
                      </div>
                      <div
                        class="flex items-center flex-1 gap-3 p-4 bg-white border border-gray-200 rounded-lg"
                      >
                        <div
                          class="flex items-center justify-center flex-shrink-0 w-10 h-10 rounded-lg bg-amber-100"
                        >
                          <svg
                            class="w-6 h-6 text-amber-600"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              stroke-linecap="round"
                              stroke-linejoin="round"
                              stroke-width="2"
                              d="M17 9V7a5 5 0 00-10 0v2m-2 0h14a2 2 0 012 2v7a2 2 0 01-2 2H5a2 2 0 01-2-2v-7a2 2 0 012-2z"
                            />
                          </svg>
                        </div>
                        <div class="flex-1 min-w-0">
                          <div class="mb-1 text-xs font-medium text-gray-500">
                            {{ t('cloudBilling.billing.balance') }}
                          </div>
                          <div class="text-xl font-bold text-gray-900">
                            {{
                              formatBalanceSummary(
                                statistics.total_balance,
                                statsSummaryCurrency
                              )
                            }}
                          </div>
                          <div
                            v-if="selectedProviderBalanceUnsupported"
                            class="mt-1 text-xs font-medium text-amber-600"
                          >
                            {{ t('cloudBilling.billing.balanceUnsupported') }}
                          </div>
                          <div
                            v-else-if="statsSummaryHasMixedCurrencies"
                            class="mt-1 text-xs font-medium text-gray-500"
                          >
                            {{
                              t('cloudBilling.billing.overviewMixedCurrency')
                            }}
                          </div>
                        </div>
                      </div>
                      <div
                        class="flex items-center flex-1 gap-3 p-4 bg-white border border-gray-200 rounded-lg"
                      >
                        <div
                          class="flex items-center justify-center flex-shrink-0 w-10 h-10 bg-purple-100 rounded-lg"
                        >
                          <svg
                            class="w-6 h-6 text-purple-600"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              stroke-linecap="round"
                              stroke-linejoin="round"
                              stroke-width="2"
                              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                            />
                          </svg>
                        </div>
                        <div class="flex-1 min-w-0">
                          <div class="mb-1 text-xs font-medium text-gray-500">
                            {{ t('cloudBilling.billing.accountCount') }}
                          </div>
                          <div class="text-xl font-bold text-gray-900">
                            {{ configuredProviderCount }}
                          </div>
                        </div>
                      </div>
                    </div>
                    <!-- Right Column: Provider Cost Distribution Pie Chart -->
                    <div class="h-full">
                      <BillingPieChart
                        :statistics="statistics"
                        :exchange-rate="statistics?.exchange_rate"
                      />
                    </div>
                  </div>

                  <!-- Summary Cards Only (for Year View) -->
                  <div v-else class="grid grid-cols-1 gap-4 md:grid-cols-4">
                    <div
                      class="flex flex-col justify-center p-3 bg-white border border-gray-200 rounded-lg"
                    >
                      <div class="text-xs font-medium text-gray-500 mb-0.5">
                        {{ t('cloudBilling.billing.totalCost') }}
                      </div>
                      <div class="text-lg font-bold text-gray-900">
                        {{
                          formatStatsSummaryAmount(
                            statistics.total_cost,
                            'total_cost'
                          )
                        }}
                      </div>
                      <div
                        v-if="statsSummaryHasMixedCurrencies"
                        class="mt-1 text-xs font-medium text-gray-500"
                      >
                        {{ t('cloudBilling.billing.overviewMixedCurrency') }}
                      </div>
                    </div>
                    <div
                      class="flex flex-col justify-center p-3 bg-white border border-gray-200 rounded-lg"
                    >
                      <div class="text-xs font-medium text-gray-500 mb-0.5">
                        {{ t('cloudBilling.billing.averageCost') }}
                      </div>
                      <div class="text-lg font-bold text-gray-900">
                        {{
                          formatStatsSummaryAmount(
                            statistics.average_cost,
                            'average_cost'
                          )
                        }}
                      </div>
                      <div
                        v-if="statsSummaryHasMixedCurrencies"
                        class="mt-1 text-xs font-medium text-gray-500"
                      >
                        {{ t('cloudBilling.billing.overviewMixedCurrency') }}
                      </div>
                    </div>
                    <div
                      class="flex flex-col justify-center p-3 bg-white border border-gray-200 rounded-lg"
                    >
                      <div class="text-xs font-medium text-gray-500 mb-0.5">
                        {{ t('cloudBilling.billing.recordCount') }}
                      </div>
                      <div class="text-lg font-bold text-gray-900">
                        {{ statistics.count }}
                      </div>
                    </div>
                    <div
                      class="flex flex-col justify-center p-3 bg-white border border-gray-200 rounded-lg"
                    >
                      <div class="text-xs font-medium text-gray-500 mb-0.5">
                        {{ t('cloudBilling.billing.balance') }}
                      </div>
                      <div class="text-lg font-bold text-gray-900">
                        {{
                          formatBalanceSummary(
                            statistics.total_balance,
                            statsSummaryCurrency
                          )
                        }}
                      </div>
                      <div
                        v-if="selectedProviderBalanceUnsupported"
                        class="mt-1 text-xs font-medium text-amber-600"
                      >
                        {{ t('cloudBilling.billing.balanceUnsupported') }}
                      </div>
                      <div
                        v-else-if="statsSummaryHasMixedCurrencies"
                        class="mt-1 text-xs font-medium text-gray-500"
                      >
                        {{ t('cloudBilling.billing.overviewMixedCurrency') }}
                      </div>
                    </div>
                  </div>

                  <BaseLoading
                    v-if="
                      statsPeriodType === 'month' &&
                      chartLoading &&
                      dailyBillingData.length === 0
                    "
                  />

                  <template v-else>
                    <!-- Cost Chart (Full Width) -->
                    <BillingChart
                      :statistics="statistics"
                      :daily-data="dailyBillingData"
                      :period-type="statsPeriodType"
                      :selected-period="statsSelectedPeriod"
                      :selected-year="statsSelectedYear"
                      :providers="providers"
                    />

                    <!-- Daily Cost Breakdown Chart (Monthly View Only) -->
                    <BillingDailyCostChart
                      v-if="statsPeriodType === 'month'"
                      :daily-data="dailyBillingData"
                      :statistics="statistics"
                      :selected-period="statsSelectedPeriod"
                    />
                  </template>
                </div>

                <div
                  v-if="!statsLoading && !statistics"
                  class="py-16 text-center border border-gray-200 rounded-lg bg-gray-50"
                >
                  <p class="text-sm font-medium text-gray-600">
                    {{ t('cloudBilling.billing.noData') }}
                  </p>
                </div>
              </div>

              <!-- Details Tab -->
              <div v-if="activeTab === 'details'">
                <!-- Details Filters -->
                <div
                  class="p-4 mb-6 bg-white border border-gray-200 rounded-lg shadow-sm"
                >
                  <div class="flex flex-wrap items-end gap-4">
                    <!-- Date Range -->
                    <div class="flex-1 min-w-[160px]">
                      <label
                        class="block mb-1 text-sm font-medium text-gray-700"
                      >
                        {{ t('cloudBilling.billing.startDate') }}
                      </label>
                      <input
                        type="date"
                        v-model="detailsStartDate"
                        :max="detailsEndDate || undefined"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                    <div class="flex-1 min-w-[160px]">
                      <label
                        class="block mb-1 text-sm font-medium text-gray-700"
                      >
                        {{ t('cloudBilling.billing.endDate') }}
                      </label>
                      <input
                        type="date"
                        v-model="detailsEndDate"
                        :min="detailsStartDate || undefined"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>

                    <!-- Provider Filter -->
                    <div class="flex-1 min-w-[180px]">
                      <label
                        class="block mb-1 text-sm font-medium text-gray-700"
                      >
                        {{ t('cloudBilling.billing.provider') }}
                      </label>
                      <select
                        v-model="detailsProviderId"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                        @change="detailsAccountId = ''"
                      >
                        <option value="">
                          {{ t('cloudBilling.billing.allProviders') }}
                        </option>
                        <option
                          v-for="provider in providers"
                          :key="provider.id"
                          :value="provider.id"
                        >
                          {{ getProviderSelectLabel(provider) }}
                        </option>
                      </select>
                    </div>

                    <!-- Account ID Filter -->
                    <div class="flex-1 min-w-[180px]">
                      <label
                        class="block mb-1 text-sm font-medium text-gray-700"
                      >
                        {{ t('cloudBilling.billing.accountId') }}
                      </label>
                      <select
                        v-model="detailsAccountId"
                        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                        :disabled="!detailsProviderId"
                      >
                        <option value="">
                          {{ t('cloudBilling.billing.allAccounts') }}
                        </option>
                        <option
                          v-for="account in availableDetailsAccounts"
                          :key="account"
                          :value="account"
                        >
                          {{
                            account || t('cloudBilling.billing.defaultAccount')
                          }}
                        </option>
                      </select>
                    </div>

                    <!-- Search -->
                    <div class="flex-1 min-w-[200px]">
                      <label
                        class="block mb-1 text-sm font-medium text-gray-700"
                      >
                        {{ t('common.search') }}
                      </label>
                      <BaseInput
                        v-model="searchQuery"
                        :placeholder="t('common.search')"
                        @update:modelValue="handleSearch"
                      >
                        <template #icon>
                          <svg
                            class="w-4 h-4 text-gray-400"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              stroke-linecap="round"
                              stroke-linejoin="round"
                              stroke-width="2"
                              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                            />
                          </svg>
                        </template>
                      </BaseInput>
                    </div>
                  </div>
                </div>

                <!-- Details Content -->
                <BaseLoading v-if="detailsLoading && billings.length === 0" />

                <div
                  v-if="!detailsLoading && billings.length === 0"
                  class="py-16 text-center border border-gray-200 rounded-lg bg-gray-50"
                >
                  <svg
                    class="w-12 h-12 mx-auto mb-4 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
                    />
                  </svg>
                  <p class="text-sm font-medium text-gray-600">
                    {{ t('cloudBilling.billing.noData') }}
                  </p>
                </div>

                <!-- Details Table -->
                <div
                  v-if="!detailsLoading && billings.length > 0"
                  class="overflow-x-auto border border-gray-200 rounded-lg"
                >
                  <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                      <tr>
                        <th
                          class="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase"
                        >
                          {{ t('cloudBilling.billing.provider') }}
                        </th>
                        <th
                          class="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase"
                        >
                          {{ t('cloudBilling.billing.accountId') }}
                        </th>
                        <th
                          class="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase"
                        >
                          {{ t('cloudBilling.billing.collectionTime') }}
                        </th>
                        <th
                          class="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase"
                        >
                          {{ t('cloudBilling.billing.cost') }}
                        </th>
                        <th
                          class="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase"
                        >
                          {{ t('cloudBilling.billing.balance') }}
                        </th>
                        <th
                          class="px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-500 uppercase"
                        >
                          {{ t('cloudBilling.billing.changeFromLastHour') }}
                        </th>
                      </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                      <tr
                        v-for="billing in billings"
                        :key="billing.id"
                        @click="handlePreview(billing)"
                        class="transition-colors cursor-pointer hover:bg-gray-50"
                      >
                        <td
                          class="px-6 py-4 text-sm font-medium text-gray-900 whitespace-nowrap"
                        >
                          {{ getBillingProviderName(billing) }}
                        </td>
                        <td
                          class="px-6 py-4 text-sm text-gray-500 whitespace-nowrap"
                        >
                          {{ billing.account_id || '-' }}
                        </td>
                        <td
                          class="px-6 py-4 text-sm text-gray-500 whitespace-nowrap"
                        >
                          {{ formatDate(billing.collection_time) }}
                        </td>
                        <td
                          class="px-6 py-4 text-sm font-medium text-gray-900 whitespace-nowrap"
                        >
                          {{ formatCost(billing.cost, billing.currency) }}
                        </td>
                        <td
                          class="px-6 py-4 text-sm font-medium text-gray-900 whitespace-nowrap"
                        >
                          <div>{{ formatBillingBalance(billing) }}</div>
                          <div
                            v-if="billing.balance_supported === false"
                            class="mt-1 text-xs font-medium text-amber-600"
                          >
                            {{
                              billing.balance_note ||
                              t('cloudBilling.billing.balanceUnsupported')
                            }}
                          </div>
                        </td>
                        <td
                          class="px-6 py-4 text-sm whitespace-nowrap"
                          :class="
                            getChangeClass(
                              billing.change_from_last_hour,
                              'text-gray-500',
                              true
                            )
                          "
                        >
                          {{ formatChange(billing.change_from_last_hour) }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div
                  v-if="!detailsLoading && detailsTotalCount > 0"
                  class="flex flex-col gap-3 px-4 py-4 mt-4 bg-white border border-gray-200 rounded-lg md:flex-row md:items-center md:justify-between"
                >
                  <div class="text-sm text-gray-600">
                    {{
                      t('common.pagination.showing', {
                        from: detailsRangeStart,
                        to: detailsRangeEnd,
                        total: detailsTotalCount
                      })
                    }}
                  </div>
                  <div class="flex items-center gap-3">
                    <label class="text-sm text-gray-600">
                      {{ t('common.pagination.itemsPerPage') }}:
                    </label>
                    <select
                      v-model.number="detailsPageSize"
                      class="px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                      <option :value="10">10</option>
                      <option :value="20">20</option>
                      <option :value="50">50</option>
                      <option :value="100">100</option>
                    </select>
                    <BaseButton
                      variant="outline"
                      size="sm"
                      :disabled="detailsPage <= 1 || detailsLoading"
                      @click="detailsPage -= 1"
                    >
                      {{ t('common.pagination.previous') }}
                    </BaseButton>
                    <span class="text-sm text-gray-600">
                      {{
                        t('common.pagination.page', {
                          current: detailsPage,
                          total: detailsTotalPages
                        })
                      }}
                    </span>
                    <BaseButton
                      variant="outline"
                      size="sm"
                      :disabled="
                        detailsPage >= detailsTotalPages || detailsLoading
                      "
                      @click="detailsPage += 1"
                    >
                      {{ t('common.pagination.next') }}
                    </BaseButton>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Billing Detail Panel -->
      <BillingDetailPanel
        :show="showPreviewModal"
        :billing="selectedBilling"
        @close="showPreviewModal = false"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'
import { useDebounce } from '@/composables/useDebounce'
import { extractResponseData } from '@/utils/api'
import {
  formatCost,
  formatChange,
  formatDate,
  getChangeClass
} from '@/utils/formatting'
import { cloudBillingApi } from '@/api/cloudBilling'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseMonthPicker from '@/components/ui/BaseMonthPicker.vue'
import BillingDetailPanel from '@/components/cloud-billing/BillingDetailPanel.vue'
import BillingChart from '@/components/cloud-billing/BillingChart.vue'
import BillingPieChart from '@/components/cloud-billing/BillingPieChart.vue'
import BillingDailyCostChart from '@/components/cloud-billing/BillingDailyCostChart.vue'
import {
  appendProviderNotesLabel,
  getLocalizedBillingProviderName,
  getLocalizedProviderDisplayName
} from '@/utils/providerDisplay'

const { t } = useI18n()

const getProviderDisplayName = (provider) =>
  getLocalizedProviderDisplayName(provider, t)
const getProviderSelectLabel = (provider) => {
  return appendProviderNotesLabel(
    getProviderDisplayName(provider),
    provider?.notes
  )
}
const getBillingProviderName = (billing) =>
  getLocalizedBillingProviderName(billing, t)

const activeTab = ref('statistics')
const tabs = computed(() => [
  { id: 'statistics', label: t('cloudBilling.billing.statistics') },
  { id: 'details', label: t('cloudBilling.billing.details') }
])
const isInitializing = ref(true)

// Statistics tab state
const statsLoading = ref(false)
const chartLoading = ref(false)
const statistics = ref(null)
const dailyBillingData = ref([])
const statsPeriodType = ref('month')
const statsSelectedPeriod = ref('')
const statsSelectedYear = ref(new Date().getFullYear())
const statsProviderId = ref('')
const statsAccountId = ref('')
const providers = ref([])
const providerTotalCount = ref(0)

// Details tab state
const detailsLoading = ref(false)
const detailsLoaded = ref(false)
const billings = ref([])
const searchQuery = ref('')
const detailsStartDate = ref('')
const detailsEndDate = ref('')
const detailsProviderId = ref('')
const detailsAccountId = ref('')
const detailsPage = ref(1)
const detailsPageSize = ref(20)
const detailsTotalCount = ref(0)
const detailsAccountOptions = ref([])
const showPreviewModal = ref(false)
const selectedBilling = ref(null)

const detailsTotalPages = computed(() =>
  Math.max(1, Math.ceil(detailsTotalCount.value / detailsPageSize.value || 1))
)
const detailsRangeStart = computed(() =>
  detailsTotalCount.value === 0
    ? 0
    : (detailsPage.value - 1) * detailsPageSize.value + 1
)
const detailsRangeEnd = computed(() =>
  Math.min(detailsPage.value * detailsPageSize.value, detailsTotalCount.value)
)

let providersRequestId = 0
let statsRequestId = 0
let chartRequestId = 0
let detailsRequestId = 0
let detailsAccountsRequestId = 0

// Count configured active providers instead of billing rows in the current period.
const configuredProviderCount = computed(() => {
  if (statsProviderId.value) {
    return providers.value.some(
      (provider) => provider.id === parseInt(statsProviderId.value)
    )
      ? 1
      : 0
  }
  return providerTotalCount.value
})

// Available accounts for statistics filter (based on selected provider)
const availableAccounts = computed(() => {
  if (
    !statistics.value ||
    !statistics.value.by_provider ||
    !statsProviderId.value
  ) {
    return []
  }

  const accounts = new Set()
  Object.values(statistics.value.by_provider).forEach((providerData) => {
    if (providerData.provider_id === parseInt(statsProviderId.value)) {
      const accountId = providerData.account_id || ''
      accounts.add(accountId)
    }
  })

  return Array.from(accounts).sort()
})

const availableDetailsAccounts = computed(() => detailsAccountOptions.value)

const selectedProviderBalanceUnsupported = computed(() => {
  if (!statsProviderId.value || !statistics.value?.by_provider) {
    return false
  }
  const rows = Object.values(statistics.value.by_provider).filter(
    (providerData) =>
      providerData.provider_id === parseInt(statsProviderId.value)
  )
  return (
    rows.length > 0 &&
    rows.every((providerData) => providerData.balance_supported === false)
  )
})

const statsSummaryCurrencies = computed(() => {
  const byProvider = statistics.value?.by_provider
  if (!byProvider) {
    return []
  }

  const rows = Object.values(byProvider).filter((providerData) => {
    if (!statsProviderId.value) {
      return true
    }
    return providerData.provider_id === parseInt(statsProviderId.value)
  })

  const currencies = Array.from(
    new Set(
      rows
        .map((providerData) => String(providerData.currency || '').trim())
        .filter(Boolean)
    )
  )

  return currencies
})

const statsSummaryRows = computed(() => {
  const byProvider = statistics.value?.by_provider
  if (!byProvider) {
    return []
  }
  return Object.values(byProvider).filter((providerData) => {
    if (!statsProviderId.value) {
      return true
    }
    return providerData.provider_id === parseInt(statsProviderId.value)
  })
})

const statsSummaryByCurrency = computed(() => {
  const grouped = {}
  statsSummaryRows.value.forEach((row) => {
    const currency = String(row.currency || 'CNY').trim() || 'CNY'
    if (!grouped[currency]) {
      grouped[currency] = {
        total_cost: 0,
        total_balance: 0,
        count: 0
      }
    }
    grouped[currency].total_cost += Number(row.total_cost || 0)
    grouped[currency].total_balance += Number(row.balance || 0)
    grouped[currency].count += 1
  })
  return grouped
})

const statsSummaryHasMixedCurrencies = computed(
  () => statsSummaryCurrencies.value.length > 1
)

const statsSummaryCurrency = computed(() =>
  statsSummaryCurrencies.value.length === 1
    ? statsSummaryCurrencies.value[0]
    : null
)

const extractProviderListData = (data) => {
  if (Array.isArray(data)) {
    return {
      list: data,
      total: data.length,
      paginated: false
    }
  }

  if (data?.results && Array.isArray(data.results)) {
    const total = Number(data.count)
    return {
      list: data.results,
      total: Number.isFinite(total) ? total : data.results.length,
      paginated: true
    }
  }

  if (data?.list && Array.isArray(data.list)) {
    const total = Number(data?.pagination?.total)
    return {
      list: data.list,
      total: Number.isFinite(total) ? total : data.list.length,
      paginated: true
    }
  }

  return {
    list: [],
    total: 0,
    paginated: false
  }
}

const extractListData = (data) => {
  if (Array.isArray(data)) {
    return {
      list: data,
      total: data.length
    }
  }

  if (data?.results && Array.isArray(data.results)) {
    return {
      list: data.results,
      total: Number(data.count) || data.results.length
    }
  }

  if (data?.list && Array.isArray(data.list)) {
    return {
      list: data.list,
      total: Number(data?.pagination?.total) || data.list.length
    }
  }

  return {
    list: [],
    total: 0
  }
}

// Initialize date range: details tab default is last 3 days (from 3 days ago to today)
const initDateRange = () => {
  const now = new Date()

  // Initialize period for statistics (current month)
  statsSelectedPeriod.value = format(now, 'yyyy-MM')
  statsSelectedYear.value = now.getFullYear()

  const endStr = format(now, 'yyyy-MM-dd')
  const start = new Date(now)
  start.setDate(start.getDate() - 3)
  const startStr = format(start, 'yyyy-MM-dd')
  detailsEndDate.value = endStr
  detailsStartDate.value = startStr
}

const mapBillingRows = (rows) => {
  return rows
    .map((billing) => {
      const providerId = billing.provider || billing.provider_id

      return {
        id: billing.id,
        provider: providerId,
        provider_display_name: getBillingProviderName(billing),
        provider_type: billing.provider_type,
        provider_notes: billing.provider_notes,
        collection_time: billing.collected_at,
        cost: billing.total_cost,
        balance: billing.balance,
        balance_supported: billing.balance_supported,
        balance_note: billing.balance_note,
        currency: billing.currency,
        change_from_last_hour: billing.change_from_last_hour,
        period: billing.period,
        hour: billing.hour,
        service_costs: billing.service_costs,
        account_id: billing.account_id
      }
    })
    .sort((a, b) => new Date(b.collection_time) - new Date(a.collection_time))
}

// Load providers list
const loadProviders = async () => {
  const currentRequestId = ++providersRequestId
  try {
    const pageSize = 10000
    const response = await cloudBillingApi.getProviders({
      is_active: true,
      page: 1,
      page_size: pageSize
    })
    const data = extractResponseData(response)
    const { list, total } = extractProviderListData(data)
    if (currentRequestId !== providersRequestId) return
    providers.value = list
    providerTotalCount.value = total
  } catch (error) {
    console.error('Failed to load providers:', error)
    if (currentRequestId === providersRequestId) {
      providers.value = []
      providerTotalCount.value = 0
    }
  }
}

const formatBalanceSummary = (value, currency = 'CNY') => {
  if (selectedProviderBalanceUnsupported.value) {
    return formatCost(0, currency || 'CNY')
  }
  if (statsSummaryHasMixedCurrencies.value) {
    const balancesByCurrency = {}
    Object.entries(statsSummaryByCurrency.value).forEach(([code, item]) => {
      balancesByCurrency[code] = Number(item.total_balance || 0)
    })
    return formatMultiCurrencySummary(balancesByCurrency)
  }
  if (!currency) {
    return '--'
  }
  return formatCost(value ?? 0, currency)
}

const formatStatsSummaryAmount = (value, metric = 'total_cost') => {
  if (statsSummaryHasMixedCurrencies.value) {
    const valuesByCurrency = {}
    Object.entries(statsSummaryByCurrency.value).forEach(([code, item]) => {
      if (metric === 'average_cost') {
        valuesByCurrency[code] =
          item.count > 0 ? Number(item.total_cost || 0) / item.count : 0
      } else {
        valuesByCurrency[code] = Number(item.total_cost || 0)
      }
    })
    return formatMultiCurrencySummary(valuesByCurrency)
  }
  if (!statsSummaryCurrency.value) {
    return '--'
  }
  return formatCost(value ?? 0, statsSummaryCurrency.value)
}

const formatMultiCurrencySummary = (valueByCurrency) => {
  const preferredOrder = ['CNY', 'USD']
  const entries = Object.entries(valueByCurrency || {})
    .filter(([, amount]) => Number.isFinite(Number(amount)))
    .sort(([a], [b]) => {
      const ai = preferredOrder.indexOf(a)
      const bi = preferredOrder.indexOf(b)
      if (ai === -1 && bi === -1) return a.localeCompare(b)
      if (ai === -1) return 1
      if (bi === -1) return -1
      return ai - bi
    })

  if (entries.length === 0) {
    return '--'
  }

  return entries
    .map(([currency, amount]) => formatCost(amount, currency))
    .join(' / ')
}

const formatBillingBalance = (billing) => {
  if (billing?.balance_supported === false) {
    return formatCost(0, billing.currency)
  }
  return formatCost(billing?.balance ?? 0, billing?.currency)
}

// Load daily billing data for chart
const loadDailyBillingData = async () => {
  const currentRequestId = ++chartRequestId

  if (statsPeriodType.value !== 'month' || !statsSelectedPeriod.value) {
    dailyBillingData.value = []
    chartLoading.value = false
    return
  }

  chartLoading.value = true
  try {
    const [year, month] = statsSelectedPeriod.value.split('-')
    const startDate = new Date(parseInt(year), parseInt(month) - 1, 1)
    const endDate = new Date(parseInt(year), parseInt(month), 0, 23, 59, 59)

    const response = await cloudBillingApi.getBillingDailySeries({
      start_date: format(startDate, 'yyyy-MM-dd'),
      end_date: format(endDate, 'yyyy-MM-dd'),
      ...(statsProviderId.value ? { provider_id: statsProviderId.value } : {}),
      ...(statsAccountId.value ? { account_id: statsAccountId.value } : {})
    })
    const data = extractResponseData(response)
    const { list } = extractListData(data)

    if (currentRequestId !== chartRequestId) return

    dailyBillingData.value = list
  } catch (error) {
    console.error('Failed to load daily billing data:', error)
    if (currentRequestId === chartRequestId) {
      dailyBillingData.value = []
    }
  } finally {
    if (currentRequestId === chartRequestId) {
      chartLoading.value = false
    }
  }
}

// Load statistics summary
const loadStatistics = async () => {
  const currentRequestId = ++statsRequestId
  statsLoading.value = true
  try {
    const params = {}

    if (statsPeriodType.value === 'month' && statsSelectedPeriod.value) {
      params.start_period = statsSelectedPeriod.value
      params.end_period = statsSelectedPeriod.value
    } else if (statsPeriodType.value === 'year' && statsSelectedYear.value) {
      const year = statsSelectedYear.value
      const now = new Date()
      const currentYear = now.getFullYear()
      const currentMonth = now.getMonth() + 1

      params.start_period = `${year}-01`
      params.end_period =
        year === currentYear
          ? `${year}-${String(currentMonth).padStart(2, '0')}`
          : `${year}-12`
    }

    if (statsProviderId.value) {
      params.provider_id = statsProviderId.value
    }

    if (statsAccountId.value) {
      params.account_id = statsAccountId.value
    }

    const response = await cloudBillingApi.getBillingStats(params)
    const data = extractResponseData(response)

    if (currentRequestId !== statsRequestId) return

    statistics.value = data

    if (statsPeriodType.value === 'month') {
      loadDailyBillingData()
    } else {
      chartRequestId += 1
      chartLoading.value = false
      dailyBillingData.value = []
    }
  } catch (error) {
    console.error('Failed to load statistics:', error)
    if (currentRequestId === statsRequestId) {
      statistics.value = null
    }
  } finally {
    if (currentRequestId === statsRequestId) {
      statsLoading.value = false
    }
  }
}

const loadDetailsAccounts = async () => {
  const currentRequestId = ++detailsAccountsRequestId

  if (!detailsProviderId.value) {
    detailsAccountOptions.value = []
    return
  }

  try {
    const response = await cloudBillingApi.getLatestBillingByProviderAccount({
      provider_id: detailsProviderId.value,
      ...(detailsStartDate.value ? { start_date: detailsStartDate.value } : {}),
      ...(detailsEndDate.value ? { end_date: detailsEndDate.value } : {})
    })
    const data = extractResponseData(response)
    const { list } = extractListData(data)

    if (currentRequestId !== detailsAccountsRequestId) return

    detailsAccountOptions.value = Array.from(
      new Set(list.map((item) => item.account_id || ''))
    ).sort()
  } catch (error) {
    console.error('Failed to load billing account options:', error)
    if (currentRequestId === detailsAccountsRequestId) {
      detailsAccountOptions.value = []
    }
  }
}

// Load billing details
const loadBillings = async ({
  query = searchQuery.value,
  resetPage = false
} = {}) => {
  if (resetPage && detailsPage.value !== 1) {
    detailsPage.value = 1
    return
  }

  if (resetPage) {
    detailsLoaded.value = false
  }

  const currentRequestId = ++detailsRequestId
  detailsLoading.value = true
  try {
    const response = await cloudBillingApi.getBillingData({
      ...(query ? { search: query } : {}),
      ...(detailsStartDate.value ? { start_date: detailsStartDate.value } : {}),
      ...(detailsEndDate.value ? { end_date: detailsEndDate.value } : {}),
      ...(detailsProviderId.value
        ? { provider_id: detailsProviderId.value }
        : {}),
      ...(detailsAccountId.value ? { account_id: detailsAccountId.value } : {}),
      page: detailsPage.value,
      page_size: detailsPageSize.value
    })
    const data = extractResponseData(response)
    const { list, total } = extractListData(data)

    if (currentRequestId !== detailsRequestId) return

    billings.value = mapBillingRows(list)
    detailsTotalCount.value = total
    detailsLoaded.value = true
  } catch (error) {
    console.error('Failed to load billings:', error)
    if (currentRequestId === detailsRequestId) {
      billings.value = []
      detailsTotalCount.value = 0
    }
  } finally {
    if (currentRequestId === detailsRequestId) {
      detailsLoading.value = false
    }
  }
}

const { debouncedFn: debouncedSearch } = useDebounce((query) => {
  loadBillings({ query, resetPage: true })
}, 300)

const handleSearch = (query) => {
  searchQuery.value = query
  debouncedSearch(query)
}

const handleRefresh = () => {
  if (activeTab.value === 'statistics') {
    loadStatistics()
  } else {
    loadDetailsAccounts()
    loadBillings({ query: searchQuery.value })
  }
}

const handlePreview = (billing) => {
  selectedBilling.value = billing
  showPreviewModal.value = true
}

// Watch tab changes
watch(activeTab, (newTab) => {
  if (isInitializing.value) return

  if (newTab === 'statistics') {
    loadStatistics()
  } else if (newTab === 'details') {
    loadDetailsAccounts()
    if (!detailsLoaded.value) {
      loadBillings({ resetPage: true })
    }
  }
})

// Watch statistics filter changes for real-time updates
watch(
  [
    statsPeriodType,
    statsSelectedPeriod,
    statsSelectedYear,
    statsProviderId,
    statsAccountId
  ],
  () => {
    if (isInitializing.value) return
    if (activeTab.value === 'statistics') {
      loadStatistics()
    }
  }
)

// Watch details filter changes
watch(
  [detailsStartDate, detailsEndDate, detailsProviderId, detailsAccountId],
  () => {
    if (isInitializing.value) return
    if (activeTab.value === 'details') {
      loadDetailsAccounts()
      loadBillings({ query: searchQuery.value, resetPage: true })
    }
  }
)

watch(detailsPage, () => {
  if (
    isInitializing.value ||
    activeTab.value !== 'details' ||
    !detailsLoaded.value
  ) {
    return
  }
  loadBillings({ query: searchQuery.value })
})

watch(detailsPageSize, () => {
  if (isInitializing.value || activeTab.value !== 'details') {
    return
  }
  loadBillings({ query: searchQuery.value, resetPage: true })
})

onMounted(() => {
  initDateRange()
  isInitializing.value = false
  loadProviders()
  loadStatistics()
})
</script>

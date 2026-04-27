<template>
  <div class="space-y-6">
    <div
      v-if="showHeader"
      class="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between"
    >
      <div>
        <h2 class="text-base font-semibold tracking-tight text-gray-900">
          {{ t('cloudBilling.billing.overviewTitle') }}
        </h2>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('cloudBilling.billing.overviewSubtitle') }}
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <div
          class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2"
        >
          <svg
            class="h-4 w-4 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 21c4.97 0 9-3.806 9-8.5S16.97 4 12 4 3 7.806 3 12.5 7.03 21 12 21z"
            />
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 4v17m-6-8.5h12"
            />
          </svg>
          <select
            v-model="selectedTimezone"
            class="bg-transparent text-xs font-medium text-gray-700 focus:outline-none"
          >
            <option
              v-for="item in timezones"
              :key="item.value"
              :value="item.value"
            >
              {{ item.label }}
            </option>
          </select>
        </div>
        <div class="flex rounded-lg border border-gray-200 bg-gray-50 p-1">
          <button
            v-for="item in currencies"
            :key="item"
            class="rounded-md px-3 py-1.5 text-xs font-semibold transition-colors"
            :class="
              selectedCurrency === item
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            "
            @click="selectedCurrency = item"
          >
            {{ item }}
          </button>
        </div>
        <BaseButton
          variant="outline"
          size="sm"
          :loading="loading"
          @click="loadOverview"
        >
          {{ t('common.refresh') }}
        </BaseButton>
      </div>
    </div>

    <div
      v-if="error"
      class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
    >
      {{ error }}
    </div>

    <BaseLoading v-if="loading && !overviewLoaded" />

    <template v-else>
      <section class="space-y-6">
        <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <article
            v-for="card in summaryCards"
            :key="card.key"
            class="group rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-colors hover:border-gray-300"
          >
            <div class="mb-4 flex items-center justify-between">
              <span
                class="text-[11px] font-semibold uppercase tracking-[0.16em] text-gray-400"
              >
                {{ card.label }}
              </span>
              <div
                class="rounded-lg bg-gray-50 p-2 text-gray-400 transition-colors group-hover:bg-primary-50 group-hover:text-primary-600"
              >
                <component :is="card.icon" class="h-4 w-4" />
              </div>
            </div>
            <div class="text-2xl font-bold tracking-tight text-gray-900">
              {{ card.value }}
            </div>
            <div v-if="card.subValue" class="mt-1 text-xs text-gray-500">
              {{ card.subValue }}
            </div>
          </article>
        </div>

        <div class="grid items-stretch gap-6 lg:grid-cols-4">
          <div class="lg:col-span-3">
            <div
              class="flex h-full flex-col rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
            >
              <div
                class="mb-5 flex flex-wrap items-center justify-between gap-3"
              >
                <div>
                  <h3 class="text-sm font-semibold text-gray-900">
                    {{ t('cloudBilling.billing.overviewCostTrend') }}
                  </h3>
                  <p class="mt-1 text-xs text-gray-500">
                    {{ t('cloudBilling.billing.overviewCostTrendHint') }}
                  </p>
                </div>
                <div class="flex items-center gap-3">
                  <div
                    class="flex rounded-lg border border-gray-200 bg-gray-50 p-1"
                  >
                    <button
                      v-for="range in trendRanges"
                      :key="range"
                      class="rounded-md px-3 py-1.5 text-xs font-semibold transition-colors"
                      :class="
                        selectedTrendRange === range
                          ? 'bg-white text-gray-900 shadow-sm'
                          : 'text-gray-500 hover:text-gray-700'
                      "
                      @click="selectedTrendRange = range"
                    >
                      {{
                        t(
                          `cloudBilling.billing.overviewTrendRange${capitalizeRange(range)}`
                        )
                      }}
                    </button>
                  </div>
                  <div
                    class="rounded-full bg-gray-100 px-3 py-1 text-[11px] font-semibold text-gray-500"
                  >
                    {{ t('cloudBilling.billing.overviewMixedCurrency') }}
                  </div>
                </div>
              </div>
              <div class="h-[320px]">
                <Line
                  v-if="trendChartData"
                  :key="trendChartRenderKey"
                  :data="trendChartData"
                  :options="trendChartOptions"
                />
              </div>
            </div>
          </div>

          <div>
            <div
              class="flex h-full flex-col rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
            >
              <div class="mb-5">
                <h3 class="text-sm font-semibold text-gray-900">
                  {{ t('cloudBilling.billing.overviewCurrencyDistribution') }}
                </h3>
              </div>
              <div class="mx-auto h-[200px] max-w-[220px]">
                <Doughnut
                  v-if="currencyChartData"
                  :data="currencyChartData"
                  :options="currencyChartOptions"
                />
              </div>
              <div class="mt-6 space-y-4">
                <div
                  v-for="item in overview.currency_breakdown"
                  :key="item.code"
                  class="space-y-2"
                >
                  <div class="flex items-center justify-between text-xs">
                    <div class="flex items-center gap-2">
                      <span
                        class="h-2.5 w-2.5 rounded-full"
                        :style="{ backgroundColor: item.color }"
                      />
                      <span class="font-medium text-gray-600"
                        >{{ item.code }} · {{ currencyDisplayName(item) }}</span
                      >
                    </div>
                    <span class="font-mono font-semibold text-gray-900">
                      {{ formatBreakdownValue(item) }}
                    </span>
                  </div>
                  <div class="h-1.5 overflow-hidden rounded-full bg-gray-100">
                    <div
                      class="h-full rounded-full"
                      :style="{
                        width: `${item.percentage}%`,
                        backgroundColor: item.color
                      }"
                    />
                  </div>
                </div>
              </div>
              <div
                class="mt-6 rounded-lg border border-primary-100 bg-primary-50 p-4"
              >
                <div class="flex items-start gap-3">
                  <svg
                    class="mt-0.5 h-4 w-4 text-primary-600"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12A9 9 0 103 12a9 9 0 0018 0z"
                    />
                  </svg>
                  <div class="min-w-0 flex-1">
                    <div class="text-xs font-semibold text-primary-900">
                      {{ t('cloudBilling.billing.overviewExchangeRate') }}
                    </div>
                    <div class="mt-1 text-[11px] leading-5 text-primary-700">
                      1 USD = {{ overview.exchange_rate }} CNY
                    </div>
                    <div
                      class="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-primary-100 pt-3 text-[11px]"
                    >
                      <span class="text-primary-600">{{
                        overview.rate_source_label
                      }}</span>
                      <span class="font-mono font-medium text-primary-800">{{
                        formatTime(overview.rate_collected_at)
                      }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div
          class="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between"
        >
          <div class="flex flex-wrap items-center gap-4">
            <div>
              <h3 class="text-sm font-semibold text-gray-900">
                {{ t('cloudBilling.billing.overviewFinancialHealth') }}
              </h3>
              <p class="mt-1 text-xs text-gray-500">
                {{ t('cloudBilling.billing.overviewFinancialHealthHint') }}
              </p>
            </div>
            <div class="hidden h-4 w-px bg-gray-200 md:block" />
            <div class="text-xs text-gray-500">
              {{ t('cloudBilling.billing.overviewTotalFunds') }}
              <span class="ml-1 font-mono font-semibold text-emerald-600">{{
                formatConvertedValue(convertedTotalFunds)
              }}</span>
            </div>
            <div class="text-xs text-gray-500">
              {{ t('cloudBilling.billing.overviewMinDays') }}
              <span
                class="ml-1 rounded-full px-2 py-0.5 font-mono font-semibold"
                :class="
                  overview.financial_health.total_days == null
                    ? 'bg-zinc-100 text-zinc-500'
                    : overview.financial_health.total_days < 10
                      ? 'bg-red-100 text-red-700'
                      : 'bg-green-100 text-green-700'
                "
              >
                {{
                  overview.financial_health.total_days == null
                    ? t('cloudBilling.billing.overviewDaysReferenceUnavailable')
                    : `${overview.financial_health.total_days}${t(
                        'cloudBilling.billing.overviewDaysUnit'
                      )}`
                }}
              </span>
            </div>
          </div>
          <div
            v-if="overview.financial_health.bottleneck"
            class="inline-flex items-center gap-2 rounded-full border border-red-100 bg-red-50 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-red-700"
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
                d="M12 9v2m0 4h.01m-7.938 4h15.876c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L2.33 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            {{ t('cloudBilling.billing.overviewBottleneck') }}:
            {{ overview.financial_health.bottleneck }}
          </div>
        </div>

        <div class="flex flex-col gap-8">
          <div class="grid items-stretch gap-8 lg:grid-cols-12">
            <div
              class="flex h-full flex-col rounded-xl border border-gray-200 bg-gray-50 p-6 lg:col-span-8"
            >
              <div class="mb-6">
                <h4
                  class="text-xs font-bold uppercase tracking-[0.16em] text-gray-900"
                >
                  {{ t('cloudBilling.billing.overviewQuotaTrend') }}
                </h4>
                <p class="mt-1 text-[11px] text-gray-500">
                  {{ t('cloudBilling.billing.overviewQuotaTrendHint') }}
                </p>
              </div>
              <div class="h-[320px] flex-1">
                <Line
                  v-if="quotaTrendChartData"
                  :data="quotaTrendChartData"
                  :options="quotaTrendChartOptions"
                />
              </div>
            </div>

            <div
              class="flex h-full flex-col rounded-xl border border-gray-200 bg-gray-50 p-6 lg:col-span-4"
            >
              <div class="mb-5">
                <h4
                  class="text-xs font-bold uppercase tracking-[0.16em] text-gray-900"
                >
                  {{ t('cloudBilling.billing.overviewRechargeTimeline') }}
                </h4>
                <p class="mt-1 text-[11px] text-gray-500">
                  {{ t('cloudBilling.billing.overviewRechargeTimelineHint') }}
                </p>
              </div>
              <div class="mb-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  class="rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors"
                  :class="
                    selectedRechargeTag === ''
                      ? 'border-primary-200 bg-primary-50 text-primary-700'
                      : 'border-gray-200 bg-white text-gray-500 hover:border-gray-300 hover:text-gray-700'
                  "
                  @click="selectedRechargeTag = ''"
                >
                  {{ t('cloudBilling.billing.overviewAllTags') }}
                </button>
                <button
                  v-for="tag in rechargeTimelineTags"
                  :key="tag"
                  type="button"
                  class="rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors"
                  :class="
                    selectedRechargeTag === tag
                      ? 'border-primary-200 bg-primary-50 text-primary-700'
                      : 'border-gray-200 bg-white text-gray-500 hover:border-gray-300 hover:text-gray-700'
                  "
                  @click="selectedRechargeTag = tag"
                >
                  {{ tag }}
                </button>
              </div>
              <div
                v-if="visibleRechargeAlerts.length"
                class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto pr-1"
              >
                <div
                  v-for="item in visibleRechargeAlerts"
                  :key="`${item.name}-${item.account_id || 'default'}`"
                  class="space-y-2"
                >
                  <div class="flex items-start justify-between gap-3 text-xs">
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center gap-2">
                        <span
                          class="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase"
                          :class="
                            item.category === 'LLM'
                              ? 'bg-gray-200 text-gray-700'
                              : 'bg-primary-100 text-primary-700'
                          "
                        >
                          {{ item.category }}
                        </span>
                        <span class="truncate font-medium text-gray-700">{{
                          rechargeProviderLabel(item)
                        }}</span>
                      </div>
                      <div
                        class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-gray-500"
                      >
                        <span class="font-mono text-gray-600">
                          {{
                            item.account_id ||
                            t('cloudBilling.billing.defaultAccount')
                          }}
                        </span>
                        <span
                          v-for="tag in item.tags || []"
                          :key="`${item.account_id || item.name}-${tag}`"
                          class="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-gray-500 ring-1 ring-inset ring-gray-200"
                        >
                          {{ tag }}
                        </span>
                      </div>
                    </div>
                    <div class="flex shrink-0 items-center gap-1.5">
                      <span
                        class="font-mono text-sm font-semibold"
                        :class="riskTextClass(daysRemainingRisk(item))"
                      >
                        {{
                          displayDaysRemaining(
                            item,
                            'cloudBilling.billing.overviewDaysShort'
                          )
                        }}
                      </span>
                      <button
                        type="button"
                        :disabled="
                          !item.recharge_info_configured ||
                          submittingRechargeKey === rechargeAlertKey(item)
                        "
                        :title="
                          item.recharge_info_configured
                            ? t('cloudBilling.billing.submitRechargeApproval')
                            : t(
                                'cloudBilling.billing.rechargeApprovalConfigureHint'
                              )
                        "
                        class="inline-flex h-6 items-center gap-0.5 whitespace-nowrap rounded-md border px-1.5 py-0 text-[11px] font-semibold leading-none outline-none transition-colors focus-visible:ring-1 focus-visible:ring-primary-300 disabled:cursor-not-allowed"
                        :class="
                          item.recharge_info_configured
                            ? 'border-primary-200 bg-primary-50 text-primary-700 hover:bg-primary-100'
                            : 'border-gray-200 bg-gray-50 text-gray-400'
                        "
                        @click="openRechargeSubmitDialog(item)"
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
                            d="M12 6v12m6-6H6"
                          />
                        </svg>
                        <span
                          v-if="
                            submittingRechargeKey !== rechargeAlertKey(item)
                          "
                        >
                          {{ t('cloudBilling.billing.submitRechargeApproval') }}
                        </span>
                        <span
                          v-else
                          class="h-3 w-3 animate-spin rounded-full border border-current border-t-transparent"
                        />
                      </button>
                    </div>
                  </div>
                  <div class="h-1.5 overflow-hidden rounded-full bg-gray-200">
                    <div
                      class="h-full rounded-full"
                      :class="riskBarClass(daysRemainingRisk(item))"
                      :style="{
                        width: hasDaysRemainingReference(item)
                          ? `${Math.min(100, item.days_remaining)}%`
                          : '0%'
                      }"
                    />
                  </div>
                </div>
              </div>
              <div
                v-else
                class="flex flex-1 items-center justify-center rounded-xl border border-dashed border-gray-200 bg-white/70 px-4 text-center text-xs text-gray-500"
              >
                {{ t('cloudBilling.billing.overviewNoRechargeAlerts') }}
              </div>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-2">
            <div class="rounded-xl border border-zinc-200 bg-zinc-50/60 p-4">
              <div class="mb-3 flex items-center justify-between">
                <h4
                  class="text-[11px] font-bold uppercase tracking-[0.18em] text-zinc-400"
                >
                  {{ t('cloudBilling.billing.overviewPrepaidAccounts') }}
                </h4>
                <span class="text-[11px] font-mono text-zinc-400">{{
                  prepaidAccounts.length
                }}</span>
              </div>
              <div class="grid gap-3 sm:grid-cols-2">
                <article
                  v-for="account in visiblePrepaidAccounts"
                  :key="account.id"
                  class="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="flex min-w-0 items-start gap-3">
                      <div
                        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-zinc-200 bg-white p-2 shadow-sm"
                      >
                        <img
                          v-if="providerIcon(account)"
                          :src="providerIcon(account)"
                          :alt="localizedProviderLabel(account)"
                          class="h-full w-full object-contain"
                        />
                        <div v-else class="text-[11px] font-bold text-zinc-500">
                          {{ providerFallbackLetter(account) }}
                        </div>
                      </div>
                      <div class="min-w-0">
                        <div class="flex items-center gap-2">
                          <h5
                            class="truncate text-sm font-semibold text-zinc-900"
                          >
                            {{ localizedAccountName(account) }}
                          </h5>
                          <span
                            class="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase"
                            :class="
                              account.category === 'LLM'
                                ? 'bg-purple-100 text-purple-700'
                                : 'bg-blue-100 text-blue-700'
                            "
                          >
                            {{ account.category }}
                          </span>
                        </div>
                        <p
                          v-if="showProviderLabel(account)"
                          class="mt-1 truncate text-[11px] text-zinc-500"
                        >
                          {{ localizedProviderLabel(account) }}
                        </p>
                        <p
                          v-if="account.notes"
                          class="mt-1 truncate text-xs font-medium text-zinc-600"
                        >
                          {{ account.notes }}
                        </p>
                      </div>
                    </div>
                    <span
                      class="h-2.5 w-2.5 rounded-full"
                      :class="riskDotClass(daysRemainingRisk(account))"
                    />
                  </div>
                  <div
                    class="mt-3 grid grid-cols-2 gap-3 rounded-xl bg-zinc-50 px-3 py-2.5"
                  >
                    <div class="min-w-0">
                      <div class="text-[11px] text-zinc-500">
                        {{ t('cloudBilling.billing.balance') }}
                      </div>
                      <div
                        class="mt-0.5 truncate font-mono text-sm font-semibold text-zinc-900"
                      >
                        {{
                          formatAccountValue(
                            account.balance,
                            account.balance_currency
                          )
                        }}
                      </div>
                    </div>
                    <div class="min-w-0 text-right">
                      <div class="text-[11px] text-zinc-500">
                        {{ t('cloudBilling.billing.overviewDaysRemaining') }}
                      </div>
                      <div
                        class="mt-0.5 font-mono text-sm font-semibold"
                        :class="riskTextClass(daysRemainingRisk(account))"
                      >
                        {{
                          displayDaysRemaining(
                            account,
                            'cloudBilling.billing.overviewDaysShort'
                          )
                        }}
                      </div>
                    </div>
                  </div>
                </article>
              </div>
              <div
                v-if="prepaidAccounts.length > accountCardInitialLimit"
                class="mt-4 flex justify-center"
              >
                <button
                  type="button"
                  class="inline-flex items-center rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-600 transition-colors hover:bg-zinc-100"
                  @click="showAllPrepaid = !showAllPrepaid"
                >
                  {{
                    showAllPrepaid ? t('common.collapse') : t('common.viewMore')
                  }}
                </button>
              </div>
            </div>

            <div class="rounded-xl border border-zinc-200 bg-zinc-50/60 p-4">
              <div class="mb-3 flex items-center justify-between">
                <h4
                  class="text-[11px] font-bold uppercase tracking-[0.18em] text-zinc-400"
                >
                  {{ t('cloudBilling.billing.overviewPostpaidAccounts') }}
                </h4>
                <span class="text-[11px] font-mono text-zinc-400">{{
                  postpaidAccounts.length
                }}</span>
              </div>
              <div class="grid gap-3 sm:grid-cols-2">
                <article
                  v-for="account in visiblePostpaidAccounts"
                  :key="account.id"
                  class="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="flex min-w-0 items-start gap-3">
                      <div
                        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-zinc-200 bg-white p-2 shadow-sm"
                      >
                        <img
                          v-if="providerIcon(account)"
                          :src="providerIcon(account)"
                          :alt="localizedProviderLabel(account)"
                          class="h-full w-full object-contain"
                        />
                        <div v-else class="text-[11px] font-bold text-zinc-500">
                          {{ providerFallbackLetter(account) }}
                        </div>
                      </div>
                      <div class="min-w-0">
                        <div class="flex items-center gap-2">
                          <h5
                            class="truncate text-sm font-semibold text-zinc-900"
                          >
                            {{ localizedAccountName(account) }}
                          </h5>
                          <span
                            class="rounded bg-zinc-100 px-1.5 py-0.5 text-[9px] font-bold uppercase text-zinc-700"
                          >
                            {{ account.category }}
                          </span>
                        </div>
                        <p
                          v-if="showProviderLabel(account)"
                          class="mt-1 truncate text-[11px] text-zinc-500"
                        >
                          {{ localizedProviderLabel(account) }}
                        </p>
                        <p
                          v-if="account.notes"
                          class="mt-1 truncate text-xs font-medium text-zinc-600"
                        >
                          {{ account.notes }}
                        </p>
                      </div>
                    </div>
                    <span
                      class="h-2.5 w-2.5 rounded-full"
                      :class="riskDotClass(daysRemainingRisk(account))"
                    />
                  </div>
                  <div
                    class="mt-3 grid grid-cols-2 gap-3 rounded-xl bg-zinc-50 px-3 py-2.5"
                  >
                    <div class="min-w-0">
                      <div class="text-[11px] text-zinc-500">
                        {{ t('cloudBilling.billing.cost') }}
                      </div>
                      <div
                        class="mt-0.5 truncate font-mono text-sm font-semibold text-zinc-900"
                      >
                        {{ formatValue(account.cost, account.cost_currency) }}
                      </div>
                    </div>
                    <div class="min-w-0 text-right">
                      <div class="text-[11px] text-zinc-500">
                        {{ t('cloudBilling.billing.overviewDaysRemaining') }}
                      </div>
                      <div
                        class="mt-0.5 font-mono text-sm font-semibold"
                        :class="riskTextClass(daysRemainingRisk(account))"
                      >
                        {{
                          displayDaysRemaining(
                            account,
                            'cloudBilling.billing.overviewDaysShort'
                          )
                        }}
                      </div>
                    </div>
                  </div>
                </article>
              </div>
              <div
                v-if="postpaidAccounts.length > accountCardInitialLimit"
                class="mt-4 flex justify-center"
              >
                <button
                  type="button"
                  class="inline-flex items-center rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-600 transition-colors hover:bg-zinc-100"
                  @click="showAllPostpaid = !showAllPostpaid"
                >
                  {{
                    showAllPostpaid
                      ? t('common.collapse')
                      : t('common.viewMore')
                  }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section
        class="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm"
      >
        <div
          class="flex flex-col gap-4 border-b border-zinc-200 p-6 lg:flex-row lg:items-center lg:justify-between"
        >
          <div class="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div>
              <h3 class="text-sm font-semibold text-zinc-900">
                {{ t('cloudBilling.billing.overviewAccountDetails') }}
              </h3>
              <p class="mt-1 text-xs text-zinc-500">
                {{ t('cloudBilling.billing.overviewAccountDetailsHint') }}
              </p>
            </div>
            <div class="relative">
              <svg
                class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M21 21l-4.35-4.35M10.5 18a7.5 7.5 0 100-15 7.5 7.5 0 000 15z"
                />
              </svg>
              <input
                v-model="searchQuery"
                type="text"
                :placeholder="
                  t('cloudBilling.billing.overviewSearchPlaceholder')
                "
                class="w-full rounded-xl border border-zinc-200 bg-zinc-50 py-2 pl-9 pr-3 text-sm text-zinc-700 outline-none transition-colors focus:border-blue-300 lg:w-72"
              />
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-xl border border-zinc-200 bg-white px-3 py-2 text-xs font-semibold text-zinc-500 transition-colors hover:bg-zinc-50"
              @click="exportAccountsCsv"
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
                  d="M12 3v12m0 0 4-4m-4 4-4-4M4 17v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1"
                />
              </svg>
              {{ t('common.export') }} CSV
            </button>
            <button
              type="button"
              class="inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold transition-colors"
              :class="
                groupByProvider
                  ? 'border-blue-200 bg-blue-50 text-blue-700'
                  : 'border-zinc-200 bg-white text-zinc-500 hover:bg-zinc-50'
              "
              @click="groupByProvider = !groupByProvider"
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
                  d="M4 6h7M4 12h16M4 18h12"
                />
              </svg>
              {{ t('cloudBilling.billing.overviewGroupByProvider') }}
            </button>
          </div>
        </div>

        <div class="overflow-x-auto">
          <table class="min-w-full divide-y divide-zinc-200">
            <thead class="bg-zinc-50">
              <tr>
                <th class="table-head">
                  {{ t('cloudBilling.billing.provider') }}
                </th>
                <th class="table-head">{{ t('cloudBilling.billing.cost') }}</th>
                <th class="table-head">
                  {{ t('cloudBilling.billing.overviewBalanceQuota') }}
                </th>
                <th class="table-head">
                  {{ t('cloudBilling.billing.overviewDaysRemaining') }}
                </th>
                <th class="table-head">
                  {{ t('cloudBilling.billing.overviewRiskStatus') }}
                </th>
                <th class="table-head">
                  {{ t('cloudBilling.billing.overviewTrendMini') }}
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-zinc-100">
              <template v-for="group in groupedRows" :key="group.name">
                <tr
                  v-if="groupByProvider"
                  class="cursor-pointer bg-zinc-50/70 transition-colors hover:bg-zinc-50"
                  @click="toggleProvider(group.name)"
                >
                  <td colspan="6" class="px-6 py-3">
                    <div class="flex items-center justify-between gap-4">
                      <div class="flex items-center gap-2">
                        <svg
                          class="h-4 w-4 text-zinc-400 transition-transform"
                          :class="
                            expandedProviders[group.name] === false
                              ? '-rotate-90'
                              : 'rotate-0'
                          "
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            stroke-width="2"
                            d="M19 9l-7 7-7-7"
                          />
                        </svg>
                        <span
                          class="text-[11px] font-bold uppercase tracking-[0.18em] text-zinc-500"
                        >
                          {{ group.name }} ({{ group.rows.length }})
                        </span>
                      </div>
                      <div class="flex items-center gap-6 text-[11px]">
                        <span class="text-zinc-500">
                          {{ t('cloudBilling.billing.overviewGroupCost') }}
                          <span
                            class="ml-1 font-mono font-semibold text-zinc-700"
                            >{{ formatValue(group.totalCost) }}</span
                          >
                        </span>
                        <span class="text-zinc-500">
                          {{ t('cloudBilling.billing.overviewGroupBalance') }}
                          <span
                            class="ml-1 font-mono font-semibold text-emerald-600"
                            >{{
                              formatConvertedValue(group.totalBalance)
                            }}</span
                          >
                        </span>
                      </div>
                    </div>
                  </td>
                </tr>
                <tr
                  v-for="account in visibleGroupRows(group)"
                  :key="account.id"
                  class="cursor-pointer transition-colors hover:bg-zinc-50/60"
                  @click="openAccountDrawer(account)"
                >
                  <td class="px-6 py-4">
                    <div class="flex items-center gap-3">
                      <div
                        class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-zinc-200 bg-white p-2 shadow-sm"
                      >
                        <img
                          v-if="providerIcon(account)"
                          :src="providerIcon(account)"
                          :alt="localizedProviderLabel(account)"
                          class="h-full w-full object-contain"
                        />
                        <div v-else class="text-[11px] font-bold text-zinc-500">
                          {{ providerFallbackLetter(account) }}
                        </div>
                      </div>
                      <div class="min-w-0">
                        <div class="flex items-center gap-2">
                          <div
                            class="truncate text-sm font-semibold text-zinc-900"
                          >
                            {{ localizedAccountName(account) }}
                          </div>
                          <span
                            class="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase"
                            :class="
                              account.category === 'LLM'
                                ? 'bg-purple-100 text-purple-700'
                                : 'bg-blue-100 text-blue-700'
                            "
                          >
                            {{ account.category }}
                          </span>
                          <span
                            class="rounded bg-zinc-100 px-1.5 py-0.5 text-[9px] font-bold uppercase text-zinc-600"
                          >
                            {{ paymentTypeLabel(account.type) }}
                          </span>
                          <span
                            v-for="tag in account.tags || []"
                            :key="`${account.id}-${tag}`"
                            class="inline-flex items-center rounded-full border border-primary-100 bg-primary-50 px-2 py-0.5 text-[9px] font-medium text-primary-700"
                          >
                            {{ tag }}
                          </span>
                        </div>
                        <div
                          v-if="showProviderLabel(account)"
                          class="mt-1 truncate text-[11px] text-zinc-500"
                        >
                          {{ localizedProviderLabel(account) }}
                        </div>
                        <div
                          v-if="account.notes"
                          class="mt-1 truncate text-xs font-medium text-zinc-600"
                        >
                          {{ account.notes }}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td class="px-6 py-4">
                    <div class="font-mono text-sm font-semibold text-zinc-800">
                      {{ formatValue(account.cost, account.cost_currency) }}
                    </div>
                  </td>
                  <td class="px-6 py-4">
                    <div class="space-y-3 text-xs">
                      <div
                        v-if="showBalance(account)"
                        class="rounded-lg bg-zinc-50 px-3 py-2"
                      >
                        <div class="text-zinc-400">
                          {{ t('cloudBilling.billing.balance') }}
                        </div>
                        <div
                          class="mt-1 font-mono text-sm font-semibold text-zinc-800"
                        >
                          {{
                            formatAccountValue(
                              account.balance,
                              account.balance_currency
                            )
                          }}
                        </div>
                      </div>
                      <div
                        v-if="account.credit_limit"
                        class="rounded-lg bg-zinc-50 px-3 py-2"
                      >
                        <div class="text-zinc-400">
                          {{ t('cloudBilling.billing.overviewCreditLimit') }}
                        </div>
                        <div
                          class="mt-1 font-mono text-sm font-semibold text-zinc-500"
                        >
                          {{
                            formatAccountValue(
                              account.credit_limit,
                              account.credit_limit_currency
                            )
                          }}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td class="px-6 py-4">
                    <div
                      class="font-mono text-sm font-semibold"
                      :class="riskTextClass(daysRemainingRisk(account))"
                    >
                      {{ displayDaysRemaining(account) }}
                    </div>
                  </td>
                  <td class="px-6 py-4">
                    <span
                      class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em]"
                      :class="riskBadgeClass(daysRemainingRisk(account))"
                    >
                      <span
                        class="h-1.5 w-1.5 rounded-full"
                        :class="riskDotClass(daysRemainingRisk(account))"
                      />
                      {{ riskLabel(daysRemainingRisk(account)) }}
                    </span>
                  </td>
                  <td class="px-6 py-4">
                    <svg viewBox="0 0 100 32" class="h-8 w-24 overflow-visible">
                      <polyline
                        fill="none"
                        :stroke="
                          daysRemainingRisk(account) === 'high'
                            ? '#e11d48'
                            : daysRemainingRisk(account) === 'medium'
                              ? '#f59e0b'
                              : daysRemainingRisk(account) === 'unknown'
                                ? '#a1a1aa'
                                : '#10b981'
                        "
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        :points="sparklinePoints(account.trend)"
                      />
                    </svg>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>

      <Teleport to="body">
        <div
          v-if="selectedAccount"
          class="fixed inset-0 z-50 flex justify-end bg-zinc-950/35 backdrop-blur-[1px]"
          @click="closeAccountDrawer"
        >
          <aside
            class="flex h-full w-full max-w-[840px] flex-col overflow-hidden bg-white shadow-2xl"
            @click.stop
          >
            <div
              class="flex items-start justify-between border-b border-zinc-200 px-6 py-5"
            >
              <div class="min-w-0">
                <div class="text-sm font-semibold text-primary-600">
                  {{ localizedProviderLabel(selectedAccount) }}
                </div>
                <h3
                  class="mt-1.5 truncate text-3xl font-semibold tracking-tight text-zinc-900"
                >
                  {{
                    selectedAccount.account_id ||
                    localizedAccountName(selectedAccount)
                  }}
                </h3>
                <div
                  class="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-zinc-500"
                >
                  <span
                    class="rounded-full bg-zinc-100 px-2.5 py-1 font-semibold text-zinc-700"
                  >
                    {{ paymentTypeLabel(selectedAccount.type) }}
                  </span>
                  <span
                    v-for="tag in selectedAccount.tags || []"
                    :key="`drawer-inline-tag-${selectedAccount.id}-${tag}`"
                    class="inline-flex items-center rounded-full border border-primary-100 bg-primary-50 px-2.5 py-1 font-semibold text-primary-700"
                  >
                    {{ tag }}
                  </span>
                  <span
                    class="rounded-full px-2.5 py-1 font-semibold"
                    :class="
                      recommendationBadgeClass(
                        recommendationStatus(
                          selectedAccount,
                          selectedAccountDetail
                        )
                      )
                    "
                  >
                    {{
                      recommendationLabel(
                        recommendationStatus(
                          selectedAccount,
                          selectedAccountDetail
                        )
                      )
                    }}
                  </span>
                  <span v-if="selectedAccount.notes" class="truncate">
                    {{ selectedAccount.notes }}
                  </span>
                </div>
              </div>
              <button
                type="button"
                class="rounded-full p-2 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-600"
                @click="closeAccountDrawer"
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

            <div class="flex-1 overflow-y-auto px-6 py-5">
              <div
                class="rounded-2xl border border-blue-100 bg-gradient-to-r from-blue-50 via-blue-50 to-emerald-50/70 p-5"
              >
                <div class="flex items-start gap-3">
                  <div
                    class="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-600/20"
                  >
                    <svg
                      class="h-5.5 w-5.5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M13 10V3L4 14h7v7l9-11h-7z"
                      />
                    </svg>
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-3">
                      <h4
                        class="text-xl font-semibold tracking-tight text-zinc-900"
                      >
                        {{
                          t('cloudBilling.billing.accountDrawerRecommendation')
                        }}
                      </h4>
                      <span
                        class="rounded-full px-2.5 py-1 text-[11px] font-semibold"
                        :class="
                          recommendationBadgeClass(
                            recommendationStatus(
                              selectedAccount,
                              selectedAccountDetail
                            )
                          )
                        "
                      >
                        {{
                          recommendationLabel(
                            recommendationStatus(
                              selectedAccount,
                              selectedAccountDetail
                            )
                          )
                        }}
                      </span>
                    </div>
                    <p class="mt-2 max-w-3xl text-sm leading-7 text-blue-700">
                      {{ recommendationMessage }}
                    </p>
                  </div>
                </div>
              </div>

              <div class="mt-5 grid gap-3 md:grid-cols-4">
                <article
                  class="rounded-2xl border border-zinc-200 bg-zinc-50 px-4 py-4"
                >
                  <div class="text-xs text-zinc-400">
                    {{ t('cloudBilling.billing.accountDrawerDailyAverage') }}
                  </div>
                  <div
                    class="mt-2 text-2xl font-semibold tracking-tight text-zinc-900"
                  >
                    {{
                      formatAccountValue(
                        selectedAccountDetail.daily_average,
                        selectedAccountDetail.service_breakdown_currency
                      )
                    }}
                  </div>
                </article>
                <article
                  class="rounded-2xl border border-zinc-200 bg-zinc-50 px-4 py-4"
                >
                  <div class="text-xs text-zinc-400">
                    {{ t('cloudBilling.billing.accountDrawerDailyPeak') }}
                  </div>
                  <div
                    class="mt-2 text-2xl font-semibold tracking-tight text-zinc-900"
                  >
                    {{
                      formatAccountValue(
                        selectedAccountDetail.daily_peak,
                        selectedAccountDetail.service_breakdown_currency
                      )
                    }}
                  </div>
                </article>
                <article
                  class="rounded-2xl border border-zinc-200 bg-zinc-50 px-4 py-4"
                >
                  <div class="text-xs text-zinc-400">
                    {{ t('cloudBilling.billing.accountDrawerPrimaryShare') }}
                  </div>
                  <div
                    class="mt-2 text-2xl font-semibold tracking-tight text-blue-600"
                  >
                    {{
                      formatPercent(selectedAccountDetail.primary_service_share)
                    }}
                  </div>
                  <div class="mt-1 truncate text-[11px] text-zinc-500">
                    {{ selectedAccountDetail.primary_service_name || '-' }}
                  </div>
                </article>
                <article
                  class="rounded-2xl border border-zinc-200 bg-zinc-50 px-4 py-4"
                >
                  <div class="text-xs text-zinc-400">
                    {{ t('cloudBilling.billing.accountDrawerServiceCount') }}
                  </div>
                  <div
                    class="mt-2 text-2xl font-semibold tracking-tight text-zinc-900"
                  >
                    {{ selectedAccountDetail.service_count ?? 0 }}
                  </div>
                </article>
              </div>

              <div
                class="mt-5 rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm"
              >
                <div class="mb-4 flex items-center justify-between gap-3">
                  <div class="flex items-center gap-3">
                    <div class="rounded-2xl bg-blue-50 p-2.5 text-blue-600">
                      <svg
                        class="h-4.5 w-4.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M3 17l6-6 4 4 8-8M3 7v10h18"
                        />
                      </svg>
                    </div>
                    <div>
                      <h4
                        class="text-xl font-semibold tracking-tight text-zinc-900"
                      >
                        {{ t('cloudBilling.billing.accountDrawerTrendTitle') }}
                      </h4>
                    </div>
                  </div>
                  <div
                    class="text-[11px] font-semibold uppercase tracking-[0.14em] text-zinc-400"
                  >
                    {{
                      t('cloudBilling.billing.accountDrawerCurrencyUnit', {
                        currency: selectedCurrency
                      })
                    }}
                  </div>
                </div>
                <div class="h-[300px]">
                  <Line
                    v-if="accountDetailChartData"
                    :data="accountDetailChartData"
                    :options="accountDetailChartOptions"
                  />
                </div>
              </div>

              <div
                v-if="selectedAccountDetail.service_breakdown?.length"
                class="mt-5 rounded-3xl border border-zinc-200 bg-zinc-50/70 p-5"
              >
                <div class="mb-3 text-sm font-semibold text-zinc-900">
                  {{ t('cloudBilling.billing.accountDrawerServiceBreakdown') }}
                </div>
                <div
                  v-if="serviceBreakdownHint"
                  class="mb-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-6 text-amber-700"
                >
                  {{ serviceBreakdownHint }}
                </div>
                <div class="space-y-2.5">
                  <div
                    v-for="item in selectedAccountDetail.service_breakdown"
                    :key="`${selectedAccount.id}-${item.name}`"
                    class="rounded-2xl border border-zinc-200 bg-white px-4 py-2.5"
                  >
                    <div
                      class="flex items-center justify-between gap-4 text-sm"
                    >
                      <div class="truncate font-medium text-zinc-700">
                        {{ displayServiceName(item.name) }}
                      </div>
                      <div class="flex items-center gap-3 text-right">
                        <div
                          class="font-mono text-[11px] font-semibold text-zinc-500"
                        >
                          {{
                            formatAccountValue(
                              item.value,
                              selectedAccountDetail.service_breakdown_currency
                            )
                          }}
                        </div>
                        <div class="font-mono font-semibold text-zinc-900">
                          {{ formatPercent(item.percentage) }}
                        </div>
                      </div>
                    </div>
                    <div
                      class="mt-2 h-2 overflow-hidden rounded-full bg-zinc-100"
                    >
                      <div
                        class="h-full rounded-full bg-blue-500"
                        :style="{
                          width: `${Math.min(item.percentage || 0, 100)}%`
                        }"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </aside>
        </div>
      </Teleport>

      <BaseModal
        :show="showRechargeSubmitDialog"
        :title="t('cloudBilling.billing.rechargeApprovalModalTitle')"
        @close="closeRechargeSubmitDialog"
      >
        <div class="space-y-4">
          <div class="rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
            <p class="text-sm font-semibold text-gray-900">
              {{ rechargeProviderLabel(rechargeSubmitTarget || {}) }}
            </p>
            <p class="mt-1 text-xs text-gray-500">
              {{
                (rechargeSubmitTarget && rechargeSubmitTarget.account_id) ||
                t('cloudBilling.billing.defaultAccount')
              }}
            </p>
          </div>

          <div class="space-y-2">
            <label class="block text-sm font-medium text-gray-700">
              {{ t('cloudBilling.providers.rechargeInfo') }}
            </label>
            <textarea
              :value="rechargeSubmitForm.recharge_info_text"
              disabled
              rows="8"
              :placeholder="
                t('cloudBilling.billing.rechargeApprovalConfigureHint')
              "
              class="block w-full cursor-not-allowed rounded-md border border-gray-200 bg-gray-100 px-3 py-2 text-sm font-mono text-gray-500 resize-none"
              style="height: 290px"
            />
            <p class="text-xs text-gray-500">
              {{ t('cloudBilling.billing.rechargeApprovalConfigureHint') }}
            </p>
          </div>

          <div class="space-y-2">
            <label class="block text-sm font-medium text-gray-700">
              {{ t('cloudBilling.billing.rechargeApprovalSubmitter') }}
            </label>
            <input
              v-model="rechargeSubmitForm.submitter_identifier"
              type="text"
              :placeholder="
                t('cloudBilling.billing.rechargeApprovalSubmitterPlaceholder')
              "
              class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <p class="text-xs text-gray-500">
              {{ t('cloudBilling.billing.rechargeApprovalSubmitterHint') }}
            </p>
          </div>

          <div class="space-y-2">
            <label class="block text-sm font-medium text-gray-700">
              {{ t('cloudBilling.billing.rechargeApprovalPaymentNote') }}
            </label>
            <textarea
              v-model="rechargeSubmitForm.payment_note"
              rows="3"
              :placeholder="
                t('cloudBilling.billing.rechargeApprovalPaymentNotePlaceholder')
              "
              class="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <p class="text-xs text-gray-500">
              {{ t('cloudBilling.billing.rechargeApprovalPaymentNoteHint') }}
            </p>
          </div>

          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-sm font-medium text-gray-700">
                {{ t('cloudBilling.billing.rechargeApprovalAmount') }}
              </label>
              <input
                v-model="rechargeSubmitForm.amount"
                type="number"
                min="0"
                step="0.01"
                :placeholder="
                  t('cloudBilling.billing.rechargeApprovalAmountPlaceholder')
                "
                class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <p
                v-if="rechargeSubmitTarget?.recommended_recharge"
                class="mt-1 text-xs text-gray-400"
              >
                {{ t('cloudBilling.billing.rechargeApprovalAmountHint') }}：
                <span class="font-medium text-primary-600">
                  {{ rechargeSubmitTarget.recommended_recharge }}
                  {{
                    rechargeSubmitTarget.recommendation_currency ||
                    selectedCurrency
                  }}
                </span>
              </p>
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-gray-700">
                {{ t('cloudBilling.billing.rechargeApprovalExpectedDate') }}
              </label>
              <input
                v-model="rechargeSubmitForm.expected_date"
                type="date"
                class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>
        </div>

        <template #footer>
          <div class="flex flex-col-reverse justify-end gap-3 sm:flex-row">
            <BaseButton variant="outline" @click="closeRechargeSubmitDialog">
              {{ t('common.cancel') }}
            </BaseButton>
            <BaseButton
              :loading="
                submittingRechargeKey ===
                rechargeAlertKey(rechargeSubmitTarget || {})
              "
              @click="submitRechargeApprovalFromDialog"
            >
              {{ t('cloudBilling.billing.rechargeApprovalSubmitButton') }}
            </BaseButton>
          </div>
        </template>
      </BaseModal>
    </template>
  </div>
</template>

<script setup>
import { computed, h, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Doughnut, Line } from 'vue-chartjs'
import {
  ArcElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip
} from 'chart.js'
import { cloudBillingApi } from '@/api/cloudBilling'
import alibabaCloudIcon from '@/assets/provider-icons/lobehub/alibabacloud.svg'
import awsIcon from '@/assets/provider-icons/lobehub/aws.svg'
import azureIcon from '@/assets/provider-icons/lobehub/azure.svg'
import baiduCloudIcon from '@/assets/provider-icons/lobehub/baiducloud.svg'
import huaweiCloudIcon from '@/assets/provider-icons/lobehub/huaweicloud.svg'
import tencentCloudIcon from '@/assets/provider-icons/lobehub/tencentcloud.svg'
import volcengineIcon from '@/assets/provider-icons/lobehub/volcengine.svg'
import zhipuIcon from '@/assets/provider-icons/lobehub/zhipu.svg'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import {
  OPERATIONS_CURRENCIES,
  OPERATIONS_DEFAULT_TIMEZONE,
  OPERATIONS_TIMEZONES
} from '@/constants/operationsView'
import {
  cloudBillingOverviewAccounts,
  cloudBillingOverviewCurrencyBreakdown,
  cloudBillingOverviewFinancialHealth,
  cloudBillingOverviewSummary
} from '@/mock/cloudBillingOverview'
import { extractErrorMessage, extractResponseData } from '@/utils/api'
import { getLocalizedProviderDisplayName } from '@/utils/providerDisplay'
import { useToast } from '@/composables/useToast'

const props = defineProps({
  showHeader: {
    type: Boolean,
    default: true
  },
  timezone: {
    type: String,
    default: ''
  },
  currency: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:timezone', 'update:currency'])

ChartJS.register(
  ArcElement,
  CategoryScale,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip
)

const createOverviewIcon = (pathDefinition) => ({
  render() {
    return h(
      'svg',
      {
        class: 'h-4 w-4',
        fill: 'none',
        stroke: 'currentColor',
        viewBox: '0 0 24 24'
      },
      [
        h('path', {
          'stroke-linecap': 'round',
          'stroke-linejoin': 'round',
          'stroke-width': '2',
          d: pathDefinition
        })
      ]
    )
  }
})

const OverviewBarChartIcon = createOverviewIcon('M8 13v7m4-12v12m4-8v8M6 20h12')
const OverviewClockIcon = createOverviewIcon(
  'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z'
)
const OverviewTrendIcon = createOverviewIcon('M3 17l6-6 4 4 8-8')
const OverviewPeakIcon = createOverviewIcon('M5 12l4 4L19 6')

const { t } = useI18n()
const { showSuccess, showError, showWarning } = useToast()

const loading = ref(false)
const overviewLoaded = ref(false)
const error = ref('')
const defaultCurrency = ref('CNY')
const searchQuery = ref('')
const groupByProvider = ref(true)
const expandedProviders = ref({})
const defaultTimezone = ref(OPERATIONS_DEFAULT_TIMEZONE)
const selectedTrendRange = ref('month')
const showAllPrepaid = ref(false)
const showAllPostpaid = ref(false)
const selectedRechargeTag = ref('')
const selectedAccount = ref(null)
const showRechargeSubmitDialog = ref(false)
const rechargeSubmitTarget = ref(null)
const submittingRechargeKey = ref('')
const rechargeSubmitForm = ref({
  recharge_info_text: '',
  submitter_identifier: '',
  payment_note: '',
  recharge_account: '',
  recharge_customer_name: '',
  payment_company: '',
  payment_way: '',
  payment_type: '',
  remit_method: '',
  amount: '',
  expected_date: ''
})
const accountCardInitialLimit = 4

const selectedCurrency = computed({
  get: () => props.currency || defaultCurrency.value,
  set: (value) => {
    defaultCurrency.value = value
    emit('update:currency', value)
  }
})

const selectedTimezone = computed({
  get: () => props.timezone || defaultTimezone.value,
  set: (value) => {
    defaultTimezone.value = value
    emit('update:timezone', value)
  }
})

const timezones = OPERATIONS_TIMEZONES
const currencies = OPERATIONS_CURRENCIES

const overview = ref(createFallbackOverview())

function createFallbackOverview() {
  return {
    summary: {
      estimated_total: cloudBillingOverviewSummary.estimatedTotal,
      current_consumed: cloudBillingOverviewSummary.currentConsumed,
      daily_average: cloudBillingOverviewSummary.dailyAverage,
      collected_days: cloudBillingOverviewSummary.collectedDays || 0,
      peak_cost: cloudBillingOverviewSummary.peakCost,
      peak_date: cloudBillingOverviewSummary.peakDate,
      trend: cloudBillingOverviewSummary.trend
    },
    currency_breakdown: cloudBillingOverviewCurrencyBreakdown,
    financial_health: {
      total_funds: cloudBillingOverviewFinancialHealth.totalFunds,
      total_days: cloudBillingOverviewFinancialHealth.totalDays,
      bottleneck: cloudBillingOverviewFinancialHealth.bottleneck,
      recharge_alerts: cloudBillingOverviewFinancialHealth.rechargeAlerts
    },
    accounts: cloudBillingOverviewAccounts.map((item) => ({
      id: item.id,
      provider_id: item.providerId || '',
      name: item.name,
      provider: item.provider,
      provider_type: item.providerType || '',
      notes: item.notes || '',
      tags: item.tags || [],
      category: item.category,
      cost: item.cost,
      cost_currency: item.costCurrency || 'CNY',
      percentage: item.percentage,
      change: item.change,
      risk: item.risk,
      balance: item.balance,
      balance_currency: item.balanceCurrency || '',
      credit_limit: item.creditLimit || null,
      credit_limit_currency: item.creditLimitCurrency || '',
      display_funds: item.displayFunds || item.creditLimit || item.balance,
      display_funds_currency:
        item.displayFundsCurrency ||
        item.creditLimitCurrency ||
        item.balanceCurrency ||
        '',
      days_remaining: item.daysRemaining,
      recent_collected_days: item.recentCollectedDays || 0,
      has_days_remaining_reference:
        item.hasDaysRemainingReference !== false &&
        Number(item.recentCollectedDays || 0) >= 7,
      type: item.type,
      usage_rate: item.usageRate || null,
      account_id: item.accountId || '',
      trend: item.trend,
      detail: item.detail || null
    })),
    exchange_rate: 7.15,
    rate_source_label: 'Internal baseline rate',
    rate_source_url: '',
    rate_collected_at: ''
  }
}

function currencyDisplayName(item) {
  const code = String(item?.code || '').toUpperCase()
  if (code === 'CNY') {
    return t('cloudBilling.billing.currencyCny')
  }
  if (code === 'USD') {
    return t('cloudBilling.billing.currencyUsd')
  }
  return item?.name || code
}

function getDatePartsInTimezone(timezone) {
  try {
    const formatter = new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    })
    const parts = formatter.formatToParts(new Date())
    const year = Number(parts.find((part) => part.type === 'year')?.value || 0)
    const month = Number(
      parts.find((part) => part.type === 'month')?.value || 0
    )
    const day = Number(parts.find((part) => part.type === 'day')?.value || 0)
    return { year, month, day }
  } catch {
    return { year: 0, month: 0, day: 0 }
  }
}

function getRemainingDaysInCurrentMonth(timezone) {
  const { year, month, day } = getDatePartsInTimezone(timezone)
  if (!year || !month || !day) {
    return 0
  }
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate()
  return Math.max(daysInMonth - day, 0)
}

function getTodayDateString(timezone) {
  const { year, month, day } = getDatePartsInTimezone(timezone)
  if (!year || !month || !day) {
    return ''
  }
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function addDaysToDateString(dateString, days) {
  if (!dateString) return ''
  const date = new Date(`${dateString}T00:00:00`)
  if (Number.isNaN(date.getTime())) return ''
  date.setDate(date.getDate() + Number(days || 0))
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function normalizeTrendCostCny(item) {
  const cnyValue = Number(item?.cny)
  const usdValue = Number(item?.usd)
  if (Number.isFinite(cnyValue) || Number.isFinite(usdValue)) {
    return (
      (Number.isFinite(cnyValue) ? cnyValue : 0) +
      convertCurrencyValue(
        Number.isFinite(usdValue) ? usdValue : 0,
        'USD',
        'CNY'
      )
    )
  }

  const normalizedCurrency = String(item?.currency || '').toUpperCase()

  const total = Number(item?.total)
  if (Number.isFinite(total)) {
    return convertCurrencyValue(total, normalizedCurrency || 'CNY', 'CNY')
  }

  const value = Number(item?.value)
  if (Number.isFinite(value)) {
    return convertCurrencyValue(value, normalizedCurrency || 'CNY', 'CNY')
  }
  return 0
}

function normalizeTrendDate(item, timezone) {
  const rawDate = String(item?.date || '').trim()
  if (!rawDate) {
    return ''
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(rawDate)) {
    return rawDate
  }
  if (/^\d{2}-\d{2}$/.test(rawDate)) {
    const { year } = getDatePartsInTimezone(timezone)
    if (year) {
      return `${year}-${rawDate}`
    }
  }
  return rawDate
}

function hasTrendCostData(item) {
  return (
    Number.isFinite(Number(item?.cny)) ||
    Number.isFinite(Number(item?.usd)) ||
    Number.isFinite(Number(item?.total)) ||
    Number.isFinite(Number(item?.value))
  )
}

const unifiedSummary = computed(() => {
  const baseSummary = overview.value.summary || {}
  const monthTrend =
    baseSummary?.trend_ranges?.month || baseSummary?.trend || []
  const today = getTodayDateString(selectedTimezone.value)
  const usableTrend = (monthTrend || []).filter((item) => {
    const date = String(item?.date || '')
    if (!date || !today) {
      return true
    }
    return date <= today
  })
  const recentTotalCost = usableTrend.reduce(
    (sum, item) => sum + normalizeTrendCostCny(item),
    0
  )
  const collectedDays = Number(baseSummary.collected_days || 0)
  const dailyAverage =
    collectedDays > 0
      ? recentTotalCost / collectedDays
      : Number(baseSummary.daily_average || 0)
  const currentConsumed = usableTrend.some((item) => hasTrendCostData(item))
    ? recentTotalCost
    : Number(baseSummary.current_consumed || 0)
  const remainingDays = getRemainingDaysInCurrentMonth(selectedTimezone.value)
  const estimatedTotal = currentConsumed + dailyAverage * remainingDays
  let peakCost = Number(baseSummary.peak_cost || 0)
  let peakDate = baseSummary.peak_date || '-'
  usableTrend.forEach((item) => {
    const cost = normalizeTrendCostCny(item)
    if (cost > peakCost) {
      peakCost = cost
      peakDate = normalizeTrendDate(item, selectedTimezone.value) || peakDate
    }
  })

  return {
    ...baseSummary,
    daily_average: dailyAverage,
    estimated_total: estimatedTotal,
    peak_cost: peakCost,
    peak_date: peakDate
  }
})

const summaryCards = computed(() => [
  {
    key: 'estimated',
    label: t('cloudBilling.billing.overviewEstimatedTotal'),
    value: formatValue(unifiedSummary.value.estimated_total),
    icon: OverviewBarChartIcon
  },
  {
    key: 'consumed',
    label: t('cloudBilling.billing.overviewConsumed'),
    value: formatValue(unifiedSummary.value.current_consumed),
    icon: OverviewClockIcon
  },
  {
    key: 'daily',
    label: t('cloudBilling.billing.overviewDailyAverage'),
    value: formatValue(unifiedSummary.value.daily_average),
    icon: OverviewTrendIcon
  },
  {
    key: 'peak',
    label: t('cloudBilling.billing.overviewPeakCost'),
    value: formatValue(unifiedSummary.value.peak_cost),
    subValue: `${t('cloudBilling.billing.overviewPeakDate')}: ${unifiedSummary.value.peak_date || '-'}`,
    icon: OverviewPeakIcon
  }
])

const trendRanges = ['today', 'week', 'thirtyDays', 'month', 'year']

const currentTrend = computed(() => {
  const trendRangesMap = overview.value.summary?.trend_ranges || {}
  return (
    trendRangesMap[selectedTrendRange.value] ||
    overview.value.summary?.trend ||
    []
  )
})

const exchangeRateValue = computed(() => {
  const rate = Number(overview.value.exchange_rate || 0)
  return rate > 0 ? rate : 7.15
})

function convertTrendTotal(item) {
  return convertAmountByCurrency(normalizeTrendCostCny(item), 'CNY')
}

const convertedTotalFunds = computed(() => {
  return sumUniqueProviderBalances(overview.value.accounts || [])
})

function formatConvertedValue(value) {
  return formatCurrencyByCode(value, selectedCurrency.value)
}

const trendChartData = computed(() => ({
  labels: currentTrend.value.map((item) => item.date),
  datasets: [
    {
      label: selectedCurrency.value,
      data: currentTrend.value.map((item) => convertTrendTotal(item)),
      borderColor: selectedCurrency.value === 'USD' ? '#6366f1' : '#10b981',
      backgroundColor:
        selectedCurrency.value === 'USD'
          ? 'rgba(99, 102, 241, 0.10)'
          : 'rgba(16, 185, 129, 0.10)',
      fill: true,
      tension: 0.36,
      pointRadius: 0
    }
  ]
}))

const trendChartRenderKey = computed(() => {
  const labels = currentTrend.value.map((item) => item.date).join('|')
  return `${selectedTrendRange.value}:${selectedCurrency.value}:${labels}`
})

const trendChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: {
      display: false,
      position: 'top',
      align: 'end',
      labels: {
        usePointStyle: true,
        boxWidth: 8,
        color: '#52525b'
      }
    },
    tooltip: {
      backgroundColor: '#ffffff',
      titleColor: '#18181b',
      bodyColor: '#3f3f46',
      borderColor: '#e4e4e7',
      borderWidth: 1,
      padding: 12,
      callbacks: {
        label: (context) =>
          `${context.dataset.label}: ${formatConvertedValue(context.parsed.y)}`
      }
    }
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { color: '#a1a1aa', maxTicksLimit: 10 }
    },
    y: {
      beginAtZero: true,
      grid: { color: '#f4f4f5' },
      ticks: {
        color: '#a1a1aa',
        callback: (value) => formatAxisTickValue(value)
      }
    }
  }
}))

const quotaTrendAccounts = computed(() =>
  [...(overview.value.accounts || [])]
    .sort(compareAccountsByAvailability)
    .slice(0, 5)
)

const quotaTrendLabels = computed(() => {
  const firstAccount = quotaTrendAccounts.value[0]
  return (firstAccount?.trend || []).map((item) => item.date)
})

const quotaTrendColors = ['#10b981', '#2563eb', '#f59e0b', '#ef4444', '#8b5cf6']

const quotaTrendChartData = computed(() => ({
  labels: quotaTrendLabels.value,
  datasets: quotaTrendAccounts.value.map((account, index) => ({
    label: quotaTrendAccountLabel(account),
    data: (account.trend || []).map((item) =>
      convertAmountByCurrency(
        Number(item.value || 0),
        account.display_funds_currency || account.balance_currency || 'CNY'
      )
    ),
    borderColor: quotaTrendColors[index % quotaTrendColors.length],
    backgroundColor: 'transparent',
    tension: 0.36,
    pointRadius: 0,
    pointHoverRadius: 4,
    borderWidth: 2
  }))
}))

const quotaTrendChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: {
      position: 'top',
      align: 'end',
      labels: {
        usePointStyle: true,
        boxWidth: 8,
        color: '#6b7280',
        font: {
          size: 10
        }
      }
    },
    tooltip: {
      backgroundColor: '#ffffff',
      titleColor: '#111827',
      bodyColor: '#374151',
      borderColor: '#e5e7eb',
      borderWidth: 1,
      padding: 12,
      callbacks: {
        label: (context) =>
          `${context.dataset.label}: ${formatConvertedValue(context.parsed.y)}`
      }
    }
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { color: '#9ca3af', maxTicksLimit: 10, font: { size: 10 } }
    },
    y: {
      grid: { color: '#e5e7eb' },
      ticks: {
        color: '#9ca3af',
        font: { size: 10 },
        callback: (value) => formatAxisTickValue(value)
      }
    }
  }
}))

const rechargeTimelineTags = computed(() => {
  const tagSet = new Set()
  ;(overview.value.financial_health?.recharge_alerts || []).forEach((item) => {
    ;(item.tags || []).forEach((tag) => {
      const normalized = String(tag || '').trim()
      if (normalized) {
        tagSet.add(normalized)
      }
    })
  })
  return Array.from(tagSet).sort((a, b) => a.localeCompare(b))
})

const filteredRechargeAlerts = computed(() => {
  const selectedTag = String(selectedRechargeTag.value || '').trim()
  const alerts = overview.value.financial_health?.recharge_alerts || []
  if (!selectedTag) {
    return alerts
  }
  return alerts.filter((item) => (item.tags || []).includes(selectedTag))
})

const visibleRechargeAlerts = computed(() =>
  filteredRechargeAlerts.value.slice(0, 5)
)

const selectedAccountDetail = computed(() => {
  const account = selectedAccount.value
  if (!account) {
    return {
      recommendation_status: 'unknown',
      daily_average: 0,
      daily_peak: 0,
      recommended_recharge: 0,
      recommended_window_days: 30,
      primary_service_name: '',
      primary_service_share: 0,
      service_count: 0,
      service_breakdown_currency: selectedCurrency.value,
      service_breakdown_source: '',
      service_breakdown_has_recent_rows: false,
      service_breakdown_coverage: 0,
      service_breakdown_complete: false,
      service_breakdown: [],
      trend_series: [],
      trend_30d: []
    }
  }
  return (
    account.detail || {
      recommendation_status: hasDaysRemainingReference(account)
        ? daysRemainingRisk(account) === 'high'
          ? 'attention'
          : 'healthy'
        : 'unknown',
      daily_average: Number(account.change || 0),
      daily_peak: Math.max(
        ...(account.trend || []).map((item) => Number(item.value || 0)),
        0
      ),
      recommended_recharge: 0,
      recommended_window_days: 30,
      primary_service_name: '',
      primary_service_share: 0,
      service_count: 0,
      service_breakdown_currency: selectedCurrency.value,
      service_breakdown_source: '',
      service_breakdown_has_recent_rows: false,
      service_breakdown_coverage: 0,
      service_breakdown_complete: false,
      service_breakdown: [],
      trend_series: [],
      trend_30d: (account.trend || []).map((item) => ({
        date: item.date,
        total: Number(item.value || 0),
        services: {}
      }))
    }
  )
})

const recommendationMessage = computed(() => {
  const account = selectedAccount.value
  if (!account) {
    return ''
  }
  if (!hasDaysRemainingReference(account)) {
    return t('cloudBilling.billing.accountDrawerNoReferenceRecommendation')
  }
  const detail = selectedAccountDetail.value
  if (!detail.recommended_recharge) {
    return t('cloudBilling.billing.accountDrawerFallbackRecommendation', {
      days: account.days_remaining
    })
  }
  return t('cloudBilling.billing.accountDrawerRecommendationMessage', {
    daily: formatAccountValue(
      detail.daily_average,
      detail.service_breakdown_currency
    ),
    days: account.days_remaining,
    amount: formatAccountValue(
      detail.recommended_recharge,
      detail.service_breakdown_currency
    ),
    window: detail.recommended_window_days || 30
  })
})

const serviceBreakdownHint = computed(() => {
  const detail = selectedAccountDetail.value
  if (!(detail.service_breakdown || []).length) {
    return ''
  }

  const coverage = Number(detail.service_breakdown_coverage || 0).toFixed(1)
  if (detail.service_breakdown_source === 'latest_billing') {
    return t('cloudBilling.billing.accountDrawerServiceBreakdownFallbackHint', {
      coverage
    })
  }

  if (!detail.service_breakdown_complete) {
    return t('cloudBilling.billing.accountDrawerServiceBreakdownCoverageHint', {
      coverage
    })
  }

  return ''
})

const accountDetailChartData = computed(() => {
  const trend = selectedAccountDetail.value.trend_30d || []
  if (!trend.length) {
    return null
  }
  const palette = [
    '#8b5cf6',
    '#14b8a6',
    '#f59e0b',
    '#ef4444',
    '#6366f1',
    '#10b981'
  ]
  const serviceDatasets = (selectedAccountDetail.value.trend_series || []).map(
    (series, index) => ({
      label: displayServiceName(series.name),
      data: series.values || [],
      borderColor:
        series.name === '__other__'
          ? '#cbd5e1'
          : palette[index % palette.length],
      backgroundColor: 'transparent',
      tension: 0.35,
      pointRadius: 0,
      borderWidth: 2,
      borderDash: series.name === '__other__' ? [6, 6] : undefined
    })
  )
  const totalDataset = {
    label: t('cloudBilling.billing.accountDrawerLegendTotal'),
    data: trend.map((item) => Number(item.total || 0)),
    borderColor: '#3b82f6',
    backgroundColor: 'rgba(59, 130, 246, 0.08)',
    fill: true,
    tension: 0.35,
    pointRadius: 3,
    pointHoverRadius: 4
  }
  return {
    labels: trend.map((item) => item.date),
    datasets: serviceDatasets.length > 0 ? serviceDatasets : [totalDataset]
  }
})

const accountDetailChartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: {
      position: 'bottom',
      labels: {
        usePointStyle: true,
        boxWidth: 10,
        color: '#52525b'
      }
    },
    tooltip: {
      backgroundColor: '#ffffff',
      titleColor: '#18181b',
      bodyColor: '#3f3f46',
      borderColor: '#e4e4e7',
      borderWidth: 1,
      padding: 12,
      callbacks: {
        label: (context) =>
          `${context.dataset.label}: ${formatAccountValue(
            context.parsed.y,
            selectedAccountDetail.value.service_breakdown_currency
          )}`
      }
    }
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { color: '#a1a1aa', maxTicksLimit: 10 }
    },
    y: {
      beginAtZero: true,
      grid: { color: '#f4f4f5' },
      ticks: {
        color: '#a1a1aa',
        callback: (value) => formatAxisTickValue(value)
      }
    }
  }
}))

const currencyChartData = computed(() => ({
  labels: (overview.value.currency_breakdown || []).map((item) => item.code),
  datasets: [
    {
      data: (overview.value.currency_breakdown || []).map((item) => item.value),
      backgroundColor: (overview.value.currency_breakdown || []).map(
        (item) => item.color
      ),
      borderWidth: 0
    }
  ]
}))

const currencyChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '68%',
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#18181b'
    }
  }
}

const filteredAccounts = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) {
    return overview.value.accounts || []
  }
  return (overview.value.accounts || []).filter((item) => {
    return (
      localizedAccountName(item).toLowerCase().includes(query) ||
      localizedProviderLabel(item).toLowerCase().includes(query) ||
      String(item.account_id || '')
        .toLowerCase()
        .includes(query)
    )
  })
})

function sumUniqueProviderBalances(accounts) {
  const providerBalances = new Map()

  ;(accounts || []).forEach((account) => {
    const providerKey = String(
      account?.provider_id || account?.provider || account?.name || ''
    )
    if (!providerKey || providerBalances.has(providerKey)) {
      return
    }

    providerBalances.set(providerKey, {
      balance: Number(account?.balance || 0),
      currency: String(account?.balance_currency || '').toUpperCase()
    })
  })

  return Array.from(providerBalances.values()).reduce((sum, item) => {
    if (item.balance <= 0) {
      return sum
    }
    return sum + convertAmountByCurrency(item.balance, item.currency)
  }, 0)
}

function normalizeCurrencyCode(currency) {
  const normalized = String(currency || '').toUpperCase()
  return normalized || 'CNY'
}

function convertCurrencyValue(value, fromCurrency, toCurrency) {
  const numericValue = Number(value || 0)
  if (!Number.isFinite(numericValue)) {
    return 0
  }

  const from = normalizeCurrencyCode(fromCurrency)
  const to = normalizeCurrencyCode(toCurrency)
  if (from === to) {
    return numericValue
  }

  const rate = exchangeRateValue.value
  if (from === 'USD' && to === 'CNY') {
    return numericValue * rate
  }
  if (from === 'CNY' && to === 'USD') {
    return numericValue / rate
  }
  return numericValue
}

const groupedRows = computed(() => {
  if (!groupByProvider.value) {
    return [
      {
        name: t('cloudBilling.billing.overviewAllAccounts'),
        rows: filteredAccounts.value,
        totalCost: filteredAccounts.value.reduce(
          (sum, item) =>
            sum +
            convertCurrencyValue(item.cost, item.cost_currency || 'CNY', 'CNY'),
          0
        ),
        totalBalance: sumUniqueProviderBalances(filteredAccounts.value)
      }
    ]
  }

  const grouped = new Map()
  filteredAccounts.value.forEach((item) => {
    if (!grouped.has(item.provider)) {
      grouped.set(item.provider, [])
    }
    grouped.get(item.provider).push(item)
  })

  return Array.from(grouped.entries()).map(([name, rows]) => ({
    name,
    rows,
    totalCost: rows.reduce(
      (sum, item) =>
        sum +
        convertCurrencyValue(item.cost, item.cost_currency || 'CNY', 'CNY'),
      0
    ),
    totalBalance: sumUniqueProviderBalances(rows)
  }))
})

const prepaidAccounts = computed(() =>
  (overview.value.accounts || []).filter((item) => item.type === 'prepaid')
)

const postpaidAccounts = computed(() =>
  (overview.value.accounts || []).filter((item) => item.type === 'postpaid')
)

const visiblePrepaidAccounts = computed(() =>
  showAllPrepaid.value
    ? prepaidAccounts.value
    : prepaidAccounts.value.slice(0, accountCardInitialLimit)
)

const visiblePostpaidAccounts = computed(() =>
  showAllPostpaid.value
    ? postpaidAccounts.value
    : postpaidAccounts.value.slice(0, accountCardInitialLimit)
)

const providerIcons = {
  aws: awsIcon,
  azure: azureIcon,
  huawei: huaweiCloudIcon,
  'huawei-intl': huaweiCloudIcon,
  tencentcloud: tencentCloudIcon,
  alibaba: alibabaCloudIcon,
  volcengine: volcengineIcon,
  baidu: baiduCloudIcon,
  zhipu: zhipuIcon
}

function daysToRisk(daysRemaining) {
  if (daysRemaining <= 10) return 'high'
  if (daysRemaining <= 30) return 'medium'
  return 'low'
}

function legacyRisk(account) {
  const risk = String(account?.risk || '').toLowerCase()
  if (risk === 'high' || risk === 'medium' || risk === 'low') {
    return risk
  }
  return ''
}

function hasDaysRemainingReference(account) {
  return Boolean(account?.has_days_remaining_reference)
}

function daysRemainingRisk(account) {
  if (!hasDaysRemainingReference(account))
    return legacyRisk(account) || 'unknown'
  return daysToRisk(account?.days_remaining)
}

function riskLabel(risk) {
  if (risk === 'unknown')
    return t('cloudBilling.billing.overviewDaysReferenceUnavailable')
  if (risk === 'high') return t('cloudBilling.billing.overviewRiskHigh')
  if (risk === 'medium') return t('cloudBilling.billing.overviewRiskMedium')
  return t('cloudBilling.billing.overviewRiskLow')
}

function riskTextClass(risk) {
  if (risk === 'unknown') return 'text-zinc-400'
  if (risk === 'high') return 'text-rose-600'
  if (risk === 'medium') return 'text-amber-600'
  return 'text-emerald-600'
}

function riskDotClass(risk) {
  if (risk === 'unknown') return 'bg-zinc-300'
  if (risk === 'high') return 'bg-rose-500'
  if (risk === 'medium') return 'bg-amber-500'
  return 'bg-emerald-500'
}

function riskBadgeClass(risk) {
  if (risk === 'unknown') return 'bg-zinc-100 text-zinc-500'
  if (risk === 'high') return 'bg-rose-50 text-rose-700'
  if (risk === 'medium') return 'bg-amber-50 text-amber-700'
  return 'bg-emerald-50 text-emerald-700'
}

function riskBarClass(risk) {
  if (risk === 'unknown') return 'bg-zinc-300'
  if (risk === 'high') return 'bg-rose-500'
  if (risk === 'medium') return 'bg-amber-500'
  return 'bg-emerald-500'
}

function displayDaysRemaining(
  account,
  unitKey = 'cloudBilling.billing.overviewDaysUnit'
) {
  if (!hasDaysRemainingReference(account)) {
    return t('cloudBilling.billing.overviewDaysReferenceUnavailable')
  }
  return `${account.days_remaining}${t(unitKey)}`
}

function recommendationBadgeClass(status) {
  if (status === 'unknown') return 'bg-zinc-100 text-zinc-500'
  if (status === 'attention') return 'bg-amber-100 text-amber-700'
  return 'bg-emerald-100 text-emerald-700'
}

function recommendationLabel(status) {
  if (status === 'unknown')
    return t('cloudBilling.billing.overviewDaysReferenceUnavailable')
  if (status === 'attention')
    return t('cloudBilling.billing.accountDrawerStatusAttention')
  return t('cloudBilling.billing.accountDrawerStatusHealthy')
}

function normalizedBalanceForSort(account) {
  const sourceValue =
    account?.balance != null ? account.balance : account?.display_funds || 0
  return convertCurrencyValue(
    Number(sourceValue || 0),
    account?.display_funds_currency || account?.balance_currency || 'CNY',
    'CNY'
  )
}

function compareAccountsByAvailability(a, b) {
  const aHasReference = hasDaysRemainingReference(a)
  const bHasReference = hasDaysRemainingReference(b)

  if (aHasReference && bHasReference) {
    return (
      a.days_remaining - b.days_remaining ||
      convertCurrencyValue(b.cost, b.cost_currency || 'CNY', 'CNY') -
        convertCurrencyValue(a.cost, a.cost_currency || 'CNY', 'CNY')
    )
  }

  if (!aHasReference && !bHasReference) {
    return (
      normalizedBalanceForSort(a) - normalizedBalanceForSort(b) ||
      convertCurrencyValue(b.cost, b.cost_currency || 'CNY', 'CNY') -
        convertCurrencyValue(a.cost, a.cost_currency || 'CNY', 'CNY')
    )
  }

  return aHasReference ? -1 : 1
}

function recommendationStatus(account, detail) {
  if (!hasDaysRemainingReference(account)) {
    const risk = legacyRisk(account)
    if (risk) {
      return risk === 'high' ? 'attention' : 'healthy'
    }
    return 'unknown'
  }
  return detail?.recommendation_status || 'healthy'
}

function displayServiceName(name) {
  if (name === '__other__') {
    return t('cloudBilling.billing.accountDrawerLegendOther')
  }
  return name || t('cloudBilling.billing.accountDrawerLegendPrimary')
}

function formatValue(value, sourceCurrency = 'CNY') {
  return formatAccountValue(value, sourceCurrency)
}

function convertAmountByCurrency(value, currency) {
  return convertCurrencyValue(value, currency, selectedCurrency.value)
}

function formatCurrencyByCode(value, currency) {
  const numericValue = Number(value || 0)
  const symbol = normalizeCurrencyCode(currency) === 'USD' ? '$' : '¥'
  return `${symbol}${numericValue.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`
}

function formatAccountValue(value, currency) {
  return formatCurrencyByCode(
    convertAmountByCurrency(value, currency),
    selectedCurrency.value
  )
}

function formatCompactValue(value) {
  const numericValue = Number(value || 0)
  if (selectedCurrency.value === 'USD') {
    return `$${Math.round(numericValue)}`
  }
  return `¥${Math.round(numericValue)}`
}

function formatAxisTickValue(value) {
  const numericValue = Number(value || 0)
  const symbol = selectedCurrency.value === 'USD' ? '$' : '¥'

  if (numericValue === 0) {
    return `${symbol}0`
  }

  if (Math.abs(numericValue) < 10) {
    return `${symbol}${numericValue.toFixed(2)}`
  }

  if (Math.abs(numericValue) < 100) {
    return `${symbol}${numericValue.toFixed(1)}`
  }

  return formatCompactValue(numericValue)
}

function formatPercent(value) {
  return `${Number(value || 0).toFixed(1)}%`
}

function showBalance(account) {
  return Number(account.balance || 0) > 0
}

function paymentTypeLabel(type) {
  if (type === 'prepaid') return t('cloudBilling.billing.overviewTypePrepaid')
  if (type === 'postpaid') return t('cloudBilling.billing.overviewTypePostpaid')
  return type || '-'
}

function localizedAccountName(account) {
  return getLocalizedProviderDisplayName(
    {
      provider_type: account?.provider_type,
      display_name: account?.name || account?.provider
    },
    t
  )
}

function withNotesLabel(baseLabel, notes) {
  const label = String(baseLabel || '').trim()
  const noteText = String(notes || '').trim()
  if (!noteText) {
    return label
  }
  return label ? `${label} - ${noteText}` : noteText
}

function quotaTrendAccountLabel(account) {
  return withNotesLabel(localizedAccountName(account), account?.notes)
}

function rechargeProviderLabel(item) {
  const baseLabel = getLocalizedProviderDisplayName(
    {
      provider_type: item?.provider_type,
      display_name: item?.name
    },
    t
  )
  return withNotesLabel(baseLabel, item?.notes)
}

function localizedProviderLabel(account) {
  return getLocalizedProviderDisplayName(
    {
      provider_type: account?.provider_type,
      display_name: account?.provider || account?.name
    },
    t
  )
}

function providerIcon(account) {
  const providerType = String(account.provider_type || '')
    .trim()
    .toLowerCase()
  if (providerType && providerIcons[providerType]) {
    return providerIcons[providerType]
  }

  const providerName =
    `${account.provider || ''} ${account.name || ''}`.toLowerCase()
  if (providerName.includes('aws')) return providerIcons.aws
  if (providerName.includes('azure')) return providerIcons.azure
  if (providerName.includes('华为') || providerName.includes('huawei'))
    return providerIcons['huawei-intl']
  if (providerName.includes('腾讯') || providerName.includes('tencent'))
    return providerIcons.tencentcloud
  if (providerName.includes('阿里') || providerName.includes('alibaba'))
    return providerIcons.alibaba
  if (providerName.includes('火山') || providerName.includes('volc'))
    return providerIcons.volcengine
  if (providerName.includes('百度') || providerName.includes('baidu'))
    return providerIcons.baidu
  if (providerName.includes('智谱') || providerName.includes('zhipu'))
    return providerIcons.zhipu
  return ''
}

function providerFallbackLetter(account) {
  return (
    String(
      localizedProviderLabel(account) || localizedAccountName(account) || '?'
    )
      .trim()
      .charAt(0) || '?'
  )
}

function showProviderLabel(account) {
  const provider = String(localizedProviderLabel(account) || '')
    .trim()
    .toLowerCase()
  const name = String(localizedAccountName(account) || '')
    .trim()
    .toLowerCase()
  return Boolean(provider) && provider !== name
}

function csvCell(value) {
  const normalized = String(value ?? '')
  return `"${normalized.replaceAll('"', '""')}"`
}

function exportAccountsCsv() {
  const headers = [
    t('cloudBilling.billing.provider'),
    t('cloudBilling.billing.accountId'),
    t('cloudBilling.billing.overviewPaymentType'),
    t('cloudBilling.billing.cost'),
    t('cloudBilling.billing.balance'),
    t('cloudBilling.billing.overviewCreditLimit'),
    t('cloudBilling.billing.overviewDaysRemaining'),
    t('cloudBilling.billing.overviewRiskStatus'),
    t('cloudBilling.billing.overviewNotes')
  ]

  const rows = filteredAccounts.value.map((account) => [
    localizedProviderLabel(account) || localizedAccountName(account) || '',
    account.account_id || '',
    paymentTypeLabel(account.type),
    formatValue(account.cost, account.cost_currency),
    showBalance(account)
      ? formatAccountValue(account.balance, account.balance_currency)
      : '',
    account.credit_limit
      ? formatAccountValue(account.credit_limit, account.credit_limit_currency)
      : '',
    displayDaysRemaining(account, 'cloudBilling.billing.overviewDaysShort'),
    riskLabel(daysRemainingRisk(account)),
    account.notes || ''
  ])

  const csvContent = [headers, ...rows]
    .map((row) => row.map(csvCell).join(','))
    .join('\n')

  const blob = new Blob(['\uFEFF' + csvContent], {
    type: 'text/csv;charset=utf-8;'
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `operations-accounts-${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function formatBreakdownValue(item) {
  if (item.code === 'USD') {
    return `$${Number(item.original_value || 0).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}`
  }
  return `¥${Number(item.value || 0).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`
}

function formatTime(isoString) {
  if (!isoString) return '--'
  try {
    return new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZone: selectedTimezone.value
    }).format(new Date(isoString))
  } catch {
    return isoString
  }
}

function capitalizeRange(value) {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function sparklinePoints(trend) {
  const values = (trend || []).map((item) => Number(item.value || 0))
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const range = Math.max(max - min, 1)
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * 100
      const y = 28 - ((value - min) / range) * 24
      return `${x},${y}`
    })
    .join(' ')
}

function toggleProvider(name) {
  expandedProviders.value = {
    ...expandedProviders.value,
    [name]: expandedProviders.value[name] === false
  }
}

function visibleGroupRows(group) {
  if (!groupByProvider.value) {
    return group.rows
  }
  return expandedProviders.value[group.name] === false ? [] : group.rows
}

function openAccountDrawer(account) {
  selectedAccount.value = account
}

function closeAccountDrawer() {
  selectedAccount.value = null
}

function rechargeAlertKey(item) {
  if (!item) return ''
  return `${item.provider_id || item.name || 'provider'}-${item.account_id || 'default'}`
}

function parseRechargeInfo(text) {
  const result = {
    recharge_account: '',
    recharge_customer_name: '',
    payment_company: '',
    payment_way: '',
    payment_type: '',
    remit_method: '',
    submitter_identifier: '',
    payment_note: ''
  }
  if (!text) return result

  // Try JSON first
  try {
    const parsed = JSON.parse(text)
    if (parsed && typeof parsed === 'object') {
      result.recharge_account =
        parsed.recharge_account || parsed.充值云账号 || parsed.充值账号 || ''
      result.recharge_customer_name =
        parsed.recharge_customer_name ||
        parsed.充值客户名称 ||
        parsed.充值客户 ||
        ''
      result.payment_company = parsed.payment_company || parsed.付款公司 || ''
      result.payment_way = parsed.payment_way || parsed.支付方式 || ''
      result.payment_type = parsed.payment_type || parsed.付款类型 || ''
      result.remit_method = parsed.remit_method || parsed.付款方式 || ''
      result.payment_note = parsed.payment_note || parsed.付款说明 || ''
      result.submitter_identifier =
        parsed.recharge_approval?.submitter_identifier ||
        parsed.recharge_approval?.submitter_user_id ||
        parsed.submitter_identifier ||
        parsed.审批发起人 ||
        parsed.提交名义 ||
        ''
      return result
    }
  } catch {
    // fall through to key-value parsing
  }

  // Key-value text parsing
  const lines = text.split('\n')
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const separatorIndex = Math.max(trimmed.indexOf('：'), trimmed.indexOf(':'))
    if (separatorIndex === -1) continue
    const key = trimmed.slice(0, separatorIndex).trim()
    const value = trimmed.slice(separatorIndex + 1).trim()

    const keyMap = {
      公有云类型: 'cloud_type',
      recharge_account: 'recharge_account',
      充值云账号: 'recharge_account',
      充值账号: 'recharge_account',
      账号: 'recharge_account',
      recharge_customer_name: 'recharge_customer_name',
      充值客户名称: 'recharge_customer_name',
      充值客户: 'recharge_customer_name',
      客户名称: 'recharge_customer_name',
      客户: 'recharge_customer_name',
      payment_company: 'payment_company',
      付款公司: 'payment_company',
      payment_way: 'payment_way',
      支付方式: 'payment_way',
      payment_type: 'payment_type',
      付款类型: 'payment_type',
      remit_method: 'remit_method',
      付款方式: 'remit_method',
      payment_note: 'payment_note',
      付款说明: 'payment_note',
      submitter_identifier: 'submitter_identifier',
      充值发起人: 'submitter_identifier',
      审批发起人: 'submitter_identifier',
      提交名义: 'submitter_identifier',
      发起人邮箱或手机号: 'submitter_identifier'
    }
    const fieldKey = keyMap[key]
    if (fieldKey) {
      result[fieldKey] = value
    }
  }
  return result
}

function extractRechargeInfoDisplayObject(source) {
  if (!source || typeof source !== 'object' || Array.isArray(source)) {
    return {}
  }

  const payee =
    source.payee && typeof source.payee === 'object' ? source.payee : {}
  return {
    cloud_type: source.cloud_type || source.公有云类型 || '',
    recharge_customer_name:
      source.recharge_customer_name ||
      source.充值客户名称 ||
      source.充值客户 ||
      '',
    recharge_account:
      source.recharge_account ||
      source.充值云账号 ||
      source.充值账号 ||
      source.account ||
      '',
    payment_company: source.payment_company || source.付款公司 || '',
    payment_way: source.payment_way || source.支付方式 || '',
    payment_type: source.payment_type || source.付款类型 || '',
    remit_method: source.remit_method || source.付款方式 || '',
    amount: source.amount || source.付款金额 || '',
    currency: source.currency || source.币种 || '',
    expected_date: source.expected_date || source.期望到账时间 || '',
    payment_note: source.payment_note || source.付款说明 || '',
    remark: source.remark || source.备注 || '',
    payee: {
      type: payee.type || payee.账户类型 || '',
      account_name: payee.account_name || payee.户名 || '',
      account_number: payee.account_number || payee.账号 || '',
      bank_name: payee.bank_name || payee.银行 || '',
      bank_region: payee.bank_region || payee.银行地区 || '',
      bank_branch: payee.bank_branch || payee.支行 || ''
    }
  }
}

function formatRechargeInfoText(source) {
  if (!source) {
    return ''
  }

  if (typeof source === 'string') {
    const trimmed = source.trim()
    if (!trimmed) {
      return ''
    }

    try {
      const parsed = JSON.parse(trimmed)
      if (parsed && typeof parsed === 'object') {
        return renderRechargeInfoObject(parsed)
      }
    } catch {
      return trimmed
    }

    return trimmed
  }

  if (typeof source === 'object') {
    return renderRechargeInfoObject(source)
  }

  return String(source).trim()
}

function extractRechargeApprovalInfo(source) {
  const result = {
    submitter_identifier: '',
    payment_note: ''
  }
  if (!source) return result

  if (typeof source === 'string') {
    const trimmed = source.trim()
    if (!trimmed) return result
    try {
      const parsed = JSON.parse(trimmed)
      if (parsed && typeof parsed === 'object') {
        result.submitter_identifier =
          parsed.recharge_approval?.submitter_identifier ||
          parsed.recharge_approval?.submitter_user_id ||
          parsed.submitter_identifier ||
          parsed.审批发起人 ||
          parsed.提交名义 ||
          ''
        result.payment_note = parsed.payment_note || parsed.付款说明 || ''
      }
    } catch {
      const parsedText = parseRechargeInfo(trimmed)
      result.submitter_identifier = parsedText.submitter_identifier || ''
      result.payment_note = parsedText.payment_note || ''
    }
    return result
  }

  if (typeof source === 'object') {
    result.submitter_identifier =
      source.recharge_approval?.submitter_identifier ||
      source.recharge_approval?.submitter_user_id ||
      source.submitter_identifier ||
      source.审批发起人 ||
      source.提交名义 ||
      ''
    result.payment_note = source.payment_note || source.付款说明 || ''
  }
  return result
}

const RECHARGE_INFO_LABEL_MAP = {
  cloud_type: '公有云类型',
  payment_type: '付款类型',
  付款类型: '付款类型',
  recharge_customer_name: '充值客户名称',
  充值客户名称: '充值客户名称',
  充值客户: '充值客户名称',
  customer_name: '充值客户名称',
  recharge_account: '充值云账号',
  充值云账号: '充值云账号',
  充值账号: '充值云账号',
  account: '充值云账号',
  payment_company: '付款公司',
  付款公司: '付款公司',
  payment_way: '支付方式',
  支付方式: '支付方式',
  remit_method: '付款方式',
  付款方式: '付款方式',
  amount: '付款金额',
  付款金额: '付款金额',
  currency: '币种',
  币种: '币种',
  expected_date: '期望到账时间',
  期望到账时间: '期望到账时间',
  payment_note: '付款说明',
  付款说明: '付款说明',
  remark: '备注',
  备注: '备注',
  'payee.type': '账户类型',
  'payee.account_name': '户名',
  'payee.account_number': '账号',
  'payee.bank_name': '银行',
  'payee.bank_region': '银行地区',
  'payee.bank_branch': '支行'
}

function translateRechargeInfoKey(key) {
  const text = String(key || '').trim()
  return RECHARGE_INFO_LABEL_MAP[text] || text
}

function shouldSkipRechargeInfoKey(key, value) {
  const text = String(value || '').trim()
  return (
    !text ||
    (translateRechargeInfoKey(key) === '备注' &&
      ['备注', 'remark'].includes(text))
  )
}

function renderRechargeInfoObject(source, prefix = '') {
  if (!source || typeof source !== 'object') {
    return ''
  }

  const lines = []
  const entries = Array.isArray(source)
    ? source.entries()
    : Object.entries(source)

  for (const [rawKey, rawValue] of entries) {
    const key = String(rawKey)
    const value = rawValue
    const path = prefix ? `${prefix}.${key}` : key

    if (value === null || value === undefined || value === '') {
      continue
    }
    if (path === 'recharge_approval') {
      continue
    }

    if (Array.isArray(value)) {
      if (value.length === 0) continue
      const nested = value.some(
        (item) => item && typeof item === 'object' && !Array.isArray(item)
      )
      if (nested) {
        value.forEach((item, index) => {
          const rendered = renderRechargeInfoObject(item, `${path}[${index}]`)
          if (rendered) {
            lines.push(rendered)
          }
        })
        continue
      }
      const label = translateRechargeInfoKey(path)
      lines.push(
        `${label}： ${value.map((item) => String(item).trim()).join('，')}`
      )
      continue
    }

    if (typeof value === 'object') {
      const nested = renderRechargeInfoObject(value, path)
      if (nested) {
        lines.push(nested)
      }
      continue
    }

    if (shouldSkipRechargeInfoKey(path, value)) {
      continue
    }

    const label = translateRechargeInfoKey(path)
    lines.push(`${label}： ${String(value).trim()}`)
  }

  return lines.join('\n')
}

const ALERT_RECHARGE_APPROVAL_EXPECTED_DAYS = 3

async function openRechargeSubmitDialog(item) {
  const today = getTodayDateString(selectedTimezone.value)
  let rechargeApprovalSource = item.recharge_info || ''
  let parsed =
    typeof rechargeApprovalSource === 'object'
      ? extractRechargeInfoDisplayObject(rechargeApprovalSource)
      : parseRechargeInfo(rechargeApprovalSource)
  let approval = extractRechargeApprovalInfo(rechargeApprovalSource)
  let rechargeInfoText = formatRechargeInfoText(
    typeof rechargeApprovalSource === 'object'
      ? extractRechargeInfoDisplayObject(rechargeApprovalSource)
      : rechargeApprovalSource
  )

  if (!rechargeInfoText && item?.provider_id) {
    try {
      const response = await cloudBillingApi.getProvider(item.provider_id)
      const provider = extractResponseData(response)
      rechargeApprovalSource =
        provider?.recharge_info || provider?.config || rechargeApprovalSource
      parsed =
        typeof rechargeApprovalSource === 'object'
          ? extractRechargeInfoDisplayObject(rechargeApprovalSource)
          : parseRechargeInfo(rechargeApprovalSource)
      approval = extractRechargeApprovalInfo(rechargeApprovalSource)
      rechargeInfoText = formatRechargeInfoText(
        typeof rechargeApprovalSource === 'object'
          ? extractRechargeInfoDisplayObject(rechargeApprovalSource)
          : rechargeApprovalSource
      )
    } catch (error) {
      console.error('Failed to load provider recharge info:', error)
    }
  }

  rechargeSubmitTarget.value = item
  rechargeSubmitForm.value = {
    recharge_info_text: rechargeInfoText,
    submitter_identifier:
      approval.submitter_identifier || parsed.submitter_identifier || '',
    payment_note: parsed.payment_note || approval.payment_note || '',
    recharge_account: parsed.recharge_account || item.account_id || '',
    recharge_customer_name: parsed.recharge_customer_name || '',
    payment_company: parsed.payment_company || '',
    payment_way: parsed.payment_way || '公司支付',
    payment_type: parsed.payment_type || '仅充值',
    remit_method: parsed.remit_method || '转账',
    amount: '',
    expected_date: addDaysToDateString(
      today,
      ALERT_RECHARGE_APPROVAL_EXPECTED_DAYS
    )
  }
  showRechargeSubmitDialog.value = true
}

function closeRechargeSubmitDialog() {
  if (submittingRechargeKey.value) return
  showRechargeSubmitDialog.value = false
  rechargeSubmitTarget.value = null
  rechargeSubmitForm.value = {
    recharge_info_text: '',
    submitter_identifier: '',
    payment_note: '',
    recharge_account: '',
    recharge_customer_name: '',
    payment_company: '',
    payment_way: '',
    payment_type: '',
    remit_method: '',
    amount: '',
    expected_date: ''
  }
}

async function submitRechargeApprovalFromDialog() {
  const item = rechargeSubmitTarget.value
  if (!item?.provider_id) return
  const amount = String(rechargeSubmitForm.value.amount || '').trim()
  const expectedDate = String(
    rechargeSubmitForm.value.expected_date || ''
  ).trim()
  const submitterIdentifier = String(
    rechargeSubmitForm.value.submitter_identifier || ''
  ).trim()
  const paymentNote = String(rechargeSubmitForm.value.payment_note || '').trim()
  if (!submitterIdentifier) {
    showWarning(
      t('cloudBilling.billing.rechargeApprovalSubmitterRequiredWarning')
    )
    return
  }
  if (!amount || !expectedDate) {
    showWarning(t('cloudBilling.billing.rechargeApprovalRequiredFields'))
    return
  }

  const key = rechargeAlertKey(item)
  submittingRechargeKey.value = key
  try {
    const response = await cloudBillingApi.submitProviderRechargeApproval(
      item.provider_id,
      {
        account_id: item.account_id,
        submitter_identifier: submitterIdentifier,
        recharge_account: rechargeSubmitForm.value.recharge_account,
        recharge_customer_name: rechargeSubmitForm.value.recharge_customer_name,
        payment_company: rechargeSubmitForm.value.payment_company,
        payment_way: rechargeSubmitForm.value.payment_way,
        payment_type: rechargeSubmitForm.value.payment_type,
        remit_method: rechargeSubmitForm.value.remit_method,
        payment_note: paymentNote,
        amount,
        currency: item.recommendation_currency || selectedCurrency.value,
        expected_date: expectedDate,
        trigger_reason: 'operations_console_timeline'
      }
    )
    const data = extractResponseData(response)
    showSuccess(
      data?.message || t('cloudBilling.billing.submitRechargeApprovalSuccess')
    )
    showRechargeSubmitDialog.value = false
    rechargeSubmitTarget.value = null
  } catch (err) {
    console.error('Failed to submit recharge approval:', err)
    showError(t('cloudBilling.billing.rechargeApprovalError'))
  } finally {
    submittingRechargeKey.value = ''
  }
}

async function loadOverview() {
  loading.value = true
  error.value = ''
  try {
    const response = await cloudBillingApi.getOverview({
      timezone: selectedTimezone.value
    })
    const data = extractResponseData(response)
    overview.value = {
      ...createFallbackOverview(),
      ...data,
      summary: {
        ...createFallbackOverview().summary,
        ...(data?.summary || {})
      },
      financial_health: {
        ...createFallbackOverview().financial_health,
        ...(data?.financial_health || {})
      },
      currency_breakdown:
        data?.currency_breakdown || createFallbackOverview().currency_breakdown,
      accounts: data?.accounts || createFallbackOverview().accounts
    }
  } catch (err) {
    overview.value = createFallbackOverview()
    error.value = extractErrorMessage(err, t('common.error'))
  } finally {
    overviewLoaded.value = true
    loading.value = false
  }
}

defineExpose({ reload: loadOverview })

onMounted(() => {
  loadOverview()
})

watch(
  () => selectedTimezone.value,
  (value, previousValue) => {
    if (!overviewLoaded.value || !value || value === previousValue) {
      return
    }
    loadOverview()
  }
)

watch(rechargeTimelineTags, (tags) => {
  if (selectedRechargeTag.value && !tags.includes(selectedRechargeTag.value)) {
    selectedRechargeTag.value = ''
  }
})

watch(
  () => overview.value.accounts,
  (accounts) => {
    if (!selectedAccount.value) {
      return
    }
    const matched = (accounts || []).find(
      (item) => item.id === selectedAccount.value.id
    )
    if (!matched) {
      selectedAccount.value = null
      return
    }
    selectedAccount.value = matched
  }
)
</script>

<style scoped>
.table-head {
  @apply px-6 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-400;
}
</style>

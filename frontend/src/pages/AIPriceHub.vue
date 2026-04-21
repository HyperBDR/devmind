<template>
  <AppLayout :show-sidebar="false">
    <div class="mx-auto w-full max-w-[1480px]">
      <section class="rounded-[28px] border border-gray-200 bg-white shadow-sm">
        <div class="border-b border-gray-200 px-6 py-5 lg:px-8">
          <div
            class="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between"
          >
            <div class="min-w-0 flex-1">
              <p
                class="text-xs font-semibold uppercase tracking-[0.22em] text-primary-600"
              >
                {{ t('aiPriceHub.eyebrow') }}
              </p>
              <h1
                class="mt-2 text-2xl font-semibold tracking-tight text-gray-900"
              >
                {{ t('aiPriceHub.title') }}
              </h1>
              <p class="mt-2 max-w-3xl text-sm leading-6 text-gray-500">
                {{ t('aiPriceHub.subtitle') }}
              </p>
            </div>

            <div
              class="flex w-full flex-col gap-3 xl:w-auto xl:min-w-[640px] xl:flex-row xl:justify-end"
            >
              <div
                class="relative min-w-0 flex-1 xl:max-w-[280px]"
                ref="platformDropdownRef"
              >
                <button
                  type="button"
                  class="flex w-full items-center rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:border-primary-300 hover:text-primary-700"
                  @click="platformOpen = !platformOpen"
                >
                  <span class="min-w-0 flex-1 truncate text-left">
                    {{
                      selectedPlatformLabel ||
                      t('aiPriceHub.selector.platformLabel')
                    }}
                  </span>
                  <svg
                    class="h-4 w-4 shrink-0 transition-transform"
                    :class="{ 'rotate-180': platformOpen }"
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
                </button>
                <Transition
                  enter-active-class="transition ease-out duration-100"
                  enter-from-class="transform opacity-0 scale-95"
                  enter-to-class="transform opacity-100 scale-100"
                  leave-active-class="transition ease-in duration-75"
                  leave-from-class="transform opacity-100 scale-100"
                  leave-to-class="transform opacity-0 scale-95"
                >
                  <div
                    v-if="platformOpen"
                    class="absolute right-0 z-30 mt-2 w-full overflow-hidden rounded-xl border border-gray-200 bg-white shadow-lg"
                  >
                    <div
                      class="border-b border-gray-100 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-gray-500"
                    >
                      {{ t('aiPriceHub.selector.platformLabel') }}
                    </div>
                    <button
                      v-for="platform in primarySources"
                      :key="platform.platform_slug"
                      type="button"
                      class="flex w-full items-center justify-between px-4 py-3 text-left text-sm text-gray-700 transition-colors hover:bg-gray-50 hover:text-gray-900"
                      @click="selectPlatform(platform.platform_slug)"
                    >
                      <span class="truncate">{{
                        platformOptionLabel(platform)
                      }}</span>
                      <span
                        v-if="platform.platform_slug === selectedPlatformSlug"
                        class="rounded-full bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700"
                      >
                        {{ t('common.current') }}
                      </span>
                    </button>
                  </div>
                </Transition>
              </div>

              <div class="relative min-w-0 flex-[1.2] xl:max-w-[340px]">
                <svg
                  class="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="m21 21-4.35-4.35M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z"
                  />
                </svg>
                <input
                  v-model="searchQuery"
                  type="text"
                  class="w-full rounded-xl border border-gray-200 bg-gray-50 py-3 pl-11 pr-4 text-sm text-gray-700 outline-none transition-all placeholder:text-gray-400 focus:border-primary-300 focus:bg-white focus:ring-4 focus:ring-primary-50"
                  :placeholder="t('aiPriceHub.search.placeholder')"
                />
              </div>
            </div>
          </div>
        </div>

        <div class="border-b border-gray-200 bg-gray-50/70 px-6 py-4 lg:px-8">
          <div class="flex flex-wrap items-center gap-3 text-sm text-gray-600">
            <span
              class="rounded-full bg-white px-3 py-1 font-medium text-gray-700 ring-1 ring-gray-200"
            >
              {{ t('aiPriceHub.stats.models') }} {{ filteredRows.length }}
            </span>
            <span
              class="rounded-full bg-white px-3 py-1 font-medium text-gray-700 ring-1 ring-gray-200"
            >
              {{ t('aiPriceHub.stats.vendors') }} {{ vendorColumns.length + 1 }}
            </span>
            <span class="text-xs text-gray-500">
              {{ t('aiPriceHub.matrix.subtitle') }}
            </span>
          </div>
        </div>

        <div class="px-6 py-6 lg:px-8">
          <BaseLoading v-if="loading" />

          <div
            v-else-if="!filteredRows.length"
            class="rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-6 py-16 text-center"
          >
            <h3 class="text-base font-semibold text-gray-900">
              {{ t('aiPriceHub.empty.title') }}
            </h3>
            <p class="mt-2 text-sm text-gray-500">
              {{ error || t('aiPriceHub.empty.description') }}
            </p>
          </div>

          <div v-else class="space-y-4">
            <div class="hidden overflow-x-auto lg:block">
              <table class="min-w-full border-collapse">
                <thead>
                  <tr class="bg-gray-50/70">
                    <th
                      class="sticky left-0 z-10 min-w-[220px] border-b border-r border-gray-200 bg-gray-50/90 px-5 py-4 text-left text-xs font-semibold uppercase tracking-[0.18em] text-gray-500 backdrop-blur"
                    >
                      {{ t('aiPriceHub.table.model') }}
                    </th>
                    <th
                      class="min-w-[210px] border-b border-r border-gray-200 bg-primary-50/60 px-5 py-4 text-left"
                    >
                      <p
                        class="text-xs font-semibold uppercase tracking-[0.18em] text-primary-700"
                      >
                        {{ t('aiPriceHub.vendors.agione') }}
                      </p>
                      <div
                        class="mt-2 grid grid-cols-2 gap-3 text-[11px] font-semibold uppercase tracking-wide text-primary-700"
                      >
                        <span>{{ t('aiPriceHub.table.input') }}</span>
                        <span>{{ t('aiPriceHub.table.output') }}</span>
                      </div>
                    </th>
                    <th
                      v-for="vendor in vendorColumns"
                      :key="vendor.key"
                      class="min-w-[210px] border-b border-r border-gray-200 px-5 py-4 text-left last:border-r-0"
                    >
                      <p
                        class="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500"
                      >
                        {{ vendor.label }}
                      </p>
                      <div
                        class="mt-2 grid grid-cols-2 gap-3 text-[11px] font-semibold uppercase tracking-wide text-gray-500"
                      >
                        <span>{{ t('aiPriceHub.table.input') }}</span>
                        <span>{{ t('aiPriceHub.table.output') }}</span>
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in filteredRows"
                    :key="row.primary_model.id"
                    class="align-top hover:bg-gray-50/50"
                  >
                    <td
                      class="sticky left-0 z-10 border-b border-r border-gray-200 bg-white px-5 py-5 backdrop-blur"
                    >
                      <p
                        class="text-sm font-semibold text-gray-900"
                        :title="row.primary_model.name"
                      >
                        {{ row.primary_model.name }}
                      </p>
                    </td>
                    <td
                      class="border-b border-r border-gray-200 bg-primary-50/30 px-5 py-5"
                    >
                      <div class="grid grid-cols-2 gap-3">
                        <div>
                          <p
                            class="whitespace-nowrap text-sm font-semibold text-gray-900"
                          >
                            {{
                              formatMoney(
                                row.primary_model.input_price_per_million,
                                row.primary_model.currency
                              )
                            }}
                          </p>
                        </div>
                        <div>
                          <p
                            class="whitespace-nowrap text-sm font-semibold text-gray-900"
                          >
                            {{
                              formatMoney(
                                row.primary_model.output_price_per_million,
                                row.primary_model.currency
                              )
                            }}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td
                      v-for="vendor in vendorColumns"
                      :key="`${row.primary_model.id}-${vendor.key}`"
                      class="border-b border-r border-gray-200 px-5 py-5 last:border-r-0"
                    >
                      <template v-if="row.comparison_by_vendor[vendor.key]">
                        <div class="grid grid-cols-2 gap-3">
                          <div>
                            <p
                              class="whitespace-nowrap text-sm font-semibold text-gray-900"
                            >
                              {{
                                formatMoney(
                                  row.comparison_by_vendor[vendor.key]
                                    .input_price_per_million,
                                  row.comparison_by_vendor[vendor.key].currency
                                )
                              }}
                            </p>
                            <p
                              class="mt-1 text-xs"
                              :class="
                                deltaTextClass(
                                  row.comparison_by_vendor[vendor.key]
                                    .input_advantage
                                )
                              "
                            >
                              {{
                                formatCompactAdvantage(
                                  row.comparison_by_vendor[vendor.key]
                                    .input_advantage,
                                  row.comparison_by_vendor[vendor.key]
                                    .input_advantage_ratio
                                )
                              }}
                            </p>
                          </div>
                          <div>
                            <p
                              class="whitespace-nowrap text-sm font-semibold text-gray-900"
                            >
                              {{
                                formatMoney(
                                  row.comparison_by_vendor[vendor.key]
                                    .output_price_per_million,
                                  row.comparison_by_vendor[vendor.key].currency
                                )
                              }}
                            </p>
                            <p
                              class="mt-1 text-xs"
                              :class="
                                deltaTextClass(
                                  row.comparison_by_vendor[vendor.key]
                                    .output_advantage
                                )
                              "
                            >
                              {{
                                formatCompactAdvantage(
                                  row.comparison_by_vendor[vendor.key]
                                    .output_advantage,
                                  row.comparison_by_vendor[vendor.key]
                                    .output_advantage_ratio
                                )
                              }}
                            </p>
                          </div>
                        </div>
                      </template>
                      <p v-else class="text-xs text-gray-400">
                        {{ t('aiPriceHub.advantage.unavailable') }}
                      </p>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="grid gap-4 lg:hidden">
              <article
                v-for="row in filteredRows"
                :key="row.primary_model.id"
                class="rounded-2xl border border-gray-200 bg-white p-4"
              >
                <div class="mb-4">
                  <h3
                    class="text-base font-semibold text-gray-900"
                    :title="row.primary_model.name"
                  >
                    {{ row.primary_model.name }}
                  </h3>
                </div>

                <div class="space-y-3">
                  <div
                    class="rounded-xl border border-primary-100 bg-primary-50/50 p-3"
                  >
                    <p
                      class="text-xs font-semibold uppercase tracking-[0.18em] text-primary-700"
                    >
                      {{ t('aiPriceHub.vendors.agione') }}
                    </p>
                    <div class="mt-3 grid grid-cols-2 gap-3">
                      <div>
                        <p
                          class="text-[11px] font-medium uppercase tracking-wide text-primary-700"
                        >
                          {{ t('aiPriceHub.table.input') }}
                        </p>
                        <p
                          class="mt-1 whitespace-nowrap text-sm font-semibold text-gray-900"
                        >
                          {{
                            formatMoney(
                              row.primary_model.input_price_per_million,
                              row.primary_model.currency
                            )
                          }}
                        </p>
                      </div>
                      <div>
                        <p
                          class="text-[11px] font-medium uppercase tracking-wide text-primary-700"
                        >
                          {{ t('aiPriceHub.table.output') }}
                        </p>
                        <p
                          class="mt-1 whitespace-nowrap text-sm font-semibold text-gray-900"
                        >
                          {{
                            formatMoney(
                              row.primary_model.output_price_per_million,
                              row.primary_model.currency
                            )
                          }}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div
                    v-for="vendor in vendorColumns"
                    :key="`${row.primary_model.id}-${vendor.key}-mobile`"
                    class="rounded-xl border border-gray-200 bg-gray-50 p-3"
                  >
                    <p
                      class="text-xs font-semibold uppercase tracking-[0.18em] text-gray-600"
                    >
                      {{ vendor.label }}
                    </p>
                    <div
                      v-if="row.comparison_by_vendor[vendor.key]"
                      class="mt-3 grid grid-cols-2 gap-3"
                    >
                      <div>
                        <p
                          class="text-[11px] font-medium uppercase tracking-wide text-gray-500"
                        >
                          {{ t('aiPriceHub.table.input') }}
                        </p>
                        <p
                          class="mt-1 whitespace-nowrap text-sm font-semibold text-gray-900"
                        >
                          {{
                            formatMoney(
                              row.comparison_by_vendor[vendor.key]
                                .input_price_per_million,
                              row.comparison_by_vendor[vendor.key].currency
                            )
                          }}
                        </p>
                        <p
                          class="mt-1 text-xs"
                          :class="
                            deltaTextClass(
                              row.comparison_by_vendor[vendor.key]
                                .input_advantage
                            )
                          "
                        >
                          {{
                            formatCompactAdvantage(
                              row.comparison_by_vendor[vendor.key]
                                .input_advantage,
                              row.comparison_by_vendor[vendor.key]
                                .input_advantage_ratio
                            )
                          }}
                        </p>
                      </div>
                      <div>
                        <p
                          class="text-[11px] font-medium uppercase tracking-wide text-gray-500"
                        >
                          {{ t('aiPriceHub.table.output') }}
                        </p>
                        <p
                          class="mt-1 whitespace-nowrap text-sm font-semibold text-gray-900"
                        >
                          {{
                            formatMoney(
                              row.comparison_by_vendor[vendor.key]
                                .output_price_per_million,
                              row.comparison_by_vendor[vendor.key].currency
                            )
                          }}
                        </p>
                        <p
                          class="mt-1 text-xs"
                          :class="
                            deltaTextClass(
                              row.comparison_by_vendor[vendor.key]
                                .output_advantage
                            )
                          "
                        >
                          {{
                            formatCompactAdvantage(
                              row.comparison_by_vendor[vendor.key]
                                .output_advantage,
                              row.comparison_by_vendor[vendor.key]
                                .output_advantage_ratio
                            )
                          }}
                        </p>
                      </div>
                    </div>
                    <p v-else class="mt-2 text-xs text-gray-400">
                      {{ t('aiPriceHub.advantage.unavailable') }}
                    </p>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </div>
      </section>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { aiPriceHubApi } from '@/api/aiPriceHub'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import { extractErrorMessage, extractResponseData } from '@/utils/api'

const { t, locale } = useI18n()

const overview = ref({
  primary_sources: [],
  primary_models: [],
  models: [],
  vendors: []
})
const comparisonRows = ref([])
const selectedPlatformSlug = ref('')
const loading = ref(false)
const error = ref('')
const searchQuery = ref('')
const platformOpen = ref(false)
const platformDropdownRef = ref(null)

const primarySources = computed(() => overview.value.primary_sources || [])
const selectedPlatform = computed(
  () =>
    primarySources.value.find(
      (item) => item.platform_slug === selectedPlatformSlug.value
    ) || null
)
const selectedPlatformLabel = computed(() => {
  const platform = selectedPlatform.value
  if (!platform) return ''
  return platformLabel(platform)
})

const VENDOR_I18N_KEYS = {
  agione: 'aiPriceHub.vendors.agione',
  aliyun: 'aiPriceHub.vendors.aliyun',
  'alibaba cloud': 'aiPriceHub.vendors.aliyun',
  'alibaba-china': 'aiPriceHub.vendors.aliyun',
  alibaba: 'aiPriceHub.vendors.aliyun',
  阿里云: 'aiPriceHub.vendors.aliyun',
  baidu: 'aiPriceHub.vendors.baidu',
  qianfan: 'aiPriceHub.vendors.baidu',
  'baidu qianfan': 'aiPriceHub.vendors.baidu',
  百度千帆: 'aiPriceHub.vendors.baidu',
  deepseek: 'aiPriceHub.vendors.deepseek',
  'deep seek': 'aiPriceHub.vendors.deepseek',
  volcengine: 'aiPriceHub.vendors.volcengine',
  'volc engine': 'aiPriceHub.vendors.volcengine',
  火山引擎: 'aiPriceHub.vendors.volcengine',
  zhipu: 'aiPriceHub.vendors.zhipu',
  'zhipu ai': 'aiPriceHub.vendors.zhipu',
  'z.ai': 'aiPriceHub.vendors.zhipu',
  'z.ai model': 'aiPriceHub.vendors.zhipu',
  智谱: 'aiPriceHub.vendors.zhipu',
  '智谱 ai': 'aiPriceHub.vendors.zhipu'
}

const vendorColumns = computed(() => {
  const map = new Map()
  comparisonRows.value.forEach((row) => {
    row.comparisons.forEach((item) => {
      const key = vendorKey(item.vendor_slug, item.vendor_name)
      if (!map.has(key)) {
        map.set(key, {
          key,
          label: localizeVendorName(item.vendor_name, item.vendor_slug)
        })
      }
    })
  })
  return Array.from(map.values()).sort((left, right) =>
    left.label.localeCompare(right.label, locale.value)
  )
})

const filteredRows = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return comparisonRows.value

  return comparisonRows.value.filter((row) => {
    const modelName = String(row.primary_model.name || '').toLowerCase()
    const matchesVendor = row.comparisons.some((item) =>
      localizeVendorName(item.vendor_name, item.vendor_slug)
        .toLowerCase()
        .includes(query)
    )
    return modelName.includes(query) || matchesVendor
  })
})

function vendorKey(slug, name) {
  return String(slug || name || '')
    .trim()
    .toLowerCase()
}

function currentIntlLocale() {
  return locale.value === 'zh-CN' ? 'zh-CN' : 'en-US'
}

function currencySymbol(currency = 'USD') {
  const symbolMap = {
    CNY: '¥',
    USD: '$',
    EUR: '€',
    GBP: '£',
    JPY: '¥',
    HKD: 'HK$'
  }
  return symbolMap[currency] || currency
}

function formatMoney(value, currency = 'USD') {
  if (value === null || value === undefined) return '-'
  const numberPart = new Intl.NumberFormat(currentIntlLocale(), {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value)
  return `${currencySymbol(currency)} ${numberPart}`
}

function formatPercent(value) {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat(currentIntlLocale(), {
    style: 'percent',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1
  }).format(value)
}

function localizeVendorName(name, slug = '') {
  const keyCandidates = [slug, name]
    .map((value) =>
      String(value || '')
        .trim()
        .toLowerCase()
    )
    .filter(Boolean)

  for (const candidate of keyCandidates) {
    const i18nKey = VENDOR_I18N_KEYS[candidate]
    if (i18nKey) {
      return t(i18nKey)
    }
  }

  return name || slug || '-'
}

function platformLabel(platform) {
  if (!platform) return ''

  const localizedName = localizeVendorName(
    platform.name || platform.vendor_name,
    platform.vendor_slug || platform.platform_slug
  )
  return platform.region
    ? `${localizedName} · ${platform.region}`
    : localizedName
}

function formatCompactAdvantage(advantage, ratio) {
  if (advantage === null || advantage === undefined) {
    return t('aiPriceHub.advantage.unavailable')
  }
  if (advantage === 0) {
    return t('aiPriceHub.advantage.same')
  }
  return advantage > 0
    ? t('aiPriceHub.advantage.compactSaving', {
        ratio: formatPercent(Math.abs(ratio))
      })
    : t('aiPriceHub.advantage.compactPremium', {
        ratio: formatPercent(Math.abs(ratio))
      })
}

function deltaTextClass(advantage) {
  if (advantage === null || advantage === undefined || advantage === 0) {
    return 'text-gray-500'
  }
  return advantage > 0 ? 'text-emerald-600' : 'text-rose-600'
}

async function loadAllComparisons() {
  const primaryModels = overview.value.primary_models || []
  if (!selectedPlatformSlug.value || !primaryModels.length) {
    comparisonRows.value = []
    return
  }

  const settled = await Promise.allSettled(
    primaryModels.map(async (model) => {
      const response = await aiPriceHubApi.getComparison(
        model.id,
        selectedPlatformSlug.value
      )
      const payload = extractResponseData(response)
      const comparisonByVendor = {}
      ;(payload.comparisons || []).forEach((item) => {
        comparisonByVendor[vendorKey(item.vendor_slug, item.vendor_name)] = item
      })
      return {
        primary_model: payload.primary_model || model,
        comparisons: payload.comparisons || [],
        comparison_by_vendor: comparisonByVendor
      }
    })
  )

  comparisonRows.value = settled
    .map((result, index) => {
      if (result.status === 'fulfilled') {
        return result.value
      }
      const primaryModel = primaryModels[index]
      return {
        primary_model: primaryModel,
        comparisons: [],
        comparison_by_vendor: {}
      }
    })
    .sort((left, right) =>
      String(left.primary_model.name).localeCompare(
        String(right.primary_model.name)
      )
    )
}

async function bootstrap() {
  loading.value = true
  error.value = ''
  try {
    const response = await aiPriceHubApi.getOverview(selectedPlatformSlug.value)
    overview.value = extractResponseData(response)
    if (
      !selectedPlatformSlug.value ||
      !primarySources.value.some(
        (item) => item.platform_slug === selectedPlatformSlug.value
      )
    ) {
      selectedPlatformSlug.value =
        overview.value.selected_platform_slug ||
        primarySources.value[0]?.platform_slug ||
        ''
    }
    await loadAllComparisons()
  } catch (err) {
    comparisonRows.value = []
    error.value = extractErrorMessage(err, t('aiPriceHub.errors.loadOverview'))
  } finally {
    loading.value = false
  }
}

async function selectPlatform(platformSlug) {
  if (platformSlug === selectedPlatformSlug.value) {
    platformOpen.value = false
    return
  }
  selectedPlatformSlug.value = platformSlug
  platformOpen.value = false
  await bootstrap()
}

function platformOptionLabel(platform) {
  return platformLabel(platform)
}

function handleClickOutside(event) {
  if (
    platformDropdownRef.value &&
    !platformDropdownRef.value.contains(event.target)
  ) {
    platformOpen.value = false
  }
}

onMounted(bootstrap)
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})
onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

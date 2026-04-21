<template>
  <AppLayout>
    <div class="w-full max-w-full p-6 space-y-6">
      <OneProPageHeader
        :eyebrow="t('hyperbdrMonitor.hostsPage.eyebrow')"
        :title="t('hyperbdrMonitor.hostsPage.title')"
        :subtitle="t('hyperbdrMonitor.hostsPage.subtitle')"
        :scope-hint="t('hyperbdrMonitor.hostsPage.scopeHint')"
      >
        <template #summary>
          <div class="xl:col-span-full">
            <div
              class="rounded-[28px] border border-gray-200/80 bg-white/70 p-2 shadow-[0_18px_40px_-30px_rgba(15,23,42,0.28)] backdrop-blur-sm"
            >
              <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <article
                  class="rounded-2xl border border-slate-200 bg-slate-50/80 px-5 py-4 shadow-[0_14px_34px_-24px_rgba(15,23,42,0.28)]"
                >
                  <p
                    class="text-[11px] font-medium uppercase tracking-[0.2em] text-slate-600/80"
                  >
                    {{ t('hyperbdrMonitor.hostsPage.resultsTitle') }}
                  </p>
                  <p
                    class="mt-3 text-3xl font-semibold tracking-tight text-gray-950"
                  >
                    {{ hostSummary.total }}
                  </p>
                  <p class="mt-2 text-sm leading-6 text-gray-500">
                    {{ t('hyperbdrMonitor.hostsPage.totalSubtitle') }}
                  </p>
                </article>
                <article
                  class="cursor-pointer rounded-2xl border border-emerald-100 bg-[linear-gradient(145deg,rgba(236,253,245,0.96),rgba(209,250,229,0.6))] px-5 py-4 shadow-[0_14px_34px_-24px_rgba(16,185,129,0.34)] transition hover:-translate-y-0.5 hover:border-emerald-200"
                  @click="
                    applyQuickFilter({
                      healthScope: 'healthy',
                      hasError: '',
                      licenseValid: ''
                    })
                  "
                >
                  <p
                    class="text-[11px] font-medium uppercase tracking-[0.2em] text-emerald-700/70"
                  >
                    {{ t('hyperbdrMonitor.hostsPage.healthyTitle') }}
                  </p>
                  <p
                    class="mt-3 text-3xl font-semibold tracking-tight text-gray-950"
                  >
                    {{ hostSummary.healthy }}
                  </p>
                  <p class="mt-2 text-sm leading-6 text-gray-500">
                    {{ t('hyperbdrMonitor.hostsPage.healthySubtitle') }}
                  </p>
                </article>
                <article
                  class="cursor-pointer rounded-2xl border border-amber-100 bg-[linear-gradient(145deg,rgba(255,251,235,0.96),rgba(254,240,138,0.16))] px-5 py-4 shadow-[0_14px_34px_-24px_rgba(245,158,11,0.34)] transition hover:-translate-y-0.5 hover:border-amber-200"
                  @click="
                    applyQuickFilter({
                      hasError: 'true',
                      healthScope: '',
                      licenseValid: ''
                    })
                  "
                >
                  <p
                    class="text-[11px] font-medium uppercase tracking-[0.2em] text-amber-700/75"
                  >
                    {{ t('hyperbdrMonitor.hostsPage.errorTitle') }}
                  </p>
                  <p
                    class="mt-3 text-3xl font-semibold tracking-tight text-gray-950"
                  >
                    {{ hostSummary.error }}
                  </p>
                  <p class="mt-2 text-sm leading-6 text-gray-500">
                    {{ t('hyperbdrMonitor.hostsPage.errorSubtitle') }}
                  </p>
                </article>
                <article
                  class="cursor-pointer rounded-2xl border border-rose-100 bg-[linear-gradient(145deg,rgba(255,241,242,0.96),rgba(254,205,211,0.4))] px-5 py-4 shadow-[0_14px_34px_-24px_rgba(244,63,94,0.3)] transition hover:-translate-y-0.5 hover:border-rose-200"
                  @click="
                    applyQuickFilter({
                      licenseValid: 'false',
                      healthScope: '',
                      hasError: ''
                    })
                  "
                >
                  <p
                    class="text-[11px] font-medium uppercase tracking-[0.2em] text-rose-700/75"
                  >
                    {{ t('hyperbdrMonitor.hostsPage.invalidLicenseTitle') }}
                  </p>
                  <p
                    class="mt-3 text-3xl font-semibold tracking-tight text-gray-950"
                  >
                    {{ hostSummary.invalidLicense }}
                  </p>
                  <p class="mt-2 text-sm leading-6 text-gray-500">
                    {{ t('hyperbdrMonitor.hostsPage.invalidLicenseSubtitle') }}
                  </p>
                </article>
              </div>
              <div
                class="mt-3 flex items-center justify-between gap-3 rounded-2xl border border-emerald-100 bg-emerald-50/65 px-4 py-3 text-sm text-emerald-900/85"
              >
                <div class="flex items-center gap-2">
                  <span class="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                  <span>{{ t('hyperbdrMonitor.hostsPage.summaryHint') }}</span>
                </div>
                <span
                  class="hidden rounded-full bg-white/80 px-3 py-1 text-xs font-medium text-emerald-700 md:inline-flex"
                >
                  {{
                    selectedDataSourceName ||
                    t('hyperbdrMonitor.labels.allDataSources')
                  }}
                </span>
              </div>
            </div>
          </div>
        </template>
      </OneProPageHeader>

      <section class="rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div class="border-b border-gray-200 px-6 py-5">
          <div
            class="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between"
          >
            <div>
              <h2 class="text-lg font-semibold text-gray-900">
                {{ t('hyperbdrMonitor.hostsPage.filtersTitle') }}
              </h2>
              <p class="mt-1 text-sm text-gray-500">
                {{ t('hyperbdrMonitor.hostsPage.filtersSubtitle') }}
              </p>
            </div>
            <div class="flex items-center gap-3">
              <p class="text-sm text-gray-500">
                {{
                  t('hyperbdrMonitor.hostsPage.showingCount', {
                    count: totalHosts
                  })
                }}
              </p>
              <div class="relative">
                <BaseButton
                  variant="outline"
                  size="sm"
                  :loading="Boolean(exportingScope)"
                  @click="exportMenuOpen = !exportMenuOpen"
                >
                  {{ t('common.export') }}
                </BaseButton>
                <div
                  v-if="exportMenuOpen"
                  class="absolute right-0 top-full z-20 mt-2 w-64 rounded-2xl border border-gray-200 bg-white p-2 shadow-xl"
                >
                  <p
                    class="px-3 pb-2 pt-1 text-xs font-medium uppercase tracking-[0.18em] text-gray-500"
                  >
                    {{ t('hyperbdrMonitor.hostsPage.exportTitle') }}
                  </p>
                  <button
                    type="button"
                    class="flex w-full flex-col rounded-xl px-3 py-3 text-left transition hover:bg-gray-50"
                    @click="exportHosts('filtered')"
                  >
                    <span class="text-sm font-medium text-gray-900">
                      {{ t('hyperbdrMonitor.hostsPage.exportScopes.filtered') }}
                    </span>
                    <span class="mt-1 text-xs leading-5 text-gray-500">
                      {{
                        t('hyperbdrMonitor.hostsPage.exportScopes.filteredHint')
                      }}
                    </span>
                  </button>
                  <button
                    type="button"
                    class="flex w-full flex-col rounded-xl px-3 py-3 text-left transition hover:bg-gray-50"
                    @click="exportHosts('data_source_all')"
                  >
                    <span class="text-sm font-medium text-gray-900">
                      {{
                        t(
                          'hyperbdrMonitor.hostsPage.exportScopes.dataSourceAll'
                        )
                      }}
                    </span>
                    <span class="mt-1 text-xs leading-5 text-gray-500">
                      {{
                        t(
                          'hyperbdrMonitor.hostsPage.exportScopes.dataSourceAllHint'
                        )
                      }}
                    </span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="px-6 py-5">
          <div
            class="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.2fr)_220px_220px_auto]"
          >
            <label class="block">
              <span
                class="mb-2 block text-xs font-medium uppercase tracking-[0.18em] text-gray-500"
              >
                {{ t('hyperbdrMonitor.hostsPage.searchLabel') }}
              </span>
              <input
                v-model="filters.name"
                class="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 outline-none transition focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
                :placeholder="t('hyperbdrMonitor.hostsPage.searchPlaceholder')"
                @keyup.enter="applyFilters"
              />
            </label>

            <label class="block">
              <span
                class="mb-2 block text-xs font-medium uppercase tracking-[0.18em] text-gray-500"
              >
                {{ t('hyperbdrMonitor.hostsPage.taskStatusLabel') }}
              </span>
              <select
                v-model="filters.status"
                class="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 outline-none transition focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
              >
                <option value="">
                  {{ t('hyperbdrMonitor.hostsPage.statusPlaceholder') }}
                </option>
                <option
                  v-for="option in taskStatusFilterOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </label>

            <label class="block">
              <span
                class="mb-2 block text-xs font-medium uppercase tracking-[0.18em] text-gray-500"
              >
                {{ t('hyperbdrMonitor.labels.authorization') }}
              </span>
              <select
                v-model="filters.licenseValid"
                class="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-900 outline-none transition focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
              >
                <option value="">
                  {{ t('hyperbdrMonitor.hostsPage.authorizationPlaceholder') }}
                </option>
                <option value="true">
                  {{ t('hyperbdrMonitor.labels.valid') }}
                </option>
                <option value="false">
                  {{ t('hyperbdrMonitor.labels.invalid') }}
                </option>
              </select>
            </label>

            <div class="flex items-end gap-3">
              <BaseButton variant="outline" @click="resetFilters">
                {{ t('hyperbdrMonitor.actions.reset') }}
              </BaseButton>
              <BaseButton :loading="loading" @click="applyFilters">
                {{ t('hyperbdrMonitor.actions.filter') }}
              </BaseButton>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap items-center gap-2">
            <span class="text-sm font-medium text-gray-500">{{
              t('hyperbdrMonitor.hostsPage.activeFilters')
            }}</span>
            <template v-if="activeFilters.length > 0">
              <span
                v-for="filter in activeFilters"
                :key="filter.key"
                class="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-medium text-gray-700"
              >
                {{ filter.label }}: {{ filter.value }}
              </span>
            </template>
            <span
              v-else
              class="inline-flex items-center rounded-full border border-dashed border-gray-200 px-3 py-1 text-xs text-gray-400"
            >
              {{ t('hyperbdrMonitor.hostsPage.noActiveFilters') }}
            </span>
          </div>
        </div>
      </section>

      <section
        class="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm"
      >
        <div class="border-b border-gray-200 px-6 py-5">
          <div
            class="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between"
          >
            <div>
              <h2 class="text-lg font-semibold text-gray-900">
                {{ t('hyperbdrMonitor.hostsPage.listTitle') }}
              </h2>
              <p class="mt-1 text-sm text-gray-500">
                {{ t('hyperbdrMonitor.hostsPage.listSubtitle') }}
              </p>
            </div>
            <p class="text-sm text-gray-500">
              {{
                t('hyperbdrMonitor.hostsPage.showingCount', {
                  count: totalHosts
                })
              }}
            </p>
          </div>
        </div>

        <BaseLoading v-if="loading && hosts.length === 0" class="py-12" />

        <div v-else class="overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50/90">
              <tr>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.host') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.tenant') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.hostStatus') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.bootStatus') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.healthStatus') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.system') }} /
                  {{ t('hyperbdrMonitor.labels.resources') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.authorization') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.errorSummary') }}
                </th>
                <th
                  class="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {{ t('hyperbdrMonitor.labels.actions') }}
                </th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 bg-white">
              <tr
                v-for="host in hosts"
                :key="`${host.data_source_id}-${host.id}`"
                class="align-top transition hover:bg-gray-50/70"
              >
                <td class="px-6 py-4 text-sm text-gray-900">
                  <div class="min-w-[220px]">
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="font-semibold text-gray-900">{{
                        host.name || '-'
                      }}</span>
                      <span
                        class="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-medium text-sky-700"
                      >
                        {{
                          host.data_source_name ||
                          t('hyperbdrMonitor.labels.dataSource')
                        }}
                      </span>
                    </div>
                    <div
                      class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500"
                    >
                      <span>ID: {{ host.id || '-' }}</span>
                      <span
                        >{{ t('hyperbdrMonitor.labels.lastCollected') }}:
                        {{ formatDateTime(host.last_collected_at) }}</span
                      >
                    </div>
                  </div>
                </td>

                <td class="px-6 py-4 text-sm text-gray-600">
                  <div class="min-w-[180px]">
                    <div class="font-medium text-gray-900">
                      {{ host.tenant_name || '-' }}
                    </div>
                    <div class="mt-2 text-xs text-gray-500">
                      {{
                        host.data_source_name ||
                        t('hyperbdrMonitor.labels.dataSource')
                      }}
                    </div>
                  </div>
                </td>

                <td class="px-6 py-4 text-sm">
                  <span
                    class="inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium leading-none"
                    :class="oneProHostStatusClass(host.status)"
                  >
                    {{ oneProHostStatusLabel(host.status, t) }}
                  </span>
                </td>

                <td class="px-6 py-4 text-sm">
                  <span
                    class="inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium leading-none"
                    :class="oneProBootStatusClass(host.boot_status)"
                  >
                    {{ oneProBootStatusLabel(host.boot_status, t) }}
                  </span>
                </td>

                <td class="px-6 py-4 text-sm">
                  <span
                    class="inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium leading-none"
                    :class="oneProHealthStatusClass(host.health_status)"
                  >
                    {{ oneProHealthStatusLabel(host.health_status, t) }}
                  </span>
                </td>

                <td class="px-6 py-4 text-sm text-gray-600">
                  <div class="min-w-[180px] space-y-2">
                    <div>
                      <div class="font-medium text-gray-900">
                        {{ host.os_type || '-' }}
                      </div>
                      <div class="mt-1 text-xs text-gray-500">
                        {{ host.host_type || '-' }}
                      </div>
                    </div>
                    <div class="flex flex-wrap gap-2 text-xs text-gray-500">
                      <span
                        class="inline-flex items-center rounded-md bg-gray-100 px-2 py-1"
                        >CPU {{ host.cpu_num || 0 }}</span
                      >
                      <span
                        class="inline-flex items-center rounded-md bg-gray-100 px-2 py-1"
                        >RAM {{ host.ram_size || 0 }} GB</span
                      >
                    </div>
                  </div>
                </td>

                <td class="px-6 py-4 text-sm">
                  <span
                    class="inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium leading-none"
                    :class="
                      host.license_valid
                        ? 'bg-green-100 text-green-700 border-green-200'
                        : 'bg-red-100 text-red-700 border-red-200'
                    "
                  >
                    {{
                      host.license_valid
                        ? t('hyperbdrMonitor.labels.valid')
                        : t('hyperbdrMonitor.labels.invalid')
                    }}
                  </span>
                </td>

                <td class="px-6 py-4 text-sm text-gray-600">
                  <div
                    v-if="host.error_message"
                    class="max-w-[240px] rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900"
                    :title="host.error_message"
                  >
                    <span class="block truncate">{{
                      summarizeError(host.error_message)
                    }}</span>
                  </div>
                  <span
                    v-else
                    class="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs text-gray-400"
                  >
                    {{ t('hyperbdrMonitor.hostsPage.noError') }}
                  </span>
                </td>

                <td class="px-6 py-4 text-sm">
                  <BaseButton
                    size="sm"
                    variant="outline"
                    @click="openHostDetail(host)"
                  >
                    {{ t('hyperbdrMonitor.actions.detail') }}
                  </BaseButton>
                </td>
              </tr>
              <tr v-if="hosts.length === 0">
                <td
                  colspan="9"
                  class="px-6 py-14 text-center text-sm text-gray-500"
                >
                  {{ t('hyperbdrMonitor.hostsPage.empty') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="border-t border-gray-200 px-6 py-4">
          <div
            class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between"
          >
            <div
              class="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4"
            >
              <div class="text-sm text-gray-700">
                <span v-if="totalCount > 0">
                  {{
                    t('common.pagination.showing', {
                      from: displayFrom,
                      to: displayTo,
                      total: totalCount
                    })
                  }}
                </span>
                <span v-else class="text-gray-500">
                  {{ t('common.noData') }}
                </span>
              </div>

              <div class="flex items-center gap-2">
                <label class="text-sm text-gray-700">
                  {{ t('common.pagination.itemsPerPage') }}:
                </label>
                <select
                  v-model.number="pageSize"
                  class="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900"
                  @change="handlePageSizeChange"
                >
                  <option :value="20">20</option>
                  <option :value="50">50</option>
                  <option :value="100">100</option>
                </select>
              </div>
            </div>

            <div class="flex items-center gap-3">
              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage <= 1 || loading"
                @click="handlePageChange(currentPage - 1)"
              >
                {{ t('common.previous') }}
              </BaseButton>

              <span
                class="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm font-medium text-gray-700"
              >
                {{
                  t('common.pagination.page', {
                    current: currentPage,
                    total: totalPages
                  })
                }}
              </span>

              <BaseButton
                variant="outline"
                size="sm"
                :disabled="currentPage >= totalPages || loading"
                @click="handlePageChange(currentPage + 1)"
              >
                {{ t('common.next') }}
              </BaseButton>
            </div>
          </div>
        </div>
      </section>

      <BaseModal
        :show="detailVisible"
        :title="
          selectedHost?.name || t('hyperbdrMonitor.hostsPage.detailTitle')
        "
        @close="closeHostDetail"
      >
        <div v-if="selectedHost" class="space-y-6">
          <div>
            <p class="text-sm text-gray-500">
              {{ t('hyperbdrMonitor.hostsPage.detailSubtitle') }}
            </p>
          </div>

          <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <section class="rounded-xl border border-gray-200 bg-gray-50 p-4">
              <h2 class="text-sm font-semibold text-gray-900">
                {{ t('hyperbdrMonitor.hostsPage.sections.basic') }}
              </h2>
              <dl class="mt-4 space-y-3 text-sm">
                <div class="flex justify-between gap-4">
                  <dt class="text-gray-500">
                    {{ t('hyperbdrMonitor.labels.hostId') }}
                  </dt>
                  <dd class="break-all text-right font-medium text-gray-900">
                    {{ selectedHost.id || '-' }}
                  </dd>
                </div>
                <div class="flex justify-between gap-4">
                  <dt class="text-gray-500">
                    {{ t('hyperbdrMonitor.labels.tenant') }}
                  </dt>
                  <dd class="text-right text-gray-900">
                    {{ selectedHost.tenant_name || '-' }}
                  </dd>
                </div>
                <div class="flex justify-between gap-4">
                  <dt class="text-gray-500">
                    {{ t('hyperbdrMonitor.labels.dataSource') }}
                  </dt>
                  <dd class="text-right text-gray-900">
                    {{ selectedHost.data_source_name || '-' }}
                  </dd>
                </div>
                <div class="flex justify-between gap-4">
                  <dt class="text-gray-500">
                    {{ t('hyperbdrMonitor.labels.system') }}
                  </dt>
                  <dd class="text-right text-gray-900">
                    {{ selectedHost.os_type || '-' }} /
                    {{ selectedHost.host_type || '-' }}
                  </dd>
                </div>
                <div class="flex justify-between gap-4">
                  <dt class="text-gray-500">
                    {{ t('hyperbdrMonitor.labels.lastCollected') }}
                  </dt>
                  <dd class="text-right text-gray-900">
                    {{ formatDateTime(selectedHost.last_collected_at) }}
                  </dd>
                </div>
              </dl>
            </section>

            <section class="rounded-xl border border-gray-200 bg-gray-50 p-4">
              <h2 class="text-sm font-semibold text-gray-900">
                {{ t('hyperbdrMonitor.hostsPage.sections.runtime') }}
              </h2>
              <dl class="mt-4 space-y-3 text-sm">
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-gray-500">
                    {{ t('hyperbdrMonitor.labels.hostStatus') }}
                  </dt>
                  <dd>
                    <span
                      class="inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium leading-none"
                      :class="oneProHostStatusClass(selectedHost.status)"
                    >
                      {{ oneProHostStatusLabel(selectedHost.status, t) }}
                    </span>
                  </dd>
                </div>
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-gray-500">
                    {{ t('hyperbdrMonitor.labels.bootStatus') }}
                  </dt>
                  <dd>
                    <span
                      class="inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium leading-none"
                      :class="oneProBootStatusClass(selectedHost.boot_status)"
                    >
                      {{ oneProBootStatusLabel(selectedHost.boot_status, t) }}
                    </span>
                  </dd>
                </div>
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-gray-500">
                    {{ t('hyperbdrMonitor.labels.healthStatus') }}
                  </dt>
                  <dd>
                    <span
                      class="inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium leading-none"
                      :class="
                        oneProHealthStatusClass(selectedHost.health_status)
                      "
                    >
                      {{
                        oneProHealthStatusLabel(selectedHost.health_status, t)
                      }}
                    </span>
                  </dd>
                </div>
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-gray-500">
                    {{ t('hyperbdrMonitor.labels.taskStatus') }}
                  </dt>
                  <dd>
                    <span
                      class="inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium leading-none"
                      :class="derivedTaskStatusClass(selectedHost.status)"
                    >
                      {{ derivedTaskStatusLabel(selectedHost.status) }}
                    </span>
                  </dd>
                </div>
              </dl>
            </section>
          </div>

          <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <section class="rounded-xl border border-gray-200 bg-gray-50 p-4">
              <h2 class="text-sm font-semibold text-gray-900">
                {{ t('hyperbdrMonitor.hostsPage.sections.resources') }}
              </h2>
              <dl class="mt-4 space-y-3 text-sm">
                <div class="flex justify-between gap-4">
                  <dt class="text-gray-500">CPU</dt>
                  <dd class="text-right text-gray-900">
                    {{ selectedHost.cpu_num || 0 }}
                  </dd>
                </div>
                <div class="flex justify-between gap-4">
                  <dt class="text-gray-500">RAM</dt>
                  <dd class="text-right text-gray-900">
                    {{ selectedHost.ram_size || 0 }} GB
                  </dd>
                </div>
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-gray-500">
                    {{ t('hyperbdrMonitor.labels.authorization') }}
                  </dt>
                  <dd>
                    <span
                      class="inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium leading-none"
                      :class="
                        selectedHost.license_valid
                          ? 'bg-green-100 text-green-700 border-green-200'
                          : 'bg-red-100 text-red-700 border-red-200'
                      "
                    >
                      {{
                        selectedHost.license_valid
                          ? t('hyperbdrMonitor.labels.valid')
                          : t('hyperbdrMonitor.labels.invalid')
                      }}
                    </span>
                  </dd>
                </div>
              </dl>
            </section>

            <section class="rounded-xl border border-gray-200 bg-gray-50 p-4">
              <h2 class="text-sm font-semibold text-gray-900">
                {{ t('hyperbdrMonitor.hostsPage.sections.error') }}
              </h2>
              <div
                class="mt-4 min-h-[140px] whitespace-pre-wrap break-words rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-700"
              >
                {{
                  selectedHost.error_message ||
                  t('hyperbdrMonitor.hostsPage.noError')
                }}
              </div>
            </section>
          </div>
        </div>
      </BaseModal>
    </div>
  </AppLayout>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'

import { oneproMonitorApi } from '@/api/oneproMonitor'
import AppLayout from '@/components/layout/AppLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseModal from '@/components/ui/BaseModal.vue'
import { useToast } from '@/composables/useToast'

import OneProPageHeader from './OneProPageHeader.vue'
import {
  formatDateTime,
  oneProBootStatusClass,
  oneProBootStatusLabel,
  oneProHealthStatusClass,
  oneProHealthStatusLabel,
  oneProHostStatusClass,
  oneProHostStatusLabel,
  unwrap
} from './shared'
import { useOneProDataSourceScope } from './useOneProDataSourceScope'

const { t } = useI18n()
const { showError } = useToast()
const route = useRoute()
const router = useRouter()
const {
  selectedDataSource,
  selectedDataSourceName,
  loadDataSources,
  appendDataSourceScope
} = useOneProDataSourceScope()

const loading = ref(false)
const exportMenuOpen = ref(false)
const exportingScope = ref('')
const hosts = ref([])
const hostSummary = ref({
  total: 0,
  healthy: 0,
  error: 0,
  invalidLicense: 0
})
const detailVisible = ref(false)
const selectedHost = ref(null)
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)
const filters = ref({
  name: '',
  status: '',
  healthScope: '',
  licenseValid: '',
  hasError: ''
})

const totalHosts = computed(() => totalCount.value)
const totalPages = computed(() =>
  Math.max(1, Math.ceil(totalCount.value / pageSize.value))
)
const displayFrom = computed(() =>
  totalCount.value === 0 ? 0 : (currentPage.value - 1) * pageSize.value + 1
)
const displayTo = computed(() =>
  Math.min(currentPage.value * pageSize.value, totalCount.value)
)

const activeFilters = computed(() => {
  const entries = []

  if (filters.value.name) {
    entries.push({
      key: 'name',
      label: t('hyperbdrMonitor.hostsPage.searchLabel'),
      value: filters.value.name
    })
  }

  if (filters.value.status) {
    entries.push({
      key: 'status',
      label: t('hyperbdrMonitor.hostsPage.taskStatusLabel'),
      value: taskStatusFilterLabel(filters.value.status)
    })
  }

  if (filters.value.healthScope) {
    entries.push({
      key: 'health_scope',
      label: t('hyperbdrMonitor.labels.healthStatus'),
      value: t(
        `hyperbdrMonitor.hostsPage.quickScopes.${filters.value.healthScope}`
      )
    })
  }

  if (
    filters.value.licenseValid === 'true' ||
    filters.value.licenseValid === 'false'
  ) {
    entries.push({
      key: 'license_valid',
      label: t('hyperbdrMonitor.labels.authorization'),
      value:
        filters.value.licenseValid === 'true'
          ? t('hyperbdrMonitor.labels.valid')
          : t('hyperbdrMonitor.labels.invalid')
    })
  }

  if (filters.value.hasError === 'true') {
    entries.push({
      key: 'has_error',
      label: t('hyperbdrMonitor.labels.errorSummary'),
      value: t('hyperbdrMonitor.hostsPage.quickScopes.hasError')
    })
  }

  if (selectedDataSource.value) {
    entries.push({
      key: 'data_source_id',
      label: t('hyperbdrMonitor.hostsPage.dataSourceLabel'),
      value: selectedDataSourceName.value || selectedDataSource.value
    })
  }

  return entries
})

const hostTaskStatusMap = {
  sync_snapshot_done: {
    label: 'completed',
    className: 'bg-green-100 text-green-700 border-green-200'
  },
  host_register_done: {
    label: 'completed',
    className: 'bg-green-100 text-green-700 border-green-200'
  },
  boot_done: {
    label: 'completed',
    className: 'bg-green-100 text-green-700 border-green-200'
  },
  clean_done: {
    label: 'completed',
    className: 'bg-green-100 text-green-700 border-green-200'
  },
  sync_failed: {
    label: 'failed',
    className: 'bg-red-100 text-red-700 border-red-200'
  },
  clean_failed: {
    label: 'failed',
    className: 'bg-red-100 text-red-700 border-red-200'
  },
  boot_failed: {
    label: 'failed',
    className: 'bg-red-100 text-red-700 border-red-200'
  },
  sync_doing: {
    label: 'processing',
    className: 'bg-amber-100 text-amber-700 border-amber-200'
  },
  clean_doing: {
    label: 'processing',
    className: 'bg-amber-100 text-amber-700 border-amber-200'
  },
  boot_doing: {
    label: 'processing',
    className: 'bg-amber-100 text-amber-700 border-amber-200'
  },
  sync_queued: {
    label: 'pending',
    className: 'bg-amber-100 text-amber-700 border-amber-200'
  },
  sync_stopped: {
    label: 'stopped',
    className: 'bg-gray-100 text-gray-700 border-gray-200'
  }
}

const taskStatusFilterOptions = computed(() => [
  {
    value: 'completed',
    label: t('hyperbdrMonitor.hostsPage.taskStatus.completed')
  },
  { value: 'failed', label: t('hyperbdrMonitor.hostsPage.taskStatus.failed') },
  {
    value: 'processing',
    label: t('hyperbdrMonitor.hostsPage.taskStatus.processing')
  }
])

function taskStatusFilterLabel(value) {
  return t(`hyperbdrMonitor.hostsPage.taskStatus.${value}`)
}

function derivedTaskStatusLabel(status) {
  const normalized =
    hostTaskStatusMap[String(status || '').toLowerCase()]?.label || 'unknown'
  return taskStatusFilterLabel(normalized)
}

function derivedTaskStatusClass(status) {
  return (
    hostTaskStatusMap[String(status || '').toLowerCase()]?.className ||
    'bg-gray-100 text-gray-700 border-gray-200'
  )
}

function summarizeError(message) {
  return String(message || '')
    .replace(/\s+/g, ' ')
    .trim()
}

function openHostDetail(host) {
  selectedHost.value = host
  detailVisible.value = true
}

function closeHostDetail() {
  detailVisible.value = false
  selectedHost.value = null
}

function resetFilters() {
  filters.value = {
    name: '',
    status: '',
    healthScope: '',
    licenseValid: '',
    hasError: ''
  }
  currentPage.value = 1
  router.replace({ query: {} })
  loadHosts()
}

function applyQuickFilter({ healthScope, licenseValid, hasError }) {
  filters.value = {
    name: '',
    status: '',
    healthScope: healthScope ?? '',
    licenseValid: licenseValid ?? '',
    hasError: hasError ?? ''
  }
  currentPage.value = 1
  loadHosts()
}

function applyFilters() {
  currentPage.value = 1
  loadHosts()
}

function handlePageChange(page) {
  if (page < 1 || page > totalPages.value || loading.value) return
  currentPage.value = page
  loadHosts()
}

function handlePageSizeChange() {
  currentPage.value = 1
  loadHosts()
}

async function loadHosts() {
  loading.value = true
  try {
    const response = await oneproMonitorApi.hosts.list(
      appendDataSourceScope({
        skip: (currentPage.value - 1) * pageSize.value,
        limit: pageSize.value,
        name: filters.value.name || undefined,
        task_status: filters.value.status || undefined,
        health_scope: filters.value.healthScope || undefined,
        license_valid: filters.value.licenseValid || undefined,
        has_error: filters.value.hasError || undefined
      })
    )
    const payload = unwrap(response)
    hosts.value = payload.items || []
    totalCount.value = Number(payload.total || 0)
    hostSummary.value = {
      total: Number(payload.summary?.total || payload.total || 0),
      healthy: Number(payload.summary?.healthy || 0),
      error: Number(payload.summary?.error || 0),
      invalidLicense: Number(payload.summary?.invalid_license || 0)
    }
    if (totalCount.value > 0 && currentPage.value > totalPages.value) {
      currentPage.value = totalPages.value
      await loadHosts()
      return
    }
  } catch (error) {
    showError(
      error?.response?.data?.detail || t('hyperbdrMonitor.hostsPage.loadError')
    )
  } finally {
    loading.value = false
  }
}

function buildExportParams(scope) {
  const params = appendDataSourceScope({
    scope,
    name: filters.value.name || undefined,
    task_status: filters.value.status || undefined,
    health_scope: filters.value.healthScope || undefined,
    license_valid: filters.value.licenseValid || undefined,
    has_error: filters.value.hasError || undefined
  })

  if (typeof route.query.tenant_id === 'string' && route.query.tenant_id) {
    params.tenant_id = route.query.tenant_id
  }

  return params
}

async function exportHosts(scope) {
  exportingScope.value = scope
  try {
    await oneproMonitorApi.hosts.export(buildExportParams(scope))
    exportMenuOpen.value = false
  } catch (error) {
    showError(
      error?.response?.data?.detail ||
        t('hyperbdrMonitor.hostsPage.exportError')
    )
  } finally {
    exportingScope.value = ''
  }
}

function syncFiltersFromRoute() {
  filters.value = {
    name: typeof route.query.name === 'string' ? route.query.name : '',
    status:
      typeof route.query.task_status === 'string'
        ? route.query.task_status
        : '',
    healthScope:
      typeof route.query.health_scope === 'string'
        ? route.query.health_scope
        : '',
    licenseValid:
      route.query.license_valid === 'true' ||
      route.query.license_valid === 'false'
        ? route.query.license_valid
        : '',
    hasError:
      route.query.has_error === 'true' || route.query.has_error === 'false'
        ? route.query.has_error
        : ''
  }
}

onMounted(async () => {
  await loadDataSources()
  syncFiltersFromRoute()
  await loadHosts()
})

watch(selectedDataSource, () => {
  currentPage.value = 1
  exportMenuOpen.value = false
  loadHosts()
})

watch(
  () => route.query,
  () => {
    syncFiltersFromRoute()
    currentPage.value = 1
    exportMenuOpen.value = false
    loadHosts()
  }
)
</script>

<template>
  <div class="p-6">
    <!-- Toolbar -->
    <div
      class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6"
    >
      <!-- Batch Actions (Left) -->
      <div class="flex items-center gap-2 flex-wrap">
        <BaseButton
          v-if="selectedArticles.length > 0"
          variant="outline"
          size="sm"
          @click="handleBatchRetry"
          class="shadow-sm"
        >
          {{ t('articles.batchRetry') }} ({{ selectedArticles.length }})
        </BaseButton>
        <BaseButton
          v-if="selectedArticles.length > 0"
          variant="danger"
          size="sm"
          @click="handleBatchDelete"
          class="shadow-sm"
        >
          {{ t('articles.batchDelete') }} ({{ selectedArticles.length }})
        </BaseButton>
      </div>

      <!-- Search and Filter (Right) -->
      <div class="flex items-center gap-3 w-full sm:w-auto">
        <BaseInput
          v-model="searchQuery"
          :placeholder="t('articles.searchPlaceholder')"
          class="flex-1 sm:w-64"
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

        <!-- Filter Button -->
        <BaseButton
          variant="outline"
          size="sm"
          @click="showFilterDrawer = true"
          class="relative flex items-center gap-2 shadow-sm hover:shadow-md transition-shadow"
        >
          <svg
            class="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"
            />
          </svg>
          {{ t('common.filter') }}
          <span
            v-if="activeFilterCount > 0"
            class="absolute -top-1 -right-1 flex items-center justify-center w-5 h-5 text-xs font-medium text-white bg-primary-600 rounded-full"
          >
            {{ activeFilterCount }}
          </span>
        </BaseButton>

        <BaseButton
          variant="outline"
          size="sm"
          :loading="loading"
          @click="handleRefresh"
          :title="t('common.refresh')"
          class="flex items-center gap-1 shadow-sm hover:shadow-md transition-shadow"
        >
          <svg
            v-if="!props.loading"
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
    </div>

    <!-- Active Filter Tags -->
    <div
      v-if="activeFilterCount > 0"
      class="flex flex-wrap items-center gap-2 mb-4"
    >
      <span
        v-if="statusFilter"
        class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
      >
        <span
          >{{ t('articles.filter.status') }}:
          {{ getStatusLabel(statusFilter) }}</span
        >
        <button
          @click="removeStatusFilter"
          class="text-gray-500 hover:text-gray-700 transition-colors"
        >
          <svg
            class="w-4 h-4"
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
      </span>
      <span
        v-if="socialAccountFilter"
        class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
      >
        <span
          >{{ t('articles.filter.storageLocation') }}:
          {{ socialAccountFilter }}</span
        >
        <button
          @click="removeSocialAccountFilter"
          class="text-gray-500 hover:text-gray-700 transition-colors"
        >
          <svg
            class="w-4 h-4"
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
      </span>
    </div>

    <BaseLoading v-if="props.loading && props.articles.length === 0" />

    <div
      v-if="!props.loading && props.articles.length === 0"
      class="py-16 text-center rounded-lg border border-gray-200 bg-gray-50"
    >
      <svg
        class="mx-auto h-12 w-12 text-gray-400 mb-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <p class="text-sm font-medium text-gray-600">
        {{ t('articles.noArticles') }}
      </p>
    </div>

    <!-- Mobile Card View with Infinite Scroll -->
    <div
      v-if="!props.loading && props.articles.length > 0"
      class="md:hidden space-y-3"
    >
      <ArticleCard
        v-for="article in props.articles"
        :key="article.id"
        :article="article"
        :uploading="uploadingIds.includes(article.id)"
        :retrying="retryingIds.includes(article.id)"
        @preview="handlePreview"
        @upload="handleUpload"
        @retry="handleRetry"
        @delete="handleDelete"
      />

      <!-- Sentinel element for intersection observer - must always exist when hasMore -->
      <div
        v-if="hasMore"
        ref="sentinelElement"
        class="h-20 flex items-center justify-center"
      >
        <!-- Loading More Indicator (Auto-load when scrolling) -->
        <div v-if="props.loading || props.loadingMore" class="py-6">
          <BaseLoading inline size="sm" />
          <p class="text-sm text-gray-500 mt-2">
            {{ t('common.loadingMore') }}
          </p>
        </div>
      </div>

      <!-- No More Data -->
      <div
        v-if="!hasMore && props.articles.length > 0"
        class="py-6 text-center"
      >
        <p class="text-sm text-gray-400">{{ t('common.noMoreData') }}</p>
      </div>
    </div>

    <!-- Desktop Table View -->
    <div
      v-if="!props.loading && props.articles.length > 0"
      class="hidden md:block overflow-x-auto relative rounded-lg border border-gray-200 bg-white shadow-sm"
    >
      <!-- Loading overlay when data exists but is refreshing -->
      <div
        v-if="props.loading"
        class="absolute inset-0 bg-white bg-opacity-80 flex items-center justify-center z-10 rounded-lg backdrop-blur-sm"
      >
        <BaseLoading inline size="lg" variant="primary" :show-text="false" />
      </div>
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gradient-to-r from-gray-50 to-gray-100">
          <tr>
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
            >
              <input
                type="checkbox"
                :checked="allSelected"
                @change="handleSelectAll"
                class="w-4 h-4 rounded border-gray-300 bg-white text-primary-600 focus:ring-primary-500 focus:ring-2 cursor-pointer checked:bg-primary-600 checked:border-primary-600"
              />
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
            >
              {{ t('articles.articleTitle') }}
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
            >
              {{ t('articles.statusLabel') }}
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
            >
              {{ t('articles.storageLocation') }}
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
            >
              {{ t('articles.legality') }}
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
            >
              {{ t('articles.transformStatus') }}
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
            >
              {{ t('articles.uploadStatus') }}
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
            >
              {{ t('articles.publishStatus') }}
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
            >
              {{ t('articles.publishedAt') }}
            </th>
            <th
              class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
            >
              {{ t('articles.createdAt') }}
            </th>
            <th
              class="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider border-b border-gray-200"
            >
              {{ t('common.moreActions') }}
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-100">
          <tr
            v-for="article in props.articles"
            :key="article.id"
            :class="[
              'transition-colors duration-150',
              selectedArticles.includes(article.id)
                ? 'bg-primary-50 hover:bg-primary-100'
                : 'hover:bg-gray-50'
            ]"
          >
            <td class="px-4 py-4 whitespace-nowrap">
              <input
                type="checkbox"
                :checked="selectedArticles.includes(article.id)"
                @change="handleSelectArticle(article.id)"
                class="w-4 h-4 rounded border-gray-300 bg-white text-primary-600 focus:ring-primary-500 focus:ring-2 cursor-pointer checked:bg-primary-600 checked:border-primary-600"
              />
            </td>
            <td class="px-4 py-4">
              <button
                @click="handlePreview(article)"
                class="text-sm font-semibold text-gray-900 max-w-md truncate text-left hover:text-primary-600 transition-colors cursor-pointer block"
                :title="article.title"
              >
                {{ article.title }}
              </button>
              <div
                v-if="article.source_url"
                class="text-xs text-gray-500 truncate max-w-md mt-1.5"
              >
                <a
                  :href="article.source_url"
                  target="_blank"
                  class="hover:text-primary-600 hover:underline transition-colors inline-flex items-center gap-1"
                >
                  <svg
                    class="w-3 h-3 flex-shrink-0"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                    />
                  </svg>
                  <span class="truncate">{{ article.source_url }}</span>
                </a>
              </div>
            </td>
            <td class="px-4 py-4 whitespace-nowrap">
              <StatusBadge :status="mapArticleStatus(article.status)" />
            </td>
            <td class="px-4 py-4 whitespace-nowrap">
              <StorageLocationBadge :location="article.social_account" />
              <span v-if="!article.social_account" class="text-sm text-gray-500"
                >-</span
              >
            </td>
            <td class="px-4 py-4 whitespace-nowrap">
              <span
                v-if="article.is_illegal === true"
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800 border border-red-200 shadow-sm"
                :title="t('articles.illegalContent')"
              >
                <svg
                  class="w-3.5 h-3.5 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                {{ t('articles.illegal') }}
              </span>
              <span
                v-else
                class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200 shadow-sm"
                :title="t('articles.legalContent')"
              >
                <svg
                  class="w-3.5 h-3.5 flex-shrink-0"
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
                {{ t('articles.legal') }}
              </span>
            </td>
            <td class="px-4 py-4 whitespace-nowrap">
              <span
                :class="[
                  'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border shadow-sm',
                  article.is_transformed === true
                    ? 'bg-purple-100 text-purple-800 border-purple-200'
                    : 'bg-amber-100 text-amber-700 border-amber-200'
                ]"
                :title="
                  article.is_transformed === true
                    ? t('articles.transformed')
                    : t('articles.notTransformed')
                "
              >
                <svg
                  v-if="article.is_transformed === true"
                  class="w-3.5 h-3.5 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <svg
                  v-else
                  class="w-3.5 h-3.5 flex-shrink-0"
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
                {{
                  article.is_transformed === true
                    ? t('articles.transformed')
                    : t('articles.notTransformed')
                }}
              </span>
            </td>
            <td class="px-4 py-4 whitespace-nowrap">
              <span
                :class="[
                  'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border shadow-sm',
                  article.is_uploaded === true
                    ? 'bg-teal-100 text-teal-800 border-teal-200'
                    : 'bg-orange-100 text-orange-700 border-orange-200'
                ]"
                :title="
                  article.is_uploaded === true
                    ? t('articles.uploaded')
                    : t('articles.notUploaded')
                "
              >
                <svg
                  v-if="article.is_uploaded === true"
                  class="w-3.5 h-3.5 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z"
                  />
                </svg>
                <svg
                  v-else
                  class="w-3.5 h-3.5 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
                {{
                  article.is_uploaded === true
                    ? t('articles.uploaded')
                    : t('articles.notUploaded')
                }}
              </span>
            </td>
            <td class="px-4 py-4 whitespace-nowrap">
              <span
                :class="[
                  'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border shadow-sm',
                  article.is_published === true
                    ? 'bg-indigo-100 text-indigo-800 border-indigo-200'
                    : 'bg-slate-100 text-slate-600 border-slate-200'
                ]"
                :title="
                  article.is_published === true
                    ? t('articles.published')
                    : t('articles.notPublished')
                "
              >
                <svg
                  v-if="article.is_published === true"
                  class="w-3.5 h-3.5 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"
                  />
                </svg>
                <svg
                  v-else
                  class="w-3.5 h-3.5 flex-shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                  />
                </svg>
                {{
                  article.is_published === true
                    ? t('articles.published')
                    : t('articles.notPublished')
                }}
              </span>
            </td>
            <td class="px-4 py-4 whitespace-nowrap">
              <span class="text-sm text-gray-600 font-medium">
                {{ formatDate(article.published_at) }}
              </span>
            </td>
            <td class="px-4 py-4 whitespace-nowrap">
              <span class="text-sm text-gray-600 font-medium">
                {{ formatDate(article.created_at) }}
              </span>
            </td>
            <td class="px-4 py-4 whitespace-nowrap text-right">
              <div class="flex justify-end gap-2">
                <BaseButton
                  v-if="article.is_transformed"
                  :variant="article.is_uploaded ? 'outline' : 'primary'"
                  size="sm"
                  :loading="uploadingIds.includes(article.id)"
                  :disabled="uploadingIds.includes(article.id)"
                  @click="handleUpload(article)"
                >
                  {{
                    article.is_uploaded
                      ? t('articles.reupload')
                      : t('articles.upload')
                  }}
                </BaseButton>
                <BaseButton
                  v-if="
                    article.status === 'failed' ||
                    article.status === 'processing' ||
                    article.status === 'completed'
                  "
                  variant="outline"
                  size="sm"
                  :loading="retryingIds.includes(article.id)"
                  :disabled="retryingIds.includes(article.id)"
                  @click="handleRetry(article)"
                >
                  {{ t('common.tryAgain') }}
                </BaseButton>
                <BaseButton
                  variant="danger"
                  size="sm"
                  @click="handleDelete(article)"
                >
                  {{ t('common.delete') }}
                </BaseButton>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination (Desktop Only) -->
    <div
      class="hidden md:flex mt-6 pt-4 border-t border-gray-200 flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
    >
      <div class="flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <div class="text-sm text-gray-700 font-medium">
          <span v-if="totalCount > 0">
            {{
              t('common.pagination.showing', {
                from: (currentPage - 1) * pageSize + 1,
                to: Math.min(currentPage * pageSize, totalCount),
                total: totalCount
              })
            }}
          </span>
          <span v-else class="text-gray-500">
            {{ t('common.noData') }}
          </span>
        </div>
        <div class="flex items-center gap-2">
          <label class="text-sm text-gray-700 font-medium">
            {{ t('common.pagination.itemsPerPage') }}:
          </label>
          <select
            :value="String(pageSize)"
            @change="handlePageSizeChange"
            class="text-sm border border-gray-300 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 bg-white cursor-pointer shadow-sm hover:shadow-md transition-shadow font-medium"
          >
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
            <option value="100">100</option>
          </select>
        </div>
      </div>
      <div v-if="totalPages > 1" class="flex items-center gap-3">
        <BaseButton
          variant="outline"
          size="sm"
          :disabled="currentPage === 1"
          @click="handlePageChange(currentPage - 1)"
          class="shadow-sm hover:shadow-md transition-shadow disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ t('common.previous') }}
        </BaseButton>
        <span
          class="text-sm text-gray-700 font-semibold flex items-center px-3 py-1.5 bg-gray-50 rounded-md border border-gray-200"
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
          :disabled="currentPage === totalPages"
          @click="handlePageChange(currentPage + 1)"
          class="shadow-sm hover:shadow-md transition-shadow disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ t('common.next') }}
        </BaseButton>
      </div>
    </div>

    <!-- Filter Drawer -->
    <FilterDrawer
      :show="showFilterDrawer"
      :filters="currentFilters"
      :available-social-accounts="props.availableSocialAccounts"
      @close="showFilterDrawer = false"
      @apply="handleFilterApply"
      @clear="handleFilterClear"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDebounce } from '@/composables/useDebounce'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import StorageLocationBadge from '@/components/ui/StorageLocationBadge.vue'
import FilterDrawer from './FilterDrawer.vue'
import { mapArticleStatus } from '@/utils/articleUtils'
import ArticleCard from './ArticleCard.vue'
import { format } from 'date-fns'

const props = defineProps({
  articles: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  currentPage: {
    type: Number,
    default: 1
  },
  totalPages: {
    type: Number,
    default: 1
  },
  totalCount: {
    type: Number,
    default: 0
  },
  pageSize: {
    type: Number,
    default: 10
  },
  uploadingIds: {
    type: Array,
    default: () => []
  },
  retryingIds: {
    type: Array,
    default: () => []
  },
  loadingMore: {
    type: Boolean,
    default: false
  },
  availableSocialAccounts: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits([
  'search',
  'filter',
  'page-change',
  'page-size-change',
  'refresh',
  'preview',
  'retry',
  'upload',
  'delete',
  'batch-retry',
  'batch-delete',
  'load-more'
])

const { t } = useI18n()

const searchQuery = ref('')
const statusFilter = ref('')
const socialAccountFilter = ref('')
const selectedArticles = ref([])
const isMobile = ref(false)
const sentinelElement = ref(null)
const showFilterDrawer = ref(false)
let observer = null

const hasMore = computed(() => {
  return props.currentPage < props.totalPages
})

const allSelected = computed(() => {
  return (
    props.articles.length > 0 &&
    props.articles.every((article) =>
      selectedArticles.value.includes(article.id)
    )
  )
})

// Use availableSocialAccounts from props (loaded from backend API)
// This provides the complete list of all social accounts, not just current page

const { debouncedFn: debouncedSearch } = useDebounce((value) => {
  emit('search', value)
}, 500)

const handleSearch = (value) => {
  debouncedSearch(value)
}

const currentFilters = computed(() => ({
  status: statusFilter.value,
  socialAccount: socialAccountFilter.value
}))

const activeFilterCount = computed(() => {
  let count = 0
  if (statusFilter.value) count++
  if (socialAccountFilter.value) count++
  return count
})

const getStatusLabel = (status) => {
  const statusMap = {
    pending: t('articles.status.pending'),
    processing: t('articles.status.processing'),
    completed: t('articles.status.completed'),
    failed: t('articles.status.failed')
  }
  return statusMap[status] || status
}

const handleFilterApply = (filters) => {
  statusFilter.value = filters.status || ''
  socialAccountFilter.value = filters.socialAccount || ''
  emit('filter', {
    status: statusFilter.value,
    socialAccount: socialAccountFilter.value
  })
}

const handleFilterClear = () => {
  statusFilter.value = ''
  socialAccountFilter.value = ''
  emit('filter', {
    status: '',
    socialAccount: ''
  })
}

const removeStatusFilter = () => {
  statusFilter.value = ''
  emit('filter', {
    status: '',
    socialAccount: socialAccountFilter.value
  })
}

const removeSocialAccountFilter = () => {
  socialAccountFilter.value = ''
  emit('filter', {
    status: statusFilter.value,
    socialAccount: ''
  })
}

const handlePageChange = (page) => {
  emit('page-change', page)
}

const handlePageSizeChange = (event) => {
  if (!event || !event.target) return
  const newPageSize = parseInt(event.target.value, 10)
  if (isNaN(newPageSize) || newPageSize <= 0) return
  emit('page-size-change', newPageSize)
}

const handleRefresh = () => {
  emit('refresh')
}

const handleSelectAll = (event) => {
  if (event.target.checked) {
    selectedArticles.value = props.articles.map((a) => a.id)
  } else {
    selectedArticles.value = []
  }
}

const handleSelectArticle = (id) => {
  const index = selectedArticles.value.indexOf(id)
  if (index > -1) {
    selectedArticles.value.splice(index, 1)
  } else {
    selectedArticles.value.push(id)
  }
}

const handlePreview = (article) => {
  emit('preview', article)
}

const handleRetry = (article) => {
  emit('retry', article)
}

const handleUpload = (article) => {
  // Emit upload event immediately, parent will handle loading state
  emit('upload', article)
}

const handleDelete = (article) => {
  emit('delete', article)
}

const handleBatchRetry = () => {
  if (selectedArticles.value.length > 0) {
    emit('batch-retry', [...selectedArticles.value])
  }
}

const handleBatchDelete = () => {
  if (selectedArticles.value.length > 0) {
    emit('batch-delete', [...selectedArticles.value])
  }
}

const loadMoreArticles = () => {
  if (props.loadingMore || !hasMore.value || props.loading) return

  emit('load-more')
}

const checkMobile = () => {
  const wasMobile = isMobile.value
  isMobile.value = window.innerWidth < 768

  // Re-setup observer if mobile status changed
  if (wasMobile !== isMobile.value) {
    if (observer) {
      observer.disconnect()
      observer = null
    }
    if (isMobile.value && hasMore.value) {
      nextTick(() => {
        setupIntersectionObserver()
      })
    }
  }
}

const setupIntersectionObserver = () => {
  if (!isMobile.value || !sentinelElement.value) {
    return
  }

  // Clean up existing observer
  if (observer) {
    observer.disconnect()
    observer = null
  }

  // Create new observer - trigger when sentinel is visible
  // Use rootMargin to trigger earlier (200px before element enters viewport)
  observer = new IntersectionObserver(
    (entries) => {
      const entry = entries[0]
      // Auto-load when sentinel element becomes visible (or is about to)
      if (
        entry.isIntersecting &&
        hasMore.value &&
        !props.loadingMore &&
        !props.loading
      ) {
        loadMoreArticles()
      }
    },
    {
      root: null, // Use viewport
      rootMargin: '200px', // Trigger 200px before reaching the element for smoother loading
      threshold: 0.01 // Trigger as soon as any part is visible
    }
  )

  observer.observe(sentinelElement.value)
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)

  // Setup intersection observer for mobile infinite scroll
  if (isMobile.value) {
    nextTick(() => {
      setupIntersectionObserver()
    })
  }
})

// Watch for changes in articles, hasMore, loading states, or mobile status to re-setup observer
watch(
  [
    () => props.articles.length,
    hasMore,
    isMobile,
    () => props.loading,
    () => props.loadingMore
  ],
  () => {
    // Only setup observer when not loading and has more data
    if (
      isMobile.value &&
      hasMore.value &&
      !props.loading &&
      !props.loadingMore
    ) {
      nextTick(() => {
        setupIntersectionObserver()
      })
    } else if (observer) {
      // Disconnect observer when loading or no more data
      observer.disconnect()
      observer = null
    }
  },
  { immediate: false }
)

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
  if (observer) {
    observer.disconnect()
    observer = null
  }
})

const formatDate = (dateString) => {
  if (!dateString) return '-'
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm')
  } catch {
    return dateString
  }
}
</script>

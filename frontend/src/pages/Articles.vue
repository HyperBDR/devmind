<template>
  <AppLayout>
    <div class="w-full max-w-full">
      <!-- Page Header -->
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-gray-900">
            {{ t('articles.title') }}
          </h1>
        </div>
      </div>

      <!-- Content Card -->
      <div class="bg-white rounded border border-gray-200 shadow-sm">
        <ArticleList
          :articles="articles"
          :loading="loading"
          :loading-more="loadingMore"
          :current-page="currentPage"
          :total-pages="totalPages"
          :total-count="totalCount"
          :page-size="pageSize"
          :uploading-ids="uploadingIds"
          :retrying-ids="retryingIds"
          @search="handleSearch"
          @filter="handleFilter"
          :available-social-accounts="availableSocialAccounts"
          @page-change="handlePageChange"
          @page-size-change="handlePageSizeChange"
          @refresh="handleRefresh"
          @preview="handlePreview"
          @retry="handleRetry"
          @upload="handleUpload"
          @delete="handleDeleteClick"
          @batch-retry="handleBatchRetryClick"
          @batch-delete="handleBatchDeleteClick"
          @load-more="handleLoadMore"
        />
      </div>

      <!-- Article Detail Panel -->
      <ArticleDetailPanel
        :show="showPreviewModal"
        :article="selectedArticle"
        @close="showPreviewModal = false"
      />

      <!-- Delete Confirmation -->
      <ConfirmDialog
        :show="showDeleteDialog"
        :title="t('articles.deleteConfirm')"
        :message="t('articles.deleteMessage')"
        :variant="'danger'"
        :loading="deleting"
        @close="showDeleteDialog = false"
        @confirm="handleDeleteConfirm"
      />

      <!-- Batch Delete Confirmation -->
      <ConfirmDialog
        :show="showBatchDeleteDialog"
        :title="t('articles.batchDeleteConfirm')"
        :message="
          t('articles.batchDeleteMessage', { count: batchDeleteIds.length })
        "
        :variant="'danger'"
        :loading="deleting"
        @close="showBatchDeleteDialog = false"
        @confirm="handleBatchDeleteConfirm"
      />

      <!-- Retry Dialog -->
      <RetryDialog
        :show="showRetryDialog"
        :status="selectedArticleForRetry?.status || ''"
        @close="showRetryDialog = false"
        @confirm="handleRetryConfirm"
      />
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useIntervalFn } from '@vueuse/core'
import AppLayout from '@/components/layout/AppLayout.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ArticleList from '@/components/articles/ArticleList.vue'
import ArticleDetailPanel from '@/components/articles/ArticleDetailPanel.vue'
import RetryDialog from '@/components/articles/RetryDialog.vue'
import { articlesApi } from '@/api/articles'
import { useToast } from '@/composables/useToast'
import { extractResponseData, extractErrorMessage } from '@/utils/api'

const { t } = useI18n()
const { showSuccess, showError } = useToast()

const articles = ref([])
const loading = ref(false)
const loadingMore = ref(false)
const currentPage = ref(1)
const totalPages = ref(1)
const pageSize = ref(10)
const totalCount = ref(0)
const searchQuery = ref('')
const statusFilter = ref('')
const socialAccountFilter = ref('')

const showPreviewModal = ref(false)
const selectedArticle = ref(null)

const showDeleteDialog = ref(false)
const deleting = ref(false)
const articleToDelete = ref(null)

const showBatchDeleteDialog = ref(false)
const batchDeleteIds = ref([])

const showRetryDialog = ref(false)
const selectedArticleForRetry = ref(null)
const uploadingIds = ref([])
const retryingIds = ref([])
const availableSocialAccounts = ref([])

const loadArticles = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (searchQuery.value) {
      params.search = searchQuery.value
    }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    if (socialAccountFilter.value) {
      params.social_account = socialAccountFilter.value
    }

    const response = await articlesApi.getArticles(params)
    const data = extractResponseData(response)

    // Handle paginated response
    // Standard DRF format: {count, next, previous, results: [...]}
    // Custom format: {list: [...], pagination: {total, page, pageSize, ...}}
    if (Array.isArray(data)) {
      articles.value = data
      totalPages.value = 1
      totalCount.value = data.length
    } else if (data && data.results) {
      // Standard DRF pagination format
      articles.value = data.results
      const actualPageSize = pageSize.value
      const total = data.count || 0
      totalCount.value = total
      totalPages.value = total > 0 ? Math.ceil(total / actualPageSize) : 1
    } else if (data && data.list && data.pagination) {
      // Custom pagination format
      articles.value = data.list
      const actualPageSize = data.pagination.pageSize || pageSize.value
      const total = data.pagination.total || 0
      totalCount.value = total
      totalPages.value = total > 0 ? Math.ceil(total / actualPageSize) : 1
      currentPage.value = data.pagination.page || 1
      // Update pageSize if backend returned a different value
      if (
        data.pagination.pageSize &&
        data.pagination.pageSize !== pageSize.value
      ) {
        pageSize.value = data.pagination.pageSize
      }
    } else {
      articles.value = data || []
      totalPages.value = 1
      totalCount.value = articles.value.length
    }
  } catch (error) {
    showError(extractErrorMessage(error, t('articles.loadError')))
  } finally {
    loading.value = false
  }
}

const handleSearch = (query) => {
  searchQuery.value = query
  currentPage.value = 1
  loadArticles()
}

const handleFilter = (filters) => {
  if (typeof filters === 'string') {
    // Backward compatibility: if string is passed, treat as status filter
    statusFilter.value = filters
  } else {
    // New format: object with status and socialAccount
    if (filters.status !== undefined) {
      statusFilter.value = filters.status
    }
    if (filters.socialAccount !== undefined) {
      socialAccountFilter.value = filters.socialAccount
    }
  }
  currentPage.value = 1
  loadArticles()
}

const handlePageChange = (page) => {
  currentPage.value = page
  loadArticles()
}

const handlePageSizeChange = (newPageSize) => {
  if (!newPageSize || newPageSize <= 0) return
  pageSize.value = newPageSize
  currentPage.value = 1
  loadArticles()
}

const handleRefresh = () => {
  loadArticles()
}

const handleLoadMore = async () => {
  // For mobile infinite scroll, load next page and append to existing articles
  if (currentPage.value >= totalPages.value || loadingMore.value) return

  const nextPage = currentPage.value + 1
  loadingMore.value = true

  try {
    const params = {
      page: nextPage,
      page_size: pageSize.value
    }
    if (searchQuery.value) {
      params.search = searchQuery.value
    }
    if (statusFilter.value) {
      params.status = statusFilter.value
    }
    if (socialAccountFilter.value) {
      params.social_account = socialAccountFilter.value
    }

    const response = await articlesApi.getArticles(params)
    const data = extractResponseData(response)

    // Append new articles to existing list
    let newArticles = []
    if (Array.isArray(data)) {
      newArticles = data
    } else if (data && data.results) {
      newArticles = data.results
    } else if (data && data.list && data.pagination) {
      newArticles = data.list
    } else {
      newArticles = data || []
    }

    // Append to existing articles instead of replacing
    articles.value = [...articles.value, ...newArticles]
    currentPage.value = nextPage
  } catch (error) {
    showError(extractErrorMessage(error, t('articles.loadError')))
  } finally {
    loadingMore.value = false
  }
}

const handlePreview = async (article) => {
  // Fetch full article details to get content, local_markdown, etc.
  // List view uses ArticleListSerializer which excludes these fields
  try {
    const response = await articlesApi.getArticle(article.id)
    const fullArticle = extractResponseData(response)
    selectedArticle.value = fullArticle
    showPreviewModal.value = true
  } catch (error) {
    showError(extractErrorMessage(error, t('articles.loadError')))
    // Fallback to list data if detail fetch fails
    selectedArticle.value = article
    showPreviewModal.value = true
  }
}

const handleRetry = (article) => {
  selectedArticleForRetry.value = article
  showRetryDialog.value = true
}

const handleRetryConfirm = async ({ force }) => {
  if (!selectedArticleForRetry.value) return

  const articleId = selectedArticleForRetry.value.id

  // Immediately add to retrying list for instant feedback
  if (!retryingIds.value.includes(articleId)) {
    retryingIds.value.push(articleId)
  }

  try {
    await articlesApi.retryArticle(articleId, force)

    // Update only the specific article in the list instead of reloading all
    const articleIndex = articles.value.findIndex((a) => a.id === articleId)
    if (articleIndex !== -1) {
      try {
        // Fetch updated article data
        const updatedArticle = await articlesApi.getArticle(articleId)
        const updatedData = extractResponseData(updatedArticle)
        articles.value[articleIndex] = updatedData
      } catch (fetchError) {
        // If fetching fails, just reload all articles
        await loadArticles()
      }
    } else {
      // Fallback: reload all if article not found
      await loadArticles()
    }

    showSuccess(t('articles.retrySuccess'))
    showRetryDialog.value = false
    selectedArticleForRetry.value = null
  } catch (error) {
    showError(extractErrorMessage(error, t('articles.retryError')))
  } finally {
    // Remove from retrying list
    const index = retryingIds.value.indexOf(articleId)
    if (index > -1) {
      retryingIds.value.splice(index, 1)
    }
  }
}

const handleUpload = async (article) => {
  // Immediately add to uploading list for instant feedback
  if (!uploadingIds.value.includes(article.id)) {
    uploadingIds.value.push(article.id)
  }

  try {
    // Force re-upload if already uploaded
    const force = article.is_uploaded === true || article.is_uploaded === 'true'
    const response = await articlesApi.uploadArticle(article.id, force)
    const data = extractResponseData(response)

    // Check if task was triggered asynchronously (status 202)
    if (response.status === 202 || data.status === 'processing') {
      // Task is running asynchronously, show success message and poll for updates
      showSuccess(
        force ? t('articles.reuploadStarted') : t('articles.uploadStarted')
      )

      // Poll for article status updates
      let pollCount = 0
      const maxPolls = 30 // Poll for up to 30 times (5 minutes if 10s interval)
      const pollInterval = setInterval(async () => {
        pollCount++
        try {
          const updatedArticle = await articlesApi.getArticle(article.id)
          const updatedData = extractResponseData(updatedArticle)

          // Update article in list
          const articleIndex = articles.value.findIndex(
            (a) => a.id === article.id
          )
          if (articleIndex !== -1) {
            articles.value[articleIndex] = updatedData
          }

          // Check if upload completed
          if (
            updatedData.is_uploaded === true ||
            updatedData.is_uploaded === 'true'
          ) {
            clearInterval(pollInterval)
            const index = uploadingIds.value.indexOf(article.id)
            if (index > -1) {
              uploadingIds.value.splice(index, 1)
            }
            showSuccess(
              force
                ? t('articles.reuploadSuccess')
                : t('articles.uploadSuccess')
            )
          } else if (pollCount >= maxPolls) {
            // Stop polling after max attempts
            clearInterval(pollInterval)
            const index = uploadingIds.value.indexOf(article.id)
            if (index > -1) {
              uploadingIds.value.splice(index, 1)
            }
          }
        } catch (pollError) {
          // Ignore polling errors, just stop polling
          clearInterval(pollInterval)
          const index = uploadingIds.value.indexOf(article.id)
          if (index > -1) {
            uploadingIds.value.splice(index, 1)
          }
        }
      }, 10000) // Poll every 10 seconds
    } else {
      // Synchronous response (shouldn't happen with new async implementation)
      // Update only the specific article in the list
      const articleIndex = articles.value.findIndex((a) => a.id === article.id)
      if (articleIndex !== -1) {
        try {
          const updatedArticle = await articlesApi.getArticle(article.id)
          const updatedData = extractResponseData(updatedArticle)
          articles.value[articleIndex] = updatedData
        } catch (fetchError) {
          await loadArticles()
        }
      } else {
        await loadArticles()
      }

      showSuccess(
        force ? t('articles.reuploadSuccess') : t('articles.uploadSuccess')
      )

      // Remove from uploading list
      const index = uploadingIds.value.indexOf(article.id)
      if (index > -1) {
        uploadingIds.value.splice(index, 1)
      }
    }
  } catch (error) {
    showError(extractErrorMessage(error, t('articles.uploadError')))
    // Remove from uploading list on error
    const index = uploadingIds.value.indexOf(article.id)
    if (index > -1) {
      uploadingIds.value.splice(index, 1)
    }
  }
}

const handleDeleteClick = (article) => {
  articleToDelete.value = article
  showDeleteDialog.value = true
}

const handleDeleteConfirm = async () => {
  if (!articleToDelete.value) return

  deleting.value = true
  try {
    await articlesApi.deleteArticle(articleToDelete.value.id)
    showSuccess(t('articles.deleteSuccess'))
    showDeleteDialog.value = false
    articleToDelete.value = null
    await loadArticles()
  } catch (error) {
    showError(extractErrorMessage(error, t('articles.deleteError')))
  } finally {
    deleting.value = false
  }
}

const handleBatchRetryClick = async (ids) => {
  // Immediately add to retrying list for instant feedback
  ids.forEach((id) => {
    if (!retryingIds.value.includes(id)) {
      retryingIds.value.push(id)
    }
  })

  try {
    // For batch retry, we need to get articles to check their status
    // For completed articles, force must be true
    // For processing articles, force is optional (default false)
    const articlesToRetry = articles.value.filter((a) => ids.includes(a.id))
    await Promise.all(
      articlesToRetry.map((article) => {
        // Completed articles require force=true
        const force = article.status === 'completed'
        return articlesApi.retryArticle(article.id, force)
      })
    )
    showSuccess(t('articles.batchRetrySuccess'))
    await loadArticles()
  } catch (error) {
    showError(extractErrorMessage(error, t('articles.batchRetryError')))
  } finally {
    // Remove from retrying list
    ids.forEach((id) => {
      const index = retryingIds.value.indexOf(id)
      if (index > -1) {
        retryingIds.value.splice(index, 1)
      }
    })
  }
}

const handleBatchDeleteClick = (ids) => {
  batchDeleteIds.value = ids
  showBatchDeleteDialog.value = true
}

const handleBatchDeleteConfirm = async () => {
  if (batchDeleteIds.value.length === 0) return

  deleting.value = true
  try {
    await articlesApi.batchDeleteArticles(batchDeleteIds.value)
    showSuccess(t('articles.batchDeleteSuccess'))
    showBatchDeleteDialog.value = false
    batchDeleteIds.value = []
    await loadArticles()
  } catch (error) {
    showError(extractErrorMessage(error, t('articles.batchDeleteError')))
  } finally {
    deleting.value = false
  }
}

// Check if there are any processing articles
const hasProcessingArticles = computed(() => {
  return articles.value.some((article) => article.status === 'processing')
})

// Polling for real-time updates when there are processing articles
const { pause, resume } = useIntervalFn(() => {
  // Only poll if there are processing articles
  if (hasProcessingArticles.value) {
    loadArticles()
  }
}, 10000) // Poll every 10 seconds

const loadSocialAccounts = async () => {
  try {
    const response = await articlesApi.getSocialAccounts()
    const data = extractResponseData(response)
    availableSocialAccounts.value = data.social_accounts || []
  } catch (error) {
    // Silently fail - filter will still work, just won't have dropdown options
    console.error('Failed to load social accounts:', error)
  }
}

onMounted(() => {
  loadSocialAccounts()
  loadArticles()
  // Start polling if there are processing articles
  if (hasProcessingArticles.value) {
    resume()
  }
})

onUnmounted(() => {
  pause()
})

// Watch for changes in processing articles to start/stop polling
watch(
  hasProcessingArticles,
  (hasProcessing) => {
    if (hasProcessing) {
      resume()
    } else {
      pause()
    }
  },
  { immediate: true }
)
</script>

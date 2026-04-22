<template>
  <div class="bg-white rounded border border-gray-200 shadow-sm">
    <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
      <div class="flex items-center gap-2 text-gray-800">
        <svg
          class="w-4 h-4 flex-none"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"
          />
        </svg>
        <h3 class="text-sm font-semibold">
          {{ t('settings.googleNewsConfig') }}
        </h3>
      </div>
    </div>
    <div class="p-4">
      <p class="text-xs text-gray-600 mb-3">
        {{ t('settings.googleNewsConfigDesc') }}
      </p>
      <form @submit.prevent="saveGoogleNewsConfig" class="space-y-3">
        <!-- Filter Words -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="filterWords"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('settings.filterWords') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{ t('settings.filterWordsDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <textarea
              id="filterWords"
              v-model="googleNewsConfig.filterWordsInput"
              :placeholder="t('settings.filterWordsPlaceholder')"
              rows="3"
              class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            ></textarea>
          </div>
        </div>

        <!-- Has Words -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="hasWords"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('settings.hasWords') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{ t('settings.hasWordsDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <textarea
              id="hasWords"
              v-model="googleNewsConfig.hasWordsInput"
              :placeholder="t('settings.hasWordsPlaceholder')"
              rows="3"
              class="block w-full px-3 py-2 text-sm border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            ></textarea>
          </div>
        </div>

        <!-- Target Language -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="targetLanguage"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('settings.targetLanguage') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{ t('settings.targetLanguageDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <div class="relative">
              <select
                id="targetLanguage"
                v-model="googleNewsConfig.target_language"
                class="block w-full pl-3 pr-10 py-2 text-sm border-gray-300 bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 rounded-md shadow-sm appearance-none cursor-pointer hover:border-gray-400 transition-colors"
              >
                <option value="en">en - English</option>
                <option value="zh-CN">zh-CN - 简体中文</option>
                <option value="zh">zh - 中文</option>
                <option value="fr">fr - French</option>
                <option value="de">de - German</option>
                <option value="ja">ja - Japanese</option>
                <option value="ko">ko - Korean</option>
              </select>
              <div
                class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2 text-gray-400"
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
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </div>
            </div>
          </div>
        </div>

        <!-- Target Region -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
          <div class="md:col-span-1">
            <label
              for="targetRegion"
              class="block text-sm font-medium text-gray-700 mb-1"
            >
              {{ t('settings.targetRegion') }}
            </label>
            <p class="text-xs text-gray-500 mb-2 md:mb-0">
              {{ t('settings.targetRegionDesc') }}
            </p>
          </div>
          <div class="md:col-span-2">
            <div class="relative">
              <select
                id="targetRegion"
                v-model="googleNewsConfig.target_region"
                class="block w-full pl-3 pr-10 py-2 text-sm border-gray-300 bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 rounded-md shadow-sm appearance-none cursor-pointer hover:border-gray-400 transition-colors"
              >
                <option value="US">US - United States</option>
                <option value="CN">CN - China Mainland</option>
                <option value="GB">GB - United Kingdom</option>
                <option value="CA">CA - Canada</option>
                <option value="AU">AU - Australia</option>
                <option value="SG">SG - Singapore</option>
                <option value="JP">JP - Japan</option>
                <option value="KR">KR - Korea</option>
              </select>
              <div
                class="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2 text-gray-400"
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
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </div>
            </div>
          </div>
        </div>

        <div v-if="googleNewsError" class="rounded-md bg-red-50 p-2.5">
          <div class="flex gap-2">
            <div class="flex-shrink-0 pt-0.5">
              <svg
                class="h-4 w-4 text-red-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fill-rule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clip-rule="evenodd"
                />
              </svg>
            </div>
            <div class="flex-1">
              <p class="text-xs font-medium text-red-800">
                {{ googleNewsError }}
              </p>
            </div>
          </div>
        </div>

        <div v-if="googleNewsSuccess" class="rounded-md bg-green-50 p-2.5">
          <div class="flex gap-2">
            <div class="flex-shrink-0 pt-0.5">
              <svg
                class="h-4 w-4 text-green-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fill-rule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clip-rule="evenodd"
                />
              </svg>
            </div>
            <div class="flex-1">
              <p class="text-xs font-medium text-green-800">
                {{ googleNewsSuccess }}
              </p>
            </div>
          </div>
        </div>

        <div class="flex justify-end mt-4">
          <BaseButton
            type="submit"
            variant="primary"
            class="w-full sm:w-auto"
            :loading="savingGoogleNews"
            :disabled="savingGoogleNews"
          >
            {{
              savingGoogleNews
                ? t('common.loading')
                : t('settings.saveSettings')
            }}
          </BaseButton>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { settingsApi } from '@/api/settings'
import BaseButton from '@/components/ui/BaseButton.vue'

const { t } = useI18n()

const googleNewsConfig = reactive({
  filterWordsInput: '',
  hasWordsInput: '',
  target_language: 'zh-CN',
  target_region: 'CN'
})

const savingGoogleNews = ref(false)
const googleNewsError = ref('')
const googleNewsSuccess = ref('')

const loadGoogleNewsConfig = async () => {
  try {
    const config = await settingsApi.getGoogleNewsConfig()
    googleNewsConfig.filterWordsInput = Array.isArray(config.filter_words)
      ? config.filter_words.join(', ')
      : ''
    googleNewsConfig.hasWordsInput = Array.isArray(config.has_words)
      ? config.has_words.join(', ')
      : ''
    googleNewsConfig.target_language = config.target_language || 'zh-CN'
    googleNewsConfig.target_region = config.target_region || 'CN'
  } catch (error) {
    console.error('Failed to load Google News config:', error)
    // Use default values if loading fails
    const defaultFilterWords = [
      'human rights',
      'china',
      'chinese',
      'ft.com',
      '中国',
      '中华人民共和国',
      'zdnet',
      'vpn',
      'political',
      'terrorism',
      'politics',
      'putin'
    ]
    googleNewsConfig.filterWordsInput = defaultFilterWords.join(', ')
    googleNewsConfig.hasWordsInput = ''
    googleNewsConfig.target_language = 'zh-CN'
    googleNewsConfig.target_region = 'CN'
  }
}

const saveGoogleNewsConfig = async () => {
  savingGoogleNews.value = true
  googleNewsError.value = ''
  googleNewsSuccess.value = ''

  try {
    // Parse filter_words and has_words from comma-separated strings
    const filter_words = googleNewsConfig.filterWordsInput
      .split(',')
      .map((word) => word.trim())
      .filter((word) => word.length > 0)

    const has_words = googleNewsConfig.hasWordsInput
      .split(',')
      .map((word) => word.trim())
      .filter((word) => word.length > 0)

    await settingsApi.updateGoogleNewsConfig({
      filter_words,
      has_words,
      target_language: googleNewsConfig.target_language,
      target_region: googleNewsConfig.target_region
    })

    googleNewsSuccess.value = t('settings.googleNewsConfigSaved')
    setTimeout(() => {
      googleNewsSuccess.value = ''
    }, 3000)
  } catch (error) {
    console.error('Failed to save Google News config:', error)
    googleNewsError.value =
      error.response?.data?.message || t('settings.googleNewsConfigError')
  } finally {
    savingGoogleNews.value = false
  }
}

onMounted(() => {
  loadGoogleNewsConfig()
})
</script>

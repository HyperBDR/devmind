<template>
  <AppLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4">
        <h1 class="text-lg font-semibold text-gray-900">
          {{ t('globalSettings.title') }}
        </h1>
        <p class="mt-1 text-sm text-gray-500">
          {{ t('globalSettings.subtitle') }}
        </p>
      </div>

      <div
        class="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden mb-6"
      >
        <div class="p-6">
          <TaskConfigSection />
        </div>
      </div>

      <div
        class="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden"
      >
        <div class="px-4 py-3 border-b border-gray-200 bg-gray-50">
          <h2 class="text-base font-semibold text-gray-900">
            {{ t('globalSettings.notificationSectionTitle') }}
          </h2>
        </div>
        <div class="p-6">
          <p class="text-sm text-gray-600 mb-4">
            {{ t('globalSettings.notificationSectionDesc') }}
          </p>
          <router-link
            to="/management/notifier/settings"
            class="inline-flex items-center gap-2 rounded-md border border-primary-300 bg-primary-50 px-4 py-2 text-sm font-medium text-primary-700 hover:bg-primary-100 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
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
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            {{ t('globalSettings.goToNotificationConfig') }}
          </router-link>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import AppLayout from '@/components/layout/AppLayout.vue'
import TaskConfigSection from '@/components/task-management/TaskConfigSection.vue'

const { t } = useI18n()
</script>

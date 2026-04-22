<template>
  <BaseModal :show="show" :title="modalTitle" @close="$emit('close')">
    <div class="space-y-6">
      <template v-if="!isSectionEditMode">
        <nav
          class="flex items-center justify-center gap-2 text-sm"
          aria-label="Steps"
        >
          <span
            class="flex items-center gap-1.5"
            :class="
              currentStep >= 1
                ? 'text-primary-600 font-medium'
                : 'text-gray-400'
            "
          >
            <span
              class="flex h-7 w-7 items-center justify-center rounded-full border"
              :class="
                currentStep >= 1
                  ? 'border-primary-600 bg-primary-50'
                  : 'border-gray-300'
              "
              >1</span
            >
            {{ t('dataCollector.settings.step1Title') }}
          </span>
          <span class="text-gray-300">→</span>
          <span
            class="flex items-center gap-1.5"
            :class="
              currentStep >= 2
                ? 'text-primary-600 font-medium'
                : 'text-gray-400'
            "
          >
            <span
              class="flex h-7 w-7 items-center justify-center rounded-full border"
              :class="
                currentStep >= 2
                  ? 'border-primary-600 bg-primary-50'
                  : 'border-gray-300'
              "
              >2</span
            >
            {{ t('dataCollector.settings.step2Title') }}
          </span>
          <span v-if="!isFullEditMode" class="text-gray-300">→</span>
          <span
            v-if="!isFullEditMode"
            class="flex items-center gap-1.5"
            :class="
              currentStep >= 3
                ? 'text-primary-600 font-medium'
                : 'text-gray-400'
            "
          >
            <span
              class="flex h-7 w-7 items-center justify-center rounded-full border"
              :class="
                currentStep >= 3
                  ? 'border-primary-600 bg-primary-50'
                  : 'border-gray-300'
              "
              >3</span
            >
            {{ t('dataCollector.settings.step3Title') }}
          </span>
        </nav>

        <form
          v-if="currentStep === 1"
          @submit.prevent="
            canGoNextFromStep1 && ((currentStep = 2), loadProjectsIfNeeded())
          "
          class="space-y-4"
        >
          <div class="space-y-3 border-b border-gray-200 pb-4">
            <h4 class="text-sm font-semibold text-gray-900">
              {{ t('dataCollector.settings.basicInfo') }}
            </h4>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
              <div class="md:col-span-1">
                <label
                  for="platform"
                  class="block text-sm font-medium text-gray-700 mb-1"
                >
                  {{ t('dataCollector.settings.platform') }}
                </label>
                <p class="text-xs text-gray-500 mb-2 md:mb-0">
                  {{ t('dataCollector.settings.platformDesc') }}
                </p>
              </div>
              <div class="md:col-span-2">
                <select
                  id="platform"
                  v-model="formData.platform"
                  required
                  class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  :disabled="!!config"
                >
                  <option value="jira">
                    {{ t('dataCollector.platforms.jira') }}
                  </option>
                  <option value="feishu">
                    {{ t('dataCollector.platforms.feishu') }}
                  </option>
                  <option value="license">
                    {{ t('dataCollector.platforms.license') }}
                  </option>
                  <option value="hyperbdr">
                    {{ t('dataCollector.platforms.hyperbdr') }}
                  </option>
                  <option value="ai_pricehub">
                    {{ t('dataCollector.platforms.ai_pricehub') }}
                  </option>
                </select>
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
              <div class="md:col-span-1">
                <label
                  for="key"
                  class="block text-sm font-medium text-gray-700 mb-1"
                >
                  {{ t('dataCollector.settings.key') }}
                </label>
                <p class="text-xs text-gray-500 mb-2 md:mb-0">
                  {{ t('dataCollector.settings.keyDesc') }}
                </p>
              </div>
              <div class="md:col-span-2">
                <BaseInput
                  id="key"
                  v-model="formData.key"
                  type="text"
                  :placeholder="t('dataCollector.settings.keyPlaceholder')"
                  required
                  class="w-full"
                />
              </div>
            </div>
          </div>

          <template v-if="formData.platform === 'jira'">
            <div class="space-y-3 border-b border-gray-200 pb-4">
              <h4 class="text-sm font-semibold text-gray-900">
                {{ t('dataCollector.settings.authConfig') }}
              </h4>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label
                    for="authVersion"
                    class="block text-sm font-medium text-gray-700 mb-1"
                  >
                    {{ t('dataCollector.jira.authVersion') }}
                  </label>
                  <p class="text-xs text-gray-500 mb-2 md:mb-0">
                    {{ t('dataCollector.jira.authVersionDesc') }}
                  </p>
                </div>
                <div class="md:col-span-2">
                  <select
                    id="authVersion"
                    v-model="formData.jira_auth_version"
                    class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  >
                    <option value="legacy">
                      {{ t('dataCollector.jira.authVersionLegacy') }}
                    </option>
                    <option value="cloud">
                      {{ t('dataCollector.jira.authVersionCloud') }}
                    </option>
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label
                    for="baseUrl"
                    class="block text-sm font-medium text-gray-700 mb-1"
                  >
                    {{ t('dataCollector.jira.baseUrl') }}
                  </label>
                  <p class="text-xs text-gray-500 mb-2 md:mb-0">
                    {{ t('dataCollector.jira.baseUrlDesc') }}
                  </p>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    id="baseUrl"
                    v-model="formData.jira_base_url"
                    type="url"
                    :placeholder="t('dataCollector.jira.baseUrlPlaceholder')"
                    required
                    class="w-full"
                  />
                </div>
              </div>
              <template v-if="formData.jira_auth_version === 'legacy'">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                  <div class="md:col-span-1">
                    <label
                      for="jiraUsername"
                      class="block text-sm font-medium text-gray-700 mb-1"
                    >
                      {{ t('dataCollector.jira.username') }}
                    </label>
                    <p class="text-xs text-gray-500 mb-2 md:mb-0">
                      {{ t('dataCollector.jira.usernameDesc') }}
                    </p>
                  </div>
                  <div class="md:col-span-2">
                    <BaseInput
                      id="jiraUsername"
                      v-model="formData.jira_username"
                      type="text"
                      :placeholder="t('dataCollector.jira.usernamePlaceholder')"
                      :required="formData.jira_auth_version === 'legacy'"
                      class="w-full"
                    />
                  </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                  <div class="md:col-span-1">
                    <label
                      for="jiraPassword"
                      class="block text-sm font-medium text-gray-700 mb-1"
                    >
                      {{ t('dataCollector.jira.password') }}
                    </label>
                    <p class="text-xs text-gray-500 mb-2 md:mb-0">
                      {{ t('dataCollector.jira.passwordDesc') }}
                    </p>
                  </div>
                  <div class="md:col-span-2">
                    <BaseInput
                      id="jiraPassword"
                      v-model="formData.jira_password"
                      type="password"
                      :placeholder="
                        config
                          ? t('dataCollector.jira.passwordPlaceholderEdit')
                          : t('dataCollector.jira.passwordPlaceholder')
                      "
                      :required="
                        !config && formData.jira_auth_version === 'legacy'
                      "
                      class="w-full"
                    />
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                  <div class="md:col-span-1">
                    <label
                      for="jiraEmail"
                      class="block text-sm font-medium text-gray-700 mb-1"
                    >
                      {{ t('dataCollector.jira.email') }}
                    </label>
                    <p class="text-xs text-gray-500 mb-2 md:mb-0">
                      {{ t('dataCollector.jira.emailDesc') }}
                    </p>
                  </div>
                  <div class="md:col-span-2">
                    <BaseInput
                      id="jiraEmail"
                      v-model="formData.jira_email"
                      type="email"
                      :placeholder="t('dataCollector.jira.emailPlaceholder')"
                      :required="formData.jira_auth_version === 'cloud'"
                      class="w-full"
                    />
                  </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                  <div class="md:col-span-1">
                    <label
                      for="jiraApiToken"
                      class="block text-sm font-medium text-gray-700 mb-1"
                    >
                      {{ t('dataCollector.jira.apiToken') }}
                    </label>
                    <p class="text-xs text-gray-500 mb-2 md:mb-0">
                      {{ t('dataCollector.jira.apiTokenDesc') }}
                    </p>
                  </div>
                  <div class="md:col-span-2">
                    <BaseInput
                      id="jiraApiToken"
                      v-model="formData.jira_api_token"
                      type="password"
                      :placeholder="
                        config
                          ? t('dataCollector.jira.apiTokenPlaceholderEdit')
                          : t('dataCollector.jira.apiTokenPlaceholder')
                      "
                      :required="
                        !config && formData.jira_auth_version === 'cloud'
                      "
                      class="w-full"
                    />
                  </div>
                </div>
              </template>
            </div>
          </template>

          <template v-else-if="formData.platform === 'feishu'">
            <div class="space-y-3 border-b border-gray-200 pb-4">
              <h4 class="text-sm font-semibold text-gray-900">
                {{ t('dataCollector.settings.authConfig') }}
              </h4>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label
                    for="feishuAppId"
                    class="block text-sm font-medium text-gray-700 mb-1"
                  >
                    {{ t('dataCollector.feishu.appId') }}
                  </label>
                  <p class="text-xs text-gray-500 mb-2 md:mb-0">
                    {{ t('dataCollector.feishu.appIdDesc') }}
                  </p>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    id="feishuAppId"
                    v-model="formData.feishu_app_id"
                    type="text"
                    :placeholder="t('dataCollector.feishu.appIdPlaceholder')"
                    required
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label
                    for="feishuAppSecret"
                    class="block text-sm font-medium text-gray-700 mb-1"
                  >
                    {{ t('dataCollector.feishu.appSecret') }}
                  </label>
                  <p class="text-xs text-gray-500 mb-2 md:mb-0">
                    {{ t('dataCollector.feishu.appSecretDesc') }}
                  </p>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    id="feishuAppSecret"
                    v-model="formData.feishu_app_secret"
                    type="password"
                    :placeholder="
                      config
                        ? t('dataCollector.feishu.appSecretPlaceholderEdit')
                        : t('dataCollector.feishu.appSecretPlaceholder')
                    "
                    :required="!config"
                    class="w-full"
                  />
                </div>
              </div>
            </div>
          </template>

          <template v-else-if="formData.platform === 'license'">
            <div class="space-y-3 border-b border-gray-200 pb-4">
              <h4 class="text-sm font-semibold text-gray-900">
                {{ t('dataCollector.settings.authConfig') }}
              </h4>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label
                    for="licenseBaseUrl"
                    class="block text-sm font-medium text-gray-700 mb-1"
                  >
                    {{ t('dataCollector.license.baseUrl') }}
                  </label>
                  <p class="text-xs text-gray-500 mb-2 md:mb-0">
                    {{ t('dataCollector.license.baseUrlDesc') }}
                  </p>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    id="licenseBaseUrl"
                    v-model="formData.license_base_url"
                    type="url"
                    :placeholder="t('dataCollector.license.baseUrlPlaceholder')"
                    required
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label
                    for="licenseUsername"
                    class="block text-sm font-medium text-gray-700 mb-1"
                  >
                    {{ t('dataCollector.license.username') }}
                  </label>
                  <p class="text-xs text-gray-500 mb-2 md:mb-0">
                    {{ t('dataCollector.license.usernameDesc') }}
                  </p>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    id="licenseUsername"
                    v-model="formData.license_username"
                    type="text"
                    :placeholder="
                      t('dataCollector.license.usernamePlaceholder')
                    "
                    required
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label
                    for="licensePassword"
                    class="block text-sm font-medium text-gray-700 mb-1"
                  >
                    {{ t('dataCollector.license.password') }}
                  </label>
                  <p class="text-xs text-gray-500 mb-2 md:mb-0">
                    {{ t('dataCollector.license.passwordDesc') }}
                  </p>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    id="licensePassword"
                    v-model="formData.license_password"
                    type="password"
                    :placeholder="
                      config
                        ? t('dataCollector.license.passwordPlaceholderEdit')
                        : t('dataCollector.license.passwordPlaceholder')
                    "
                    :required="!config"
                    class="w-full"
                  />
                </div>
              </div>
            </div>
          </template>

          <template v-else-if="formData.platform === 'hyperbdr'">
            <div class="space-y-3 border-b border-gray-200 pb-4">
              <h4 class="text-sm font-semibold text-gray-900">
                {{ t('dataCollector.settings.authConfig') }}
              </h4>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label
                    for="hyperbdr_base_url"
                    class="block text-sm font-medium text-gray-700 mb-1"
                  >
                    {{ t('dataCollector.hyperbdr.baseUrl') }}
                  </label>
                  <p class="text-xs text-gray-500 mb-2 md:mb-0">
                    {{ t('dataCollector.hyperbdr.baseUrlDesc') }}
                  </p>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    id="hyperbdr_base_url"
                    v-model="formData.hyperbdr_base_url"
                    type="url"
                    :placeholder="
                      t('dataCollector.hyperbdr.baseUrlPlaceholder')
                    "
                    required
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label
                    for="hyperbdrUsername"
                    class="block text-sm font-medium text-gray-700 mb-1"
                  >
                    {{ t('dataCollector.hyperbdr.username') }}
                  </label>
                  <p class="text-xs text-gray-500 mb-2 md:mb-0">
                    {{ t('dataCollector.hyperbdr.usernameDesc') }}
                  </p>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    id="hyperbdrUsername"
                    v-model="formData.hyperbdr_username"
                    type="text"
                    :placeholder="
                      t('dataCollector.hyperbdr.usernamePlaceholder')
                    "
                    required
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label
                    for="hyperbdrPassword"
                    class="block text-sm font-medium text-gray-700 mb-1"
                  >
                    {{ t('dataCollector.hyperbdr.password') }}
                  </label>
                  <p class="text-xs text-gray-500 mb-2 md:mb-0">
                    {{ t('dataCollector.hyperbdr.passwordDesc') }}
                  </p>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    id="hyperbdrPassword"
                    v-model="formData.hyperbdr_password"
                    type="password"
                    :placeholder="
                      config
                        ? t('dataCollector.hyperbdr.passwordPlaceholderEdit')
                        : t('dataCollector.hyperbdr.passwordPlaceholder')
                    "
                    :required="!config"
                    class="w-full"
                  />
                </div>
              </div>
            </div>
          </template>

          <!-- AI Price Hub: 配置主平台信息 -->
          <template v-else-if="formData.platform === 'ai_pricehub'">
            <div class="space-y-3 border-b border-gray-200 pb-4">
              <h4 class="text-sm font-semibold text-gray-900">
                {{ t('dataCollector.aiPriceHub.primarySourceTitle') }}
              </h4>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label class="block text-sm font-medium text-gray-700 mb-1">
                    {{ t('dataCollector.aiPriceHub.platformSlug') }}
                  </label>
                  <p class="text-xs text-gray-500 mb-2 md:mb-0">
                    {{ t('dataCollector.aiPriceHub.platformSlugDesc') }}
                  </p>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    v-model="formData.ai_pricehub_platform_slug"
                    type="text"
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label class="block text-sm font-medium text-gray-700 mb-1">
                    {{ t('dataCollector.aiPriceHub.vendorName') }}
                  </label>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    v-model="formData.ai_pricehub_vendor_name"
                    type="text"
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label class="block text-sm font-medium text-gray-700 mb-1">
                    {{ t('dataCollector.aiPriceHub.endpointUrl') }}
                  </label>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    v-model="formData.ai_pricehub_endpoint_url"
                    type="url"
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label class="block text-sm font-medium text-gray-700 mb-1">
                    {{ t('dataCollector.aiPriceHub.region') }}
                  </label>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    v-model="formData.ai_pricehub_region"
                    type="text"
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label class="block text-sm font-medium text-gray-700 mb-1">
                    {{ t('dataCollector.aiPriceHub.currency') }}
                  </label>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    v-model="formData.ai_pricehub_currency"
                    type="text"
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label class="block text-sm font-medium text-gray-700 mb-1">
                    {{ t('dataCollector.aiPriceHub.pointsPerCurrencyUnit') }}
                  </label>
                </div>
                <div class="md:col-span-2">
                  <BaseInput
                    v-model.number="
                      formData.ai_pricehub_points_per_currency_unit
                    "
                    type="number"
                    min="0"
                    step="0.01"
                    class="w-full"
                  />
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
                <div class="md:col-span-1">
                  <label class="block text-sm font-medium text-gray-700 mb-1">
                    {{ t('dataCollector.aiPriceHub.parserLlmConfigUuid') }}
                  </label>
                </div>
                <div class="md:col-span-2">
                  <select
                    v-model="formData.ai_pricehub_parser_llm_config_uuid"
                    class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 disabled:bg-gray-100 disabled:text-gray-500"
                    :disabled="aiPriceHubLlmOptionsLoading"
                  >
                    <option value="">
                      {{
                        aiPriceHubLlmOptionsLoading
                          ? t('dataCollector.aiPriceHub.parserLlmLoading')
                          : t('dataCollector.aiPriceHub.parserLlmPlaceholder')
                      }}
                    </option>
                    <option
                      v-for="option in aiPriceHubLlmSelectOptions"
                      :key="option.uuid"
                      :value="option.uuid"
                    >
                      {{ option.label }}
                    </option>
                  </select>
                  <p
                    v-if="aiPriceHubLlmLoadError"
                    class="mt-1 text-xs text-red-600"
                  >
                    {{ aiPriceHubLlmLoadError }}
                  </p>
                  <p
                    v-else-if="
                      !aiPriceHubLlmOptionsLoading &&
                      aiPriceHubLlmSelectOptions.length === 0
                    "
                    class="mt-1 text-xs text-gray-500"
                  >
                    {{ t('dataCollector.aiPriceHub.parserLlmEmpty') }}
                  </p>
                </div>
              </div>
            </div>
          </template>

          <div
            v-if="
              formData.platform === 'jira' ||
              formData.platform === 'feishu' ||
              formData.platform === 'license' ||
              formData.platform === 'hyperbdr' ||
              formData.platform === 'ai_pricehub'
            "
            class="space-y-1 pt-2"
          >
            <p class="text-sm text-gray-500">
              {{ t('dataCollector.settings.verifyHint') }}
            </p>
            <div class="flex flex-wrap items-center gap-3">
              <span v-if="step1AuthVerified" class="text-sm text-green-600">
                {{ t('dataCollector.settings.verifyAuthSuccess') }}
              </span>
              <span v-if="authError" class="text-sm text-red-600">
                {{ authError }}
              </span>
            </div>
          </div>
        </form>

        <div v-else-if="currentStep === 2" class="space-y-4">
          <!-- Jira: 选择项目 -->
          <template v-if="formData.platform === 'jira'">
            <p class="text-sm text-gray-600">
              {{ t('dataCollector.settings.selectProjectsDesc') }}
            </p>
            <div
              v-if="projectsLoading"
              class="py-8 text-center text-sm text-gray-500"
            >
              {{ t('dataCollector.settings.loadingProjects') }}
            </div>
            <div
              v-else-if="projectsError"
              class="rounded-md p-3 text-sm bg-red-50 text-red-800"
            >
              {{ projectsError }}
            </div>
            <div
              v-else-if="projects.length === 0"
              class="py-8 text-center text-sm text-gray-500"
            >
              {{ t('dataCollector.settings.noProjects') }}
            </div>
            <div
              v-else
              class="max-h-64 overflow-y-auto rounded border border-gray-200 divide-y divide-gray-200"
            >
              <label
                v-for="proj in projects"
                :key="proj.key"
                class="flex items-center gap-3 px-4 py-2 hover:bg-gray-50 cursor-pointer"
              >
                <input
                  v-model="formData.selected_project_keys"
                  type="checkbox"
                  :value="proj.key"
                  class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span class="font-medium text-gray-900">{{ proj.key }}</span>
                <span class="text-sm text-gray-500">{{ proj.name }}</span>
              </label>
            </div>
          </template>

          <!-- License: 选择订单采集 -->
          <template v-else-if="formData.platform === 'license'">
            <p class="text-sm text-gray-600">
              {{ t('dataCollector.license.step2Desc') }}
            </p>
            <div
              v-if="projectsLoading"
              class="py-8 text-center text-sm text-gray-500"
            >
              {{ t('dataCollector.settings.loadingProjects') }}
            </div>
            <div
              v-else-if="projectsError"
              class="rounded-md p-3 text-sm bg-red-50 text-red-800"
            >
              {{ projectsError }}
            </div>
            <div
              v-else-if="projects.length === 0"
              class="py-8 text-center text-sm text-gray-500"
            >
              {{ t('dataCollector.settings.noProjects') }}
            </div>
            <div
              v-else
              class="max-h-64 overflow-y-auto rounded border border-gray-200 divide-y divide-gray-200"
            >
              <label
                v-for="proj in projects"
                :key="proj.key"
                class="flex items-center gap-3 px-4 py-2 hover:bg-gray-50 cursor-pointer"
              >
                <input
                  v-model="formData.selected_project_keys"
                  type="checkbox"
                  :value="proj.key"
                  class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span class="font-medium text-gray-900">{{
                  proj.key === 'order'
                    ? t('dataCollector.license.orderCollection')
                    : proj.name
                }}</span>
                <span class="text-sm text-gray-500">{{
                  proj.key === 'order'
                    ? t('dataCollector.license.orderCollection')
                    : proj.name
                }}</span>
              </label>
            </div>
          </template>

          <!-- AI Price Hub: 选择比价采集类型 -->
          <template v-else-if="formData.platform === 'ai_pricehub'">
            <p class="text-sm text-gray-600">
              {{ t('dataCollector.aiPriceHub.step2Desc') }}
            </p>
            <div
              v-if="projectsLoading"
              class="py-8 text-center text-sm text-gray-500"
            >
              {{ t('dataCollector.settings.loadingProjects') }}
            </div>
            <div
              v-else-if="projectsError"
              class="rounded-md p-3 text-sm bg-red-50 text-red-800"
            >
              {{ projectsError }}
            </div>
            <div
              v-else-if="projects.length === 0"
              class="py-8 text-center text-sm text-gray-500"
            >
              {{ t('dataCollector.settings.noProjects') }}
            </div>
            <div
              v-else
              class="max-h-64 overflow-y-auto rounded border border-gray-200 divide-y divide-gray-200"
            >
              <label
                v-for="proj in projects"
                :key="proj.key"
                class="flex items-center gap-3 px-4 py-2 hover:bg-gray-50 cursor-pointer"
              >
                <input
                  v-model="formData.selected_project_keys"
                  type="checkbox"
                  :value="proj.key"
                  class="h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                <span class="font-medium text-gray-900">{{
                  proj.name || proj.key
                }}</span>
                <span class="text-sm text-gray-500">{{ proj.key }}</span>
              </label>
            </div>
          </template>

          <template v-else-if="formData.platform === 'hyperbdr'">
            <p class="text-sm text-gray-600">
              {{ t('dataCollector.hyperbdr.step2Desc') }}
            </p>
          </template>

          <!-- Feishu: 手动配置审批定义 ID + 名称 -->
          <template v-else-if="formData.platform === 'feishu'">
            <p class="text-sm text-gray-600">
              {{ t('dataCollector.feishu.approvalDefinitionsDesc') }}
            </p>
            <div class="space-y-2">
              <div
                v-for="(item, index) in formData.feishu_definitions"
                :key="index"
                class="grid grid-cols-12 gap-3 items-start"
              >
                <div class="col-span-5">
                  <label class="block text-xs font-medium text-gray-500 mb-1">
                    {{ t('dataCollector.feishu.approvalDefinitionId') }}
                  </label>
                  <BaseInput v-model="item.id" type="text" class="w-full" />
                </div>
                <div class="col-span-5">
                  <label class="block text-xs font-medium text-gray-500 mb-1">
                    {{ t('dataCollector.feishu.approvalDefinitionName') }}
                  </label>
                  <BaseInput v-model="item.name" type="text" class="w-full" />
                </div>
                <div class="col-span-2 flex items-end justify-end">
                  <BaseButton
                    type="button"
                    variant="ghost"
                    size="sm"
                    @click="removeFeishuDefinition(index)"
                  >
                    {{ t('common.delete') }}
                  </BaseButton>
                </div>
              </div>
              <div>
                <BaseButton
                  type="button"
                  variant="outline"
                  size="sm"
                  @click="addFeishuDefinition"
                >
                  {{ t('dataCollector.feishu.addApprovalDefinition') }}
                </BaseButton>
              </div>
            </div>
          </template>

          <!-- 其他平台暂不需要第二步 -->
          <template v-else>
            <p class="text-sm text-gray-500">
              {{ t('dataCollector.settings.selectProjectsDesc') }}
            </p>
          </template>
        </div>

        <form
          v-else-if="currentStep === 3"
          @submit.prevent="handleSubmit"
          class="space-y-4"
        >
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
            <div class="md:col-span-1">
              <label
                for="isEnabled"
                class="block text-sm font-medium text-gray-700 mb-1"
              >
                {{ t('dataCollector.settings.isEnabled') }}
              </label>
              <p class="text-xs text-gray-500 mb-2 md:mb-0">
                {{ t('dataCollector.settings.isEnabledDesc') }}
              </p>
            </div>
            <div class="md:col-span-2">
              <label class="relative inline-flex items-center cursor-pointer">
                <input
                  id="isEnabled"
                  v-model="formData.is_enabled"
                  type="checkbox"
                  class="sr-only peer"
                />
                <div
                  class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"
                />
                <span class="ml-3 text-sm text-gray-700">
                  {{
                    formData.is_enabled
                      ? t('common.enabled')
                      : t('common.disabled')
                  }}
                </span>
              </label>
            </div>
          </div>
          <div class="space-y-3 border-t border-gray-200 pt-4">
            <h4 class="text-sm font-semibold text-gray-900">
              {{ t('dataCollector.settings.scheduleSection') }}
            </h4>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
              <div class="md:col-span-1">
                <label
                  for="scheduleCron"
                  class="block text-sm font-medium text-gray-700 mb-1"
                >
                  {{ t('dataCollector.settings.scheduleCron') }}
                </label>
                <p class="text-xs text-gray-500 mb-2 md:mb-0">
                  {{ t('dataCollector.settings.scheduleCronDesc') }}
                </p>
              </div>
              <div class="md:col-span-2">
                <BaseInput
                  id="scheduleCron"
                  v-model="formData.schedule_cron"
                  type="text"
                  :placeholder="
                    t('dataCollector.settings.scheduleCronPlaceholder')
                  "
                  class="w-full"
                />
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
              <div class="md:col-span-1">
                <label
                  for="cleanupCron"
                  class="block text-sm font-medium text-gray-700 mb-1"
                >
                  {{ t('dataCollector.settings.cleanupCron') }}
                </label>
                <p class="text-xs text-gray-500 mb-2 md:mb-0">
                  {{ t('dataCollector.settings.cleanupCronDesc') }}
                </p>
              </div>
              <div class="md:col-span-2">
                <BaseInput
                  id="cleanupCron"
                  v-model="formData.cleanup_cron"
                  type="text"
                  :placeholder="
                    t('dataCollector.settings.cleanupCronPlaceholder')
                  "
                  class="w-full"
                />
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
              <div class="md:col-span-1">
                <label
                  for="retentionDays"
                  class="block text-sm font-medium text-gray-700 mb-1"
                >
                  {{ t('dataCollector.settings.retentionDays') }}
                </label>
                <p class="text-xs text-gray-500 mb-2 md:mb-0">
                  {{ t('dataCollector.settings.retentionDaysDesc') }}
                </p>
              </div>
              <div class="md:col-span-2">
                <BaseInput
                  id="retentionDays"
                  v-model.number="formData.retention_days"
                  type="number"
                  min="1"
                  class="w-full"
                />
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
              <div class="md:col-span-1">
                <label
                  for="initialRange"
                  class="block text-sm font-medium text-gray-700 mb-1"
                >
                  {{ t('dataCollector.settings.initialRange') }}
                </label>
                <p class="text-xs text-gray-500 mb-2 md:mb-0">
                  {{ t('dataCollector.settings.initialRangeDesc') }}
                </p>
              </div>
              <div class="md:col-span-2">
                <select
                  id="initialRange"
                  v-model="formData.initial_range"
                  class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <template v-if="formData.platform === 'feishu'">
                    <option value="10d">
                      {{ t('dataCollector.settings.initialRange10d') }}
                    </option>
                    <option value="30d">
                      {{ t('dataCollector.settings.initialRange30d') }}
                    </option>
                  </template>
                  <template v-else>
                    <option value="1m">
                      {{ t('dataCollector.settings.initialRange1m') }}
                    </option>
                    <option value="3m">
                      {{ t('dataCollector.settings.initialRange3m') }}
                    </option>
                  </template>
                </select>
              </div>
            </div>
          </div>
        </form>
      </template>

      <template v-else-if="isSectionEditMode && editSection === 'schedule'">
        <div class="max-h-[60vh] overflow-y-auto space-y-4 pr-1">
          <p class="text-sm text-gray-500">
            {{ config.key }} · {{ t('dataCollector.settings.scheduleSection') }}
          </p>
          <section class="space-y-3">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-center">
              <div class="md:col-span-1">
                <label
                  for="sec-isEnabled"
                  class="block text-sm font-medium text-gray-700 mb-1"
                  >{{ t('dataCollector.settings.isEnabled') }}</label
                >
              </div>
              <div class="md:col-span-2">
                <label class="relative inline-flex items-center cursor-pointer">
                  <input
                    id="sec-isEnabled"
                    v-model="formData.is_enabled"
                    type="checkbox"
                    class="sr-only peer"
                  />
                  <div
                    class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"
                  />
                  <span class="ml-3 text-sm text-gray-700">{{
                    formData.is_enabled
                      ? t('common.enabled')
                      : t('common.disabled')
                  }}</span>
                </label>
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
              <div class="md:col-span-1">
                <label
                  for="sec-scheduleCron"
                  class="block text-sm font-medium text-gray-700 mb-1"
                  >{{ t('dataCollector.settings.scheduleCron') }}</label
                >
              </div>
              <div class="md:col-span-2">
                <BaseInput
                  id="sec-scheduleCron"
                  v-model="formData.schedule_cron"
                  type="text"
                  :placeholder="
                    t('dataCollector.settings.scheduleCronPlaceholder')
                  "
                  class="w-full"
                />
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
              <div class="md:col-span-1">
                <label
                  for="sec-cleanupCron"
                  class="block text-sm font-medium text-gray-700 mb-1"
                  >{{ t('dataCollector.settings.cleanupCron') }}</label
                >
              </div>
              <div class="md:col-span-2">
                <BaseInput
                  id="sec-cleanupCron"
                  v-model="formData.cleanup_cron"
                  type="text"
                  :placeholder="
                    t('dataCollector.settings.cleanupCronPlaceholder')
                  "
                  class="w-full"
                />
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
              <div class="md:col-span-1">
                <label
                  for="sec-retentionDays"
                  class="block text-sm font-medium text-gray-700 mb-1"
                  >{{ t('dataCollector.settings.retentionDays') }}</label
                >
              </div>
              <div class="md:col-span-2">
                <BaseInput
                  id="sec-retentionDays"
                  v-model.number="formData.retention_days"
                  type="number"
                  min="1"
                  class="w-full"
                />
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 items-start">
              <div class="md:col-span-1">
                <label
                  for="sec-initialRange"
                  class="block text-sm font-medium text-gray-700 mb-1"
                  >{{ t('dataCollector.settings.initialRange') }}</label
                >
              </div>
              <div class="md:col-span-2">
                <select
                  id="sec-initialRange"
                  v-model="formData.initial_range"
                  class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <template v-if="formData.platform === 'feishu'">
                    <option value="10d">
                      {{ t('dataCollector.settings.initialRange10d') }}
                    </option>
                    <option value="30d">
                      {{ t('dataCollector.settings.initialRange30d') }}
                    </option>
                  </template>
                  <template v-else>
                    <option value="1m">
                      {{ t('dataCollector.settings.initialRange1m') }}
                    </option>
                    <option value="3m">
                      {{ t('dataCollector.settings.initialRange3m') }}
                    </option>
                  </template>
                </select>
              </div>
            </div>
          </section>
        </div>
      </template>
    </div>

    <template #footer>
      <div class="flex flex-col-reverse sm:flex-row justify-end gap-3">
        <BaseButton
          variant="outline"
          @click="$emit('close')"
          class="w-full sm:w-auto"
        >
          {{ isSectionEditMode ? t('common.close') : t('common.cancel') }}
        </BaseButton>
        <template v-if="isSectionEditMode">
          <BaseButton
            type="button"
            :loading="savingSection"
            :disabled="savingSection"
            @click="handleSaveSection"
            class="w-full sm:w-auto"
          >
            {{ savingSection ? t('common.saving') : t('common.save') }}
          </BaseButton>
        </template>
        <template v-else-if="currentStep === 1">
          <BaseButton
            type="button"
            variant="outline"
            :loading="authVerifying"
            :disabled="!step1AuthFieldsFilled || authVerifying"
            :title="
              !step1AuthFieldsFilled
                ? t('dataCollector.settings.verifyAuthRequired')
                : ''
            "
            @click="handleVerifyAuth"
            class="w-full sm:w-auto"
          >
            {{
              authVerifying
                ? t('common.loading')
                : t('dataCollector.settings.verifyAuth')
            }}
          </BaseButton>
          <BaseButton
            type="button"
            :disabled="!canGoNextFromStep1"
            :title="
              !canGoNextFromStep1 ? t('dataCollector.settings.verifyFirst') : ''
            "
            @click="goToProjectStep"
            class="w-full sm:w-auto"
          >
            {{ t('dataCollector.settings.nextStep') }}
          </BaseButton>
        </template>
        <template v-else-if="currentStep === 2 && isFullEditMode">
          <BaseButton
            variant="outline"
            @click="currentStep = 1"
            class="w-full sm:w-auto"
          >
            {{ t('dataCollector.settings.prevStep') }}
          </BaseButton>
          <BaseButton
            type="button"
            :loading="saving"
            :disabled="saving || !canGoNextFromStep2"
            @click="handleSubmit"
            class="w-full sm:w-auto"
          >
            {{ saving ? t('common.saving') : t('common.save') }}
          </BaseButton>
        </template>
        <template v-else-if="currentStep === 2">
          <BaseButton
            variant="outline"
            @click="currentStep = 1"
            class="w-full sm:w-auto"
          >
            {{ t('dataCollector.settings.prevStep') }}
          </BaseButton>
          <BaseButton
            type="button"
            :disabled="!canGoNextFromStep2"
            @click="currentStep = 3"
            class="w-full sm:w-auto"
          >
            {{ t('dataCollector.settings.nextStep') }}
          </BaseButton>
        </template>
        <template v-else>
          <BaseButton
            variant="outline"
            @click="currentStep = 2"
            class="w-full sm:w-auto"
          >
            {{ t('dataCollector.settings.prevStep') }}
          </BaseButton>
          <BaseButton
            :loading="saving"
            :disabled="saving"
            @click="handleSubmit"
            class="w-full sm:w-auto"
          >
            {{ saving ? t('common.saving') : t('common.save') }}
          </BaseButton>
        </template>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, watch, reactive, computed, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '@/composables/useToast'
import { extractResponseData, extractErrorMessage } from '@/utils/api'
import { dataCollectorApi } from '@/api/dataCollector'
import BaseModal from '@/components/ui/BaseModal.vue'
import BaseInput from '@/components/ui/BaseInput.vue'
import BaseButton from '@/components/ui/BaseButton.vue'

const props = defineProps({
  show: { type: Boolean, default: false },
  config: { type: Object, default: null },
  editSection: { type: String, default: null }
})

const emit = defineEmits(['close', 'saved', 'section-saved'])

const { t } = useI18n()
const { showSuccess, showError } = useToast()
const saving = ref(false)
const savingSchedule = ref(false)
const currentStep = ref(1)
const projects = ref([])
const projectsLoading = ref(false)
const projectsError = ref('')
const step1AuthVerified = ref(false)
const authVerifying = ref(false)
const authError = ref('')
const aiPriceHubLlmOptions = ref([])
const aiPriceHubLlmOptionsLoading = ref(false)
const aiPriceHubLlmLoadError = ref('')

const formData = reactive({
  platform: 'jira',
  key: '',
  is_enabled: true,
  // Jira-specific fields
  jira_auth_version: 'legacy',
  jira_base_url: '',
  jira_username: '',
  jira_password: '',
  jira_email: '',
  jira_api_token: '',
  // Feishu-specific fields
  feishu_app_id: '',
  feishu_app_secret: '',
  feishu_definitions: [],
  // License-specific fields
  license_base_url: '',
  license_username: '',
  license_password: '',
  // HyperBDR-specific fields
  hyperbdr_base_url: '',
  hyperbdr_username: '',
  hyperbdr_password: '',
  // AI Price Hub-specific fields
  ai_pricehub_platform_slug: 'agione',
  ai_pricehub_vendor_name: 'AGIOne',
  ai_pricehub_region: '',
  ai_pricehub_endpoint_url: '',
  ai_pricehub_currency: 'CNY',
  ai_pricehub_points_per_currency_unit: 10.0,
  ai_pricehub_parser_llm_config_uuid: '',
  // Common fields
  selected_project_keys: [],
  schedule_cron: '0 */2 * * *',
  cleanup_cron: '0 3 * * *',
  retention_days: 180,
  initial_range: '1m'
})

const isSectionEditMode = computed(
  () => !!props.config && props.editSection === 'schedule'
)
const isFullEditMode = computed(
  () => !!props.config && props.editSection === 'full'
)
const aiPriceHubLlmSelectOptions = computed(() => {
  const base = Array.isArray(aiPriceHubLlmOptions.value)
    ? [...aiPriceHubLlmOptions.value]
    : []
  const selected = (formData.ai_pricehub_parser_llm_config_uuid || '').trim()
  if (selected && !base.find((item) => item.uuid === selected)) {
    base.unshift({
      uuid: selected,
      label: `${selected} (${t('dataCollector.aiPriceHub.currentSelected')})`
    })
  }
  return base
})

const modalTitle = computed(() => {
  if (!props.config) return t('dataCollector.settings.addConfig')
  if (props.editSection === 'full')
    return t('dataCollector.settings.editConfig')
  if (props.editSection === 'schedule')
    return t('dataCollector.settings.editScheduleAndRetention')
  return t('dataCollector.settings.editConfig')
})

const savingSection = computed(() => {
  if (props.editSection === 'schedule') return savingSchedule.value
  return false
})

const step1AuthFieldsFilled = computed(() => {
  if (formData.platform === 'jira') {
    const base = (formData.jira_base_url || '').trim()
    if (!base) return false
    if (formData.jira_auth_version === 'legacy') {
      return (
        !!(formData.jira_username || '').trim() &&
        !!(formData.jira_password || '').trim()
      )
    }
    return (
      !!(formData.jira_email || '').trim() &&
      !!(formData.jira_api_token || '').trim()
    )
  }
  if (formData.platform === 'feishu') {
    return (
      !!(formData.feishu_app_id || '').trim() &&
      !!(formData.feishu_app_secret || '').trim()
    )
  }
  if (formData.platform === 'license') {
    return (
      !!(formData.license_base_url || '').trim() &&
      !!(formData.license_username || '').trim() &&
      !!(formData.license_password || '').trim()
    )
  }
  if (formData.platform === 'hyperbdr') {
    return (
      !!(formData.hyperbdr_base_url || '').trim() &&
      !!(formData.hyperbdr_username || '').trim() &&
      (!!(formData.hyperbdr_password || '').trim() || !!props.config)
    )
  }
  if (formData.platform === 'ai_pricehub') {
    return (
      !!(formData.ai_pricehub_platform_slug || '').trim() &&
      !!(formData.ai_pricehub_vendor_name || '').trim() &&
      !!(formData.ai_pricehub_endpoint_url || '').trim() &&
      !!(formData.ai_pricehub_currency || '').trim() &&
      Number(formData.ai_pricehub_points_per_currency_unit) > 0 &&
      !!(formData.ai_pricehub_parser_llm_config_uuid || '').trim()
    )
  }
  return false
})

const canGoNextFromStep1 = computed(() => step1AuthVerified.value)

const canGoNextFromStep2 = computed(() => {
  if (
    formData.platform === 'jira' ||
    formData.platform === 'license' ||
    formData.platform === 'ai_pricehub'
  ) {
    return (
      Array.isArray(formData.selected_project_keys) &&
      formData.selected_project_keys.length > 0
    )
  }
  if (formData.platform === 'feishu') {
    const defs = Array.isArray(formData.feishu_definitions)
      ? formData.feishu_definitions
      : []
    const validDefs = defs.filter(
      (d) => (d.id || '').trim() && (d.name || '').trim()
    )
    return validDefs.length > 0
  }
  return true
})

async function handleVerifyAuth() {
  authError.value = ''
  authVerifying.value = true
  try {
    const value = buildAuthValue()
    const res = await dataCollectorApi.validateConfigPayload(
      formData.platform,
      value
    )
    const data = extractResponseData(res)
    if (data && data.valid) {
      step1AuthVerified.value = true
      showSuccess(t('dataCollector.settings.verifyAuthSuccess'))
    } else {
      step1AuthVerified.value = false
      const msg =
        data && data.message
          ? data.message
          : t('dataCollector.settings.verifyAuthRequired')
      authError.value = msg
      showError(msg)
    }
  } catch (e) {
    step1AuthVerified.value = false
    const msg = extractErrorMessage(
      e,
      t('dataCollector.settings.verifyAuthRequired')
    )
    authError.value = msg
    showError(msg)
  } finally {
    authVerifying.value = false
  }
}

function buildAuthValue() {
  if (formData.platform === 'jira') {
    const value = { base_url: formData.jira_base_url }
    value.auth = {
      auth_version: formData.jira_auth_version,
      base_url: formData.jira_base_url
    }
    if (formData.jira_auth_version === 'legacy') {
      value.auth.username = formData.jira_username
      value.auth.password = formData.jira_password
    } else {
      value.auth.email = formData.jira_email
      value.auth.api_token = formData.jira_api_token
    }
    return value
  }
  if (formData.platform === 'feishu') {
    return {
      auth: {
        app_id: formData.feishu_app_id,
        app_secret: formData.feishu_app_secret
      }
    }
  }
  if (formData.platform === 'license') {
    return {
      base_url: formData.license_base_url,
      auth: {
        username: formData.license_username,
        password: formData.license_password
      }
    }
  }
  if (formData.platform === 'hyperbdr') {
    return {
      base_url: formData.hyperbdr_base_url,
      auth: {
        base_url: formData.hyperbdr_base_url,
        username: formData.hyperbdr_username,
        password: formData.hyperbdr_password
      }
    }
  }
  if (formData.platform === 'ai_pricehub') {
    return {
      primary_sources: [
        {
          id: 1,
          vendor_slug: 'agione',
          platform_slug: (formData.ai_pricehub_platform_slug || '').trim(),
          vendor_name: (formData.ai_pricehub_vendor_name || '').trim(),
          region: (formData.ai_pricehub_region || '').trim(),
          endpoint_url: (formData.ai_pricehub_endpoint_url || '').trim(),
          parser_llm_config_uuid: (
            formData.ai_pricehub_parser_llm_config_uuid || ''
          ).trim(),
          currency: (formData.ai_pricehub_currency || '').trim() || 'CNY',
          points_per_currency_unit:
            Number(formData.ai_pricehub_points_per_currency_unit) || 10.0,
          is_enabled: true,
          notes: ''
        }
      ]
    }
  }
  return {}
}

function buildAuthValueForPatch() {
  if (formData.platform === 'hyperbdr') {
    return {
      base_url: formData.hyperbdr_base_url,
      auth: {
        base_url: formData.hyperbdr_base_url,
        username: formData.hyperbdr_username,
        password: formData.hyperbdr_password
      }
    }
  }
  if (formData.platform === 'ai_pricehub') {
    return {
      primary_sources: [
        {
          id: 1,
          vendor_slug: 'agione',
          platform_slug: (formData.ai_pricehub_platform_slug || '').trim(),
          vendor_name: (formData.ai_pricehub_vendor_name || '').trim(),
          region: (formData.ai_pricehub_region || '').trim(),
          endpoint_url: (formData.ai_pricehub_endpoint_url || '').trim(),
          parser_llm_config_uuid: (
            formData.ai_pricehub_parser_llm_config_uuid || ''
          ).trim(),
          currency: (formData.ai_pricehub_currency || '').trim() || 'CNY',
          points_per_currency_unit:
            Number(formData.ai_pricehub_points_per_currency_unit) || 10.0,
          is_enabled: true,
          notes: ''
        }
      ]
    }
  }
  if (formData.platform === 'license') {
    return {
      base_url: formData.license_base_url,
      auth: {
        username: formData.license_username,
        password: formData.license_password
      }
    }
  }
  const v = {
    base_url: formData.jira_base_url,
    auth: {
      auth_version: formData.jira_auth_version,
      base_url: formData.jira_base_url
    }
  }
  if (formData.jira_auth_version === 'legacy') {
    v.auth.username = formData.jira_username
    v.auth.password = formData.jira_password
  } else {
    v.auth.email = formData.jira_email
    v.auth.api_token = formData.jira_api_token
  }
  return v
}

function buildFullEditValueForPatch() {
  const authPatch = buildAuthValueForPatch()
  if (formData.platform === 'hyperbdr') {
    return authPatch
  }
  const projectKeys = Array.isArray(formData.selected_project_keys)
    ? formData.selected_project_keys
    : []
  return {
    ...authPatch,
    project_keys: projectKeys
  }
}

function buildScheduleValueForPatch() {
  return {
    schedule_cron: formData.schedule_cron || '0 */2 * * *',
    cleanup_cron: formData.cleanup_cron || '0 3 * * *',
    retention_days: formData.retention_days ?? 180,
    initial_range: formData.initial_range || '1m'
  }
}

function buildValue() {
  const value = {
    schedule_cron: formData.schedule_cron || '0 */2 * * *',
    cleanup_cron: formData.cleanup_cron || '0 3 * * *',
    retention_days: formData.retention_days || 180,
    initial_range: formData.initial_range || '1m',
    runtime_state: {
      first_collect_at: null,
      last_collect_start_at: null,
      last_collect_end_at: null,
      last_success_collect_at: null,
      last_validate_at: null,
      last_cleanup_at: null
    }
  }
  if (formData.platform === 'jira') {
    value.base_url = formData.jira_base_url
    value.auth = {
      auth_version: formData.jira_auth_version,
      base_url: formData.jira_base_url
    }
    if (formData.jira_auth_version === 'legacy') {
      value.auth.username = formData.jira_username
      value.auth.password = formData.jira_password
    } else {
      value.auth.email = formData.jira_email
      value.auth.api_token = formData.jira_api_token
    }
    value.project_keys = Array.isArray(formData.selected_project_keys)
      ? formData.selected_project_keys
      : []
  } else if (formData.platform === 'feishu') {
    value.auth = {
      app_id: formData.feishu_app_id,
      app_secret: formData.feishu_app_secret
    }
    const defs = Array.isArray(formData.feishu_definitions)
      ? formData.feishu_definitions
          .map((d) => ({
            id: String(d.id || '').trim(),
            name: String(d.name || '').trim()
          }))
          .filter((d) => d.id && d.name)
      : []
    value.approval_definitions = defs
    value.project_keys = defs.map((d) => d.id)
  } else if (formData.platform === 'license') {
    value.base_url = formData.license_base_url
    value.auth = {
      username: formData.license_username,
      password: formData.license_password
    }
    value.project_keys = Array.isArray(formData.selected_project_keys)
      ? formData.selected_project_keys
      : []
  } else if (formData.platform === 'hyperbdr') {
    value.base_url = formData.hyperbdr_base_url
    value.auth = {
      base_url: formData.hyperbdr_base_url,
      username: formData.hyperbdr_username,
      password: formData.hyperbdr_password
    }
  } else if (formData.platform === 'ai_pricehub') {
    value.primary_sources = [
      {
        id: 1,
        vendor_slug: 'agione',
        platform_slug: (formData.ai_pricehub_platform_slug || '').trim(),
        vendor_name: (formData.ai_pricehub_vendor_name || '').trim(),
        region: (formData.ai_pricehub_region || '').trim(),
        endpoint_url: (formData.ai_pricehub_endpoint_url || '').trim(),
        parser_llm_config_uuid: (
          formData.ai_pricehub_parser_llm_config_uuid || ''
        ).trim(),
        currency: (formData.ai_pricehub_currency || '').trim() || 'CNY',
        points_per_currency_unit:
          Number(formData.ai_pricehub_points_per_currency_unit) || 10.0,
        is_enabled: true,
        notes: ''
      }
    ]
    value.project_keys = Array.isArray(formData.selected_project_keys)
      ? formData.selected_project_keys
      : ['sync']
  }
  return value
}

function applyConfig(c) {
  if (!c) return
  const v = c.value || {}
  const auth = v.auth || {}
  formData.platform = c.platform || 'jira'
  formData.key = c.key || ''
  formData.is_enabled = c.is_enabled !== false
  formData.jira_auth_version = auth.auth_version || 'legacy'
  formData.jira_base_url = v.base_url || auth.base_url || ''
  formData.jira_username = auth.username || ''
  formData.jira_password = ''
  formData.jira_email = auth.email || ''
  formData.jira_api_token = ''
  formData.license_base_url = v.base_url || auth.base_url || ''
  formData.license_username = auth.username || ''
  formData.license_password = ''
  formData.hyperbdr_base_url = v.base_url || auth.base_url || ''
  formData.hyperbdr_username = auth.username || ''
  formData.hyperbdr_password = ''
  // Feishu 只在新建时从表单获取，编辑时不回显密钥
  formData.feishu_app_id = auth.app_id || ''
  formData.feishu_app_secret = ''
  formData.feishu_definitions = Array.isArray(v.approval_definitions)
    ? v.approval_definitions.map((d) => ({
        id: d.id ?? d.code ?? d.key ?? '',
        name: d.name ?? ''
      }))
    : []
  formData.selected_project_keys = Array.isArray(v.project_keys)
    ? [...v.project_keys]
    : formData.platform === 'feishu'
      ? formData.feishu_definitions.map((d) => d.id).filter((x) => x)
      : formData.platform === 'ai_pricehub'
        ? ['sync']
        : []
  const primarySource =
    Array.isArray(v.primary_sources) && v.primary_sources.length > 0
      ? v.primary_sources[0]
      : null
  formData.ai_pricehub_platform_slug = primarySource?.platform_slug || 'agione'
  formData.ai_pricehub_vendor_name = primarySource?.vendor_name || 'AGIOne'
  formData.ai_pricehub_region = primarySource?.region || ''
  formData.ai_pricehub_endpoint_url = primarySource?.endpoint_url || ''
  formData.ai_pricehub_currency = primarySource?.currency || 'CNY'
  formData.ai_pricehub_points_per_currency_unit =
    Number(primarySource?.points_per_currency_unit) || 10.0
  formData.ai_pricehub_parser_llm_config_uuid =
    primarySource?.parser_llm_config_uuid || ''
  formData.schedule_cron = v.schedule_cron || '0 */2 * * *'
  formData.cleanup_cron = v.cleanup_cron || '0 3 * * *'
  formData.retention_days = v.retention_days ?? 180
  formData.initial_range = v.initial_range || '1m'
}

watch(
  () => props.config,
  (c) => {
    applyConfig(c)
    if ((c?.platform || formData.platform) === 'ai_pricehub') {
      loadAiPriceHubLlmOptions()
    }
    const v = c?.value || {}
    const hasBaseUrl = !!(v.base_url || v.auth?.base_url)
    const needProjects =
      (props.editSection === 'full' || props.editSection === 'sync') &&
      (formData.platform === 'jira' ||
        formData.platform === 'license' ||
        formData.platform === 'ai_pricehub')
    const canLoadProjects =
      (formData.platform === 'jira' && hasBaseUrl) ||
      (formData.platform === 'license' && hasBaseUrl) ||
      formData.platform === 'ai_pricehub'
    if (needProjects && canLoadProjects) {
      nextTick(loadProjectsIfNeeded)
    }
  },
  { immediate: true }
)

watch(
  () => props.show,
  (visible) => {
    if (visible) {
      step1AuthVerified.value = false
      authError.value = ''
      authVerifying.value = false
      if (props.config) {
        applyConfig(props.config)
        currentStep.value = 1
        projects.value = []
        projectsError.value = ''
      } else {
        formData.platform = 'jira'
        formData.key = ''
        formData.is_enabled = true
        formData.jira_auth_version = 'legacy'
        formData.jira_base_url = ''
        formData.jira_username = ''
        formData.jira_password = ''
        formData.jira_email = ''
        formData.jira_api_token = ''
        formData.feishu_app_id = ''
        formData.feishu_app_secret = ''
        formData.feishu_definitions = []
        formData.license_base_url = ''
        formData.license_username = ''
        formData.license_password = ''
        formData.hyperbdr_base_url = ''
        formData.hyperbdr_username = ''
        formData.hyperbdr_password = ''
        formData.ai_pricehub_platform_slug = 'agione'
        formData.ai_pricehub_vendor_name = 'AGIOne'
        formData.ai_pricehub_region = ''
        formData.ai_pricehub_endpoint_url = ''
        formData.ai_pricehub_currency = 'CNY'
        formData.ai_pricehub_points_per_currency_unit = 10.0
        formData.ai_pricehub_parser_llm_config_uuid = ''
        formData.selected_project_keys = []
        formData.schedule_cron = '0 */2 * * *'
        formData.cleanup_cron = '0 3 * * *'
        formData.retention_days = 180
        formData.initial_range = '1m'
        currentStep.value = 1
        projects.value = []
        projectsError.value = ''
      }
      if (formData.platform === 'ai_pricehub') {
        loadAiPriceHubLlmOptions()
      }
    }
  }
)

watch(
  () => [
    formData.jira_base_url,
    formData.jira_username,
    formData.jira_password,
    formData.jira_email,
    formData.jira_api_token,
    formData.jira_auth_version,
    formData.license_base_url,
    formData.license_username,
    formData.license_password,
    formData.hyperbdr_base_url,
    formData.hyperbdr_username,
    formData.hyperbdr_password
  ],
  () => {
    projects.value = []
    projectsError.value = ''
  }
)

watch(
  () => ({
    platform: formData.platform,
    key: formData.key,
    jira_base_url: formData.jira_base_url,
    jira_username: formData.jira_username,
    jira_password: formData.jira_password,
    jira_email: formData.jira_email,
    jira_api_token: formData.jira_api_token,
    jira_auth_version: formData.jira_auth_version,
    feishu_app_id: formData.feishu_app_id,
    feishu_app_secret: formData.feishu_app_secret,
    license_base_url: formData.license_base_url,
    license_username: formData.license_username,
    license_password: formData.license_password,
    hyperbdr_base_url: formData.hyperbdr_base_url,
    hyperbdr_username: formData.hyperbdr_username,
    hyperbdr_password: formData.hyperbdr_password,
    ai_pricehub_platform_slug: formData.ai_pricehub_platform_slug,
    ai_pricehub_vendor_name: formData.ai_pricehub_vendor_name,
    ai_pricehub_region: formData.ai_pricehub_region,
    ai_pricehub_endpoint_url: formData.ai_pricehub_endpoint_url,
    ai_pricehub_currency: formData.ai_pricehub_currency,
    ai_pricehub_points_per_currency_unit:
      formData.ai_pricehub_points_per_currency_unit,
    ai_pricehub_parser_llm_config_uuid:
      formData.ai_pricehub_parser_llm_config_uuid
  }),
  () => {
    step1AuthVerified.value = false
    authError.value = ''
  },
  { deep: true }
)

watch(
  () => currentStep.value,
  (step) => {
    if (step === 1) {
      step1AuthVerified.value = false
      authError.value = ''
    }
  }
)

// 平台切换时，为不同平台设置合适的首次采集范围默认值
watch(
  () => formData.platform,
  (plat) => {
    if (plat === 'feishu') {
      if (
        !formData.initial_range ||
        formData.initial_range === '1m' ||
        formData.initial_range === '3m'
      ) {
        formData.initial_range = '10d'
      }
    } else if (plat === 'jira' || plat === 'license' || plat === 'hyperbdr') {
      if (
        formData.initial_range === '10d' ||
        formData.initial_range === '30d' ||
        formData.initial_range === '90d'
      ) {
        formData.initial_range = '1m'
      }
    }
    if (plat === 'ai_pricehub') {
      loadAiPriceHubLlmOptions()
    }
  }
)

async function loadAiPriceHubLlmOptions() {
  if (aiPriceHubLlmOptionsLoading.value) return
  if (aiPriceHubLlmOptions.value.length > 0) return
  aiPriceHubLlmOptionsLoading.value = true
  aiPriceHubLlmLoadError.value = ''
  try {
    const res = await dataCollectorApi.getLlmOptions()
    const payload = extractResponseData(res)
    const rows = Array.isArray(payload?.options)
      ? payload.options
      : Array.isArray(payload)
        ? payload
        : []
    aiPriceHubLlmOptions.value = rows
      .map((item) => {
        const uuid = String(item?.uuid || '').trim()
        if (!uuid) return null
        const model = item?.config?.model || item?.provider || uuid
        const provider = item?.provider || ''
        const label = provider ? `${model} (${provider})` : model
        return { uuid, label }
      })
      .filter(Boolean)
  } catch (e) {
    aiPriceHubLlmLoadError.value = extractErrorMessage(
      e,
      t('dataCollector.aiPriceHub.parserLlmLoadError')
    )
    aiPriceHubLlmOptions.value = []
  } finally {
    aiPriceHubLlmOptionsLoading.value = false
  }
}

async function loadProjectsIfNeeded() {
  if (
    formData.platform !== 'jira' &&
    formData.platform !== 'license' &&
    formData.platform !== 'ai_pricehub'
  )
    return
  if (projects.value.length > 0) return
  projectsLoading.value = true
  projectsError.value = ''
  try {
    if (formData.platform === 'ai_pricehub') {
      projects.value = [
        {
          key: 'sync',
          id: 'sync',
          name: t('dataCollector.aiPriceHub.syncCollection')
        }
      ]
      if (
        !Array.isArray(formData.selected_project_keys) ||
        formData.selected_project_keys.length === 0
      ) {
        formData.selected_project_keys = ['sync']
      }
      return
    }
    const configUuid = props.config?.uuid ?? null
    const value = buildAuthValue()
    const res = await dataCollectorApi.fetchProjects(
      formData.platform,
      value,
      configUuid
    )
    const data = extractResponseData(res)
    projects.value = data?.projects ?? []
  } catch (e) {
    projectsError.value = extractErrorMessage(
      e,
      t('dataCollector.settings.noProjects')
    )
    projects.value = []
  } finally {
    projectsLoading.value = false
  }
}

function goToProjectStep() {
  currentStep.value = 2
  loadProjectsIfNeeded()
}

watch(currentStep, (step) => {
  if (step === 2) {
    loadProjectsIfNeeded()
  }
})

watch(
  () => [props.show, props.editSection],
  ([visible, section]) => {
    const needLoad =
      visible &&
      props.config &&
      (section === 'full' || section === 'sync') &&
      ((formData.platform === 'jira' && formData.jira_base_url) ||
        (formData.platform === 'license' && formData.license_base_url) ||
        formData.platform === 'ai_pricehub')
    if (needLoad) {
      loadProjectsIfNeeded()
    }
  },
  { immediate: true }
)

async function handleSaveSchedule() {
  savingSchedule.value = true
  try {
    const res = await dataCollectorApi.patchConfig(props.config.uuid, {
      value: buildScheduleValueForPatch(),
      is_enabled: formData.is_enabled,
      version: props.config.version
    })
    const data = extractResponseData(res)
    if (data) applyConfig(data)
    showSuccess(t('dataCollector.settings.scheduleUpdateSuccess'))
    emit('section-saved', data)
  } catch (e) {
    showError(extractErrorMessage(e, t('common.error')))
  } finally {
    savingSchedule.value = false
  }
}

async function handleSaveSection() {
  if (props.editSection === 'schedule') await handleSaveSchedule()
}

function addFeishuDefinition() {
  if (!Array.isArray(formData.feishu_definitions)) {
    formData.feishu_definitions = []
  }
  formData.feishu_definitions.push({ id: '', name: '' })
}

function removeFeishuDefinition(index) {
  if (!Array.isArray(formData.feishu_definitions)) return
  formData.feishu_definitions.splice(index, 1)
}

async function handleSubmit() {
  // 步骤 2 校验：Jira 需要至少选一个项目；Feishu 需要至少配置一个审批定义
  if (!canGoNextFromStep2.value) {
    showError(t('dataCollector.settings.selectAtLeastOne'))
    return
  }
  saving.value = true
  try {
    const keyTrimmed = (formData.key || '').trim()
    if (!keyTrimmed) {
      showError(t('dataCollector.settings.keyRequired'))
      return
    }
    if (isFullEditMode.value) {
      await dataCollectorApi.patchConfig(props.config.uuid, {
        key: keyTrimmed,
        value: buildFullEditValueForPatch(),
        is_enabled: formData.is_enabled,
        version: props.config.version
      })
      showSuccess(t('dataCollector.settings.updateSuccess'))
      emit('section-saved', null)
      emit('close')
    } else {
      const value = buildValue()
      if (props.config) {
        await dataCollectorApi.patchConfig(props.config.uuid, {
          key: keyTrimmed,
          value,
          is_enabled: formData.is_enabled,
          version: props.config.version
        })
        showSuccess(t('dataCollector.settings.updateSuccess'))
      } else {
        await dataCollectorApi.createConfig({
          platform: formData.platform,
          key: keyTrimmed,
          value,
          is_enabled: formData.is_enabled
        })
        showSuccess(t('dataCollector.settings.createSuccess'))
      }
      emit('saved')
      emit('close')
    }
  } catch (e) {
    const msg = extractErrorMessage(e, t('common.error'))
    showError(msg)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Transition
    enter-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-150"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="show"
      class="fixed inset-0 bg-gray-900 bg-opacity-50 z-40"
      @click="handleClose"
    />
  </Transition>
  <Transition
    enter-active-class="transition-transform duration-300 ease-out"
    enter-from-class="translate-x-full"
    enter-to-class="translate-x-0"
    leave-active-class="transition-transform duration-250 ease-in"
    leave-from-class="translate-x-0"
    leave-to-class="translate-x-full"
  >
    <div
      v-if="show"
      class="fixed inset-y-0 right-0 w-full max-w-2xl bg-white shadow-xl z-50 flex flex-col"
    >
      <div
        class="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100 flex-shrink-0"
      >
        <h2 class="text-lg font-semibold text-gray-900">
          {{ t('dataCollector.records.detailTitle') }}
        </h2>
        <button
          type="button"
          class="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          @click="handleClose"
        >
          <svg
            class="w-5 h-5"
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
      <nav
        v-if="record"
        class="flex border-b border-gray-200 px-6 flex-shrink-0 bg-gray-50"
      >
        <button
          type="button"
          :class="
            activeTab === 'detail'
              ? 'border-primary-600 text-primary-600 bg-white -mb-px'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          "
          class="px-4 py-3 text-sm font-medium border-b-2 transition-colors"
          @click="activeTab = 'detail'"
        >
          {{ t('dataCollector.records.tabDetail') }}
        </button>
        <button
          v-if="record.platform !== 'license'"
          type="button"
          :class="
            activeTab === 'comments'
              ? 'border-primary-600 text-primary-600 bg-white -mb-px'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          "
          class="px-4 py-3 text-sm font-medium border-b-2 transition-colors"
          @click="activeTab = 'comments'"
        >
          <span v-if="record.platform === 'feishu'">
            {{ t('dataCollector.records.tabApprovalFlow') }}
          </span>
          <span v-else>
            {{ t('dataCollector.records.tabComments') }}
          </span>
          <span
            v-if="
              record.platform === 'feishu'
                ? feishuTimelineRows.length
                : commentsList.length
            "
            class="ml-1 text-gray-500"
          >
            ({{
              record.platform === 'feishu'
                ? feishuTimelineRows.length
                : commentsList.length
            }})
          </span>
        </button>
        <button
          v-if="record.platform !== 'license'"
          type="button"
          :class="
            activeTab === 'attachments'
              ? 'border-primary-600 text-primary-600 bg-white -mb-px'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          "
          class="px-4 py-3 text-sm font-medium border-b-2 transition-colors"
          @click="activeTab = 'attachments'"
        >
          {{ t('dataCollector.records.tabAttachments') }}
          <span v-if="effectiveAttachments.length" class="ml-1 text-gray-500"
            >({{ effectiveAttachments.length }})</span
          >
        </button>
      </nav>
      <div class="flex-1 overflow-y-auto min-h-0">
        <BaseLoading v-if="loading && !record" class="p-8" />
        <div v-else-if="!record" class="p-6 text-center text-sm text-gray-500">
          {{ t('dataCollector.records.recordNotFound') }}
        </div>
        <template v-else>
          <div v-show="activeTab === 'detail'" class="p-6 space-y-6">
            <section v-if="record.platform === 'jira'" class="jira-basic-data">
              <h3 class="text-sm font-semibold text-gray-900 mb-4">
                {{ t('dataCollector.records.basicData') }}
              </h3>
              <dl class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div>
                  <dt class="text-gray-500">
                    {{ t('dataCollector.records.platform') }}
                  </dt>
                  <dd class="font-medium text-gray-900">
                    {{ record.platform }}
                  </dd>
                </div>
                <div>
                  <dt class="text-gray-500">
                    {{ t('dataCollector.records.sourceId') }}
                  </dt>
                  <dd class="font-medium text-gray-900">
                    {{ record.source_unique_id }}
                  </dd>
                </div>
                <div class="sm:col-span-2">
                  <dt class="text-gray-500">
                    {{ t('dataCollector.records.title') }}
                  </dt>
                  <dd class="font-medium text-gray-900">{{ displayTitle }}</dd>
                </div>
                <template v-if="jiraKeyFields">
                  <div v-for="(v, k) in jiraKeyFields" :key="k">
                    <dt class="text-gray-500">{{ k }}</dt>
                    <dd class="text-gray-900 break-words">{{ v }}</dd>
                  </div>
                </template>
                <div>
                  <dt class="text-gray-500">
                    {{ t('dataCollector.records.lastCollected') }}
                  </dt>
                  <dd class="text-gray-900">
                    {{ formatDate(record.last_collected_at) }}
                  </dd>
                </div>
                <div>
                  <dt class="text-gray-500">
                    {{ t('dataCollector.records.deleted') }}
                  </dt>
                  <dd
                    :class="
                      record.is_deleted ? 'text-red-600' : 'text-gray-900'
                    "
                  >
                    {{ record.is_deleted ? t('common.yes') : t('common.no') }}
                  </dd>
                </div>
                <div
                  v-if="
                    record.filter_metadata &&
                    Object.keys(record.filter_metadata).length
                  "
                  class="sm:col-span-2"
                >
                  <dt class="text-gray-500">
                    {{ t('dataCollector.records.filterMetadata') }}
                  </dt>
                  <dd class="flex flex-wrap gap-2 mt-1">
                    <span
                      v-for="(val, key) in record.filter_metadata"
                      :key="key"
                      class="inline-flex items-center rounded-md bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700"
                    >
                      {{ key }}: {{ val }}
                    </span>
                  </dd>
                </div>
              </dl>
            </section>

            <section
              v-if="record.platform === 'jira' && jiraDescriptionText"
              class="mt-6"
            >
              <h3 class="text-sm font-semibold text-gray-900 mb-4">
                {{ t('dataCollector.records.issueDescription') }}
              </h3>
              <div class="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div
                  class="text-sm text-gray-900 whitespace-pre-wrap break-words"
                >
                  {{ jiraDescriptionText }}
                </div>
              </div>
            </section>

            <template v-else>
              <section>
                <h3 class="text-sm font-semibold text-gray-900 mb-4">
                  {{ t('dataCollector.records.basicInfo') }}
                </h3>
                <dl class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt class="text-gray-500">
                      {{ t('dataCollector.records.platform') }}
                    </dt>
                    <dd class="font-medium text-gray-900">
                      {{ record.platform }}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-gray-500">
                      {{
                        record.platform === 'feishu'
                          ? t('dataCollector.records.approvalInstanceCode')
                          : t('dataCollector.records.sourceId')
                      }}
                    </dt>
                    <dd class="font-medium text-gray-900">
                      {{ record.source_unique_id }}
                    </dd>
                  </div>
                  <div
                    v-if="record.platform === 'license'"
                    class="sm:col-span-2"
                  >
                    <dt class="text-gray-500">
                      {{ t('dataCollector.records.resourceType') }}
                    </dt>
                    <dd class="font-medium text-gray-900">
                      {{ t('dataCollector.records.order') }}
                    </dd>
                  </div>
                  <div v-else class="sm:col-span-2">
                    <dt class="text-gray-500">
                      {{
                        record.platform === 'feishu'
                          ? t('dataCollector.records.approvalName')
                          : t('dataCollector.records.title')
                      }}
                    </dt>
                    <dd class="font-medium text-gray-900">
                      {{
                        record.platform === 'feishu'
                          ? (record.filter_metadata?.approval_name ??
                            displayTitle)
                          : displayTitle
                      }}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-gray-500">
                      {{ t('dataCollector.records.lastCollected') }}
                    </dt>
                    <dd class="text-gray-900">
                      {{ formatDate(record.last_collected_at) }}
                    </dd>
                  </div>
                  <div>
                    <dt class="text-gray-500">
                      {{ t('dataCollector.records.deleted') }}
                    </dt>
                    <dd
                      :class="
                        record.is_deleted ? 'text-red-600' : 'text-gray-900'
                      "
                    >
                      {{ record.is_deleted ? t('common.yes') : t('common.no') }}
                    </dd>
                  </div>
                </dl>
              </section>
              <section
                v-if="
                  record.filter_metadata &&
                  Object.keys(record.filter_metadata).length
                "
              >
                <h3 class="text-sm font-semibold text-gray-900 mb-4">
                  {{ t('dataCollector.records.filterMetadata') }}
                </h3>
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="(val, key) in record.filter_metadata"
                    :key="key"
                    class="inline-flex items-center rounded-md bg-gray-100 px-2.5 py-1 text-sm font-medium text-gray-700"
                  >
                    {{ key }}: {{ val }}
                  </span>
                </div>
              </section>
            </template>

            <section>
              <button
                type="button"
                class="w-full px-4 py-3 flex items-center justify-between bg-gray-50 border border-gray-200 rounded-t text-left text-sm font-semibold text-gray-700 hover:bg-gray-100"
                @click="showRawData = !showRawData"
              >
                {{ t('dataCollector.records.rawData') }}
                <svg
                  class="w-4 h-4 transition-transform"
                  :class="{ 'rotate-180': showRawData }"
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
              <div
                v-show="showRawData"
                class="p-4 border border-t-0 border-gray-200 rounded-b overflow-x-auto"
              >
                <pre
                  class="text-xs text-gray-700 bg-gray-50 p-4 rounded whitespace-pre-wrap break-words"
                  >{{ rawDataJson }}</pre
                >
              </div>
            </section>
          </div>

          <div v-show="activeTab === 'comments'" class="p-6">
            <!-- Feishu: show approval flow based on instance.timeline -->
            <template v-if="record.platform === 'feishu'">
              <section v-if="feishuTimelineRows.length">
                <h3 class="text-sm font-semibold text-gray-900 mb-4">
                  {{ t('dataCollector.records.approvalFlow') }} ({{
                    feishuTimelineRows.length
                  }})
                </h3>
                <div class="overflow-x-auto border border-gray-200 rounded-lg">
                  <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                      <tr>
                        <th
                          class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                        >
                          {{ t('dataCollector.records.approvalNodeName') }}
                        </th>
                        <th
                          class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                        >
                          {{ t('dataCollector.records.approvalUser') }}
                        </th>
                        <th
                          class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                        >
                          {{ t('dataCollector.records.approvalStatus') }}
                        </th>
                        <th
                          class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase"
                        >
                          {{ t('dataCollector.records.approvalTime') }}
                        </th>
                      </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-100">
                      <tr
                        v-for="row in feishuTimelineRows"
                        :key="row.index"
                        class="hover:bg-gray-50"
                      >
                        <td class="px-4 py-3 text-sm text-gray-700">
                          {{ row.nodeDisplay }}
                        </td>
                        <td class="px-4 py-3 text-sm text-gray-900">
                          <div class="flex items-center gap-2">
                            <span
                              class="inline-flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-primary-500 to-primary-600 text-xs font-semibold text-white uppercase"
                            >
                              {{ (row.userName || '—').slice(0, 2) }}
                            </span>
                            <div class="min-w-0">
                              <div
                                class="text-sm font-medium text-gray-900 truncate"
                              >
                                {{ row.userName || '—' }}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td class="px-4 py-3 text-sm">
                          <span
                            class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium"
                            :class="feishuStatusBadgeClass(row.status)"
                          >
                            {{ row.statusLabel }}
                          </span>
                        </td>
                        <td
                          class="px-4 py-3 text-sm text-gray-700 whitespace-nowrap"
                        >
                          {{ row.time ? formatDate(row.time) : '—' }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </section>
              <div v-else class="py-8 text-center text-sm text-gray-500">
                {{ t('dataCollector.records.noApprovalFlow') }}
              </div>
            </template>

            <!-- Other platforms: keep original comments view -->
            <template v-else>
              <section v-if="commentsList.length">
                <h3 class="text-sm font-semibold text-gray-900 mb-4">
                  {{ t('dataCollector.records.commentsFullData') }} ({{
                    commentsList.length
                  }})
                </h3>
                <ul class="space-y-4">
                  <li
                    v-for="(c, idx) in commentsList"
                    :key="c.id || idx"
                    class="border border-gray-200 rounded-lg p-4 bg-gray-50"
                  >
                    <dl class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                      <div v-if="c.id != null">
                        <dt class="text-gray-500">
                          {{ t('dataCollector.records.commentId') }}
                        </dt>
                        <dd class="text-gray-900 font-mono">{{ c.id }}</dd>
                      </div>
                      <div>
                        <dt class="text-gray-500">
                          {{ t('dataCollector.records.commentAuthor') }}
                        </dt>
                        <dd class="text-gray-900">{{ commentAuthor(c) }}</dd>
                      </div>
                      <div v-if="c.created">
                        <dt class="text-gray-500">
                          {{ t('dataCollector.records.commentCreated') }}
                        </dt>
                        <dd class="text-gray-900">
                          {{ formatDate(c.created) }}
                        </dd>
                      </div>
                      <div v-if="c.updated">
                        <dt class="text-gray-500">
                          {{ t('dataCollector.records.commentUpdated') }}
                        </dt>
                        <dd class="text-gray-900">
                          {{ formatDate(c.updated) }}
                        </dd>
                      </div>
                      <div class="sm:col-span-2">
                        <dt class="text-gray-500">
                          {{ t('dataCollector.records.commentBody') }}
                        </dt>
                        <dd
                          class="text-gray-900 whitespace-pre-wrap break-words mt-1"
                        >
                          {{ commentBodyText(c) }}
                        </dd>
                      </div>
                    </dl>
                    <div class="mt-3 pt-3 border-t border-gray-200">
                      <button
                        type="button"
                        class="w-full px-3 py-2 flex items-center justify-between bg-white border border-gray-200 rounded text-left text-xs font-medium text-gray-600 hover:bg-gray-50"
                        @click="toggleCommentRaw(idx)"
                      >
                        {{ t('dataCollector.records.commentRawData') }}
                        <svg
                          class="w-3.5 h-3.5 transition-transform shrink-0"
                          :class="{ 'rotate-180': expandedCommentRaw.has(idx) }"
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
                      <div
                        v-show="expandedCommentRaw.has(idx)"
                        class="mt-2 p-3 border border-gray-200 rounded overflow-x-auto bg-white"
                      >
                        <pre
                          class="text-xs text-gray-700 whitespace-pre-wrap break-words"
                          >{{ commentRawJson(c) }}</pre
                        >
                      </div>
                    </div>
                  </li>
                </ul>
              </section>
              <div v-else class="py-8 text-center text-sm text-gray-500">
                {{ t('dataCollector.records.noComments') }}
              </div>
            </template>
          </div>

          <div v-show="activeTab === 'attachments'" class="p-6">
            <section v-if="effectiveAttachments.length">
              <h3 class="text-sm font-semibold text-gray-900 mb-4">
                {{ t('dataCollector.records.attachments') }} ({{
                  effectiveAttachments.length
                }})
              </h3>
              <ul class="divide-y divide-gray-200">
                <li
                  v-for="(att, idx) in effectiveAttachments"
                  :key="att.uuid || att.id || idx"
                  class="py-3 flex items-center gap-3"
                >
                  <span
                    class="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center bg-gray-100 text-gray-600"
                    :title="
                      att.file_type ||
                      getFileTypeCategory(att.file_name, att.file_type)
                    "
                  >
                    <svg
                      v-if="
                        getFileTypeCategory(att.file_name, att.file_type) ===
                        'pdf'
                      "
                      class="w-6 h-6"
                      fill="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path
                        d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm-1 2 5 5h-5V4zm-3 10.5a1.5 1.5 0 1 1 3 0 1.5 1.5 0 0 1-3 0zm1.5-4a2.5 2.5 0 0 1 2.45 2h-4.9a2.5 2.5 0 0 1 2.45-2zm5.5 4a1.5 1.5 0 0 1-3 0 1.5 1.5 0 0 1 3 0zm0-4a2.5 2.5 0 0 1-2.45 2h-4.9A2.5 2.5 0 0 1 13 12.5z"
                      />
                    </svg>
                    <svg
                      v-else-if="
                        getFileTypeCategory(att.file_name, att.file_type) ===
                        'image'
                      "
                      class="w-6 h-6"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                      />
                    </svg>
                    <svg
                      v-else-if="
                        getFileTypeCategory(att.file_name, att.file_type) ===
                        'word'
                      "
                      class="w-6 h-6"
                      fill="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        d="M6 2a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6H6zm2 2h5v5h-5V4zm5.5 10.5L11 20H9l2.5-5.5H9.5V13H13v1.5h-1.5L15 20h2l-2.5-5.5H14V14h-2v-.5h2.5z"
                      />
                    </svg>
                    <svg
                      v-else-if="
                        getFileTypeCategory(att.file_name, att.file_type) ===
                        'excel'
                      "
                      class="w-6 h-6"
                      fill="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm-1 2 5 5h-5V4zm-2.5 11L9 15l1.5-3 1.5 3 1.5-3L17 17h-2l-1-2-1 2h-2z"
                      />
                    </svg>
                    <svg
                      v-else-if="
                        getFileTypeCategory(att.file_name, att.file_type) ===
                        'text'
                      "
                      class="w-6 h-6"
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
                      class="w-6 h-6"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                      />
                    </svg>
                  </span>
                  <div class="min-w-0 flex-1">
                    <p
                      class="text-sm font-medium text-gray-900 truncate"
                      :title="att.file_name"
                    >
                      {{ att.file_name }}
                    </p>
                    <p class="text-xs text-gray-500 mt-0.5">
                      <span v-if="att.file_type" class="mr-2">{{
                        att.file_type
                      }}</span>
                      <span>{{ formatFileSize(att.file_size) }}</span>
                      <span v-if="attachmentDisplayDate(att)" class="ml-2">{{
                        formatDate(attachmentDisplayDate(att))
                      }}</span>
                    </p>
                  </div>
                  <div
                    v-if="att.uuid"
                    class="flex items-center gap-1 flex-shrink-0"
                  >
                    <button
                      v-if="canViewInBrowser(att)"
                      type="button"
                      class="p-2 rounded-md text-gray-500 hover:text-primary-600 hover:bg-primary-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      :title="t('dataCollector.records.viewInBrowser')"
                      :disabled="viewingAttachment === (att.uuid || att.id)"
                      @click="onViewAttachment(att)"
                    >
                      <svg
                        class="w-5 h-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                        />
                      </svg>
                    </button>
                    <button
                      type="button"
                      class="p-2 rounded-md text-gray-500 hover:text-primary-600 hover:bg-primary-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      :title="t('dataCollector.records.download')"
                      :disabled="downloadingAttachment === (att.uuid || att.id)"
                      @click="onDownloadAttachment(att)"
                    >
                      <svg
                        class="w-5 h-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                        />
                      </svg>
                    </button>
                  </div>
                  <span
                    v-else
                    class="flex-shrink-0 p-2 rounded-md text-gray-300 cursor-not-allowed"
                    :title="t('dataCollector.records.downloadNotSynced')"
                  >
                    <svg
                      class="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                      />
                    </svg>
                  </span>
                </li>
              </ul>
            </section>
            <div v-else class="py-8 text-center text-sm text-gray-500">
              {{ t('dataCollector.records.noAttachments') }}
            </div>
          </div>
        </template>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import { dataCollectorApi } from '@/api/dataCollector'
import { extractResponseData } from '@/utils/api'
import { useToast } from '@/composables/useToast'

const props = defineProps({
  show: { type: Boolean, default: false },
  recordUuid: { type: String, default: '' }
})

const emit = defineEmits(['close'])

const { t } = useI18n()
const toast = useToast()
const loading = ref(false)
const record = ref(null)
const showRawData = ref(false)
const activeTab = ref('detail')
const expandedCommentRaw = ref(new Set())
const downloadingAttachment = ref(null)
const viewingAttachment = ref(null)

const displayTitle = computed(() => {
  if (!record.value) return ''
  if (record.value.raw_data?.issue?.fields?.summary)
    return record.value.raw_data.issue.fields.summary
  return record.value.source_unique_id || '—'
})

const jiraKeyFields = computed(() => {
  if (!record.value?.raw_data?.issue?.fields) return null
  const f = record.value.raw_data.issue.fields
  const status = f.status?.name ?? f.status
  const created = f.created ?? ''
  const updated = f.updated ?? ''
  const issuetype = f.issuetype?.name ?? f.issuetype
  const project = f.project?.key ?? f.project?.name ?? f.project
  return {
    [t('dataCollector.records.summary')]: f.summary ?? '—',
    [t('dataCollector.records.status')]: status ?? '—',
    [t('dataCollector.records.issuetype')]: issuetype ?? '—',
    [t('dataCollector.records.project')]: project ?? '—',
    [t('dataCollector.records.sourceCreated')]: created,
    [t('dataCollector.records.sourceUpdated')]: updated
  }
})

function extractAdfText(node) {
  if (!node) return ''
  if (typeof node === 'string') return node
  if (node.text != null) return String(node.text)
  if (Array.isArray(node.content))
    return node.content.map(extractAdfText).join('')
  return ''
}

const jiraDescriptionText = computed(() => {
  const desc = record.value?.raw_data?.issue?.fields?.description
  if (desc == null) return ''
  if (typeof desc === 'string') return desc
  if (desc.content && Array.isArray(desc.content)) return extractAdfText(desc)
  try {
    return typeof desc === 'object' ? JSON.stringify(desc) : String(desc)
  } catch {
    return ''
  }
})

const rawDataJson = computed(() => {
  if (!record.value?.raw_data) return '{}'
  try {
    return JSON.stringify(record.value.raw_data, null, 2)
  } catch {
    return String(record.value.raw_data)
  }
})

const commentsList = computed(() => {
  const list = record.value?.raw_data?.comments
  return Array.isArray(list) ? list : []
})

const feishuUserMap = computed(() => {
  const inst = record.value?.raw_data?.instance
  const map = {}
  if (!inst || typeof inst !== 'object') return map

  function addUser(u) {
    if (!u || typeof u !== 'object') return
    const id = u.user_id || u.id || u.open_id || u.openId
    const name =
      u.name || u.username || u.cn_name || u.en_name || u.display_name
    if (id && name && !map[id]) {
      map[id] = name
    }
  }

  const candidateArrays = [
    'approvers',
    'cc_list',
    'participants',
    'users',
    'user_list',
    'userList'
  ]
  candidateArrays.forEach((key) => {
    const arr = inst[key]
    if (Array.isArray(arr)) {
      arr.forEach(addUser)
    }
  })

  const userMap = inst.user_map || inst.userMap
  if (userMap && typeof userMap === 'object') {
    Object.entries(userMap).forEach(([id, val]) => {
      if (typeof val === 'string') {
        if (!map[id]) map[id] = val
      } else if (val && typeof val === 'object') {
        const name =
          val.name ||
          val.username ||
          val.cn_name ||
          val.en_name ||
          val.display_name
        if (id && name && !map[id]) {
          map[id] = name
        }
      }
    })
  }

  return map
})

const feishuTimeline = computed(() => {
  const inst = record.value?.raw_data?.instance
  if (!inst || typeof inst !== 'object') return []
  const tl = inst.timeline || inst.time_line || inst.approval_timeline
  return Array.isArray(tl) ? tl : []
})

/** task_id -> node_name from instance.task_list, for timeline node name column */
const feishuTaskIdToNodeName = computed(() => {
  const inst = record.value?.raw_data?.instance
  if (!inst || typeof inst !== 'object') return {}
  const taskList = inst.task_list || inst.task_list_list || inst.tasks || []
  if (!Array.isArray(taskList)) return {}
  const map = {}
  for (const task of taskList) {
    if (!task || typeof task !== 'object') continue
    const tid = task.task_id ?? task.id
    if (tid == null) continue
    const name = task.node_name ?? task.name ?? task.node_key
    if (name != null && String(name).trim())
      map[String(tid).trim()] = String(name).trim()
  }
  return map
})

const feishuTimelineRows = computed(() => {
  const taskIdToNodeName = feishuTaskIdToNodeName.value
  return feishuTimeline.value.map((item, index) => {
    const rawAction =
      item.type || item.result || item.action || item.node_status || item.status
    const action =
      typeof rawAction === 'string'
        ? rawAction.toUpperCase()
        : String(rawAction || '')

    // CC: users from ext.user_id_list or user_id_list
    let userName
    let userId
    if (action === 'CC') {
      const ext = item.ext || {}
      const idList =
        ext.user_id_list ??
        item.user_id_list ??
        (ext.user_id ? [ext.user_id] : [])
      const ids = Array.isArray(idList) ? idList : [idList].filter(Boolean)
      const names = ids
        .map((id) => resolveFeishuUserName(id, null))
        .filter((n) => n && n !== '—')
      userName = names.length
        ? names.join(', ')
        : resolveFeishuUserName(
            item.user_id || item.userId || item.operator_id || item.operatorId,
            item
          )
      userId =
        ids[0] ??
        item.user_id ??
        item.userId ??
        item.operator_id ??
        item.operatorId
    } else {
      userId =
        item.user_id ||
        item.userId ||
        item.operator_id ||
        item.operatorId ||
        item.user?.user_id ||
        item.operator?.user_id
      userName = resolveFeishuUserName(userId, item)
    }
    const time =
      item.create_time ||
      item.time ||
      item.update_time ||
      item.action_time ||
      item.timestamp

    const statusLabel = (() => {
      const s = action
      switch (s) {
        case 'START':
          return '审批开始'
        case 'PASS':
          return '通过'
        case 'REJECT':
          return '拒绝'
        case 'AUTO_PASS':
          return '自动通过'
        case 'AUTO_REJECT':
          return '自动拒绝'
        case 'REMOVE_REPEAT':
          return '自动通过'
        case 'TRANSFER':
          return '转交'
        case 'ADD_APPROVER_BEFORE':
          return '前加签'
        case 'ADD_APPROVER':
          return '并加签'
        case 'ADD_APPROVER_AFTER':
          return '后加签'
        case 'DELETE_APPROVER':
          return '减签'
        case 'ROLLBACK_SELECTED':
          return '指定回退'
        case 'ROLLBACK':
          return '全部回退'
        case 'CANCEL':
          return '撤回'
        case 'DELETE':
          return '删除'
        case 'CC':
          return '抄送'
        default:
          return action || '—'
      }
    })()

    const taskId = item.task_id != null ? String(item.task_id).trim() : ''
    const nodeNameFromTask = taskId ? (taskIdToNodeName[taskId] ?? null) : null
    const node =
      nodeNameFromTask ??
      item.type ??
      item.result ??
      item.status ??
      item.node_name ??
      item.nodeName ??
      item.stage_name ??
      item.step_name ??
      '—'
    const nodeUpper = node != null ? String(node).toUpperCase() : ''
    const nodeDisplay =
      nodeUpper === 'CC'
        ? '抄送'
        : nodeUpper === 'START'
          ? '审批开始'
          : node || '—'
    const remark = item.comment || item.remark || item.reason || item.note || ''
    return {
      index: index + 1,
      userId,
      userName,
      time,
      status: action,
      statusLabel,
      node,
      nodeDisplay,
      remark,
      raw: item
    }
  })
})

function resolveFeishuUserName(userId, item) {
  if (item) {
    if (item.user_name) return item.user_name
    if (item.operator_name) return item.operator_name
    if (item.user && typeof item.user === 'object') {
      const u = item.user
      const name =
        u.name || u.username || u.cn_name || u.en_name || u.display_name
      if (name) return name
    }
    if (item.operator && typeof item.operator === 'object') {
      const o = item.operator
      const name =
        o.name || o.username || o.cn_name || o.en_name || o.display_name
      if (name) return name
    }
  }
  if (userId && feishuUserMap.value[userId]) {
    return feishuUserMap.value[userId]
  }
  return userId || '—'
}

function feishuStatusBadgeClass(status) {
  const s = String(status || '').toUpperCase()
  if (!s) return 'bg-gray-100 text-gray-700'
  if (
    s === 'PASS' ||
    s === 'AUTO_PASS' ||
    s === 'REMOVE_REPEAT' ||
    s.includes('同意') ||
    s.includes('通过')
  ) {
    return 'bg-green-100 text-green-800'
  }
  if (
    s === 'REJECT' ||
    s === 'AUTO_REJECT' ||
    s.includes('拒绝') ||
    s.includes('驳回')
  ) {
    return 'bg-red-100 text-red-800'
  }
  if (
    s === 'START' ||
    s === 'ROLLBACK' ||
    s === 'ROLLBACK_SELECTED' ||
    s.includes('开始') ||
    s.includes('处理中')
  ) {
    return 'bg-amber-100 text-amber-800'
  }
  return 'bg-gray-100 text-gray-700'
}

function feishuStatusDotClass(status) {
  const s = String(status || '').toUpperCase()
  if (!s) return 'bg-gray-300'
  if (
    s === 'PASS' ||
    s === 'AUTO_PASS' ||
    s === 'REMOVE_REPEAT' ||
    s.includes('同意') ||
    s.includes('通过')
  ) {
    return 'bg-green-400'
  }
  if (
    s === 'REJECT' ||
    s === 'AUTO_REJECT' ||
    s.includes('拒绝') ||
    s.includes('驳回')
  ) {
    return 'bg-red-400'
  }
  if (
    s === 'START' ||
    s === 'ROLLBACK' ||
    s === 'ROLLBACK_SELECTED' ||
    s.includes('开始') ||
    s.includes('处理中')
  ) {
    return 'bg-amber-400'
  }
  return 'bg-gray-300'
}

function commentAuthor(c) {
  if (!c) return '—'
  const a = c.author
  if (typeof a === 'string') return a
  if (a?.displayName) return a.displayName
  if (a?.name) return a.name
  return '—'
}

function commentBodyText(c) {
  if (!c) return ''
  const b = c.body
  if (typeof b === 'string') return b
  if (b?.content && Array.isArray(b.content)) {
    return b.content.map((n) => (n?.text != null ? n.text : '')).join('')
  }
  try {
    return typeof b === 'object' ? JSON.stringify(b) : String(b)
  } catch {
    return ''
  }
}

function commentRawJson(c) {
  if (!c) return '{}'
  try {
    return JSON.stringify(c, null, 2)
  } catch {
    return String(c)
  }
}

function toggleCommentRaw(idx) {
  const set = new Set(expandedCommentRaw.value)
  if (set.has(idx)) set.delete(idx)
  else set.add(idx)
  expandedCommentRaw.value = set
}

const effectiveAttachments = computed(() => {
  const rec = record.value
  if (!rec) return []
  const fromDb = rec.attachments || []
  if (fromDb.length) {
    return fromDb.map((a) => ({
      uuid: a.uuid,
      file_name: a.file_name,
      file_url: a.file_url,
      file_type: a.file_type || '',
      file_size: a.file_size ?? 0,
      source_created_at: a.source_created_at,
      created_at: a.created_at
    }))
  }
  const fromRaw = rec.raw_data?.attachments
  if (!Array.isArray(fromRaw)) return []
  return fromRaw.map((a, i) => ({
    id: a.id,
    file_name: a.filename || a.file_name || a.name || `attachment-${i + 1}`,
    file_url: a.content || a.url || a.file_url,
    file_type: a.mimeType || '',
    file_size: a.size ?? 0,
    source_created_at: a.created,
    created_at: null
  }))
})

function formatDate(s) {
  if (s === null || s === undefined || s === '') return '—'
  try {
    if (typeof s === 'number') {
      const ms = s > 1e12 ? s : s * 1000
      return new Date(ms).toLocaleString()
    }
    if (typeof s === 'string' && /^\d+$/.test(s)) {
      const num = Number(s)
      const ms = num > 1e12 ? num : num * 1000
      return new Date(ms).toLocaleString()
    }
    return new Date(s).toLocaleString()
  } catch {
    return String(s)
  }
}

function formatFileSize(bytes) {
  if (bytes == null || bytes === 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let v = Number(bytes)
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return i === 0 ? `${v} ${units[i]}` : `${v.toFixed(1)} ${units[i]}`
}

function attachmentDisplayDate(att) {
  return att.source_created_at || att.created_at
}

function getFileTypeCategory(name, mimeType) {
  const n = (name || '').toLowerCase()
  const m = (mimeType || '').toLowerCase()
  if (/\.(pdf)$/i.test(n) || m.includes('pdf')) return 'pdf'
  if (/\.(png|jpe?g|gif|webp|svg|bmp|ico)$/i.test(n) || m.startsWith('image/'))
    return 'image'
  if (/\.(docx?|doc)$/i.test(n) || m.includes('word') || m.includes('msword'))
    return 'word'
  if (
    /\.(xlsx?|xls|csv)$/i.test(n) ||
    m.includes('sheet') ||
    m.includes('excel')
  )
    return 'excel'
  if (/\.(txt|md|log)$/i.test(n) || m.startsWith('text/')) return 'text'
  return 'file'
}

function canViewInBrowser(att) {
  const cat = getFileTypeCategory(att.file_name, att.file_type)
  return cat === 'pdf' || cat === 'image' || cat === 'text'
}

async function onViewAttachment(att) {
  if (!att.uuid) return
  const uuid = typeof att.uuid === 'string' ? att.uuid : String(att.uuid)
  viewingAttachment.value = uuid
  try {
    const blob = await dataCollectorApi.getAttachmentBlob(uuid)
    const url = window.URL.createObjectURL(blob)
    window.open(url, '_blank', 'noopener,noreferrer')
    setTimeout(() => window.URL.revokeObjectURL(url), 30000)
  } catch (err) {
    let msg = t('dataCollector.records.downloadFailed')
    if (err.response?.data instanceof Blob) {
      try {
        const text = await err.response.data.text()
        const j = JSON.parse(text)
        msg = j.detail || j.message || text
      } catch {
        if (err.response?.data?.text) msg = await err.response.data.text()
      }
    } else if (err.response?.data?.detail) {
      msg = err.response.data.detail
    } else if (err.message) {
      msg = err.message
    }
    toast.showError(msg)
  } finally {
    viewingAttachment.value = null
  }
}

async function onDownloadAttachment(att) {
  if (!att.uuid) return
  const uuid = typeof att.uuid === 'string' ? att.uuid : String(att.uuid)
  downloadingAttachment.value = uuid
  try {
    await dataCollectorApi.downloadAttachment(uuid, att.file_name)
  } catch (err) {
    let msg = t('dataCollector.records.downloadFailed')
    if (err.response?.data instanceof Blob) {
      try {
        const text = await err.response.data.text()
        const j = JSON.parse(text)
        msg = j.detail || j.message || text
      } catch {
        if (err.response?.data?.text) msg = await err.response.data.text()
      }
    } else if (err.response?.data?.detail) {
      msg = err.response.data.detail
    } else if (err.message) {
      msg = err.message
    }
    toast.showError(msg)
  } finally {
    downloadingAttachment.value = null
  }
}

async function loadRecord() {
  if (!props.recordUuid) {
    record.value = null
    return
  }
  loading.value = true
  record.value = null
  try {
    const res = await dataCollectorApi.getRecord(props.recordUuid)
    const data = extractResponseData(res)
    record.value = data
  } catch {
    record.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => props.recordUuid,
  (uuid) => {
    if (uuid && props.show) loadRecord()
    else record.value = null
  },
  { immediate: true }
)

watch(
  () => props.show,
  (visible) => {
    if (visible && props.recordUuid) loadRecord()
    if (!visible) {
      record.value = null
      showRawData.value = false
      activeTab.value = 'detail'
      expandedCommentRaw.value = new Set()
    }
  }
)

function handleClose() {
  emit('close')
}
</script>

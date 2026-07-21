<template>
  <!-- Mobile overlay -->
  <Transition
    enter-active-class="transition-opacity duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-150"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="showMobileMenu && isMobile"
      @click="$emit('close')"
      class="fixed inset-0 bg-gray-900 bg-opacity-50 z-40 lg:hidden"
    />
  </Transition>

  <!-- Sidebar -->
  <aside
    :class="[
      'relative flex h-full flex-shrink-0 flex-col border-r transition-all duration-300 ease-in-out',
      isQuotationPlatform
        ? 'quotation-sidebar border-slate-800'
        : 'border-gray-200 bg-white',
      !isMobile && collapsed ? 'w-16' : 'w-64',
      isMobile ? 'fixed inset-y-0 left-0 z-50' : 'static',
      isMobile && !showMobileMenu ? '-translate-x-full' : 'translate-x-0'
    ]"
  >
    <!-- Logo and close button -->
    <div
      class="flex h-16 items-center border-b"
      :class="[
        isQuotationPlatform ? 'border-slate-800' : 'border-gray-200',
        !isMobile && collapsed ? 'justify-center px-2' : 'justify-between px-4'
      ]"
    >
      <router-link
        v-if="!(isQuotationPlatform && collapsed && !isMobile)"
        :to="homePath"
        class="flex items-center min-w-0"
        :class="!isMobile && collapsed ? 'justify-center' : 'space-x-2 flex-1'"
        @click="isMobile && $emit('close')"
        :title="!isMobile && collapsed ? t('common.appName') : undefined"
      >
        <img
          :src="isQuotationPlatform ? quoteDeskLogo : '/android-chrome-192x192.png'"
          :alt="isQuotationPlatform ? 'Quote Desk logo' : 'DevMind logo'"
          class="w-8 h-8"
        />
        <div
          v-if="isQuotationPlatform && (isMobile || !collapsed)"
          class="min-w-0"
        >
          <div class="truncate text-sm font-semibold text-white">
            {{ t('quotation.menuTitle') }}
          </div>
        </div>
        <span
          v-else-if="isMobile || !collapsed"
          class="text-xl font-semibold text-gray-900 truncate"
          >{{ t('common.appName') }}</span
        >
      </router-link>
      <button
        v-if="!isMobile"
        type="button"
        class="sidebar-toggle"
        :class="[
          isQuotationPlatform ? 'sidebar-toggle-quotation' : '',
          isQuotationPlatform && collapsed
            ? 'sidebar-toggle-quotation-collapsed'
            : ''
        ]"
        :aria-label="
          collapsed ? t('common.expandSidebar') : t('common.collapseSidebar')
        "
        :title="
          collapsed ? t('common.expandSidebar') : t('common.collapseSidebar')
        "
        @click="$emit('toggle-collapse')"
      >
        <svg
          class="w-4 h-4 transition-transform"
          :class="collapsed ? 'rotate-180' : ''"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M15 19l-7-7 7-7"
          />
        </svg>
      </button>
      <button
        v-if="isMobile"
        @click="$emit('close')"
        class="p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100"
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

    <!-- Navigation -->
    <nav
      class="flex-1 py-4 space-y-1 flex flex-col"
      :class="[
        isQuotationPlatform ? 'quotation-navigation' : '',
        isQuotationPlatform && collapsed && !isMobile
          ? 'quotation-navigation-collapsed'
          : '',
        collapsed && !isMobile
          ? 'overflow-visible px-2'
          : 'overflow-y-auto px-3'
      ]"
    >
      <div class="flex-1 space-y-1">
        <template v-if="!isQuotationPlatform">
        <router-link
          v-if="userStore.userHasFeature('workspace')"
          to="/dashboard"
          class="nav-item"
          :class="[
            isActive('/dashboard') ? 'nav-item-active' : '',
            collapsed && !isMobile ? 'nav-item-collapsed' : ''
          ]"
          @click="isMobile && $emit('close')"
          @mouseenter="preloadRoute('/dashboard')"
          :title="collapsed && !isMobile ? t('dashboard.title') : undefined"
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
              d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
            />
          </svg>
          <span v-if="isMobile || !collapsed">{{ t('dashboard.title') }}</span>
        </router-link>

        <!-- Cloud Billing Menu with Submenu -->
        <div
          v-if="userStore.userHasFeature('operations_console')"
          class="menu-group"
          :class="collapsed && !isMobile ? 'menu-group-collapsed' : ''"
        >
          <button
            @click="toggleCloudBillingMenu"
            class="nav-item nav-item-parent w-full"
            :class="collapsed && !isMobile ? 'nav-item-collapsed' : ''"
            :title="
              collapsed && !isMobile ? t('cloudBilling.menuTitle') : undefined
            "
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
                d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
              />
            </svg>
            <span v-if="isMobile || !collapsed" class="flex-1 text-left">{{
              t('cloudBilling.menuTitle')
            }}</span>
            <svg
              v-if="isMobile || !collapsed"
              class="w-4 h-4 transition-transform"
              :class="cloudBillingMenuOpen ? 'rotate-90' : ''"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>

          <Transition
            enter-active-class="transition-all duration-200 ease-out"
            enter-from-class="opacity-0 max-h-0"
            enter-to-class="opacity-100 max-h-96"
            leave-active-class="transition-all duration-200 ease-in"
            leave-from-class="opacity-100 max-h-96"
            leave-to-class="opacity-0 max-h-0"
          >
            <div
              v-if="cloudBillingMenuOpen || (collapsed && !isMobile)"
              class="submenu"
              :class="collapsed && !isMobile ? 'submenu-flyout' : ''"
            >
              <div v-if="collapsed && !isMobile" class="submenu-flyout-title">
                {{ t('cloudBilling.menuTitle') }}
              </div>
              <router-link
                to="/cloud-billing/billing"
                class="nav-item nav-item-child"
                :class="
                  isActive('/cloud-billing/billing') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/cloud-billing/billing')"
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
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span>{{ t('cloudBilling.billing.title') }}</span>
              </router-link>
              <router-link
                to="/cloud-billing/tasks"
                class="nav-item nav-item-child"
                :class="
                  isActive('/cloud-billing/tasks') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/cloud-billing/tasks')"
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
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
                  />
                </svg>
                <span>{{ t('cloudBilling.tasks.title') }}</span>
              </router-link>
              <router-link
                to="/cloud-billing/alerts"
                class="nav-item nav-item-child"
                :class="
                  isActive('/cloud-billing/alerts') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/cloud-billing/alerts')"
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
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                <span>{{ t('cloudBilling.alerts.title') }}</span>
              </router-link>
              <router-link
                to="/cloud-billing/settings"
                class="nav-item nav-item-child"
                :class="
                  isActive('/cloud-billing/settings') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/cloud-billing/settings')"
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
                <span>{{ t('cloudBilling.settings.title') }}</span>
              </router-link>
            </div>
          </Transition>
        </div>

        <!-- Data Collector Menu with Submenu -->
        <div
          v-if="userStore.userHasFeature('operations_console')"
          class="menu-group"
          :class="collapsed && !isMobile ? 'menu-group-collapsed' : ''"
        >
          <button
            @click="toggleDataCollectorMenu"
            class="nav-item nav-item-parent w-full"
            :class="collapsed && !isMobile ? 'nav-item-collapsed' : ''"
            :title="
              collapsed && !isMobile ? t('dataCollector.menuTitle') : undefined
            "
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
                d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
              />
            </svg>
            <span v-if="isMobile || !collapsed" class="flex-1 text-left">{{
              t('dataCollector.menuTitle')
            }}</span>
            <svg
              v-if="isMobile || !collapsed"
              class="w-4 h-4 transition-transform"
              :class="dataCollectorMenuOpen ? 'rotate-90' : ''"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>

          <Transition
            enter-active-class="transition-all duration-200 ease-out"
            enter-from-class="opacity-0 max-h-0"
            enter-to-class="opacity-100 max-h-96"
            leave-active-class="transition-all duration-200 ease-in"
            leave-from-class="opacity-100 max-h-96"
            leave-to-class="opacity-0 max-h-0"
          >
            <div
              v-if="dataCollectorMenuOpen || (collapsed && !isMobile)"
              class="submenu"
              :class="collapsed && !isMobile ? 'submenu-flyout' : ''"
            >
              <div v-if="collapsed && !isMobile" class="submenu-flyout-title">
                {{ t('dataCollector.menuTitle') }}
              </div>
              <router-link
                to="/data-collector/stats"
                class="nav-item nav-item-child"
                :class="
                  isActive('/data-collector/stats') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/data-collector/stats')"
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
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                  />
                </svg>
                <span>{{ t('dataCollector.stats.title') }}</span>
              </router-link>
              <router-link
                to="/data-collector/records"
                class="nav-item nav-item-child"
                :class="
                  isActive('/data-collector/records') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/data-collector/records')"
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
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span>{{ t('dataCollector.records.pageTitle') }}</span>
              </router-link>
              <router-link
                to="/data-collector/tasks"
                class="nav-item nav-item-child"
                :class="
                  isActive('/data-collector/tasks') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/data-collector/tasks')"
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
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
                  />
                </svg>
                <span>{{ t('dataCollector.tasks.title') }}</span>
              </router-link>
              <router-link
                to="/data-collector/settings"
                class="nav-item nav-item-child"
                :class="
                  isActive('/data-collector/settings') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/data-collector/settings')"
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
                <span>{{ t('dataCollector.settings.title') }}</span>
              </router-link>
            </div>
          </Transition>
        </div>
        </template>

        <!-- Quote Desk platform navigation -->
        <div
          v-if="isQuotationPlatform"
          class="menu-group"
          :class="collapsed && !isMobile ? 'menu-group-collapsed' : ''"
        >
          <button
            @click="toggleQuotationMenu"
            class="nav-item nav-item-parent w-full"
            :class="collapsed && !isMobile ? 'nav-item-collapsed' : ''"
            :title="
              collapsed && !isMobile ? t('quotation.menuTitle') : undefined
            "
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
                d="M9 14h6m-6-4h6m2 10H7a2 2 0 01-2-2V6a2 2 0 012-2h5l5 5v9a2 2 0 01-2 2z"
              />
            </svg>
            <span v-if="isMobile || !collapsed" class="flex-1 text-left">{{
              t('quotation.menuTitle')
            }}</span>
            <svg
              v-if="isMobile || !collapsed"
              class="w-4 h-4 transition-transform"
              :class="quotationMenuOpen ? 'rotate-90' : ''"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>

          <Transition
            enter-active-class="transition-all duration-200 ease-out"
            enter-from-class="opacity-0 max-h-0"
            enter-to-class="opacity-100 max-h-96"
            leave-active-class="transition-all duration-200 ease-in"
            leave-from-class="opacity-100 max-h-96"
            leave-to-class="opacity-0 max-h-0"
          >
            <div
              v-if="quotationMenuOpen || (collapsed && !isMobile)"
              class="submenu"
            >
              <router-link
                to="/quotation/dashboard"
                class="nav-item nav-item-child"
                :class="
                  isActive('/quotation/dashboard') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/quotation/dashboard')"
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
                    d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
                  />
                </svg>
                <span>{{ t('quotation.dashboard') }}</span>
              </router-link>
              <router-link
                to="/quotation/list"
                class="nav-item nav-item-child"
                :class="isActive('/quotation/list') ? 'nav-item-active' : ''"
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/quotation/list')"
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
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
                <span>{{ t('quotation.list') }}</span>
              </router-link>
              <router-link
                to="/quotation/create"
                class="nav-item nav-item-child"
                :class="
                  isActive('/quotation/create') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/quotation/create')"
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
                    d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <span>{{ t('quotation.create') }}</span>
              </router-link>
              <router-link
                to="/quotation/catalog"
                class="nav-item nav-item-child"
                :class="
                  isActive('/quotation/catalog') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/quotation/catalog')"
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
                <span>{{ t('quotation.catalog') }}</span>
              </router-link>
              <router-link
                to="/quotation/audit"
                class="nav-item nav-item-child"
                :class="
                  isActive('/quotation/audit') ? 'nav-item-active' : ''
                "
                @click="isMobile && $emit('close')"
                @mouseenter="preloadRoute('/quotation/audit')"
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
                    d="M9 12h6m-6 4h6M9 8h2m6 13H7a2 2 0 01-2-2V5a2 2 0 012-2h7l5 5v11a2 2 0 01-2 2z"
                  />
                </svg>
                <span>{{ t('quotation.audit') }}</span>
              </router-link>
            </div>
          </Transition>
        </div>
      </div>

      <!-- Settings Menu -->
      <div
        class="mt-auto border-t pt-4"
        :class="isQuotationPlatform ? 'quotation-settings' : 'border-gray-200'"
      >
        <router-link
          :to="{ name: 'SettingsNotifications' }"
          class="nav-item"
          :class="[
            isActive('/settings/notifications') ? 'nav-item-active' : '',
            isQuotationPlatform ? 'quotation-settings-link' : '',
            collapsed && !isMobile ? 'nav-item-collapsed' : ''
          ]"
          @mouseenter="preloadRoute('/settings/notifications')"
          :title="collapsed && !isMobile ? t('common.settings') : undefined"
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
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
          <span v-if="isMobile || !collapsed">{{ t('common.settings') }}</span>
        </router-link>
      </div>
    </nav>
  </aside>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '@/store/user'
import { getCurrentPlatformKey } from '@/utils/platformAccess'
import quoteDeskLogo from '@/assets/quote-desk-logo.svg'

defineProps({
  showMobileMenu: {
    type: Boolean,
    default: false
  },
  collapsed: {
    type: Boolean,
    default: false
  }
})

defineEmits(['close', 'toggle-collapse'])

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isQuotationPlatform = computed(
  () => getCurrentPlatformKey(route.path) === 'quotation_management'
)
const homePath = computed(() =>
  isQuotationPlatform.value
    ? '/quotation/dashboard'
    : userStore.getUserLandingPath()
)

// Menu expand/collapse state - default to expanded
const cloudBillingMenuOpen = ref(true)
const dataCollectorMenuOpen = ref(true)
const quotationMenuOpen = ref(true)

// Load expanded state from localStorage
const loadExpandedState = () => {
  if (typeof window === 'undefined') return
  const saved = localStorage.getItem('sidebar_cloud_billing_expanded')
  if (saved !== null) {
    try {
      cloudBillingMenuOpen.value = JSON.parse(saved)
    } catch (e) {
      // Ignore parse errors
    }
  }
  const savedDC = localStorage.getItem('sidebar_data_collector_expanded')
  if (savedDC !== null) {
    try {
      dataCollectorMenuOpen.value = JSON.parse(savedDC)
    } catch (e) {
      // Ignore parse errors
    }
  }
  const savedQuotation = localStorage.getItem('sidebar_quotation_expanded')
  if (savedQuotation !== null) {
    try {
      quotationMenuOpen.value = JSON.parse(savedQuotation)
    } catch (e) {
      // Ignore parse errors
    }
  }
}

// Save expanded state to localStorage
const saveExpandedState = () => {
  if (typeof window === 'undefined') return
  localStorage.setItem(
    'sidebar_cloud_billing_expanded',
    JSON.stringify(cloudBillingMenuOpen.value)
  )
  localStorage.setItem(
    'sidebar_data_collector_expanded',
    JSON.stringify(dataCollectorMenuOpen.value)
  )
  localStorage.setItem(
    'sidebar_quotation_expanded',
    JSON.stringify(quotationMenuOpen.value)
  )
}

const MOBILE_BREAKPOINT = 1024

const isMobile = computed(() => {
  if (typeof window === 'undefined') return false
  return window.innerWidth < MOBILE_BREAKPOINT
})

const isActive = (path) => {
  if (path === '/dashboard') {
    return route.path === '/dashboard' || route.path === '/'
  }
  // For submenu items, use exact match or starts with
  return route.path === path || route.path.startsWith(path + '/')
}

const toggleCloudBillingMenu = () => {
  cloudBillingMenuOpen.value = !cloudBillingMenuOpen.value
  saveExpandedState()
}

const toggleDataCollectorMenu = () => {
  dataCollectorMenuOpen.value = !dataCollectorMenuOpen.value
  saveExpandedState()
}

const toggleQuotationMenu = () => {
  quotationMenuOpen.value = !quotationMenuOpen.value
  saveExpandedState()
}

// Auto-expand menu if current route is in that section
watch(
  () => route.path,
  (newPath) => {
    if (newPath.startsWith('/cloud-billing')) {
      cloudBillingMenuOpen.value = true
      saveExpandedState()
    }
    if (newPath.startsWith('/data-collector')) {
      dataCollectorMenuOpen.value = true
      saveExpandedState()
    }
    if (newPath.startsWith('/quotation')) {
      quotationMenuOpen.value = true
      saveExpandedState()
    }
  },
  { immediate: true }
)

// Preload route component on link hover for faster navigation
// Use a cache to avoid duplicate preloads
const preloadCache = new Set()

const preloadRoute = (path) => {
  // Skip if already preloaded
  if (preloadCache.has(path)) {
    return
  }

  try {
    const route = router.resolve(path)
    if (route.matched.length > 0) {
      const matched = route.matched[0]
      // Preload the component if it's lazy-loaded
      if (matched.components) {
        Object.values(matched.components).forEach((component) => {
          if (typeof component === 'function') {
            // Mark as preloading
            preloadCache.add(path)
            component().catch(() => {
              // Remove from cache on error so we can retry
              preloadCache.delete(path)
            })
          }
        })
      }
    }
  } catch (error) {
    // Ignore preload errors silently
  }
}

onMounted(() => {
  loadExpandedState()
})
</script>

<style scoped>
.nav-item {
  @apply flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-all duration-200;
}

.nav-item-collapsed {
  @apply h-10 w-10 justify-center gap-0 px-0 py-0;
}

.nav-item-active {
  @apply bg-primary-50 text-primary-600;
}

.nav-item-parent {
  @apply w-full cursor-pointer font-semibold text-gray-800;
}

.nav-item-parent:hover {
  @apply bg-gray-50;
}

.nav-item-child {
  @apply relative pl-10 py-2 text-sm font-normal text-gray-600;
  margin-left: 0.75rem;
  border-radius: 0.375rem;
}

.nav-item-child:hover {
  @apply bg-gray-50;
}

.nav-item-child.nav-item-active {
  @apply bg-primary-50 text-primary-600 font-medium;
}

.menu-group {
  @apply space-y-0 mb-1.5;
}

.menu-group-collapsed {
  @apply relative;
}

.submenu {
  @apply overflow-hidden pl-0 mt-1 space-y-0.5;
  transition: all 0.2s ease-in-out;
}

.submenu-flyout {
  @apply invisible absolute left-full top-0 z-50 ml-3 min-w-56 rounded-lg border border-gray-200 bg-white p-2 opacity-0 shadow-lg;
  max-height: none;
  overflow: visible;
  transition:
    opacity 0.15s ease,
    visibility 0.15s ease,
    transform 0.15s ease;
  transform: translateX(-0.25rem);
}

.menu-group-collapsed:hover .submenu-flyout,
.menu-group-collapsed:focus-within .submenu-flyout {
  @apply visible opacity-100;
  transform: translateX(0);
}

.submenu-flyout-title {
  @apply px-3 pb-2 pt-1 text-xs font-semibold text-gray-500;
}

.submenu .nav-item {
  @apply ml-0;
}

.submenu-flyout .nav-item-child {
  @apply ml-0 px-3 pl-3;
}

.submenu-flyout .nav-item-child::before {
  content: none;
}

/* Add a subtle left border indicator for child items */
.nav-item-child::before {
  content: '';
  @apply absolute left-6 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-gray-300 rounded;
  transition: all 0.2s;
}

.nav-item-child.nav-item-active::before {
  @apply bg-primary-500 w-1;
}

/* Improve icon spacing in parent items */
.nav-item-parent svg:first-child {
  @apply flex-shrink-0;
}

.nav-item-parent span {
  @apply flex-shrink-0;
}

.nav-item-parent svg:last-child {
  @apply flex-shrink-0 ml-1 opacity-70;
  transition:
    transform 0.2s ease-in-out,
    opacity 0.2s;
}

.nav-item-parent:hover svg:last-child {
  @apply opacity-100;
}

.sidebar-toggle {
  @apply absolute -right-3 top-5 z-10 flex h-6 w-6 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-600 shadow-sm transition-colors hover:bg-gray-50 hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500;
}

.quotation-sidebar {
  background: #070a18;
  color: #cbd5e1;
}

.quotation-navigation .menu-group {
  margin-bottom: 0;
}

.quotation-navigation .menu-group::before {
  display: block;
  padding: 0.25rem 0.75rem 0.5rem;
  color: #7783a0;
  content: 'BUSINESS VIEWS';
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.quotation-navigation-collapsed .menu-group::before {
  display: none;
}

.quotation-navigation .nav-item-parent {
  display: none;
}

.quotation-navigation .submenu {
  margin-top: 0;
  overflow: visible;
}

.quotation-navigation-collapsed .submenu {
  overflow: visible;
}

.quotation-navigation-collapsed .nav-item-child {
  width: 2.5rem;
  height: 2.5rem;
  margin-right: auto;
  margin-left: auto;
  justify-content: center;
  gap: 0;
  padding: 0;
  border-radius: 0.5rem;
}

.quotation-navigation-collapsed .nav-item-child span {
  display: none;
}

.quotation-navigation .nav-item-child {
  margin-left: 0;
  border-radius: 9999px;
  padding: 0.625rem 0.75rem;
  color: #c4cbe0;
  font-weight: 600;
}

.quotation-navigation .nav-item-child::before {
  content: none;
}

.quotation-navigation .nav-item-child:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #ffffff;
}

.quotation-navigation .nav-item-child.nav-item-active {
  background-color: #2563eb;
  color: #ffffff;
  font-weight: 700;
}

.quotation-navigation.quotation-navigation-collapsed .nav-item-child {
  margin-right: auto;
  margin-left: auto;
  padding: 0;
  border-radius: 0.5rem;
}

.quotation-settings {
  border-color: #1e293b;
}

.quotation-settings-link {
  color: #c4cbe0;
}

.quotation-settings-link:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #ffffff;
}

.quotation-sidebar .quotation-settings .nav-item-collapsed {
  margin-right: auto;
  margin-left: auto;
}

.sidebar-toggle-quotation {
  right: 0.75rem;
  border-color: #334155;
  background: #111827;
  color: #94a3b8;
}

.sidebar-toggle-quotation:hover {
  background: #1e293b;
  color: #ffffff;
}

.sidebar-toggle-quotation-collapsed {
  top: 1rem;
  right: auto;
  left: 50%;
  width: 2rem;
  height: 2rem;
  transform: translateX(-50%);
}
</style>

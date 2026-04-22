import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/store/user'
import { adminRoutes } from '@/admin/routes'
import { getLandingPath, hasFeature } from '@/utils/platformAccess'

const routes = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/Auth.vue'),
    meta: { requiresGuest: true }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/pages/Dashboard.vue'),
    meta: { requiresAuth: true, requiredFeature: 'workspace' }
  },
  {
    path: '/settings',
    redirect: (to) => ({
      path: '/settings/profile',
      query: to.query
    })
  },
  {
    path: '/settings/profile',
    name: 'SettingsProfile',
    component: () => import('@/pages/settings/Profile.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/settings/jira',
    name: 'SettingsJira',
    component: () => import('@/pages/settings/Jira.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/settings/gitlab',
    name: 'SettingsGitLab',
    component: () => import('@/pages/settings/GitLab.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/settings/llm',
    name: 'SettingsLLM',
    component: () => import('@/pages/settings/LLM.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/settings/feishu',
    name: 'SettingsFeishu',
    component: () => import('@/pages/settings/Feishu.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/settings/notifications',
    name: 'SettingsNotifications',
    component: () => import('@/pages/settings/Notifications.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/operations',
    redirect: '/operations/dashboard'
  },
  {
    path: '/operations/dashboard',
    name: 'OperationsDashboard',
    component: () => import('@/pages/Operations/Dashboard.vue'),
    meta: { requiresAuth: true, requiredFeature: 'operations_console' }
  },
  {
    path: '/hyperbdr-dashboard',
    name: 'HyperBRDDashboard',
    component: () => import('@/pages/HyperBDRDashboard.vue'),
    meta: { requiresAuth: true, requiredFeature: 'hyperbdr_dashboard' }
  },
  {
    path: '/cloud-billing',
    redirect: '/cloud-billing/billing'
  },
  {
    path: '/cloud-billing/billing',
    name: 'CloudBillingBilling',
    component: () => import('@/pages/CloudBilling/Billing.vue'),
    meta: { requiresAuth: true, requiredFeature: 'operations_console' }
  },
  {
    path: '/cloud-billing/ai-pricing',
    redirect: '/ai-pricehub'
  },
  {
    path: '/ai-pricehub',
    name: 'AIPriceHub',
    component: () => import('@/pages/AIPriceHub.vue'),
    meta: { requiresAuth: true, requiredFeature: 'ai_pricehub' }
  },
  {
    path: '/cloud-billing/tasks',
    name: 'CloudBillingTasks',
    component: () => import('@/pages/CloudBilling/Tasks.vue'),
    meta: { requiresAuth: true, requiredFeature: 'operations_console' }
  },
  {
    path: '/cloud-billing/alerts',
    name: 'CloudBillingAlerts',
    component: () => import('@/pages/CloudBilling/Alerts/Records.vue'),
    meta: { requiresAuth: true, requiredFeature: 'operations_console' }
  },
  {
    path: '/cloud-billing/settings',
    name: 'CloudBillingSettings',
    component: () => import('@/pages/CloudBilling/Settings.vue'),
    meta: { requiresAuth: true, requiredFeature: 'operations_console' }
  },
  {
    path: '/data-collector',
    redirect: '/data-collector/stats'
  },
  {
    path: '/data-collector/stats',
    name: 'DataCollectorStats',
    component: () => import('@/pages/DataCollector/Stats.vue'),
    meta: { requiresAuth: true, requiredFeature: 'operations_console' }
  },
  {
    path: '/data-collector/records',
    name: 'DataCollectorRecords',
    component: () => import('@/pages/DataCollector/Records.vue'),
    meta: { requiresAuth: true, requiredFeature: 'operations_console' }
  },
  {
    path: '/data-collector/records/:uuid',
    name: 'DataCollectorRecordDetail',
    component: () => import('@/pages/DataCollector/RecordDetail.vue'),
    meta: { requiresAuth: true, requiredFeature: 'operations_console' }
  },
  {
    path: '/data-collector/tasks',
    name: 'DataCollectorTasks',
    component: () => import('@/pages/DataCollector/Tasks.vue'),
    meta: { requiresAuth: true, requiredFeature: 'operations_console' }
  },
  {
    path: '/data-collector/settings',
    name: 'DataCollectorSettings',
    component: () => import('@/pages/DataCollector/Settings.vue'),
    meta: { requiresAuth: true, requiredFeature: 'operations_console' }
  },
  {
    path: '/hyperbdr-monitor/:pathMatch(.*)*',
    redirect: (to) => ({
      path: '/hyperbdr-dashboard',
      query: to.query
    })
  },
  {
    path: '/llm',
    redirect: '/management/llm/stats'
  },
  {
    path: '/llm/stats',
    redirect: '/management/llm/stats'
  },
  {
    path: '/llm/usage',
    redirect: '/management/llm/usage'
  },
  {
    path: '/llm/config',
    redirect: '/management/llm/config'
  },
  {
    path: '/llm/:pathMatch(.*)*',
    redirect: '/management/llm/stats'
  },
  {
    path: '/task-management',
    redirect: '/management/task-management/list'
  },
  {
    path: '/task-management/list',
    redirect: '/management/task-management/list'
  },
  {
    path: '/task-management/stats',
    redirect: '/management/task-management/stats'
  },
  {
    path: '/task-management/settings',
    redirect: '/management/task-management/settings'
  },
  {
    path: '/task-management/:pathMatch(.*)*',
    redirect: '/management/task-management/list'
  },
  {
    path: '/notifier',
    redirect: '/management/notifier/stats'
  },
  {
    path: '/notifier/stats',
    redirect: '/management/notifier/stats'
  },
  {
    path: '/notifier/records',
    redirect: '/management/notifier/records'
  },
  {
    path: '/notifier/channels',
    redirect: '/management/notifier/channels'
  },
  {
    path: '/notifier/settings',
    redirect: '/management/notifier/settings'
  },
  {
    path: '/notifier/config',
    redirect: '/management/notifier/settings'
  },
  {
    path: '/notifier/:pathMatch(.*)*',
    redirect: '/management/notifier/stats'
  },
  ...adminRoutes,
  {
    path: '/404',
    name: 'NotFound',
    component: () => import('@/pages/NotFound.vue')
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'CatchAll',
    component: () => import('@/pages/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    // Always scroll to top on route change for better UX
    return { top: 0 }
  }
})

// Navigation guards
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  if (to.meta.requiresAuth) {
    const hasToken = !!localStorage.getItem('access_token')

    if (!hasToken) {
      next('/login')
      return
    }

    if (!userStore.user) {
      try {
        const authSuccess = await userStore.checkAuth()
        if (!authSuccess) {
          next('/login')
          return
        }
      } catch {
        next('/login')
        return
      }
    }

    if (
      to.meta.requiredFeature &&
      !hasFeature(userStore.userInfo, to.meta.requiredFeature)
    ) {
      next(getLandingPath(userStore.userInfo))
      return
    }

    next()
  } else if (to.meta.requiresGuest && userStore.isAuthenticated) {
    next(getLandingPath(userStore.userInfo))
  } else {
    next()
  }
})

export default router

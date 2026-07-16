import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useUserStore } from '@/store/user'

export interface AppUser {
  name: string
  title: string
  email: string
  role: string
}

function roleLabelFromDevMind(user: any): string {
  if (user?.is_staff) return 'Admin'
  const roles = user?.roles || user?.platform_roles || []
  const firstRole =
    Array.isArray(roles) && roles.length > 0
      ? roles[0]?.name || roles[0]
      : user?.role
  return String(firstRole || 'Sales')
}

function mapDevMindUser(user: any): AppUser | null {
  if (!user) return null
  const profile = user.profile || {}
  const firstName = user.first_name || ''
  const lastName = user.last_name || ''
  const fullName = `${firstName} ${lastName}`.trim()
  return {
    name: profile.nickname || fullName || user.username || user.email || 'DevMind User',
    title: profile.bio || '',
    email: user.email || user.username || '',
    role: roleLabelFromDevMind(user),
  }
}

export const useAuthStore = defineStore('quotation-auth', () => {
  const userStore = useUserStore()
  const authReady = ref(false)
  const authError = ref<string | null>(null)
  const loading = ref(false)

  const embeddedAuth = true
  const currentUser = computed(() => mapDevMindUser(userStore.user))
  const isAuthenticated = computed(() => !!currentUser.value)
  const displayName = computed(() => currentUser.value?.name || '')
  const roleLabel = computed(() => currentUser.value?.role || '')
  const ready = computed(() => authReady.value)
  const user = computed(() => currentUser.value)

  async function bootstrap() {
    authReady.value = false
    authError.value = null
    try {
      if (!userStore.user) {
        await userStore.checkAuth()
      }
      if (!userStore.user) {
        authError.value = 'DevMind 登录状态不可用，请重新登录。'
      }
    } catch (error: unknown) {
      authError.value =
        error instanceof Error ? error.message : 'DevMind 登录状态不可用。'
    } finally {
      authReady.value = true
    }
    return currentUser.value
  }

  async function login() {
    await bootstrap()
    if (!currentUser.value) {
      throw new Error(authError.value || 'DevMind 登录状态不可用。')
    }
    return currentUser.value
  }

  async function logout() {
    await userStore.logout()
  }

  async function fetchCurrentUser() {
    await bootstrap()
    if (!currentUser.value) {
      throw new Error(authError.value || 'DevMind 登录状态不可用。')
    }
    return currentUser.value
  }

  return {
    embeddedAuth,
    authReady,
    ready,
    isAuthenticated,
    authError,
    currentUser,
    user,
    loading,
    displayName,
    roleLabel,
    bootstrap,
    login,
    logout,
    fetchCurrentUser,
    ensureEmbeddedSession: fetchCurrentUser,
  }
})

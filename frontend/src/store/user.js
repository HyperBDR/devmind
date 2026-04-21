import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import {
  getAvailablePlatforms,
  getLandingPath,
  hasFeature
} from '@/utils/platformAccess'

export const useUserStore = defineStore('user', () => {
  // State
  const user = ref(null)
  const token = ref(localStorage.getItem('access_token'))
  const loading = ref(false)
  const error = ref(null)

  // Getters
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const userInfo = computed(() => user.value)
  const availablePlatforms = computed(() => getAvailablePlatforms(user.value))
  const landingPath = computed(() => getLandingPath(user.value))

  // No-op: UI language is managed separately (localStorage); Profile.language is for
  // backend/AI only. Kept for future use if we need to load other preferences here.
  const loadUserPreferences = async () => {}

  // Actions
  const login = async (credentials) => {
    loading.value = true
    error.value = null

    try {
      const response = await authApi.login(credentials)

      // Handle the actual response format from backend
      const data = response.data.data || response.data

      // Handle JWT response format
      if (data.access) {
        token.value = data.access
        user.value = data.user

        // Save tokens to localStorage
        localStorage.setItem('access_token', data.access)
        if (data.refresh) {
          localStorage.setItem('refresh_token', data.refresh)
        }
      } else {
        // Fallback for different response format
        token.value = data.token || data.access_token
        user.value = data.user
        localStorage.setItem('access_token', token.value)
      }

      await loadUserPreferences()
      await checkAuthStatus()

      return data
    } catch (err) {
      error.value =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        'Login failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  const clearAuthState = () => {
    user.value = null
    token.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  const logout = async () => {
    try {
      // Call backend logout API to invalidate token
      await authApi.logout()
    } catch (error) {
      console.error('Logout API call failed:', error)
      // Continue with local cleanup even if API call fails
    } finally {
      clearAuthState()
    }
  }

  const checkAuth = async () => {
    // Check if we have a token in localStorage
    const storedToken = localStorage.getItem('access_token')
    if (!storedToken) {
      clearAuthState()
      return false
    }

    // Update token if it's not already set
    if (!token.value) {
      token.value = storedToken
    }

    try {
      const response = await authApi.getProfile()
      // Handle the actual response format from backend
      const data = response.data.data || response.data
      user.value = data

      await loadUserPreferences()

      return true
    } catch (err) {
      clearAuthState()
      return false
    }
  }

  const checkAuthStatus = async () => {
    try {
      const response = await authApi.getProfile()
      const data = response.data.data || response.data

      user.value = data

      if (!token.value && localStorage.getItem('access_token')) {
        token.value = localStorage.getItem('access_token')
      }

      await loadUserPreferences()

      return data
    } catch (err) {
      // Silently handle 502 errors (backend service unavailable)
      // Only log other errors for debugging
      if (err?.response?.status !== 502 && err?.code !== 'ERR_BAD_RESPONSE') {
        console.error('Check auth status failed:', err)
      }
      return null
    }
  }

  const updateProfile = async (profileData) => {
    loading.value = true
    error.value = null

    try {
      const response = await authApi.updateProfile(profileData)
      // Handle the actual response format from backend
      const data = response.data.data || response.data
      user.value = data
      return data
    } catch (err) {
      error.value = err.response?.data?.message || 'Update failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  const setUser = (userData) => {
    user.value = userData
  }

  const setToken = (tokenValue, refreshValue = null) => {
    token.value = tokenValue
    if (tokenValue) {
      localStorage.setItem('access_token', tokenValue)
    }
    if (refreshValue) {
      localStorage.setItem('refresh_token', refreshValue)
    }
  }

  const userHasFeature = (featureKey) => hasFeature(user.value, featureKey)
  const getUserLandingPath = () => getLandingPath(user.value)

  return {
    // State
    user,
    token,
    loading,
    error,
    // Getters
    isAuthenticated,
    userInfo,
    availablePlatforms,
    landingPath,
    // Actions
    login,
    logout,
    checkAuth,
    checkAuthStatus,
    updateProfile,
    setUser,
    setToken,
    userHasFeature,
    getUserLandingPath,
    // Helper functions
    loadUserPreferences
  }
})

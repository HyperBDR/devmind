/* global __APP_VERSION__ */

export const appVersion =
  import.meta.env.VITE_APP_VERSION || __APP_VERSION__ || 'unknown'

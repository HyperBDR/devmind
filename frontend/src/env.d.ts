/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'

  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}

declare module '@/store/user' {
  export function useUserStore(): {
    user: any
    checkAuth(): Promise<unknown>
    logout(): Promise<unknown>
  }
}

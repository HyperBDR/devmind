/**
 * Auth presentation mode for host-system embedding.
 *
 * - embedded (default): no login UI; auto-login with demo credentials for local/dev
 * - standalone: show LoginPage (temporary fallback)
 *
 * Host SSO / token passthrough will replace auto-login later.
 */

export type AuthMode = 'embedded' | 'standalone';

const DEFAULT_DEV_EMAIL = 'alice.chen@oneprocloud.com';
export function getAuthMode(): AuthMode {
  const raw = (import.meta.env.VITE_AUTH_MODE as string | undefined)?.trim().toLowerCase();
  return raw === 'standalone' ? 'standalone' : 'embedded';
}

export function isEmbeddedAuthMode(): boolean {
  return getAuthMode() === 'embedded';
}

export function getDevAuthCredentials(): { email: string; password: string } {
  const email = (import.meta.env.VITE_DEV_AUTH_EMAIL as string | undefined)?.trim() || DEFAULT_DEV_EMAIL;
  const password = (import.meta.env.VITE_DEV_AUTH_PASSWORD as string | undefined) || '';
  return { email, password };
}

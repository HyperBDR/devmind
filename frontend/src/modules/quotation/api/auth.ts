import { getDevAuthCredentials } from '../config/authMode';
import { apiRequest, clearAccessToken, getAccessToken, setAccessToken } from './client';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  title?: string | null;
  role: string;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export function formatRoleLabel(role: string): string {
  const map: Record<string, string> = {
    sales: 'Sales',
    sales_director: 'Sales Director',
    presales: 'Presales',
    admin: 'Admin',
  };
  return map[role.toLowerCase()] || role;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const data = await apiRequest<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  setAccessToken(data.access_token);
  return data;
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  return apiRequest<AuthUser>('/auth/me');
}

/**
 * Resolve a session for embedded mode: reuse valid token, otherwise demo auto-login.
 * Host SSO will replace the auto-login branch later.
 */
export async function ensureEmbeddedSession(): Promise<AuthUser> {
  const token = getAccessToken();
  if (token) {
    try {
      return await fetchCurrentUser();
    } catch {
      clearAccessToken();
    }
  }
  const { email, password } = getDevAuthCredentials();
  const result = await login(email, password);
  return result.user;
}

export async function logout(): Promise<void> {
  try {
    await apiRequest('/auth/logout', { method: 'POST' });
  } finally {
    clearAccessToken();
  }
}

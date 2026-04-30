const API_BASE = '/api';

export interface InitDbResult {
  status: string;
  message?: string;
  synced?: number;
  total?: number;
  mode?: string;
}

export interface SyncStatusResult {
  scheduler_running: boolean;
  api_configured: boolean;
  sync_limit: number;
}

export const api = {
  async initDb(source: 'api' | 'excel' = 'api', fullSync = false): Promise<InitDbResult> {
    const params = new URLSearchParams({ source, full_sync: String(fullSync) });
    const res = await fetch(`${API_BASE}/init-db?${params}`, { method: 'POST' });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Sync failed: ${res.status} ${text}`);
    }
    return res.json();
  },

  async syncStatus(): Promise<SyncStatusResult> {
    const res = await fetch(`${API_BASE}/sync/status`);
    if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
    return res.json();
  },

  async ping(): Promise<{ pong: boolean }> {
    const res = await fetch(`${API_BASE}/ping`);
    if (!res.ok) throw new Error(`Ping failed: ${res.status}`);
    return res.json();
  },
};

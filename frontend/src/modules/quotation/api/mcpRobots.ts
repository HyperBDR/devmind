import apiClient from '@/api'

export type McpRobotScope = 'quotation:read' | 'invoice:read'

export interface McpRobotCredential {
  id: string
  name: string
  user_id: number
  username: string
  scopes: McpRobotScope[]
  created_at: string
  expires_at: string | null
  revoked_at: string | null
}

export interface CreatedMcpRobotCredential extends McpRobotCredential {
  token: string
}

function responseData<T>(response: { data: unknown }): T {
  const payload = response.data as { data?: T }
  return payload?.data ?? (response.data as T)
}

export async function getMcpRobotCredentials(): Promise<
  McpRobotCredential[]
> {
  const response = await apiClient.get('/v1/mcp/robots/')
  return responseData<{ results: McpRobotCredential[] }>(response).results
}

export async function createMcpRobotCredential(payload: {
  name: string
  user_id: number
  expires_in_days: number
}): Promise<CreatedMcpRobotCredential> {
  const response = await apiClient.post('/v1/mcp/robots/', payload)
  return responseData<CreatedMcpRobotCredential>(response)
}

export async function revokeMcpRobotCredential(
  credentialId: string,
): Promise<void> {
  await apiClient.delete(`/v1/mcp/robots/${credentialId}/`)
}

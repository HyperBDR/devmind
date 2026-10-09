import api from './index'

export function getMcpOAuthAuthorization(transactionId) {
  return api
    .get(`/v1/mcp/oauth/transactions/${transactionId}`)
    .then((response) => response.data?.data ?? response.data)
}

export function finishMcpOAuthAuthorization(transactionId, approved) {
  return api
    .post(`/v1/mcp/oauth/transactions/${transactionId}`, { approved })
    .then((response) => response.data?.data ?? response.data)
}

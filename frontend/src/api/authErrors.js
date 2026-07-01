export function isSessionInvalidError(error) {
  return error?.response?.status === 401
}

export function shouldKeepAuthStateOnError(error) {
  const status = error?.response?.status
  if (Number.isInteger(status)) {
    return status === 408 || status >= 500
  }

  if (!error?.isAxiosError) {
    return false
  }

  return ['ECONNABORTED', 'ERR_NETWORK', 'ETIMEDOUT'].includes(error.code)
}

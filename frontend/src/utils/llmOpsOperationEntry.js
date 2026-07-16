export function parseLLMOpsOperationTarget(search = '') {
  const params = new URLSearchParams(String(search || ''))

  return {
    modelId: positiveIntegerParam(params, 'model_id'),
    openPlatformConfig: params.get('open_platform_config') === '1',
    platformId: positiveIntegerParam(params, 'platform_id'),
    sourceId: positiveIntegerParam(params, 'source_id'),
    section: params.get('section') || ''
  }
}

function positiveIntegerParam(params, key) {
  const value = Number(params.get(key))
  return Number.isInteger(value) && value > 0 ? value : null
}

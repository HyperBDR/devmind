// Canonical meta-model helpers shared by LLM Ops front-end components.
//
// Meta-model semantics:
//   * Meta model = a real model family published by a model owner
//     (OpenAI, Anthropic, Google, Aliyun, DeepSeek, Kimi, MiniMax, ...).
//   * Meta owner = the company that develops the model.
//   * Supplier / price source = a third party that resells access
//     (SiliconFlow, OpenRouter, Volcano Ark, ...). They are *never*
//     a meta owner and must never own a meta model row.

const META_MODEL_OWNER_RULES = [
  { test: (code) => code.startsWith('deepseek-'), code: 'deepseek' },
  { test: (code) => code.startsWith('qwen'), code: 'aliyun' },
  { test: (code) => code.startsWith('wanx'), code: 'aliyun-wanx' },
  { test: (code) => code.startsWith('wan'), code: 'aliyun-wanx' },
  { test: (code) => code.startsWith('doubao-'), code: 'volcengine' },
  { test: (code) => code.startsWith('claude-'), code: 'anthropic' },
  { test: (code) => code.startsWith('gemini-'), code: 'google' },
  { test: (code) => code.startsWith('gpt-'), code: 'openai' },
  { test: (code) => code.startsWith('o1'), code: 'openai' },
  { test: (code) => code.startsWith('o3'), code: 'openai' },
  { test: (code) => code.startsWith('o4'), code: 'openai' },
  { test: (code) => code.startsWith('text-embedding-'), code: 'openai' }
]

// Supplier / price-source aliases. These are *not* meta owners and
// must never appear in meta-model filters.
export const SUPPLIER_SOURCE_OWNER_ALIASES = new Set([
  'siliconflow',
  'openrouter',
  'yunce',
  'agione'
])

/**
 * Resolve the canonical meta-owner code for a model identifier.
 *
 * @param {string} modelCode Raw model code (case-insensitive).
 * @returns {string} Owner code, or empty string when unknown.
 */
export function canonicalMetaOwnerCode(modelCode) {
  const code = String(modelCode || '').toLowerCase()
  if (!code) return ''
  for (const rule of META_MODEL_OWNER_RULES) {
    if (rule.test(code)) return rule.code
  }
  return ''
}

/**
 * @param {string} ownerCode Candidate owner code.
 * @returns {boolean} True when the code is a real meta owner, not a
 *   supplier alias.
 */
export function isCanonicalMetaOwnerCode(ownerCode) {
  const code = String(ownerCode || '').toLowerCase()
  if (!code) return false
  if (SUPPLIER_SOURCE_OWNER_ALIASES.has(code)) return false
  return true
}

/**
 * Resolve the canonical meta owner for a model record. The backend
 * serialiser exposes `owner_*` fields on meta models and
 * `meta_model_owner_*` fields on SKU rows. When they are missing,
 * the resolver falls back to model code prefix lookup so the UI keeps
 * a consistent grouping.
 *
 * @param {object} modelRecord Either a meta-model or an LLM model.
 * @param {Array<object>} providers Provider list (LLMProvider rows).
 * @returns {{id: (string|number), code: string, name: string}}
 *   Empty fields when no canonical owner can be determined.
 */
export function resolveCanonicalMetaOwner(modelRecord, providers) {
  if (!modelRecord) {
    return { id: '', code: '', name: '' }
  }
  const ownerCode = String(
    modelRecord.owner_code || modelRecord.meta_model_owner_code || ''
  ).toLowerCase()
  if (ownerCode && isCanonicalMetaOwnerCode(ownerCode)) {
    const hit = (providers || []).find(
      (p) => String(p.code).toLowerCase() === ownerCode
    )
    if (hit) {
      return { id: ownerCode, code: ownerCode, name: hit.name }
    }
    return {
      id: ownerCode,
      code: ownerCode,
      name:
        modelRecord.owner_name || modelRecord.meta_model_owner_name || ownerCode
    }
  }
  const code = canonicalMetaOwnerCode(
    modelRecord.meta_model_code ||
      modelRecord.code ||
      modelRecord.model_code ||
      ''
  )
  if (!code) {
    return {
      id: modelRecord.owner_code || modelRecord.meta_model_owner_code || '',
      code: '',
      name: modelRecord.owner_name || modelRecord.meta_model_owner_name || ''
    }
  }
  const hit = (providers || []).find(
    (p) => String(p.code).toLowerCase() === code
  )
  if (hit) {
    return { id: code, code, name: hit.name }
  }
  return { id: code, code, name: code }
}

/**
 * Filter the supplied provider list down to canonical meta owners
 * (excludes supplier / price-source aliases).
 *
 * @param {Array<object>} providers Raw provider rows.
 * @returns {Array<object>} Providers safe to use as meta owners.
 */
export function canonicalMetaOwnerOptions(providers) {
  return (providers || []).filter((p) => isCanonicalMetaOwnerCode(p.code))
}

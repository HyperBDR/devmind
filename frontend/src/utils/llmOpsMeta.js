// Canonical meta-model helpers shared by LLM Ops front-end components.
//
// Meta-model semantics:
//   * Meta model = a real model SKU published by a model vendor
//     (OpenAI, Anthropic, Google, Aliyun, DeepSeek, Kimi, MiniMax, ...).
//   * Meta vendor = the company that develops the model.
//   * Supplier / price source = a third party that resells access
//     (SiliconFlow, OpenRouter, Volcano Ark, ...). They are *never*
//     a meta vendor and must never own a meta model row.

const META_MODEL_VENDOR_RULES = [
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

// Supplier / price-source aliases. These are *not* meta vendors and
// must never appear in meta-model filters.
export const SUPPLIER_SOURCE_VENDOR_ALIASES = new Set([
  'siliconflow',
  'openrouter',
  'yunce',
  'agione'
])

/**
 * Resolve the canonical meta-vendor code for a model identifier.
 *
 * @param {string} modelCode Raw model code (case-insensitive).
 * @returns {string} Vendor code, or empty string when unknown.
 */
export function canonicalMetaVendorCode(modelCode) {
  const code = String(modelCode || '').toLowerCase()
  if (!code) return ''
  for (const rule of META_MODEL_VENDOR_RULES) {
    if (rule.test(code)) return rule.code
  }
  return ''
}

/**
 * @param {string} vendorCode Candidate vendor code.
 * @returns {boolean} True when the code is a real meta vendor, not a
 *   supplier alias.
 */
export function isCanonicalMetaVendorCode(vendorCode) {
  const code = String(vendorCode || '').toLowerCase()
  if (!code) return false
  if (SUPPLIER_SOURCE_VENDOR_ALIASES.has(code)) return false
  return true
}

/**
 * Resolve the canonical meta-vendor for a model record. The backend
 * serialiser already exposes `effective_vendor_*` fields, so the
 * resolver prefers those. When they are missing it falls back to the
 * model code prefix lookup so the UI keeps a consistent grouping.
 *
 * @param {object} modelRecord Either a meta-model or an LLM model.
 * @param {Array<object>} providers Vendor list (LLMProvider rows).
 * @returns {{id: (string|number), code: string, name: string}}
 *   Empty fields when no canonical vendor can be determined.
 */
export function resolveCanonicalMetaVendor(modelRecord, providers) {
  if (!modelRecord) {
    return { id: '', code: '', name: '' }
  }
  const effectiveCode = String(
    modelRecord.effective_vendor_code ||
      modelRecord.vendor_code ||
      ''
  ).toLowerCase()
  if (effectiveCode && isCanonicalMetaVendorCode(effectiveCode)) {
    const hit = (providers || []).find(
      (p) => String(p.code).toLowerCase() === effectiveCode
    )
    if (hit) {
      return { id: hit.id, code: hit.code, name: hit.name }
    }
  }
  const code = canonicalMetaVendorCode(
    modelRecord.code ||
      modelRecord.meta_model_code ||
      modelRecord.model_code ||
      ''
  )
  if (!code) {
    return {
      id: modelRecord.effective_vendor || modelRecord.vendor || '',
      code: '',
      name:
        modelRecord.effective_vendor_name ||
        modelRecord.vendor_name ||
        ''
    }
  }
  const hit = (providers || []).find(
    (p) => String(p.code).toLowerCase() === code
  )
  if (hit) {
    return { id: hit.id, code: hit.code, name: hit.name }
  }
  return { id: '', code, name: code }
}

/**
 * Filter the supplied provider list down to canonical meta vendors
 * (excludes supplier / price-source aliases).
 *
 * @param {Array<object>} providers Raw provider rows.
 * @returns {Array<object>} Providers safe to use as meta vendors.
 */
export function canonicalMetaVendorOptions(providers) {
  return (providers || []).filter((p) =>
    isCanonicalMetaVendorCode(p.code)
  )
}

// Compatibility URLs must not carry archived workspace actions forward.
export function redirectLegacyLlmOps() {
  return { path: '/agione', query: {}, hash: '' }
}

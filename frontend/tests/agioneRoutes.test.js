import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { createMemoryHistory, createRouter } from 'vue-router'
import { redirectLegacyLlmOps } from '../src/utils/agioneRoutes.js'
import {
  getAvailablePlatforms,
  getLandingPath,
  hasFeature,
  normalizeFeatureKeys
} from '../src/utils/platformAccess.js'

const source = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')

test('canonical AGIOne route is independently authenticated and named', () => {
  const route = source.split("path: '/agione'")[1].split('path:')[0]
  assert.match(route, /name: 'Agione'/)
  assert.match(route, /requiresAuth: true/)
  assert.match(route, /requiredFeature: 'agione_ops'/)
  assert.match(route, /pages\/AgioneOps\.vue/)
  assert.doesNotMatch(route, /appKey|llm_ops/)
  for (const path of ['/llm-ops', '/llm-ops/archive']) {
    const legacy = source.split(`path: '${path}'`)[1].split('path:')[0]
    assert.match(legacy, /redirect: redirectLegacyLlmOps/)
    assert.doesNotMatch(legacy, /component|alias|appKey/)
  }
})

test('legacy redirects drop all archived query actions and hashes', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/agione', name: 'Agione', component: {} },
      { path: '/llm-ops', redirect: redirectLegacyLlmOps },
      { path: '/llm-ops/archive', redirect: redirectLegacyLlmOps }
    ]
  })
  for (const path of [
    '/llm-ops?section=reseller&action=publish#pricing',
    '/llm-ops/archive?section=monitor#history',
    '/llm-ops?section=reconciliation#focus',
    '/llm-ops/archive'
  ]) {
    await router.push(path)
    assert.equal(router.currentRoute.value.fullPath, '/agione')
    assert.equal(router.currentRoute.value.name, 'Agione')
    assert.deepEqual(router.currentRoute.value.query, {})
    assert.equal(router.currentRoute.value.hash, '')
  }
})

test('stale AGIOne profile paths are corrected without granting old users access', () => {
  for (const oldPath of ['/llm-ops', '/llm-ops/archive', '/dashboard']) {
    const user = {
      access_profile: {
        visible_features: ['agione_ops'],
        available_platforms: [{ key: 'agione_ops', default_path: oldPath }],
        preferred_platform: 'agione_ops',
        landing_path: oldPath
      }
    }
    assert.equal(getLandingPath(user), '/agione')
    assert.equal(getAvailablePlatforms(user).find(x => x.key === 'agione_ops').defaultPath, '/agione')
  }
  const legacy = { access_profile: { visible_features: ['llm_ops'], preferred_platform: 'llm_ops' } }
  assert.equal(hasFeature(legacy, 'agione_ops'), false)
  assert.equal(getLandingPath(legacy), '/dashboard')
  assert.deepEqual(normalizeFeatureKeys(['llm_operations']), ['llm_ops'])
  assert.equal(getAvailablePlatforms({ is_staff: true }).some(x => x.key === 'llm_ops'), false)
})

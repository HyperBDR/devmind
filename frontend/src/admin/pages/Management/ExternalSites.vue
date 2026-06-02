<template>
  <AdminLayout>
    <div class="w-full max-w-full p-6">
      <div class="mb-4">
        <h1 class="text-lg font-semibold text-gray-900">外部站点代理</h1>
        <p class="mt-1 text-sm text-gray-500">
          配置外部站点代理标识、目标服务地址和认证方式。
        </p>
      </div>

      <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
        <div class="p-6">
          <div class="flex flex-wrap items-center justify-end gap-3 mb-6">
            <BaseButton
              variant="outline"
              size="sm"
              :loading="loading"
              @click="loadList"
            >
              刷新
            </BaseButton>
            <BaseButton variant="primary" size="sm" @click="openAddModal">
              新增站点
            </BaseButton>
          </div>

          <BaseLoading v-if="loading" />
          <template v-else>
            <div
              v-if="list.length === 0"
              class="py-16 text-center rounded-lg border border-gray-200 bg-gray-50"
            >
              <p class="text-sm font-medium text-gray-600">暂无外部站点配置</p>
            </div>
            <div
              v-else
              class="overflow-x-auto rounded-lg border border-gray-200"
            >
              <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                  <tr>
                    <th
                      class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider"
                    >
                      名称
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider"
                    >
                      访问路径
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider"
                    >
                      访问方式
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider"
                    >
                      目标地址
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider"
                    >
                      协议
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider"
                    >
                      认证方式
                    </th>
                    <th
                      class="px-4 py-3 text-left text-xs font-semibold text-gray-700 uppercase tracking-wider"
                    >
                      启用
                    </th>
                    <th
                      class="px-4 py-3 text-right text-xs font-semibold text-gray-700 uppercase tracking-wider"
                    >
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-100">
                  <tr
                    v-for="row in list"
                    :key="row.id"
                    class="hover:bg-gray-50"
                  >
                    <td
                      class="px-4 py-3 whitespace-nowrap text-sm text-gray-900"
                    >
                      {{ row.name }}
                    </td>
                    <td
                      class="px-4 py-3 whitespace-nowrap text-sm text-gray-700 font-mono"
                    >
                      {{ row.path_prefix }}
                    </td>
                    <td
                      class="px-4 py-3 whitespace-nowrap text-sm text-gray-700"
                    >
                      {{ accessModeLabel(row.access_mode) }}
                    </td>
                    <td
                      class="px-4 py-3 whitespace-nowrap text-sm text-gray-700"
                    >
                      {{ displayTarget(row) }}
                    </td>
                    <td
                      class="px-4 py-3 whitespace-nowrap text-sm text-gray-700"
                    >
                      {{
                        row.access_mode === 'proxy'
                          ? (row.target_scheme || 'http').toUpperCase()
                          : '-'
                      }}
                    </td>
                    <td
                      class="px-4 py-3 whitespace-nowrap text-sm text-gray-700"
                    >
                      {{ authTypeLabel(row.auth_type) }}
                    </td>
                    <td
                      class="px-4 py-3 whitespace-nowrap text-sm text-gray-700"
                    >
                      {{ row.is_active ? '是' : '否' }}
                    </td>
                    <td class="px-4 py-3 whitespace-nowrap text-right">
                      <div class="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          class="inline-flex items-center justify-center rounded p-1.5 text-blue-600 hover:bg-blue-50"
                          @click="openSite(row)"
                        >
                          打开
                        </button>
                        <button
                          type="button"
                          class="inline-flex items-center justify-center rounded p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                          @click="copyPath(row)"
                        >
                          复制链接
                        </button>
                        <button
                          type="button"
                          class="inline-flex items-center justify-center rounded p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                          @click="openEditModal(row)"
                        >
                          编辑
                        </button>
                        <button
                          type="button"
                          class="inline-flex items-center justify-center rounded p-1.5 text-gray-500 hover:bg-red-50 hover:text-red-600"
                          @click="confirmDelete(row)"
                        >
                          删除
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
      </div>

      <BaseModal
        :show="showModal"
        :title="editingId ? '编辑外部站点' : '新增外部站点'"
        @close="closeModal"
      >
        <form @submit.prevent="submitForm" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1"
              >名称</label
            >
            <input
              v-model="form.name"
              type="text"
              class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"
              required
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1"
              >代理标识</label
            >
            <input
              v-model="form.slug"
              type="text"
              class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md font-mono"
              placeholder="my_service"
              required
            />
            <p class="mt-1 text-xs text-gray-500">
              实际访问路径将自动生成为 /proxy/{{ form.slug || 'your_slug' }}/
            </p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1"
              >访问路径</label
            >
            <input
              :value="`/proxy/${form.slug || 'your_slug'}/`"
              type="text"
              class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md font-mono bg-gray-50"
              readonly
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1"
              >访问方式</label
            >
            <select
              v-model="form.access_mode"
              class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md bg-white"
            >
              <option value="proxy">平台代理</option>
              <option value="iframe">Iframe 嵌入</option>
              <option value="redirect">直接跳转</option>
            </select>
          </div>
          <div v-if="form.access_mode === 'proxy'">
            <label class="block text-sm font-medium text-gray-700 mb-1"
              >目标服务地址</label
            >
            <input
              v-model="form.target_host"
              type="text"
              class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"
              placeholder="frontend:3000 或 127.0.0.1:18082"
              required
            />
          </div>
          <div v-if="form.access_mode === 'proxy'">
            <label class="block text-sm font-medium text-gray-700 mb-1"
              >目标服务协议</label
            >
            <select
              v-model="form.target_scheme"
              class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md bg-white"
            >
              <option value="http">HTTP</option>
              <option value="https">HTTPS</option>
            </select>
          </div>
          <div
            v-if="
              form.access_mode === 'proxy' && form.target_scheme === 'https'
            "
          >
            <label class="flex items-center gap-2">
              <input
                v-model="form.verify_tls"
                type="checkbox"
                class="rounded border-gray-300"
              />
              <span class="text-sm text-gray-700">校验 HTTPS 证书</span>
            </label>
            <p class="mt-1 text-xs text-gray-500">
              仅在目标使用自签证书且无法替换时取消勾选。
            </p>
          </div>
          <div v-else>
            <label class="block text-sm font-medium text-gray-700 mb-1"
              >外部 URL</label
            >
            <input
              v-model="form.external_url"
              type="text"
              class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"
              placeholder="https://myteamone.io"
              required
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1"
              >描述</label
            >
            <textarea
              v-model="form.description"
              class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"
              rows="2"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1"
              >所需功能标识</label
            >
            <input
              v-model="form.required_feature"
              type="text"
              class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"
              placeholder="admin_console"
            />
          </div>
          <div v-if="form.access_mode === 'proxy'">
            <label class="block text-sm font-medium text-gray-700 mb-1"
              >认证方式</label
            >
            <select
              v-model="form.auth_type"
              class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md bg-white"
            >
              <option value="none">无认证</option>
              <option value="token_fetch">外部服务自签发 Token</option>
              <option value="static_token">静态 Token</option>
              <option value="hmac">HMAC 签名</option>
            </select>
          </div>

          <template v-if="form.auth_type === 'static_token'">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1"
                >静态 Token</label
              >
              <input
                v-model="form.static_token"
                type="text"
                class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"
              />
            </div>
          </template>

          <template v-if="form.auth_type === 'token_fetch'">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1"
                >Token 获取 URL</label
              >
              <input
                v-model="form.token_fetch_url"
                type="text"
                class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1"
                >Token 获取方法</label
              >
              <select
                v-model="form.token_fetch_method"
                class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md bg-white"
              >
                <option value="POST">POST</option>
                <option value="GET">GET</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1"
                >Token 请求头(JSON)</label
              >
              <textarea
                v-model="form.token_fetch_headers_text"
                class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md font-mono"
                rows="3"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1"
                >Token 请求体(JSON)</label
              >
              <textarea
                v-model="form.token_fetch_body_text"
                class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md font-mono"
                rows="3"
              />
            </div>
          </template>

          <template v-if="form.auth_type === 'hmac'">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1"
                >HMAC 密钥</label
              >
              <input
                v-model="form.hmac_secret"
                type="text"
                class="block w-full px-3 py-2 text-sm border border-gray-300 rounded-md"
              />
            </div>
          </template>

          <div class="flex items-center gap-2">
            <input id="is_active" v-model="form.is_active" type="checkbox" />
            <label for="is_active" class="text-sm text-gray-700">启用</label>
          </div>

          <div v-if="formMessage" class="text-red-600 text-sm">
            {{ formMessage }}
          </div>

          <div
            class="flex flex-wrap items-center justify-end gap-3 pt-2 border-t border-gray-200"
          >
            <BaseButton type="button" variant="outline" @click="closeModal"
              >取消</BaseButton
            >
            <BaseButton type="submit" variant="primary" :loading="saving">
              {{ editingId ? '保存' : '新增站点' }}
            </BaseButton>
          </div>
        </form>
      </BaseModal>

      <BaseModal
        :show="showDeleteConfirm"
        title="删除外部站点"
        @close="showDeleteConfirm = false"
      >
        <p class="text-sm text-gray-700 mb-4">确认删除该外部站点配置？</p>
        <div class="flex flex-wrap items-center justify-end gap-3">
          <BaseButton variant="outline" @click="showDeleteConfirm = false"
            >取消</BaseButton
          >
          <BaseButton
            variant="primary"
            :loading="deleting"
            class="bg-red-600 hover:bg-red-700"
            @click="doDelete"
            >删除</BaseButton
          >
        </div>
      </BaseModal>
    </div>
  </AdminLayout>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useToast } from '@/composables/useToast'
import { externalProxyAdminApi } from '@/admin/api'
import AdminLayout from '@/admin/layout/AdminLayout.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseLoading from '@/components/ui/BaseLoading.vue'
import BaseModal from '@/components/ui/BaseModal.vue'

const { showSuccess, showError } = useToast()

const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const list = ref([])
const showModal = ref(false)
const showDeleteConfirm = ref(false)
const editingId = ref(null)
const deleteTarget = ref(null)
const formMessage = ref('')

const defaultForm = () => ({
  name: '',
  slug: '',
  access_mode: 'proxy',
  target_host: '',
  target_scheme: 'http',
  verify_tls: true,
  external_url: '',
  description: '',
  required_feature: 'admin_console',
  auth_type: 'none',
  static_token: '',
  token_fetch_url: '',
  token_fetch_method: 'POST',
  token_fetch_headers_text: '{}',
  token_fetch_body_text: '{}',
  hmac_secret: '',
  is_active: true,
  order: 0
})

const form = reactive(defaultForm())

function accessModeLabel(value) {
  return (
    {
      proxy: '平台代理',
      iframe: 'Iframe 嵌入',
      redirect: '直接跳转'
    }[value] || value
  )
}

function authTypeLabel(value) {
  return (
    {
      none: '无认证',
      token_fetch: '外部服务自签发 Token',
      static_token: '静态 Token',
      hmac: 'HMAC 签名'
    }[value] || value
  )
}

function displayTarget(row) {
  if (row.access_mode === 'proxy') {
    return row.target_host || '-'
  }
  return row.external_url || '-'
}

function resetForm() {
  Object.assign(form, defaultForm())
  editingId.value = null
  formMessage.value = ''
}

function parseJsonText(value, fieldName) {
  try {
    return value?.trim() ? JSON.parse(value) : {}
  } catch {
    throw new Error(`${fieldName} 不是合法 JSON`)
  }
}

function buildPayload() {
  const payload = {
    name: form.name.trim(),
    slug: form.slug.trim(),
    access_mode: form.access_mode,
    description: form.description.trim(),
    required_feature: form.required_feature.trim(),
    is_active: form.is_active,
    order: form.order
  }

  if (form.access_mode === 'proxy') {
    payload.target_host = form.target_host.trim()
    payload.target_scheme = form.target_scheme
    payload.verify_tls = form.verify_tls
    payload.auth_type = form.auth_type
    if (!editingId.value || form.static_token.trim()) {
      payload.static_token = form.static_token
    }
    if (form.auth_type === 'token_fetch') {
      payload.token_fetch_url = form.token_fetch_url.trim()
      payload.token_fetch_method = form.token_fetch_method
      if (!editingId.value || form.token_fetch_headers_text.trim()) {
        payload.token_fetch_headers = parseJsonText(
          form.token_fetch_headers_text,
          'Token 请求头'
        )
      }
      if (!editingId.value || form.token_fetch_body_text.trim()) {
        payload.token_fetch_body = parseJsonText(
          form.token_fetch_body_text,
          'Token 请求体'
        )
      }
    }
    if (!editingId.value || form.hmac_secret.trim()) {
      payload.hmac_secret = form.hmac_secret
    }
  } else {
    payload.external_url = form.external_url.trim()
    payload.auth_type = 'none'
  }

  return payload
}

async function loadList() {
  loading.value = true
  try {
    list.value = await externalProxyAdminApi.getSites()
  } catch (e) {
    list.value = []
    showError(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openAddModal() {
  resetForm()
  showModal.value = true
}

function openEditModal(row) {
  resetForm()
  editingId.value = row.id
  Object.assign(form, {
    name: row.name || '',
    slug: row.slug || '',
    access_mode: row.access_mode || 'proxy',
    target_host: row.target_host || '',
    target_scheme: row.target_scheme || 'http',
    verify_tls: row.verify_tls !== false,
    external_url: row.external_url || '',
    description: row.description || '',
    required_feature: row.required_feature || 'admin_console',
    auth_type: row.auth_type || 'none',
    static_token: '',
    token_fetch_url: row.token_fetch_url || '',
    token_fetch_method: row.token_fetch_method || 'POST',
    token_fetch_headers_text: '',
    token_fetch_body_text: '',
    hmac_secret: '',
    is_active: !!row.is_active,
    order: row.order || 0
  })
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  resetForm()
}

async function submitForm() {
  saving.value = true
  formMessage.value = ''
  try {
    const payload = buildPayload()
    if (editingId.value) {
      await externalProxyAdminApi.putSite(editingId.value, payload)
    } else {
      await externalProxyAdminApi.postSite(payload)
    }
    showSuccess('保存成功')
    closeModal()
    loadList()
  } catch (e) {
    formMessage.value = e?.response?.data?.detail || e?.message || '保存失败'
  } finally {
    saving.value = false
  }
}

function confirmDelete(row) {
  deleteTarget.value = row
  showDeleteConfirm.value = true
}

async function doDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await externalProxyAdminApi.deleteSite(deleteTarget.value.id)
    showSuccess('删除成功')
    showDeleteConfirm.value = false
    deleteTarget.value = null
    loadList()
  } catch (e) {
    showError(e?.response?.data?.detail || e?.message || '删除失败')
  } finally {
    deleting.value = false
  }
}

function openSite(row) {
  if (row.access_mode === 'proxy') {
    window.open(`/proxy/${row.slug}/`, '_blank', 'noopener')
  } else if (row.access_mode === 'iframe') {
    window.open(
      `/management/external-sites/frame/${row.id}`,
      '_blank',
      'noopener'
    )
  } else {
    window.open(
      `/management/external-sites/open/${row.id}`,
      '_blank',
      'noopener'
    )
  }
}

async function copyPath(row) {
  try {
    let url
    if (row.access_mode === 'proxy') {
      url = `${window.location.origin}/proxy/${row.slug}/`
    } else {
      const data = await externalProxyAdminApi.launchSite(row.id)
      url = data?.launch_url || row.external_url
    }
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(url)
    } else {
      const ta = document.createElement('textarea')
      ta.value = url
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    showSuccess('链接已复制')
  } catch (e) {
    showError(e?.message || '复制失败')
  }
}

onMounted(() => {
  loadList()
})
</script>

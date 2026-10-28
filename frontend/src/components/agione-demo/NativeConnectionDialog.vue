<template>
  <dialog ref="dialog" class="native-connection-dialog" aria-labelledby="nativeConnectionTitle" @close="clearSecrets" @cancel="clearSecrets">
    <form v-if="canManage" @submit.prevent="save" autocomplete="off">
      <div class="native-heading"><h2 id="nativeConnectionTitle">AGIOne 原生直连配置</h2><button type="button" aria-label="关闭连接配置" :disabled="busy" @click="close">×</button></div>
      <p>DevMind 后端直接请求 AGIOne 上游，不中转 8011。密钥仅写入后端加密存储，不会回显。</p>
      <label>已有原生连接<select v-model="editingId" :disabled="busy" @change="selectExisting"><option value="">新建连接</option><option v-for="item in connections" :key="item.id" :value="item.id">{{ item.name }} · {{ item.platform }} / {{ item.principalKind }}</option></select></label>
      <div class="native-grid">
        <label>名称<input v-model.trim="draft.name" maxlength="160" required :disabled="busy" /></label>
        <label>上游 HTTPS 地址<input v-model.trim="draft.endpoint" type="url" required placeholder="https://AGIOne上游域名" :disabled="busy" /></label>
        <label>平台<select v-model="draft.platform" :disabled="busy || !!editingId"><option value="pro">Pro</option><option value="cc">CC</option></select></label>
        <label>账号身份<select v-model="draft.principalKind" :disabled="busy || !!editingId"><option value="provider">Provider</option><option value="operator">Operator</option></select></label>
        <label>预期租户 ID<input v-model.trim="draft.expectedTenantId" required maxlength="160" :disabled="busy || !!editingId" /></label>
        <label>认证方式<select v-model="draft.authMode" :disabled="busy" @change="clearSecrets"><option value="aksk">AK / SK 签名</option><option value="password">账号密码登录</option></select></label>
        <label>API 前缀<input v-model.trim="draft.apiPrefix" placeholder="/hyperone" :disabled="busy" /></label>
        <label>用户名（可选核验）<input v-model="draft.username" autocomplete="off" :disabled="busy" /></label>
        <template v-if="draft.authMode === 'aksk'"><label>Access Key<input v-model="draft.accessKey" type="password" autocomplete="new-password" :required="!editingId" :disabled="busy" /></label><label>Secret Key<input v-model="draft.secretKey" type="password" autocomplete="new-password" :required="!editingId" :disabled="busy" /></label></template>
        <template v-else><label>密码<input v-model="draft.password" type="password" autocomplete="new-password" :required="!editingId" :disabled="busy" /></label><label>密码 AES Key<input v-model="draft.passwordAesKey" type="password" autocomplete="new-password" :required="!editingId" :disabled="busy" /></label><label>Client ID<input v-model="draft.clientId" autocomplete="off" :required="!editingId" :disabled="busy" /></label><label>Client Secret<input v-model="draft.clientSecret" type="password" autocomplete="new-password" :required="!editingId" :disabled="busy" /></label></template>
        <label>shost（按上游要求）<input v-model.trim="draft.shost" autocomplete="off" :disabled="busy" /></label><label>static_route（按上游要求）<input v-model.trim="draft.staticRoute" autocomplete="off" :disabled="busy" /></label>
      </div>
      <label class="native-check"><input v-model="draft.enabled" type="checkbox" :disabled="busy" />启用连接</label>
      <label v-if="currentUserId" class="native-check"><input v-model="grantSelf" type="checkbox" :disabled="busy" />明确授权当前账号读取此连接（不授权同步或写入）</label>
      <p>编辑时密钥留空表示保留原凭据；填写新密钥会替换整组认证配置。保存不会自动执行验证操作。</p>
      <p v-if="error" role="alert">{{ error }}</p><p v-if="status" role="status">{{ status }}</p>
      <div class="native-footer"><button type="button" :disabled="busy || !editingId" @click="verify">测试直连身份</button><button type="button" :disabled="busy" @click="close">取消</button><button type="submit" :disabled="busy">{{ busy ? '处理中…' : '保存加密配置' }}</button></div>
    </form>
    <div v-else><h2 id="nativeConnectionTitle">连接配置未授权</h2><p>需要管理员显式配置权限。</p><button type="button" @click="close">关闭</button></div>
  </dialog>
</template>

<script setup>
import { onBeforeUnmount, reactive, ref } from 'vue'
import { agioneOpsApi } from '@/api/agioneOps'
const props = defineProps({ canManage: Boolean, connections: { type: Array, default: () => [] }, currentUserId: { type: [String, Number], default: '' } })
const emit = defineEmits(['changed'])
const dialog = ref(null), busy = ref(false), editingId = ref(''), error = ref(''), status = ref(''), grantSelf = ref(false)
const defaults = () => ({ name: '', endpoint: '', platform: 'pro', principalKind: 'provider', expectedTenantId: '', enabled: true, authMode: 'aksk', apiPrefix: '/hyperone', username: '', accessKey: '', secretKey: '', password: '', passwordAesKey: '', clientId: '', clientSecret: '', shost: '', staticRoute: '' })
const draft = reactive(defaults())
function clearSecrets() { for (const key of ['accessKey', 'secretKey', 'password', 'passwordAesKey', 'clientSecret']) draft[key] = '' }
function close() { if (busy.value) return; clearSecrets(); dialog.value?.close() }
function open() { if (!props.canManage) return; Object.assign(draft, defaults()); editingId.value = ''; grantSelf.value = false; error.value = ''; status.value = ''; dialog.value?.showModal() }
function selectExisting() { clearSecrets(); const item = props.connections.find(row => row.id === editingId.value); Object.assign(draft, defaults(), item ? { name: item.name, endpoint: item.endpoint || '', platform: item.platform, principalKind: item.principalKind, expectedTenantId: item.expectedTenantId || '', enabled: item.enabled } : {}); status.value = ''; error.value = ''; grantSelf.value = false }
function safeError(exc) { const code = exc?.response?.data?.data?.errorCode; return /^[A-Za-z_0-9]{1,100}$/.test(code || '') ? `操作未完成（${code}），请检查地址、权限与配置。` : '操作未完成，请检查连接配置或读取权限。' }
async function save() {
  if (!props.canManage || busy.value) return
  const actor = props.currentUserId
  busy.value = true; error.value = ''; status.value = ''
  try {
    const payload = { name: draft.name, endpoint: draft.endpoint, enabled: draft.enabled }
    if (!editingId.value) Object.assign(payload, { sourceKind: 'native', platform: draft.platform, principalKind: draft.principalKind, expectedTenantId: draft.expectedTenantId })
    const changingSecrets = draft.authMode === 'aksk' ? !!(draft.accessKey || draft.secretKey) : !!(draft.password || draft.passwordAesKey || draft.clientSecret)
    if (!editingId.value || changingSecrets) {
      const credentials = { auth_mode: draft.authMode, api_prefix: draft.apiPrefix }
      for (const [key, value] of Object.entries({ username: draft.username, shost: draft.shost, static_route: draft.staticRoute })) if (value) credentials[key] = value
      if (draft.authMode === 'aksk') { if (!draft.accessKey || !draft.secretKey) throw new Error('missing'); Object.assign(credentials, { access_key: draft.accessKey, secret_key: draft.secretKey }) }
      else { if (!draft.password || !draft.passwordAesKey || !draft.clientId || !draft.clientSecret || !draft.username) throw new Error('missing'); Object.assign(credentials, { password: draft.password, password_aes_key: draft.passwordAesKey, client_id: draft.clientId, client_secret: draft.clientSecret }) }
      payload.credentials = credentials
    }
    const response = editingId.value ? await agioneOpsApi.updateConnection(editingId.value, payload) : await agioneOpsApi.createConnection(payload)
    const connection = response?.data?.data
    if (!connection?.id) throw new Error('invalidResponse')
    if (!props.canManage || props.currentUserId !== actor) return
    editingId.value = connection.id
    if (grantSelf.value && props.currentUserId) await agioneOpsApi.grantConnection(connection.id, props.currentUserId, { canView: true, canSync: false })
    status.value = '配置已保存。可显式点击“测试直连身份”；业务读取只使用 DevMind 原生接口。'
    emit('changed')
  } catch (exc) { error.value = safeError(exc) }
  finally { clearSecrets(); busy.value = false }
}
async function verify() { if (!props.canManage || !editingId.value || busy.value) return; busy.value = true; error.value = ''; status.value = ''; try { await agioneOpsApi.verifyConnection(editingId.value); status.value = '上游直连身份验证通过。'; emit('changed') } catch (exc) { error.value = safeError(exc) } finally { busy.value = false } }
onBeforeUnmount(clearSecrets)
defineExpose({ open, close })
</script>

<style scoped>
.native-connection-dialog { width: min(850px, calc(100vw - 32px)); max-height: calc(100dvh - 48px); border: 1px solid #dbe2ec; border-radius: 12px; padding: 24px; color: #17233b; background: #fff; overflow-y: auto; }
.native-connection-dialog::backdrop { background: #15283f45; }
.native-heading,.native-footer { display: flex; align-items: center; gap: 12px; justify-content: space-between; }
.native-heading h2 { font-size: 20px; margin: 0; }
.native-connection-dialog p { font-size: 13px; line-height: 1.7; color: #586880; margin: 12px 0; }
.native-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 14px; margin: 16px 0; }
.native-connection-dialog label { display: flex; flex-direction: column; gap: 7px; font-size: 13px; }
.native-connection-dialog input,.native-connection-dialog select { border: 1px solid #ccd6e4; border-radius: 6px; padding: 9px; min-width: 0; color: #17233b; background: white; }
.native-connection-dialog .native-check { flex-direction: row; align-items: center; margin: 12px 0; }
.native-footer { justify-content: flex-end; margin-top: 20px; }
.native-footer button,.native-heading button { padding: 8px 12px; border: 1px solid #ccd6e4; border-radius: 6px; background: white; }
.native-footer button[type=submit] { background: #2563eb; color: white; }
@media(max-width:600px) { .native-grid { grid-template-columns: 1fr; } .native-footer { flex-wrap: wrap; } }
</style>

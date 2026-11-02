<template>
  <dialog
    ref="dialog"
    class="native-connection-dialog"
    aria-labelledby="nativeConnectionTitle"
    @close="clearSecrets"
    @cancel="clearSecrets"
  >
    <form @submit.prevent="save" autocomplete="off">
      <div class="native-heading">
        <div>
          <h2 id="nativeConnectionTitle">
            {{ editing ? '连接设置' : '连接 AGIOne' }}
          </h2>
          <p>
            {{
              editing
                ? '查看连接状态或更新访问密钥。'
                : '验证成功后自动采集经营数据。'
            }}
          </p>
        </div>
        <button
          type="button"
          aria-label="关闭连接配置"
          :disabled="busy"
          @click="close"
        >
          ×
        </button>
      </div>
      <div v-if="editing" class="native-status">
        <div>
          <span class="status-dot"></span
          ><b>{{ editing.enabled ? '已连接' : '已断开' }}</b>
        </div>
        <dl>
          <div>
            <dt>平台</dt>
            <dd>AGIOne {{ platformLabel(editing.platform) }}</dd>
          </div>
          <div>
            <dt>账号身份</dt>
            <dd>{{ accountLabel(editing.principalKind) }}</dd>
          </div>
          <div>
            <dt>最近连接验证</dt>
            <dd>{{ displayTime(editing.verifiedAt) }}</dd>
          </div>
        </dl>
      </div>
      <p v-if="editing" class="native-security">
        连接验证不代表上游已确认账号身份。若身份选错，请先断开此连接，
        再使用正确身份添加新连接；原连接及历史数据会保留。
      </p>
      <label v-if="!editing"
        >平台
        <select v-model="draft.platform" :disabled="busy">
          <option value="pro">AGIOne Pro</option>
          <option value="cc">AGIOne CC</option>
        </select>
      </label>
      <label v-if="!editing">账号身份
        <select v-model="draft.principalKind" :disabled="busy" required>
          <option value="" disabled>请选择账号身份</option>
          <option value="provider">Provider</option>
          <option value="operator">Operator</option>
        </select>
      </label>
      <p v-if="!editing" class="native-security">
        接口可访问不代表身份已确认。上游角色无法识别时，系统无法验证
        您的选择；选错可能导致数据范围不正确。请先核实账号身份。
      </p>
      <div v-if="editing" class="native-section-title">更新密钥</div>
      <label
        >Access Key
        <input
          v-model="draft.accessKey"
          type="password"
          autocomplete="new-password"
          :disabled="busy"
          :placeholder="editing ? '输入新 AK' : '请输入 AK'"
        />
      </label>
      <label
        >Secret Key
        <input
          v-model="draft.secretKey"
          type="password"
          autocomplete="new-password"
          :disabled="busy"
          :placeholder="editing ? '输入新 SK' : '请输入 SK'"
        />
      </label>
      <p class="native-security">
        ▣ 密钥加密保存，不会回显。{{ editing ? '留空则保留当前密钥。' : '' }}
      </p>
      <p v-if="error" class="native-error" role="alert">{{ error }}</p>
      <p v-if="status" class="native-success" role="status">{{ status }}</p>
      <div class="native-footer">
        <button
          v-if="editing && editing.enabled"
          type="button"
          class="danger"
          :disabled="busy"
          @click="disconnect"
        >
          断开连接
        </button>
        <span class="native-spacer"></span>
        <button type="button" :disabled="busy" @click="close">取消</button>
        <button type="submit" class="primary" :disabled="busy || !canSave">
          {{ busy ? '正在验证…' : editing ? '保存并验证' : '保存并连接' }}
        </button>
      </div>
    </form>
  </dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { agioneOpsApi } from '@/api/agioneOps'

const emit = defineEmits(['changed', 'disconnected'])
const dialog = ref(null),
  busy = ref(false),
  editing = ref(null)
const error = ref(''),
  status = ref('')
const draft = reactive({ platform: 'pro', principalKind: '', accessKey: '', secretKey: '' })
const canSave = computed(() =>
  editing.value
    ? (!draft.accessKey && !draft.secretKey) ||
      (!!draft.accessKey && !!draft.secretKey)
    : !!draft.principalKind && !!draft.accessKey && !!draft.secretKey
)

function clearSecrets() {
  draft.accessKey = ''
  draft.secretKey = ''
}
function platformLabel(value) {
  return value === 'cc' ? 'CC' : 'Pro'
}
function accountLabel(value) {
  return value === 'operator' ? 'Operator' : 'Provider'
}
function displayTime(value) {
  if (!value || !Number.isFinite(Date.parse(value))) return '尚未验证'
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}
function safeError(exc) {
  const code =
    exc?.response?.data?.data?.errorCode ||
    exc?.response?.data?.data?.detail?.code
  return (
    {
      SOURCE_AUTH_FAILED: 'AK 或 SK 无效，请检查后重试。',
      SOURCE_FORBIDDEN: '当前密钥无法访问所选身份的数据，请检查账号身份及权限。',
      SOURCE_ROLE_NOT_VERIFIED: '无法确认账号身份，请联系管理员检查账号角色。',
      SOURCE_IDENTITY_MISMATCH: '账号身份与上游返回的角色不一致。',
      SELF_SERVICE_CONNECTION_EXISTS: '该 AGIOne 账号已经连接。',
      credential_unavailable: '服务端尚未配置凭据加密密钥。'
    }[code] || '连接未完成，请检查密钥或稍后重试。'
  )
}
function open(item = null) {
  editing.value = item
  draft.platform = item?.platform || 'pro'
  draft.principalKind = ''
  clearSecrets()
  error.value = ''
  status.value = ''
  dialog.value?.showModal()
}
function close() {
  if (!busy.value) {
    clearSecrets()
    dialog.value?.close()
  }
}
async function save() {
  if (busy.value || !canSave.value) return
  if (editing.value && !draft.accessKey && !draft.secretKey) return close()
  busy.value = true
  error.value = ''
  status.value = ''
  try {
    const body = {
      platform: draft.platform,
      accessKey: draft.accessKey,
      secretKey: draft.secretKey
    }
    if (!editing.value) body.principalKind = draft.principalKind
    const response = editing.value
      ? await agioneOpsApi.updatePersonalConnection(editing.value.id, body)
      : await agioneOpsApi.createPersonalConnection(body)
    const connection = response?.data?.data
    if (!connection?.id) throw new Error('invalidResponse')
    const unverified = !editing.value && connection.roleVerified !== true
    status.value = editing.value
      ? '密钥已更新，连接验证通过。'
      : unverified
        ? '连接已创建，但账号身份未由上游确认。若选错，请在连接设置中断开后重新添加。'
        : '连接成功，正在自动采集数据。'
    clearSecrets()
    emit('changed', connection.id)
    if (!unverified) setTimeout(() => close(), 500)
  } catch (exc) {
    error.value = safeError(exc)
  } finally {
    busy.value = false
  }
}
async function disconnect() {
  if (!editing.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    await agioneOpsApi.disconnectPersonalConnection(editing.value.id)
    const id = editing.value.id
    busy.value = false
    close()
    emit('disconnected', id)
  } catch (exc) {
    error.value = safeError(exc)
    busy.value = false
  }
}
onBeforeUnmount(clearSecrets)
defineExpose({ open, close })
</script>

<style scoped>
.native-connection-dialog {
  width: min(470px, calc(100vw - 32px));
  max-height: calc(100dvh - 48px);
  border: 1px solid #dbe2ec;
  border-radius: 14px;
  padding: 0;
  color: #17233b;
  background: #fff;
  box-shadow: 0 20px 65px #15283f35;
}
.native-connection-dialog::backdrop {
  background: #15283f66;
}
.native-connection-dialog form {
  padding: 22px 24px 20px;
}
.native-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.native-heading h2 {
  margin: 0;
  font-size: 19px;
}
.native-heading p {
  margin: 5px 0 0;
  font-size: 12px;
  color: #75859d;
}
.native-heading button {
  border: 0;
  background: transparent;
  color: #75859d;
  font-size: 22px;
  padding: 0 4px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 14px;
  font-size: 13px;
  font-weight: 600;
}
input,
select {
  min-height: 42px;
  box-sizing: border-box;
  border: 1px solid #ccd6e4;
  border-radius: 7px;
  padding: 9px 11px;
  color: #17233b;
  background: #fff;
  font: inherit;
}
input:focus,
select:focus {
  outline: 2px solid #2563eb;
  outline-offset: 1px;
}
.native-status {
  border: 1px solid #dbe5f3;
  border-radius: 9px;
  overflow: hidden;
  margin-bottom: 18px;
}
.native-status > div {
  padding: 10px 12px;
  background: #f4f8ff;
  color: #16865a;
  font-size: 13px;
}
.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #1fbd78;
  margin-right: 8px;
}
.native-status dl {
  margin: 0;
}
.native-status dl div {
  display: grid;
  grid-template-columns: 100px 1fr;
  padding: 8px 12px;
  border-top: 1px solid #edf1f6;
  font-size: 12px;
}
.native-status dt {
  color: #75859d;
}
.native-status dd {
  margin: 0;
}
.native-section-title {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #e5eaf1;
  font-size: 14px;
  font-weight: 700;
}
.native-security {
  margin: 10px 0 0;
  color: #75859d;
  font-size: 12px;
}
.native-error,
.native-success {
  margin: 12px 0 0;
  padding: 9px 10px;
  border-radius: 7px;
  font-size: 12px;
}
.native-error {
  color: #b42318;
  background: #fff1f0;
}
.native-success {
  color: #087a4b;
  background: #ebfbf3;
}
.native-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 22px;
}
.native-spacer {
  flex: 1;
}
.native-footer button {
  min-height: 38px;
  padding: 8px 14px;
  border: 1px solid #ccd6e4;
  border-radius: 7px;
  background: #fff;
  color: #17233b;
}
.native-footer .primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}
.native-footer .danger {
  border-color: #f2b8b5;
  color: #c4322b;
}
.native-footer button:disabled {
  opacity: 0.55;
}
@media (max-width: 520px) {
  .native-connection-dialog form {
    padding: 18px 16px 16px;
  }
  .native-footer {
    flex-wrap: wrap;
  }
  .native-spacer {
    display: none;
    width: 100%;
  }
}
</style>

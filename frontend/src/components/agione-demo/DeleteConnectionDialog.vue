<template>
  <dialog ref="dialog" class="delete-connection-dialog" @close="$emit('close')" @cancel="cancel">
    <form @submit.prevent="$emit('confirm')">
      <header>
        <h2>删除连接？</h2>
        <button type="button" aria-label="关闭" :disabled="busy" @click="close">×</button>
      </header>
      <p>确定删除以下连接？</p>
      <div class="connection-name">{{ connectionName }}</div>
      <p class="description">{{ description }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <footer>
        <button type="button" :disabled="busy" @click="close">取消</button>
        <button type="submit" class="danger" :disabled="busy">{{ busy ? '正在删除…' : '确认删除' }}</button>
      </footer>
    </form>
  </dialog>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  connectionName: { type: String, required: true },
  description: { type: String, required: true },
  busy: { type: Boolean, default: false },
  error: { type: String, default: '' }
})
defineEmits(['confirm', 'close'])
const dialog = ref(null)
function open () { dialog.value?.showModal() }
function close () { dialog.value?.close() }
function cancel (event) { if (props.busy) event.preventDefault() }
defineExpose({ open, close })
</script>

<style scoped>
.delete-connection-dialog { width: min(420px, calc(100vw - 32px)); max-width: none; box-sizing: border-box; padding: 26px 28px; border: 0; border-radius: 12px; color: #1b304d; box-shadow: 0 24px 70px #0f1d3040; }
.delete-connection-dialog::backdrop { background: #11203573; }
header { display: flex; justify-content: space-between; align-items: center; }
h2 { margin: 0; font-size: 18px; }
header button { border: 0; background: transparent; color: #8b9ab0; font-size: 23px; cursor: pointer; }
p { margin: 20px 0 12px; color: #536985; font-size: 14px; line-height: 1.7; }
.connection-name { padding: 13px 14px; border-radius: 7px; background: #f2f5fa; font-size: 14px; font-weight: 600; }
p.description { margin: 14px 0 22px; color: #73869f; font-size: 13px; }
p.error { color: #c8303d; }
footer { display: flex; justify-content: flex-end; gap: 10px; }
footer button { padding: 9px 17px; border: 1px solid #dce3ee; border-radius: 6px; background: white; color: #253b59; cursor: pointer; }
footer .danger { border-color: #df4249; background: #df4249; color: white; font-weight: 600; }
button:disabled { opacity: .55; cursor: not-allowed; }
</style>

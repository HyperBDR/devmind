<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { Eraser, ImagePlus, PenLine, Trash2, Upload, X } from 'lucide-vue-next'
import {
  getUserSignatureGallery,
  removeUserSignatureFromGallery,
  rememberUserSignature,
} from '../utils/signatureStorage'
import { useQuotationI18n } from '../composables/useQuotationI18n'

const { t } = useQuotationI18n()

type SignatureMode = 'draw' | 'upload'

const props = withDefaults(
  defineProps<{
    modelValue?: string
    value?: string
    userEmail?: string
    className?: string
  }>(),
  {
    modelValue: undefined,
    value: '',
    className: '',
  },
)

const emit = defineEmits<{
  'update:modelValue': [dataUrl: string]
  change: [dataUrl: string]
}>()

function currentSignature() {
  return props.modelValue ?? props.value ?? ''
}

function emitSignature(dataUrl: string) {
  emit('update:modelValue', dataUrl)
  emit('change', dataUrl)
}

const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/jpg']
const MAX_FILE_SIZE_MB = 2
const MAX_IMAGE_WIDTH = 480
const CANVAS_HEIGHT = 120

const mode = ref<SignatureMode>('draw')
const gallery = ref<string[]>(getUserSignatureGallery(props.userEmail))
const error = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const isDrawing = ref(false)
const lastPoint = ref<{ x: number; y: number } | null>(null)
const hasInk = ref(false)

function readImageFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const img = new Image()
      img.onload = () => {
        const scale = Math.min(1, MAX_IMAGE_WIDTH / img.width)
        const width = Math.max(1, Math.floor(img.width * scale))
        const height = Math.max(1, Math.floor(img.height * scale))
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height

        const ctx = canvas.getContext('2d')
        if (!ctx) {
          reject(new Error(t('quotation.components.signature.errorProcessImage')))
          return
        }

        ctx.clearRect(0, 0, width, height)
        ctx.drawImage(img, 0, 0, width, height)
        resolve(canvas.toDataURL('image/png'))
      }
      img.onerror = () => reject(new Error(t('quotation.components.signature.errorReadImage')))
      img.src = String(reader.result)
    }
    reader.onerror = () => reject(new Error(t('quotation.components.signature.errorReadImage')))
    reader.readAsDataURL(file)
  })
}

function setupCanvasContext(canvas: HTMLCanvasElement) {
  const displayWidth = canvas.parentElement?.clientWidth || 320
  const ratio = window.devicePixelRatio || 1
  canvas.width = Math.floor(displayWidth * ratio)
  canvas.height = Math.floor(CANVAS_HEIGHT * ratio)
  canvas.style.width = `${displayWidth}px`
  canvas.style.height = `${CANVAS_HEIGHT}px`

  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  ctx.strokeStyle = '#0f172a'
  ctx.lineWidth = 2
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  return { ctx, displayWidth }
}

function drawImageOnCanvas(canvas: HTMLCanvasElement, dataUrl: string) {
  const setup = setupCanvasContext(canvas)
  if (!setup) return

  const { ctx, displayWidth } = setup
  const img = new Image()
  img.onload = () => {
    ctx.clearRect(0, 0, displayWidth, CANVAS_HEIGHT)
    ctx.drawImage(img, 0, 0, displayWidth, CANVAS_HEIGHT)
  }
  img.src = dataUrl
}

function persistSignature(dataUrl: string) {
  if (!props.userEmail) return
  rememberUserSignature(props.userEmail, dataUrl)
}

watch(
  () => props.userEmail,
  () => {
    gallery.value = getUserSignatureGallery(props.userEmail)
  },
)

watch(
  [mode, () => currentSignature()],
  async () => {
    if (mode.value !== 'draw') return
    await nextTick()
    const canvas = canvasRef.value
    if (!canvas) return

    const signature = currentSignature()
    if (signature) {
      drawImageOnCanvas(canvas, signature)
      hasInk.value = true
      return
    }

    const setup = setupCanvasContext(canvas)
    if (setup) {
      setup.ctx.clearRect(0, 0, setup.displayWidth, CANVAS_HEIGHT)
    }
    hasInk.value = false
  },
  { immediate: true },
)

onMounted(() => {
  gallery.value = getUserSignatureGallery(props.userEmail)
})

function handleClear() {
  emitSignature('')
  persistSignature('')
  error.value = ''

  if (mode.value === 'draw') {
    const canvas = canvasRef.value
    if (!canvas) return
    const setup = setupCanvasContext(canvas)
    if (setup) {
      setup.ctx.clearRect(0, 0, setup.displayWidth, CANVAS_HEIGHT)
    }
    hasInk.value = false
  }
}

function exportDrawnSignature() {
  const canvas = canvasRef.value
  if (!canvas || !hasInk.value) {
    emitSignature('')
    persistSignature('')
    return
  }

  const dataUrl = canvas.toDataURL('image/png')
  emitSignature(dataUrl)
  persistSignature(dataUrl)
  if (props.userEmail) {
    gallery.value = getUserSignatureGallery(props.userEmail)
  }
}

function getPoint(event: PointerEvent) {
  const canvas = canvasRef.value
  if (!canvas) return null
  const rect = canvas.getBoundingClientRect()
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

function handlePointerDown(event: PointerEvent) {
  const point = getPoint(event)
  if (!point) return

  isDrawing.value = true
  lastPoint.value = point
  ;(event.currentTarget as HTMLCanvasElement).setPointerCapture(event.pointerId)
}

function handlePointerMove(event: PointerEvent) {
  if (!isDrawing.value) return

  const canvas = canvasRef.value
  const point = getPoint(event)
  const prev = lastPoint.value
  if (!canvas || !point || !prev) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.beginPath()
  ctx.moveTo(prev.x, prev.y)
  ctx.lineTo(point.x, point.y)
  ctx.stroke()

  lastPoint.value = point
  hasInk.value = true
}

function finishDrawing(event: PointerEvent) {
  if (!isDrawing.value) return
  isDrawing.value = false
  lastPoint.value = null
  const target = event.currentTarget as HTMLCanvasElement
  if (target.hasPointerCapture(event.pointerId)) {
    target.releasePointerCapture(event.pointerId)
  }
  exportDrawnSignature()
}

async function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  if (!ACCEPTED_TYPES.includes(file.type)) {
    error.value = t('quotation.components.signature.errorInvalidType')
    return
  }

  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    error.value = t('quotation.components.signature.errorMaxSize', {
      size: MAX_FILE_SIZE_MB,
    })
    return
  }

  try {
    const dataUrl = await readImageFileAsDataUrl(file)
    emitSignature(dataUrl)
    if (props.userEmail) {
      gallery.value = rememberUserSignature(props.userEmail, dataUrl)
    }
    error.value = ''
  } catch {
    error.value = t('quotation.components.signature.errorUploadFailed')
  }
}

function handleSelect(dataUrl: string) {
  emitSignature(dataUrl)
  if (props.userEmail) {
    gallery.value = rememberUserSignature(props.userEmail, dataUrl)
  }
}

function handleRemoveFromGallery(dataUrl: string) {
  if (!props.userEmail) return
  const nextGallery = removeUserSignatureFromGallery(props.userEmail, dataUrl)
  gallery.value = nextGallery
  if (currentSignature() === dataUrl) {
    emitSignature(nextGallery[0] || '')
  }
}
</script>

<template>
  <div :class="className">
    <div class="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
      <button
        type="button"
        :class="`inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-semibold cursor-pointer ${
          mode === 'draw' ? 'bg-white text-blue-600 shadow-xs' : 'text-slate-600 hover:text-slate-800'
        }`"
        @click="mode = 'draw'"
      >
        <PenLine class="h-3.5 w-3.5" />
        {{ t('quotation.components.signature.modeDraw') }}
      </button>
      <button
        type="button"
        :class="`inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-semibold cursor-pointer ${
          mode === 'upload' ? 'bg-white text-blue-600 shadow-xs' : 'text-slate-600 hover:text-slate-800'
        }`"
        @click="mode = 'upload'"
      >
        <Upload class="h-3.5 w-3.5" />
        {{ t('quotation.components.signature.modeUpload') }}
      </button>
    </div>

    <div v-if="mode === 'draw'" class="mt-3">
      <div class="overflow-hidden rounded-lg border border-dashed border-slate-300 bg-white">
        <canvas
          ref="canvasRef"
          data-testid="signature-pad-canvas"
          class="block w-full cursor-crosshair touch-none bg-white"
          @pointerdown="handlePointerDown"
          @pointermove="handlePointerMove"
          @pointerup="finishDrawing"
          @pointerleave="finishDrawing"
        />
      </div>
      <div class="mt-2 flex items-center justify-between gap-2">
        <p class="text-xs font-medium text-slate-400">
          {{ t('quotation.components.signature.drawHint') }}
        </p>
        <button
          type="button"
          class="inline-flex cursor-pointer items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-600 hover:bg-slate-50"
          @click="handleClear"
        >
          <Eraser class="h-3.5 w-3.5" />
          {{ t('quotation.components.signature.clear') }}
        </button>
      </div>
    </div>

    <div v-else class="mt-3">
      <div
        class="flex min-h-[120px] items-center justify-center overflow-hidden rounded-lg border border-dashed border-slate-300 bg-white p-4"
      >
        <div v-if="currentSignature()" class="flex flex-col items-center gap-2">
          <img
            :src="currentSignature()"
            alt="Selected signature"
            data-testid="signature-image-preview"
            class="max-h-24 max-w-full object-contain"
          />
          <button
            type="button"
            class="inline-flex cursor-pointer items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            @click="fileInputRef?.click()"
          >
            <Upload class="h-3.5 w-3.5" />
            {{ t('quotation.components.signature.reupload') }}
          </button>
        </div>
        <div v-else class="flex flex-col items-center gap-2 text-slate-400">
          <ImagePlus class="h-8 w-8" />
          <p class="text-xs font-medium">{{ t('quotation.components.signature.uploadPrompt') }}</p>
          <button
            type="button"
            class="inline-flex cursor-pointer items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            @click="fileInputRef?.click()"
          >
            <Upload class="h-3.5 w-3.5" />
            {{ t('quotation.components.signature.uploadButton') }}
          </button>
        </div>
      </div>

      <div class="mt-2 flex flex-wrap items-center gap-2">
        <button
          v-if="currentSignature()"
          type="button"
          class="inline-flex cursor-pointer items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
          @click="handleClear"
        >
          <X class="h-3.5 w-3.5" />
          {{ t('quotation.components.signature.clearCurrent') }}
        </button>
        <input
          ref="fileInputRef"
          type="file"
          accept="image/png,image/jpeg"
          class="hidden"
          @change="handleFileChange"
        />
      </div>

      <p v-if="error" class="mt-2 text-xs text-red-500">{{ error }}</p>

      <div v-if="gallery.length > 0" class="mt-3 space-y-2">
        <p class="text-xs font-semibold text-slate-500">{{ t('quotation.components.signature.galleryTitle') }}</p>
        <div class="flex flex-wrap gap-2">
          <div
            v-for="(item, index) in gallery"
            :key="`${item.slice(0, 24)}-${index}`"
            class="relative"
          >
            <button
              type="button"
              :class="`h-16 w-24 cursor-pointer rounded-md border bg-white p-1 hover:border-blue-400 ${
                currentSignature() === item ? 'border-blue-500 ring-2 ring-blue-100' : 'border-slate-200'
              }`"
              @click="handleSelect(item)"
            >
              <img
                :src="item"
                :alt="`Saved signature ${index + 1}`"
                class="h-full w-full object-contain"
              />
            </button>
            <button
              type="button"
              class="absolute -right-1 -top-1 cursor-pointer rounded-full border border-slate-200 bg-white p-0.5 text-slate-500 hover:text-red-500"
              :aria-label="t('quotation.components.signature.deleteAriaLabel')"
              @click="handleRemoveFromGallery(item)"
            >
              <Trash2 class="h-3 w-3" />
            </button>
          </div>
        </div>
      </div>

      <p class="mt-2 text-xs font-medium text-slate-400">
        {{ t('quotation.components.signature.uploadHint') }}
      </p>
    </div>
  </div>
</template>

import { onBeforeUnmount, onMounted, type Ref } from 'vue'

/** Bind click-outside close behavior to an existing element ref (use with template ref="..."). */
export function bindClickOutside(containerRef: Ref<HTMLElement | null>, onClose: () => void) {
  const handlePointerDown = (event: MouseEvent) => {
    if (!containerRef.value?.contains(event.target as Node)) {
      onClose()
    }
  }

  onMounted(() => {
    document.addEventListener('mousedown', handlePointerDown)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('mousedown', handlePointerDown)
  })
}

/** @deprecated prefer bindClickOutside with a template ref */
export function useClickOutside(onClose: () => void) {
  // kept for DropdownMenu re-export compatibility; callers should use bindClickOutside
  void onClose
  return { value: null } as Ref<HTMLElement | null>
}

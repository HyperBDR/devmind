import { computed, onBeforeUnmount, ref } from 'vue'

export function useResizableSidebar({
  cssVariable = '--sidebar-width',
  initialWidth = 380,
  maxWidth = 560,
  minWidth = 340
} = {}) {
  const sidebarWidth = ref(initialWidth)
  const isResizingSidebar = ref(false)
  const resizeStartX = ref(0)
  const resizeStartWidth = ref(0)

  const gridStyle = computed(() => ({
    [cssVariable]: `${sidebarWidth.value}px`
  }))

  function clampSidebarWidth(width) {
    return Math.min(maxWidth, Math.max(minWidth, Math.round(width)))
  }

  function stopSidebarResize() {
    if (!isResizingSidebar.value) return
    isResizingSidebar.value = false
    document.removeEventListener('pointermove', handleSidebarResize)
    document.removeEventListener('pointerup', stopSidebarResize)
  }

  function handleSidebarResize(event) {
    if (!isResizingSidebar.value) return
    const delta = event.clientX - resizeStartX.value
    sidebarWidth.value = clampSidebarWidth(resizeStartWidth.value + delta)
  }

  function startSidebarResize(event) {
    if (!event?.isPrimary) return
    event.preventDefault()
    isResizingSidebar.value = true
    resizeStartX.value = event.clientX
    resizeStartWidth.value = sidebarWidth.value
    document.addEventListener('pointermove', handleSidebarResize)
    document.addEventListener('pointerup', stopSidebarResize)
  }

  onBeforeUnmount(() => {
    stopSidebarResize()
  })

  return {
    gridStyle,
    isResizingSidebar,
    sidebarWidth,
    startSidebarResize,
    stopSidebarResize
  }
}

const activeDrawers = new Set()

export function isDialogBackdropPointer(event) {
  const dialog = event.currentTarget
  if (!dialog?.open || event.target !== dialog) return false
  if (!Number.isFinite(event.clientX) || !Number.isFinite(event.clientY)) {
    return false
  }
  const rect = dialog.getBoundingClientRect()
  return event.clientX < rect.left || event.clientX >= rect.right ||
    event.clientY < rect.top || event.clientY >= rect.bottom
}

export function createDialogBackdropDismiss(dismiss) {
  let pressedDialog = null
  function reset() { pressedDialog = null }
  function onPointerDown(event) {
    pressedDialog = event.isPrimary !== false &&
      (event.button == null || event.button === 0) &&
      isDialogBackdropPointer(event) ? event.currentTarget : null
  }
  function onClick(event) {
    const shouldDismiss = pressedDialog === event.currentTarget &&
      isDialogBackdropPointer(event)
    reset()
    if (!shouldDismiss) return
    event.preventDefault()
    dismiss()
  }
  return { onPointerDown, onClick, reset }
}

export function releaseOriginalDialog(dialog, {force=false} = {}) {
  if (!dialog || (dialog.open && !force)) return
  activeDrawers.delete(dialog)
  if (![...activeDrawers].some(node=>node.ownerDocument===dialog.ownerDocument)) dialog.ownerDocument?.documentElement?.classList.remove('agione-drawer-open')
  dialog.id = dialog.dataset.agioneDialogId || 'agione-inactive-dialog'
  const body = dialog.querySelector('[data-agione-dialog-body]')
  if (body) body.id = `${dialog.id}-body`
}

export function claimOriginalDialog(dialog) {
  if (!dialog) return
  const root = dialog.closest('.agione-demo')
  for (const previous of root?.querySelectorAll('dialog#dialog') || []) {
    if (previous === dialog) continue
    if (previous.open) previous.close()
    releaseOriginalDialog(previous)
  }
  dialog.id = 'dialog'
  if(dialog.classList.contains('request-drawer')){ activeDrawers.add(dialog); dialog.ownerDocument?.documentElement?.classList.add('agione-drawer-open') }
  const body = dialog.querySelector('[data-agione-dialog-body]')
  if (body) body.id = 'dialogBody'
}

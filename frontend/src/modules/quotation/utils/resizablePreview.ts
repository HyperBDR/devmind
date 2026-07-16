export const MIN_PREVIEW_WIDTH_PERCENT = 42;
export const MAX_PREVIEW_WIDTH_PERCENT = 78;
export const DEFAULT_PREVIEW_WIDTH_PERCENT = 58;

export function clampPreviewWidthPercent(value: number): number {
  return Math.min(MAX_PREVIEW_WIDTH_PERCENT, Math.max(MIN_PREVIEW_WIDTH_PERCENT, Math.round(value)));
}

export function getPreviewWidthPercentFromPointer({
  containerLeft,
  containerWidth,
  pointerClientX,
}: {
  containerLeft: number;
  containerWidth: number;
  pointerClientX: number;
}): number {
  if (containerWidth <= 0) return clampPreviewWidthPercent(DEFAULT_PREVIEW_WIDTH_PERCENT);
  const leftWidthPercent = ((pointerClientX - containerLeft) / containerWidth) * 100;
  return clampPreviewWidthPercent(100 - leftWidthPercent);
}

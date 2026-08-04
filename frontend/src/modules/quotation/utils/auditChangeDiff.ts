export type AuditDiffLineKind = 'context' | 'removed' | 'added'

export interface AuditDiffLine {
  kind: AuditDiffLineKind
  text: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value)
  )
}

function jsonLines(value: unknown): string[] {
  const normalized =
    value === undefined || value === '' ? null : value
  try {
    return (JSON.stringify(normalized, null, 2) ?? 'null').split('\n')
  } catch {
    return ['null']
  }
}

function diffJsonLines(
  oldLines: string[],
  newLines: string[],
): AuditDiffLine[] {
  const lengths = Array.from(
    { length: oldLines.length + 1 },
    () => Array<number>(newLines.length + 1).fill(0),
  )

  for (let oldIndex = oldLines.length - 1; oldIndex >= 0; oldIndex -= 1) {
    for (
      let newIndex = newLines.length - 1;
      newIndex >= 0;
      newIndex -= 1
    ) {
      lengths[oldIndex][newIndex] =
        oldLines[oldIndex] === newLines[newIndex]
          ? lengths[oldIndex + 1][newIndex + 1] + 1
          : Math.max(
              lengths[oldIndex + 1][newIndex],
              lengths[oldIndex][newIndex + 1],
            )
    }
  }

  const lines: AuditDiffLine[] = []
  let oldIndex = 0
  let newIndex = 0
  while (
    oldIndex < oldLines.length ||
    newIndex < newLines.length
  ) {
    if (
      oldIndex < oldLines.length &&
      newIndex < newLines.length &&
      oldLines[oldIndex] === newLines[newIndex]
    ) {
      lines.push({
        kind: 'context',
        text: oldLines[oldIndex],
      })
      oldIndex += 1
      newIndex += 1
      continue
    }
    if (
      oldIndex < oldLines.length &&
      (
        newIndex >= newLines.length ||
        lengths[oldIndex + 1][newIndex] >=
          lengths[oldIndex][newIndex + 1]
      )
    ) {
      lines.push({
        kind: 'removed',
        text: oldLines[oldIndex],
      })
      oldIndex += 1
      continue
    }
    lines.push({
      kind: 'added',
      text: newLines[newIndex],
    })
    newIndex += 1
  }
  return lines
}

export function buildAuditChangeLines(
  value: unknown,
): AuditDiffLine[] {
  if (
    !isRecord(value) ||
    !Object.prototype.hasOwnProperty.call(value, 'old') ||
    !Object.prototype.hasOwnProperty.call(value, 'new')
  ) {
    return jsonLines(value).map((text) => ({
      kind: 'context',
      text,
    }))
  }

  return diffJsonLines(
    jsonLines(value.old),
    jsonLines(value.new),
  )
}

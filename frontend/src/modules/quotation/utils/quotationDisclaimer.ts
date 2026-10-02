// Keep these A4 renderer measurements in sync with export_renderer.py.
const A4_PAGE_WIDTH_POINTS = 595
const A4_SIDE_MARGINS_INCHES = 0.75
const POINTS_PER_INCH = 72
const DISCLAIMER_FONT_SIZE_POINTS = 6.75
const AVERAGE_GLYPH_WIDTH = 0.45

const disclaimerWrapWidth =
  (A4_PAGE_WIDTH_POINTS - 2 * A4_SIDE_MARGINS_INCHES * POINTS_PER_INCH) /
  (DISCLAIMER_FONT_SIZE_POINTS * AVERAGE_GLYPH_WIDTH)

function isWideCharacter(char: string): boolean {
  const code = char.codePointAt(0) || 0
  return (
    code > 0xffff ||
    (code >= 0x1100 && code <= 0x115f) ||
    code === 0x2329 ||
    code === 0x232a ||
    (code >= 0x2e80 && code <= 0xa4cf) ||
    (code >= 0xac00 && code <= 0xd7a3) ||
    (code >= 0xf900 && code <= 0xfaff) ||
    (code >= 0xfe10 && code <= 0xfe6f) ||
    (code >= 0xff01 && code <= 0xff60) ||
    (code >= 0xffe0 && code <= 0xffe6)
  )
}

function wrapLine(line: string): string[] {
  const chars = Array.from(line)
  const wrapped: string[] = []
  let start = 0

  while (start < chars.length) {
    let end = start
    let lastSpace = -1
    let usedWidth = 0

    while (end < chars.length) {
      const char = chars[end]
      const charWidth = isWideCharacter(char) ? 2.25 : 1
      if (usedWidth + charWidth > disclaimerWrapWidth) break
      usedWidth += charWidth
      end += 1
      if (/\s/u.test(char)) lastSpace = end
    }

    if (end === chars.length) {
      wrapped.push(chars.slice(start, end).join(''))
      break
    }

    if (lastSpace > start) end = lastSpace
    wrapped.push(chars.slice(start, end).join(''))
    start = end
  }

  return wrapped.length ? wrapped : ['']
}

export function wrapQuotationDisclaimer(value: string): string {
  return value
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .split('\n')
    .flatMap(wrapLine)
    .join('\n')
}

/**
 * Generate favicon PNGs and ICO from your existing logo with transparent background.
 * Does NOT replace your logo design - only resizes and ensures transparency.
 *
 * Put your logo in one of:
 *   - public/logo-source.svg
 *   - public/logo-source.png
 * Then run: npm run generate-favicons
 *
 * If logo-source.png has white background, white will be converted to transparent.
 */

import sharp from 'sharp'
import toIco from 'to-ico'
import { readFileSync, writeFileSync, existsSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const publicDir = join(__dirname, '..', 'public')

const LOGO_SVG = join(publicDir, 'logo-source.svg')
const LOGO_PNG = join(publicDir, 'logo-source.png')

const sizes = [
  { name: 'favicon-16x16.png', size: 16 },
  { name: 'favicon-32x32.png', size: 32 },
  { name: 'apple-touch-icon.png', size: 180 },
  { name: 'android-chrome-192x192.png', size: 192 },
  { name: 'android-chrome-512x512.png', size: 512 }
]

function getLogoSource() {
  if (existsSync(LOGO_SVG)) return { path: LOGO_SVG, type: 'svg' }
  if (existsSync(LOGO_PNG)) return { path: LOGO_PNG, type: 'png' }
  console.error(
    'No logo source found. Please add your logo as:\n  - public/logo-source.svg\n  - or public/logo-source.png\nThen run: npm run generate-favicons'
  )
  process.exit(1)
}

/**
 * For PNG with white background: set white pixels to transparent.
 */
async function ensureTransparentPng(inputPath) {
  const { data, info } = await sharp(inputPath)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true })
  const threshold = 250
  for (let i = 0; i < data.length; i += 4) {
    if (
      data[i] >= threshold &&
      data[i + 1] >= threshold &&
      data[i + 2] >= threshold
    ) {
      data[i + 3] = 0
    }
  }
  return sharp(data, { raw: info }).png()
}

async function main() {
  const { path: logoPath, type } = getLogoSource()
  const isSvg = type === 'svg'

  let pipeline
  if (isSvg) {
    const svgBuffer = readFileSync(logoPath)
    pipeline = sharp(svgBuffer)
  } else {
    pipeline = await ensureTransparentPng(logoPath)
  }

  const meta = await pipeline.metadata()
  const w = meta.width || 1
  const h = meta.height || 1
  const cropRatio = 0.55
  const cropW = Math.round(w * cropRatio)
  const cropH = Math.round(h * cropRatio)
  const left = Math.round((w - cropW) / 2)
  const top = Math.round((h - cropH) / 2)
  const cropped = pipeline
    .clone()
    .extract({ left, top, width: cropW, height: cropH })

  const png16 = await cropped.clone().resize(16, 16).png().toBuffer()
  const png32 = await cropped.clone().resize(32, 32).png().toBuffer()

  for (const { name, size } of sizes) {
    const buf = await cropped.clone().resize(size, size).png().toBuffer()
    writeFileSync(join(publicDir, name), buf)
    console.log('Written:', name)
  }

  const icoBuffer = await toIco([png16, png32])
  writeFileSync(join(publicDir, 'favicon.ico'), icoBuffer)
  console.log('Written: favicon.ico')

  if (isSvg) {
    writeFileSync(join(publicDir, 'favicon.svg'), readFileSync(logoPath))
    console.log('Written: favicon.svg (from your logo)')
  }
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})

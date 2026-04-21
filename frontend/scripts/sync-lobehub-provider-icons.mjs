import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const projectRoot = path.resolve(__dirname, '..')

const iconSourceDir = path.join(
  projectRoot,
  'node_modules',
  '@lobehub',
  'icons-static-svg',
  'icons'
)
const iconTargetDir = path.join(
  projectRoot,
  'src',
  'assets',
  'provider-icons',
  'lobehub'
)
const manifestPath = path.join(
  projectRoot,
  'src',
  'assets',
  'provider-icons',
  'lobehub-provider-manifest.json'
)

const iconAliasByProvider = {
  fireworksai: 'fireworks',
  infiniai: 'infinigence',
  ollamacloud: 'ollama',
  taichu: 'aimass',
  togetherai: 'together',
  v0: 'vercel',
  vercelaigateway: 'vercel'
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
}

function readProviderIds() {
  if (fs.existsSync(manifestPath)) {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
    return Object.keys(manifest).sort((a, b) => a.localeCompare(b))
  }

  if (fs.existsSync(iconTargetDir)) {
    return fs
      .readdirSync(iconTargetDir)
      .filter((fileName) => fileName.endsWith('.svg'))
      .map((fileName) => fileName.replace(/\.svg$/, ''))
      .sort((a, b) => a.localeCompare(b))
  }

  throw new Error(
    'No provider seed found. Ensure lobehub-provider-manifest.json exists.'
  )
}

function pickSourceIcon(providerId) {
  const slug = iconAliasByProvider[providerId] || providerId
  const colorPath = path.join(iconSourceDir, `${slug}-color.svg`)
  const plainPath = path.join(iconSourceDir, `${slug}.svg`)

  if (fs.existsSync(colorPath)) {
    return {
      exists: true,
      sourcePath: colorPath,
      sourceSlug: `${slug}-color`
    }
  }

  if (fs.existsSync(plainPath)) {
    return {
      exists: true,
      sourcePath: plainPath,
      sourceSlug: slug
    }
  }

  return {
    exists: false,
    sourcePath: null,
    sourceSlug: slug
  }
}

function cleanupOldFiles(validNames) {
  if (!fs.existsSync(iconTargetDir)) return
  const files = fs.readdirSync(iconTargetDir)

  for (const file of files) {
    if (!file.endsWith('.svg')) continue
    if (validNames.has(file)) continue
    fs.rmSync(path.join(iconTargetDir, file))
  }
}

function syncProviderIcons() {
  ensureDir(iconTargetDir)

  const providerIds = readProviderIds()
  const manifest = {}
  const validFileNames = new Set()

  for (const providerId of providerIds) {
    const picked = pickSourceIcon(providerId)
    manifest[providerId] = {
      found: picked.exists,
      source: picked.sourceSlug
    }

    if (!picked.exists) continue

    const targetFileName = `${providerId}.svg`
    const targetPath = path.join(iconTargetDir, targetFileName)
    fs.copyFileSync(picked.sourcePath, targetPath)
    validFileNames.add(targetFileName)
  }

  cleanupOldFiles(validFileNames)
  fs.writeFileSync(
    manifestPath,
    JSON.stringify(manifest, null, 2) + '\n',
    'utf8'
  )

  const total = providerIds.length
  const found = Object.values(manifest).filter((item) => item.found).length
  const missing = total - found

  console.log(`Synced provider icons: ${found}/${total}`)
  console.log(`Missing provider icons: ${missing}`)

  if (missing > 0) {
    const missingIds = providerIds.filter((id) => !manifest[id].found)
    console.log(`Missing list: ${missingIds.join(', ')}`)
  }
}

syncProviderIcons()

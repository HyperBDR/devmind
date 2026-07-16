export function resolveAssistantQuestionGroups(profileGroups, localizedGroups) {
  const sourceGroups = Array.isArray(profileGroups) ? profileGroups : []
  const translations = localizedGroups || {}
  const keys = sourceGroups.length
    ? sourceGroups.map((group) => group?.key).filter(Boolean)
    : Object.keys(translations)

  return keys
    .map((key) => {
      const source = sourceGroups.find((group) => group?.key === key) || {}
      const localized = translations[key]
      return {
        key,
        title: localized?.title || source.title || key,
        questions: localized?.questions || source.questions || []
      }
    })
    .filter((group) => group.questions.length > 0)
}

export function resolveQuickPromptLimit(value, fallback = 6) {
  const normalized = Number(value)
  if (!Number.isInteger(normalized) || normalized < 1) return fallback
  return Math.min(normalized, 12)
}

export function buildQuickPrompts(groups, limit = 6) {
  const availableGroups = Array.isArray(groups) ? groups : []
  const promptLimit = Math.max(0, Number(limit) || 0)
  const maxQuestions = Math.max(
    0,
    ...availableGroups.map((group) => group?.questions?.length || 0)
  )
  const prompts = []

  for (let index = 0; index < maxQuestions; index += 1) {
    for (const group of availableGroups) {
      const question = group?.questions?.[index]
      if (!question) continue
      prompts.push({
        groupKey: group.key,
        groupTitle: group.title,
        question
      })
      if (prompts.length === promptLimit) return prompts
    }
  }
  return prompts
}

export function splitFollowUpQuestions(value) {
  const text = String(value || '').trim()
  const markerMatch = text.match(
    /(需要我(?:进一步|继续|再)|你可以继续问|可以继续追问|建议追问|suggested follow-up questions?|follow-up questions?|you can (?:also )?(?:ask|continue with))[：:]\s*/imu
  )
  if (!markerMatch) return { body: text, questions: [] }

  const markerIndex = markerMatch.index
  const body = text.slice(0, markerIndex).trim()
  const tail = text.slice(markerIndex + markerMatch[0].length).trim()
  const questions = extractFollowUpQuestions(tail)
  if (!questions.length) return { body: text, questions: [] }
  return { body, questions }
}

function extractFollowUpQuestions(value) {
  const lines = String(value || '')
    .split(/\n+/u)
    .map((line) => normalizeFollowUpLine(line))
    .filter(Boolean)
  const candidates = lines.length
    ? lines
    : String(value || '').match(/[^？?。.!！]+[？?]/gu) || []
  return [...new Set(candidates.map((item) => cleanFollowUpText(item)))]
    .filter((item) => item.length >= 6)
    .slice(0, 3)
}

function normalizeFollowUpLine(line) {
  const value = String(line || '').trim()
  if (!value) return ''
  return value.replace(/^[-*+]\s+/u, '').replace(/^\d+[.)、]\s*/u, '')
}

function cleanFollowUpText(value) {
  return String(value || '')
    .replace(/\*\*/gu, '')
    .replace(/[`*_]/gu, '')
    .replace(/\s+/gu, ' ')
    .trim()
}

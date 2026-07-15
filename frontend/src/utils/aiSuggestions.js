const groupMatchers = [
  {
    key: 'data_quality',
    pattern:
      /同步|数据质量|权限|字段缺失|可信|抓取|sync|data quality|permission|missing field|reliab/iu
  },
  {
    key: 'pipeline',
    pattern: /pipeline|立项|转化|高潜|停滞|conversion|opportunit|stalled/iu
  },
  {
    key: 'oversea',
    pattern:
      /海外|license|国家|产品类型|利润|结算|overseas|country|product type|margin|settlement/iu
  },
  {
    key: 'cash_risk',
    pattern:
      /回款|待回款|催收|合同|续约|到期|collection|receivable|contract|renewal|expir/iu
  }
]

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

export function selectFollowUpQuestions(question, groups, limit = 3) {
  const availableGroups = Array.isArray(groups) ? groups : []
  if (!availableGroups.length) return []

  const source = String(question || '').trim()
  const matchedKey = groupMatchers.find((item) =>
    item.pattern.test(source)
  )?.key
  const selectedGroup =
    availableGroups.find((group) => group.key === matchedKey) ||
    availableGroups.find((group) => group.key === 'daily_review') ||
    availableGroups[0]

  return [...new Set(selectedGroup?.questions || [])]
    .filter((item) => String(item || '').trim())
    .filter((item) => String(item).trim() !== source)
    .slice(0, Math.max(0, Number(limit) || 0))
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

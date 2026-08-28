export type SpellIssueKind = 'english' | 'chinese'

export interface SpellIssue {
  kind: SpellIssueKind
  word: string
  suggestion: string
  start: number
  end: number
}

const ENGLISH_REPLACEMENTS: Record<string, string> = {
  accomodate: 'accommodate',
  adress: 'address',
  availble: 'available',
  calender: 'calendar',
  definately: 'definitely',
  enviroment: 'environment',
  occured: 'occurred',
  paramter: 'parameter',
  pleas: 'please',
  reciever: 'receiver',
  recieve: 'receive',
  seperate: 'separate',
  servce: 'service',
  succesful: 'successful',
  sucess: 'success',
  teh: 'the',
  untill: 'until',
  wierd: 'weird',
  widht: 'width',
  montly: 'monthly',
}

const CHINESE_REPLACEMENTS: Record<string, string> = {
  帐单: '账单',
  帐号: '账号',
  配制: '配置',
  测試: '测试',
  其她: '其他',
  其它: '其他',
  部份: '部分',
  恢愎: '恢复',
  连系: '联系',
  合拼: '合并',
  数剧: '数据',
  信启: '信息',
}

const TERM_EXCLUSIONS = new Set([
  'agione',
  'alibaba',
  'deepseek',
  'feishu',
  'hyperbdr',
  'openai',
  'onepro',
])

function isExcludedTerm(word: string): boolean {
  return TERM_EXCLUSIONS.has(word.toLowerCase())
}

function collectIssues(
  text: string,
  replacements: Record<string, string>,
  kind: SpellIssueKind,
  pattern: RegExp,
): SpellIssue[] {
  const issues: SpellIssue[] = []
  for (const match of text.matchAll(pattern)) {
    const word = match[0]
    const start = match.index ?? 0
    const key = word.toLowerCase()
    const suggestion = replacements[key] || replacements[word]
    if (!suggestion || isExcludedTerm(word)) continue
    issues.push({
      kind,
      word,
      suggestion,
      start,
      end: start + word.length,
    })
  }
  return issues
}

export function checkSpelling(text: string): SpellIssue[] {
  if (!text.trim()) return []
  const englishIssues = collectIssues(
    text,
    ENGLISH_REPLACEMENTS,
    'english',
    /[A-Za-z][A-Za-z'-]*/g,
  )
  const chineseIssues: SpellIssue[] = []
  for (const [word, suggestion] of Object.entries(CHINESE_REPLACEMENTS)) {
    let start = text.indexOf(word)
    while (start >= 0) {
      chineseIssues.push({
        kind: 'chinese',
        word,
        suggestion,
        start,
        end: start + word.length,
      })
      start = text.indexOf(word, start + word.length)
    }
  }
  return [...englishIssues, ...chineseIssues].sort(
    (left, right) => left.start - right.start,
  )
}

export function replaceSpellIssue(text: string, issue: SpellIssue): string {
  const currentStart = text.indexOf(issue.word)
  const start = currentStart >= 0 ? currentStart : issue.start
  const suggestion =
    issue.word[0] && issue.word[0] === issue.word[0].toUpperCase()
      ? issue.suggestion[0].toUpperCase() + issue.suggestion.slice(1)
      : issue.suggestion
  const end = start + issue.word.length
  return `${text.slice(0, start)}${suggestion}${text.slice(end)}`
}

const REVIEW_DIMENSION_LABELS: Record<string, string> = {
  opening_strength: '开局强度',
  first_coolpoint_timing: '首个爽点时机',
  hook_chain: '章末钩子链',
  volume_escalation: '分卷升级梯度',
  foreshadowing_payoff: '伏笔兑现',
  anticipation_delivery: '期待感兑现',
  toxic_recheck: '毒点复查',
  hook: '开篇钩子',
  coolpoint_density: '爽点密度',
  conflict_sustain: '冲突可持续性',
  character_want: '人物欲望',
  golden_finger: '金手指设计',
  foreshadow: '伏笔设计',
  volume_rhythm: '分卷节奏',
}

const SETTING_LABELS: Record<string, string> = {
  title: '书名',
  one_sentence_summary: '一句话梗概',
  full_synopsis: '完整梗概',
  world_setting: '世界观设定',
  golden_finger: '金手指设定',
  characters: '人物设定',
  relationships: '人物关系',
  volumes: '分卷规划',
  foreshadowings: '伏笔规划',
  chapter_outline: '章节规划',
}

const TECHNICAL_TERMS: Array<[RegExp, string]> = [
  [/\bfirst_coolpoint_timing\b/gi, '首个爽点时机'],
  [/\bforeshadowing_payoff\b/gi, '伏笔兑现'],
  [/\banticipation_delivery\b/gi, '期待感兑现'],
  [/\bopening_strength\b/gi, '开局强度'],
  [/\bvolume_escalation\b/gi, '分卷升级梯度'],
  [/\btoxic_recheck\b/gi, '毒点复查'],
  [/\bhook_chain\b/gi, '章末钩子链'],
  [/\bone_sentence_summary\b/gi, '一句话梗概'],
  [/\bforeshadowing_ops\b/gi, '伏笔操作'],
  [/\bchapter_function\b/gi, '章节功能'],
  [/\bfull_synopsis\b/gi, '完整梗概'],
  [/\bworld_setting\b/gi, '世界观设定'],
  [/\bgolden_finger\b/gi, '金手指设定'],
  [/\bclimax_hint\b/gi, '卷末高潮'],
  [/\barc_goal\b/gi, '卷目标'],
  [/\bhook_type\b/gi, '钩子类型'],
  [/\bdimension_scores\b/gi, '各项评分'],
  [/\btotal_score\b/gi, '总分'],
  [/\bfix_hint\b/gi, '修订方向'],
  [/\bforeshadowings\b/gi, '伏笔规划'],
  [/\bcharacters\b/gi, '人物设定'],
  [/\bvolumes\b/gi, '分卷规划'],
  [/\bchapters\b/gi, '章节规划'],
  [/\bsettings\b/gi, '设定'],
  [/\bcoolpoint\b/gi, '爽点'],
  [/\bsummary\b/gi, '章节摘要'],
  [/\bpayoff\b/gi, '兑现'],
  [/\bplant\b/gi, '埋设'],
  [/\bclimax\b/gi, '高潮'],
  [/\bhook\b/gi, '钩子'],
  [/\barc\b/gi, '故事弧'],
  [/\bKPI\b/g, '关键指标'],
  [/\bSchema\b/gi, '数据格式'],
  [/\bJSON\b/g, '结构化数据'],
  [/\bAI\b/g, '人工智能'],
]

function formatChapterRange(startText: string, endText?: string): string {
  const start = Number(startText)
  const end = Number(endText || startText)
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start) {
    return '章节规划'
  }
  return start === end ? `第${start}章` : `第${start}—${end}章`
}

export function reviewDimensionLabel(key?: string): string {
  const normalized = (key || '').trim()
  if (!normalized) return '其他指标'
  if (REVIEW_DIMENSION_LABELS[normalized]) return REVIEW_DIMENSION_LABELS[normalized]
  if (/[^\x00-\x7f]/.test(normalized)) return normalized
  return '其他指标'
}

export function formatReviewTarget(target?: string): string {
  const normalized = (target || '').trim()
  if (!normalized) return '整体蓝图'

  const chapterMatch = normalized.match(/^chapters:(\d+)(?:-(\d+))?$/i)
  if (chapterMatch) return formatChapterRange(chapterMatch[1], chapterMatch[2])

  const settingMatch = normalized.match(/^settings:([a-z0-9_]+)$/i)
  if (settingMatch) return `设定：${SETTING_LABELS[settingMatch[1]] || '其他设定项'}`

  if (/^(global|blueprint|overall)$/i.test(normalized)) return '整体蓝图'
  return localizeReviewText(normalized)
}

export function localizeReviewText(text?: string): string {
  if (!text) return ''
  let localized = String(text)

  localized = localized.replace(
    /(?:第[一二三四五六七八九十百\d]+卷\s*)?volumes\[(\d+)\]\.arc_goal\b/gi,
    (_, index: string) => `第${Number(index) + 1}卷的卷目标`,
  )
  localized = localized.replace(
    /(?:第[一二三四五六七八九十百\d]+卷\s*)?volumes\[(\d+)\]\.climax_hint\b/gi,
    (_, index: string) => `第${Number(index) + 1}卷的卷末高潮`,
  )
  localized = localized.replace(
    /第([一二三四五六七八九十百\d]+)卷\s*arc_goal\b/gi,
    '第$1卷的卷目标',
  )
  localized = localized.replace(
    /第([一二三四五六七八九十百\d]+)卷\s*climax_hint\b/gi,
    '第$1卷的卷末高潮',
  )
  localized = localized.replace(
    /\bchapters:(\d+)(?:-(\d+))?\b/gi,
    (_, start: string, end?: string) => formatChapterRange(start, end),
  )
  localized = localized.replace(
    /\bsettings:([a-z0-9_]+)\b/gi,
    (_, key: string) => `设定：${SETTING_LABELS[key] || '其他设定项'}`,
  )

  for (const [pattern, replacement] of TECHNICAL_TERMS) {
    localized = localized.replace(pattern, replacement)
  }

  // 审稿模型偶尔会输出未登记的 snake_case 字段；产品界面不应暴露内部字段名。
  return localized.replace(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/gi, '对应字段')
}

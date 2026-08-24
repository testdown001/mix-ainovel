// AIMETA P=写作台章节轨状态语义|R=统一章纲与正文状态标签|NR=不含状态持久化|E=resolveChapterRailStatus|X=internal|A=纯函数|D=ts|S=none|RD=./README.ai
import type { Chapter } from '@/api/novel'

export type ChapterRailStatusKind =
  | 'done'
  | 'working'
  | 'confirm'
  | 'failed'
  | 'predicted'
  | 'planned'

export interface ChapterRailStatus {
  kind: ChapterRailStatusKind
  label: string
}

interface ChapterRailStatusInput {
  generationStatus?: Chapter['generation_status']
  generating?: boolean
  evaluating?: boolean
  hasPrediction?: boolean
}

/**
 * 章纲和正文是两个不同完成层级：有章纲表示“已规划”，只有正文选版完成才是“已完成”。
 * 所有章节轨文案从这里解释，避免把完成态误写成“规划中”。
 */
export function resolveChapterRailStatus({
  generationStatus,
  generating = false,
  evaluating = false,
  hasPrediction = false,
}: ChapterRailStatusInput): ChapterRailStatus {
  if (generationStatus === 'successful') return { kind: 'done', label: '已完成' }

  if (generating || generationStatus === 'generating') {
    return { kind: 'working', label: '生成中' }
  }
  if (evaluating || generationStatus === 'evaluating') {
    return { kind: 'working', label: '评审中' }
  }
  if (generationStatus === 'selecting') return { kind: 'working', label: '确认中' }
  if (generationStatus === 'waiting_for_confirm') {
    return { kind: 'confirm', label: '待确认' }
  }
  if (generationStatus === 'evaluation_failed') {
    return { kind: 'failed', label: '评审失败' }
  }
  if (generationStatus === 'failed') return { kind: 'failed', label: '生成失败' }
  if (hasPrediction) return { kind: 'predicted', label: '已推演' }
  return { kind: 'planned', label: '已规划' }
}

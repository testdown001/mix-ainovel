export const AUTHORING_STAGES = [
  { id: 1, label: '章节规划' },
  { id: 2, label: '正文创作' },
] as const

interface AuthoringStageInput {
  generationStatus?: string | null
  hasContent?: boolean
  hasEvaluation?: boolean
}

const WRITING_STATUSES = new Set([
  'generating',
  'evaluating',
  'selecting',
  'waiting_for_confirm',
  'successful',
  'evaluation_failed',
])

/**
 * 用户只需要理解“规划”和“正文”两步。剧情梳理与一致性检查仍在后台执行，
 * 不再各占一个可点击的顶层阶段。
 */
export function resolveAuthoringStage(input: AuthoringStageInput): 1 | 2 {
  if (
    input.hasContent ||
    input.hasEvaluation ||
    WRITING_STATUSES.has(input.generationStatus || '')
  ) {
    return 2
  }
  return 1
}

/** 规划或章纲发生变化后，旧的情节梳理不能继续作为正文约束。 */
export function invalidatePrediction<T extends object>(
  metadata: T | null | undefined,
): Omit<T, 'prediction'> {
  const next = { ...(metadata || {}) } as T & { prediction?: unknown }
  delete next.prediction
  return next
}

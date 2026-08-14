/**
 * 「本次跳过了哪些精修步骤」的读取与措辞。
 *
 * 生成有软时间预算：单个后处理步最坏约 180 秒，剩余预算不够一整步就跳过，带当前稿
 * 返回（否则会冲破 600 秒硬超时、整章失败）。上游变慢时这会**静默**发生——2026-08-14
 * 线上实测，上游变慢后标准档一章 380 秒，使命规划 120 秒 + 正文 259 秒，整条后处理链
 * 一步没跑，用户按标准档付费却拿到一份没过质检的初稿，界面上完全看不出来。
 *
 * 结论本来就在响应里（review_summaries.time_budget.skipped，异步路径由 worker 带出
 * skipped_for_budget），此前没人读它。
 */

const STEP_LABELS: Record<string, string> = {
  combined_revision: '按评审意见修订',
  consistency: '一致性校对',
  humanization: '打磨行文',
  optimizer: '精修文字',
  enrichment: '补充细节',
  density_compression: '压缩冗余',
  six_dimension: '六维质量评审',
  guardrail_rewrite: '底线校验',
  prose_sculpting: '文体雕琢',
  density_sculpting: '密度雕琢',
  golden_paragraph: '金句段落',
  quality_detection: '质量检测',
}

/** 从生成响应里取出被时间预算跳过的步骤（两条路径的载荷形状不同）。 */
export function extractSkippedSteps(result: unknown): string[] {
  if (!result || typeof result !== 'object') return []
  const payload = result as Record<string, any>

  // 异步任务路径：worker 直接带出来的扁平字段
  if (Array.isArray(payload.skipped_for_budget)) {
    return payload.skipped_for_budget.filter((item: unknown) => typeof item === 'string')
  }

  // 同步 / SSE 路径：藏在选中版本的 review_summaries 里
  const variants = Array.isArray(payload.variants) ? payload.variants : []
  for (const variant of variants) {
    const skipped = variant?.metadata?.review_summaries?.time_budget?.skipped
    if (Array.isArray(skipped) && skipped.length) {
      return skipped.filter((item: unknown) => typeof item === 'string')
    }
  }
  return []
}

/** 用户能看懂的说明；无跳过则返回空串。 */
export function describeSkippedSteps(steps: string[]): string {
  if (!steps.length) return ''
  const labels = [...new Set(steps.map((step) => STEP_LABELS[step] || step))]
  return `本次生成上游较慢，为避免超时跳过了${labels.join('、')}。正文已交付，如需完整质检可稍后重新生成。`
}

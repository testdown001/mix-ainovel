/**
 * 生成阶段词汇表：stage key → 用户语言的阶段名 + 进度百分比。
 *
 * 三种进度来源（Go 网关异步任务 / SSE 直连 / 本地进度 WS）发的都是同一套 stage key，
 * 但此前没人按 key 解释它：前端在 ChapterGenerating 里按中文关键词猜进度、后端
 * task_worker 里另有一张关键词表猜同一件事，两张表各写各的，且都建立在「阶段文案里
 * 恰好含某个词」之上——改一句文案，进度条就悄悄失准。批量生成那条路径更直接把机器名
 * （generate_versions / batch_generating）当阶段名显示给用户看。
 *
 * 这里是前端唯一的解释处：key 是稳定的，文案与百分比都只在这里改。
 * 百分比按实测耗时分布排（标准档一章约 108s：上下文与写作约占前六成，后处理链约四成），
 * 不追求精确，只保证单调推进且不会长时间停在同一个数字上。
 */

export interface ResolvedStage {
  /** 用户语言的阶段名 */
  label: string
  /** 该阶段对应的进度百分比；null 表示不认识这个阶段，不要动进度 */
  percent: number | null
}

const STAGE_TABLE: Record<string, ResolvedStage> = {
  // —— 排队与开工 ——
  queued: { label: '排队中', percent: 3 },
  pending: { label: '排队中', percent: 3 },
  submitted: { label: '已提交任务', percent: 4 },
  starting: { label: '准备生成', percent: 8 },
  task_started: { label: '开始生成', percent: 10 },

  // —— 上下文与写作 ——
  prepare_context: { label: '检索相关剧情与设定', percent: 14 },
  generate_chapter_mission: { label: '规划本章任务', percent: 22 },
  build_generation_prompt: { label: '整理设定与前情', percent: 30 },
  generate_fast_version: { label: '撰写正文', percent: 45 },
  generate_versions: { label: '撰写正文（多版本）', percent: 45 },
  generate_scene_by_scene: { label: '逐场景撰写', percent: 45 },
  batch_generating: { label: '连续生成中', percent: 30 },

  // —— 后处理链：约占一章四成时长，逐步播报，避免长时间停在「撰写正文」——
  post_combined_revision: { label: '按评审意见修订', percent: 58 },
  post_consistency: { label: '一致性校对', percent: 62 },
  post_humanization: { label: '打磨行文', percent: 66 },
  post_optimizer: { label: '精修文字', percent: 70 },
  post_polish: { label: '润色', percent: 73 },
  post_enrichment: { label: '补充细节', percent: 76 },
  post_density_compression: { label: '压缩冗余', percent: 78 },
  post_six_dimension: { label: '六维质量评审', percent: 84 },
  post_auto_refine: { label: '按评分补写', percent: 87 },
  post_six_dimension_rescore: { label: '复评', percent: 89 },
  post_guardrail_rewrite: { label: '底线校验', percent: 90 },

  // —— 收尾 ——
  persist_versions: { label: '保存章节', percent: 94 },
  completed: { label: '生成完成', percent: 100 },
  task_completed: { label: '生成完成', percent: 100 },
}

/** Agent 模式（agent:taizi:start 之类）：阶段名用后端给的中文消息，进度按环节粗分。 */
const AGENT_ROLE_PERCENT: Record<string, number> = {
  system: 10,
  taizi: 15,
  hubu: 20,
  zhongshu: 30,
  plan: 30,
  bingbu: 50,
  write: 50,
  menxia: 80,
  review: 80,
}

/**
 * 解释一条阶段事件。
 *
 * @param key 后端发的 stage 标识
 * @param message 后端附带的中文说明（认不出 key 时用它兜底，总比显示机器名强）
 */
export function resolveStage(key?: string | null, message?: string | null): ResolvedStage {
  const stageKey = (key || '').trim()
  const fallbackLabel = (message || '').trim()

  const known = STAGE_TABLE[stageKey]
  if (known) {
    return known
  }

  const agentMatch = stageKey.match(/^agent:(\w+):(\w+)$/)
  if (agentMatch) {
    return {
      label: fallbackLabel || stageKey,
      percent: AGENT_ROLE_PERCENT[agentMatch[1]] ?? null,
    }
  }

  if (fallbackLabel) {
    // 认不出的阶段：显示后端消息（都是中文），但不动进度——猜错的进度比不动更伤信任
    return { label: fallbackLabel, percent: null }
  }

  return { label: stageKey || '处理中', percent: null }
}

/** 是否为机器名（用于测试与兜底判断：不该把这种东西显示给用户）。 */
export function looksLikeMachineName(text: string): boolean {
  return /^[a-z][a-z0-9_:]*$/i.test(text.trim())
}

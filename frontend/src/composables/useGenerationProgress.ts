/**
 * 章节生成进度状态机：一个状态，三种来源。
 *
 * 生成进度有三条互不相同的来路——Go 网关异步任务（WS 推送，断了降级轮询）、SSE 直连、
 * 后端本地进度 WS。它们此前各喂各的字符串给同一个 `streamingStage`，谁最后写谁赢：
 * 单章路径优先用中文 message、批量路径优先用机器名，进度条则在组件里按中文关键词
 * 另猜一遍。用户看到的是一会儿「多版本生成中」一会儿「generate_versions」，以及一条
 * 会卡住不动的进度条。
 *
 * 这里收成一个状态机：所有来源都走 applyStage()，阶段名与百分比统一由
 * utils/generationStages 解释，百分比单调不回退（回退比停住更像出错）。
 * 降级也是状态的一部分并显式告知——用户有权知道「实时推送没了，现在是每 2 秒问一次」。
 */
import { computed, ref } from 'vue'
import { resolveStage } from '@/utils/generationStages'

export type ProgressSource = 'async' | 'stream'

export interface StageLogEntry {
  at: Date
  label: string
}

export interface StageInput {
  stage?: string | null
  message?: string | null
  /** 来源自带的百分比（Go 任务状态里有），与本地映射取较大值 */
  percent?: number | null
}

export function useGenerationProgress() {
  const active = ref(false)
  const chapterNumber = ref<number | null>(null)
  const source = ref<ProgressSource>('stream')
  const label = ref('')
  const percent = ref(0)
  const logs = ref<StageLogEntry[]>([])
  const degraded = ref(false)
  const degradedReason = ref('')

  const sourceLabel = computed(() =>
    source.value === 'async' ? '后台任务' : '直连生成',
  )

  const INITIAL_LABEL = '准备生成'

  function start(chapter: number, from: ProgressSource) {
    active.value = true
    chapterNumber.value = chapter
    source.value = from
    label.value = INITIAL_LABEL
    percent.value = 2
    // 日志从第一行就有内容：后端的 starting 事件解析出来也是「准备生成」，
    // 若这里留空，那条事件会因为与当前标签相同而不记，日志开头就少一行
    logs.value = [{ at: new Date(), label: INITIAL_LABEL }]
    degraded.value = false
    degradedReason.value = ''
  }

  function applyStage(input: StageInput) {
    if (!active.value) return
    const resolved = resolveStage(input.stage, input.message)

    if (resolved.label && resolved.label !== label.value) {
      label.value = resolved.label
      const last = logs.value[logs.value.length - 1]
      if (!last || last.label !== resolved.label) {
        logs.value.push({ at: new Date(), label: resolved.label })
      }
    }

    // 单调推进：后处理链里几步会并行/跳过，事件顺序不保证严格递增，
    // 进度条往回跳会被读成「重来了一遍」
    const candidates = [resolved.percent, input.percent].filter(
      (value): value is number => typeof value === 'number' && Number.isFinite(value),
    )
    if (candidates.length) {
      percent.value = Math.min(100, Math.max(percent.value, ...candidates))
    }
  }

  /** 标记降级并如实说明当前走的是哪条路（同一原因只记一次日志）。 */
  function markDegraded(reason: string) {
    if (degraded.value && degradedReason.value === reason) return
    degraded.value = true
    degradedReason.value = reason
    logs.value.push({ at: new Date(), label: reason })
  }

  function finish() {
    if (!active.value) return
    percent.value = 100
    label.value = '生成完成'
    active.value = false
  }

  function reset() {
    active.value = false
    chapterNumber.value = null
    label.value = ''
    percent.value = 0
    logs.value = []
    degraded.value = false
    degradedReason.value = ''
  }

  return {
    active,
    chapterNumber,
    source,
    sourceLabel,
    label,
    percent,
    logs,
    degraded,
    degradedReason,
    start,
    applyStage,
    markDegraded,
    finish,
    reset,
  }
}

export type GenerationProgress = ReturnType<typeof useGenerationProgress>

/** 传给展示组件的只读快照（组件不需要也不应该改状态）。 */
export interface GenerationProgressView {
  label: string
  percent: number
  logs: StageLogEntry[]
  degraded: boolean
  degradedReason: string
  sourceLabel: string
}

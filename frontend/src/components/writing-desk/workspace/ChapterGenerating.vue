<!-- AIMETA P=生成中_章节生成进度|R=进度展示_流式输出_实时看板|NR=不含生成逻辑|E=component:ChapterGenerating|X=internal|A=生成状态|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="h-full">
    <!-- 新版进度看板 -->
    <WritingProgressBoard
      v-if="useNewBoard"
      :project-id="projectId || ''"
      :chapter-number="chapterNumber || 0"
      :initial-progress="initialProgress"
      @view="handleViewResult"
      @adjust="handleAdjust"
      @supplement="handleSupplement"
      @stop="handleStop"
      @complete="handleComplete"
    />

    <!-- 增强版加载视图 -->
    <div v-else class="flex items-center justify-center h-full">
      <div class="md-card md-card-outlined p-6 max-w-lg w-full" style="border-radius: var(--md-radius-xl);">
        <!-- 头部：spinner + 标题 -->
        <div class="text-center mb-4">
          <div class="w-14 h-14 rounded-full mx-auto flex items-center justify-center mb-3" style="background-color: var(--md-primary-container);">
            <div class="md-spinner" style="width: 32px; height: 32px;"></div>
          </div>
          <h3 class="md-headline-small font-semibold">{{ statusText.title }}</h3>
        </div>

        <!-- 时间信息栏 -->
        <div class="flex justify-between items-center mb-3 px-1">
          <span class="md-body-small md-on-surface-variant">
            {{ isDetached ? `已等待 ${elapsedFormatted}` : `已用时 ${elapsedFormatted}` }}
          </span>
          <span class="md-body-small" style="color: var(--md-primary);">
            {{ estimatedRemainingText }}
          </span>
        </div>

        <!-- 当前阶段 + 进度通道降级告知 -->
        <div class="flex items-center justify-between gap-3 mb-2 px-1">
          <span class="md-label-large">{{ currentStageLabel }}</span>
          <span v-if="!isDetached" class="md-body-small md-on-surface-variant">{{ progressPercent }}%</span>
        </div>
        <p v-if="degradedReason" class="md-body-small mb-2 px-1" style="color: var(--md-tertiary, #7a5900);">
          {{ degradedReason }}
        </p>

        <!-- 进度条：接管别人的生成（刷新/换设备）时没有阶段来源，用不定量条，
             而不是画一个不动的百分比假装知道进度 -->
        <div class="gen-progress-track mb-4">
          <div
            v-if="isDetached"
            class="gen-progress-fill gen-progress-indeterminate"
          ></div>
          <div v-else class="gen-progress-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>

        <!-- 滚动阶段日志 -->
        <div
          ref="logContainerRef"
          class="md-card md-card-outlined p-3 text-left mb-4"
          style="border-radius: var(--md-radius-md); max-height: 200px; overflow-y: auto;"
        >
          <p class="md-label-small mb-2" style="color: var(--md-primary);">生成日志</p>
          <div
            v-for="(log, index) in stageLogs"
            :key="index"
            class="log-entry"
            :class="{ 'log-entry-current': index === stageLogs.length - 1 }"
          >
            <span class="log-time">{{ formatLogTime(log.timestamp) }}</span>
            <span class="log-icon" :class="index === stageLogs.length - 1 ? 'log-icon-active' : 'log-icon-done'">
              {{ index === stageLogs.length - 1 ? '▶' : '✓' }}
            </span>
            <span class="log-message">{{ log.message }}</span>
          </div>
          <div v-if="stageLogs.length === 0" class="log-entry log-entry-current">
            <span class="log-icon log-icon-active">▶</span>
            <span class="log-message">{{
              isDetached ? '这一章在你打开本页前就开始了，看不到之前的阶段' : '等待开始...'
            }}</span>
          </div>
        </div>

        <!-- 实时草稿预览 -->
        <div
          v-if="previewText"
          class="md-card md-card-outlined p-3 text-left mb-4"
          style="border-radius: var(--md-radius-md); max-height: 220px; overflow-y: auto;"
        >
          <p class="md-label-small mb-2" style="color: var(--md-primary);">实时草稿预览</p>
          <pre class="m3-stream-preview md-body-small">{{ previewText }}</pre>
        </div>

        <!-- 底部提示 -->
        <div class="md-card md-card-filled p-3 text-left" style="border-radius: var(--md-radius-lg);">
          <p class="md-body-small md-on-surface-variant">
            生成过程通常需要 2-4 分钟，请耐心等待。您可以随时离开此页面，生成完成后再回来查看。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import type { Chapter } from '@/api/novel'
import type { GenerationProgressView } from '@/composables/useGenerationProgress'
import WritingProgressBoard from '@/components/writing-desk/WritingProgressBoard.vue'
import { getWritingProgress, type WritingProgress as WritingProgressType } from '@/api/writingProgress'

interface Props {
  chapterNumber: number | null
  status: Chapter['generation_status'] | null
  streamingDraftText?: string
  streamingStage?: string | null
  projectId?: string
  /**
   * 统一进度状态（WritingDesk 的状态机产出）。缺省时退回只看 streamingStage 的老行为
   * ——刷新页面后由轮询接管的场景没有状态机，此时只知道「在生成」。
   */
  generationProgress?: GenerationProgressView | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'view'): void
  (e: 'adjust'): void
  (e: 'supplement'): void
  (e: 'stop'): void
}>()

// ===== 新版看板 =====
const useNewBoard = ref(false) // 默认使用增强的 SSE 视图
const initialProgress = ref<WritingProgressType | null>(null)

onMounted(async () => {
  // 可选：尝试加载 WebSocket 进度看板（目前禁用，优先使用 SSE 视图）
  // if (props.projectId && props.chapterNumber) {
  //   try {
  //     const progress = await getWritingProgress(props.projectId, props.chapterNumber)
  //     if (progress) {
  //       initialProgress.value = progress
  //       useNewBoard.value = true
  //     }
  //   } catch (e) {
  //     console.warn('获取进度失败，使用增强视图')
  //   }
  // }
})

// ===== 增强视图：日志 + 时间预估 =====

interface StageLogEntry {
  timestamp: Date
  message: string
}

const localStageLogs = ref<StageLogEntry[]>([])
const logContainerRef = ref<HTMLElement | null>(null)
const startTime = ref(Date.now())
const elapsedSeconds = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

// 有状态机就用它的日志，没有（刷新后由轮询接管）才自己按 streamingStage 累积
const stageLogs = computed<StageLogEntry[]>(() => {
  const shared = props.generationProgress?.logs
  if (shared?.length) {
    return shared.map((entry) => ({ timestamp: entry.at, message: entry.label }))
  }
  return localStageLogs.value
})

/**
 * 「接管态」：本页没有这次生成的进度来源（刷新页面、换设备、别处发起的生成）。
 * 此时只知道「它在跑」，不知道跑到哪一步——就别装作知道。
 */
const isDetached = computed(() => !props.generationProgress && !props.streamingStage)

const currentStageLabel = computed(() => {
  if (props.generationProgress?.label) return props.generationProgress.label
  if (props.streamingStage) return props.streamingStage
  return '服务端生成中，状态每 10 秒刷新'
})

const degradedReason = computed(() =>
  props.generationProgress?.degraded ? props.generationProgress.degradedReason : '',
)

watch(() => props.streamingStage, (newStage, oldStage) => {
  if (newStage && newStage !== oldStage) {
    const last = localStageLogs.value[localStageLogs.value.length - 1]
    if (!last || last.message !== newStage) {
      localStageLogs.value.push({
        timestamp: new Date(),
        message: newStage
      })
    }
  }
}, { immediate: true })

// 日志滚到底：两种来源都要跟随
watch(() => stageLogs.value.length, () => {
  nextTick(() => {
    if (logContainerRef.value) {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    }
  })
})

// 计时器
onMounted(() => {
  startTime.value = Date.now()
  timer = setInterval(() => {
    elapsedSeconds.value = Math.floor((Date.now() - startTime.value) / 1000)
  }, 1000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})

// 已用时格式化
const elapsedFormatted = computed(() => {
  const mins = Math.floor(elapsedSeconds.value / 60)
  const secs = elapsedSeconds.value % 60
  return `${mins}:${String(secs).padStart(2, '0')}`
})

// 进度百分比由状态机给（阶段 key → 百分比只在 utils/generationStages 解释一次）。
// 这里原先另有一张中文关键词表，和后端 task_worker 那张各写各的：阶段文案一改就失准，
// 后处理链那四成时长更是全程匹配不到任何关键词、进度条一动不动。
// 没有状态机（刷新后轮询接管）时不装懂：给一个不动的低值，由「已用时」说明还在跑。
const progressPercent = computed(() => props.generationProgress?.percent ?? 5)

// 预估剩余时间
const estimatedRemainingText = computed(() => {
  // 接管态下已用时是从打开本页算的，不是生成真正的起点，据此推算剩余时间等于编数字
  if (isDetached.value) return '完成后自动出现'
  const progress = progressPercent.value
  const elapsed = elapsedSeconds.value

  if (progress >= 95) return '即将完成'
  if (elapsed < 10 || progress < 10) return '预计需要 2~4 分钟'

  // 使用更保守的预估：限制最大预估时间，避免早期阶段预估过长
  const estimatedTotal = elapsed / (progress / 100)
  const cappedTotal = Math.min(estimatedTotal, elapsed * 3) // 最多预估为当前已用时的 3 倍
  const remaining = Math.max(0, Math.ceil(cappedTotal - elapsed))

  if (remaining <= 0) return '即将完成'
  if (remaining < 60) return `预计剩余 ${remaining} 秒`

  const mins = Math.floor(remaining / 60)
  const secs = remaining % 60

  // 超过 5 分钟时，显示范围而不是精确值
  if (mins >= 5) return '预计剩余 5~8 分钟'
  if (secs > 0) return `预计剩余 ${mins} 分 ${secs} 秒`
  return `预计剩余 ${mins} 分钟`
})

// 日志时间格式化
function formatLogTime(date: Date): string {
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

// ===== 状态文案 =====
const statusText = computed(() => {
  switch (props.status) {
    case 'generating':
      return {
        title: `AI 正在为您创作第${props.chapterNumber}章`,
      }
    case 'evaluating':
      return {
        title: `AI 正在评审第${props.chapterNumber}章的多个版本`,
      }
    case 'selecting':
      return {
        title: `正在确认第${props.chapterNumber}章的最终版本`,
      }
    default:
      return {
        title: '请稍候...',
      }
  }
})

const previewText = computed(() => {
  const raw = props.streamingDraftText || ''
  if (!raw.trim()) return ''
  const maxLen = 2200
  if (raw.length <= maxLen) {
    return raw
  }
  return `...${raw.slice(-maxLen)}`
})

// ===== WritingProgressBoard 事件处理 =====
function handleViewResult() {
  emit('view')
}

function handleAdjust() {
  emit('adjust')
}

function handleSupplement() {
  emit('supplement')
}

function handleStop() {
  emit('stop')
}

function handleComplete(progress: WritingProgressType) {
  console.log('写作完成:', progress)
  emit('view')
}
</script>

<style scoped>
/* 进度条 */
.gen-progress-track {
  width: 100%;
  height: 6px;
  background: var(--md-surface-container-highest, #e0e0e0);
  border-radius: 3px;
  overflow: hidden;
}

.gen-progress-fill {
  height: 100%;
  background: var(--md-primary, #1976d2);
  border-radius: 3px;
  transition: width 0.6s ease;
}

/* 不定量进度：只表示「在跑」，不表示进度到了几成 */
.gen-progress-indeterminate {
  width: 35%;
  animation: gen-progress-slide 1.6s ease-in-out infinite;
}

@keyframes gen-progress-slide {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(300%); }
}

/* 日志条目 */
.log-entry {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 3px 0;
  font-size: 13px;
  line-height: 1.5;
}

.log-time {
  flex-shrink: 0;
  font-size: 11px;
  font-family: monospace;
  color: var(--md-outline, #999);
}

.log-icon {
  flex-shrink: 0;
  font-size: 10px;
  width: 14px;
  text-align: center;
}

.log-icon-done {
  color: var(--md-primary, #1976d2);
}

.log-icon-active {
  color: var(--md-primary, #1976d2);
  animation: log-blink 1.2s ease-in-out infinite;
}

.log-message {
  color: var(--md-on-surface-variant, #666);
}

.log-entry-current .log-message {
  color: var(--md-primary, #1976d2);
  font-weight: 500;
}

@keyframes log-blink {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

/* 草稿预览 */
.m3-stream-preview {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  line-height: 1.6;
}
</style>

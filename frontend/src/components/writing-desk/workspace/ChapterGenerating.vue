<!-- AIMETA P=生成中_章节生成进度|R=进度展示_流式输出_实时看板|NR=不含生成逻辑|E=component:ChapterGenerating|X=internal|A=生成状态|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="h-full">
    <!-- 新版进度看板 -->
    <WritingProgressBoard
      v-if="useNewBoard"
      :project-id="projectId"
      :chapter-number="chapterNumber || 0"
      :initial-progress="initialProgress"
      @view="handleViewResult"
      @adjust="handleAdjust"
      @supplement="handleSupplement"
      @stop="handleStop"
      @complete="handleComplete"
    />

    <!-- 旧版简洁视图（兼容） -->
    <div v-else class="flex items-center justify-center h-full">
      <div class="md-card md-card-outlined p-8 text-center max-w-md" style="border-radius: var(--md-radius-xl);">
        <div class="w-16 h-16 rounded-full mx-auto flex items-center justify-center mb-5" style="background-color: var(--md-primary-container);">
          <div class="md-spinner" style="width: 36px; height: 36px;"></div>
        </div>
        <h3 class="md-headline-small font-semibold mb-3">{{ statusText.title }}</h3>
        <div class="space-y-2 md-body-medium md-on-surface-variant mb-6">
          <p class="m3-pulse">{{ statusText.line1 }}</p>
          <p class="m3-pulse" style="animation-delay: 0.5s">{{ statusText.line2 }}</p>
          <p class="m3-pulse" style="animation-delay: 1s">🎨 描绘生动场景...</p>
          <p v-if="stageHint" class="md-body-small !text-left px-1" style="color: var(--md-primary);">
            {{ stageHint }}
          </p>
        </div>
        <div class="md-progress-linear md-progress-linear-indeterminate mb-5">
          <div class="md-progress-linear-bar"></div>
        </div>
        <div
          v-if="previewText"
          class="md-card md-card-outlined p-3 text-left mb-5"
          style="border-radius: var(--md-radius-md); max-height: 220px; overflow-y: auto;"
        >
          <p class="md-label-medium mb-2" style="color: var(--md-primary);">实时草稿预览</p>
          <pre class="m3-stream-preview md-body-small">{{ previewText }}</pre>
        </div>
        <div class="md-card md-card-filled p-4 text-left" style="border-radius: var(--md-radius-lg);">
          <p class="md-body-small md-on-surface-variant">
            生成过程通常需要2分钟以上，请耐心等待。您可以随时离开此页面，生成完成后再回来查看。
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import type { Chapter } from '@/api/novel'
import WritingProgressBoard from '@/components/writing-desk/WritingProgressBoard.vue'
import { getWritingProgress, type WritingProgress as WritingProgressType } from '@/api/writingProgress'

interface Props {
  chapterNumber: number | null
  status: Chapter['generation_status'] | null
  streamingDraftText?: string
  streamingStage?: string | null
  projectId?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'view'): void
  (e: 'adjust'): void
  (e: 'supplement'): void
  (e: 'stop'): void
}>()

// 是否使用新版看板
const useNewBoard = ref(true)
const initialProgress = ref<WritingProgressType | null>(null)

// 加载已有进度
onMounted(async () => {
  if (props.projectId && props.chapterNumber) {
    try {
      const progress = await getWritingProgress(props.projectId, props.chapterNumber)
      if (progress) {
        initialProgress.value = progress
      }
    } catch (e) {
      console.warn('获取进度失败，使用旧版视图')
      useNewBoard.value = false
    }
  } else {
    useNewBoard.value = false
  }
})

// 事件处理
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

const statusText = computed(() => {
  switch (props.status) {
    case 'generating':
      return {
        title: `AI 正在为您创作第${props.chapterNumber}章`,
        line1: '✨ 构思情节发展...',
        line2: '📝 编织精彩对话...'
      }
    case 'evaluating':
      return {
        title: `AI 正在评审第${props.chapterNumber}章的多个版本`,
        line1: '🧐 分析故事结构...',
        line2: '⚖️ 比较版本优劣...'
      }
    case 'selecting':
      return {
        title: `正在确认第${props.chapterNumber}章的最终版本`,
        line1: '💾 保存您的选择...',
        line2: '✍️ 生成最终摘要...'
      }
    default:
      return {
        title: '请稍候...',
        line1: '正在处理您的请求...',
        line2: '...'
      }
  }
})

const stageHint = computed(() => {
  if (!props.streamingStage) return ''
  return props.streamingStage.trim()
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
</script>

<style scoped>
.m3-pulse {
  animation: m3-pulse 1.6s ease-in-out infinite;
}

@keyframes m3-pulse {
 0%,
 100% {
    opacity: 0.55;
  }
  50% {
    opacity: 1;
  }
}

.m3-stream-preview {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  line-height: 1.6;
}
</style>

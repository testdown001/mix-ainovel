<!-- AIMETA P=蓝图确认_蓝图确认对话框|R=确认操作|NR=不含编辑功能|E=component:BlueprintConfirmation|X=internal|A=确认对话框|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="p-8 bg-white rounded-2xl shadow-2xl fade-in">
    <h2 class="text-3xl font-bold text-center text-gray-800 mb-6">信息收集完成！</h2>

    <div class="text-center mb-8">
      <div 
        class="prose prose-lg prose-gray max-w-none mx-auto mb-4 text-gray-600"
        v-html="renderedAiMessage"
      ></div>
      <p class="text-sm text-gray-500">
        我们已经收集了足够的信息来为您创建详细的小说蓝图。点击下方按钮开始生成您的专属故事大纲。
      </p>
    </div>

    <!-- 高级加载状态 -->
    <div v-if="isGenerating" class="text-center py-12">
      <!-- 主加载动画 -->
      <div class="relative mx-auto mb-8 w-24 h-24">
        <!-- 外圆环 -->
        <div
          class="absolute inset-0 border-4 rounded-full transition-colors duration-500"
          :class="progress >= 100 ? 'border-green-100' : 'border-indigo-100'"
        ></div>
        <!-- 旋转的渐变圆环 -->
        <div
          class="absolute inset-0 border-4 border-transparent rounded-full transition-colors duration-500"
          :class="[
            progress >= 100
              ? 'border-t-green-500 border-r-green-400'
              : 'border-t-indigo-500 border-r-indigo-400',
            progress < 100 ? 'animate-spin' : ''
          ]"
        ></div>
        <!-- 内部脉冲圆 -->
        <div
          class="absolute inset-3 rounded-full animate-pulse opacity-20 transition-colors duration-500"
          :class="progress >= 100 ? 'bg-green-500' : 'bg-indigo-500'"
        ></div>
        <!-- 中心图标 -->
        <div
          class="absolute inset-6 rounded-full flex items-center justify-center transition-colors duration-500"
          :class="progress >= 100 ? 'bg-green-500' : 'bg-indigo-500'"
        >
          <svg
            v-if="progress >= 100"
            class="w-6 h-6 text-white"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
          </svg>
          <svg
            v-else
            class="w-6 h-6 text-white animate-pulse"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
          </svg>
        </div>
      </div>

      <!-- 加载文本 + 真实已用时 -->
      <div class="space-y-4">
        <h3 class="text-xl font-semibold text-gray-800">{{ loadingText }}</h3>
        <p class="text-sm text-gray-500">已用时 {{ elapsedLabel }} · AI 正在为你打造专属蓝图</p>

        <!-- 分阶段清单：步骤按经验节奏逐步推进 / 打勾 -->
        <ul class="max-w-md mx-auto text-left space-y-2.5 mt-2">
          <li
            v-for="(stage, i) in STAGES"
            :key="i"
            class="flex items-center gap-3 text-sm transition-colors duration-300"
            :class="i < currentStageIndex ? 'text-gray-700' : i === currentStageIndex ? 'text-indigo-600 font-medium' : 'text-gray-400'"
          >
            <span class="flex-shrink-0 w-5 h-5 flex items-center justify-center">
              <!-- 已完成：打勾 -->
              <svg v-if="i < currentStageIndex" class="w-4 h-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
              </svg>
              <!-- 进行中：脉冲点 -->
              <span v-else-if="i === currentStageIndex" class="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse"></span>
              <!-- 待进行：灰点 -->
              <span v-else class="w-2 h-2 rounded-full bg-gray-300"></span>
            </span>
            <span>{{ stage }}</span>
          </li>
        </ul>

        <!-- 进度条：按已进入的阶段推进 -->
        <div class="w-full max-w-md mx-auto">
          <div class="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
            <div
              class="h-2 rounded-full transition-all duration-700 ease-out relative"
              :class="progress >= 100 ? 'bg-gradient-to-r from-green-500 to-emerald-600' : 'bg-gradient-to-r from-indigo-500 to-purple-600'"
              :style="{ width: `${progress}%` }"
            >
              <!-- 闪光效果 -->
              <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-30 animate-shimmer"></div>
            </div>
          </div>
        </div>

        <!-- 诚实提示：步骤为预估节奏，已用时为真实计时 -->
        <div class="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200 max-w-md mx-auto">
          <p class="text-sm text-blue-800 flex items-start gap-2 text-left">
            <svg class="w-4 h-4 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>
            </svg>
            <span>蓝图为一次成型，上方步骤为预估节奏、已用时为真实计时。复杂设定可能需要数分钟，请耐心等待…</span>
          </p>
        </div>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div v-else class="text-center space-x-4">
      <button
        @click="$emit('back')"
        class="bg-gray-200 text-gray-700 font-bold py-3 px-8 rounded-full hover:bg-gray-300 transition-all duration-300 transform hover:scale-105"
      >
        返回对话
      </button>
      <button
        @click="generateBlueprint"
        :disabled="isGenerating"
        class="bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-bold py-3 px-8 rounded-full hover:from-indigo-600 hover:to-purple-700 transition-all duration-300 transform hover:scale-105 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
      >
        <span class="flex items-center justify-center">
          <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
            <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
          </svg>
          开始创建蓝图
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted, inject } from 'vue'
import { marked } from 'marked'
import { useNovelStore } from '@/stores/novel'
import { globalAlert } from '@/composables/useAlert'
import { humanizeGenerationError } from '@/utils/errorHumanize'

// 配置 marked
marked.setOptions({
  gfm: true,           // 启用 GitHub 风格语法
  breaks: true         // 将单个换行视为 <br>
})

interface Props {
  aiMessage: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  blueprintGenerated: [response: any]
  back: []
}>()

const novelStore = useNovelStore()
const isGenerating = ref(false)
const isDone = ref(false)
const timeElapsed = ref(0)   // 真实已用秒数（基于开始时间戳计算，非估算）

// 蓝图为一次成型的单次大模型调用，中途无真实子阶段；下列步骤按经验节奏推进，
// 给用户「正在逐步成型」的可信反馈，而「已用时」为真实计时。
const STAGES = [
  '分析故事结构',
  '构建角色关系网络',
  '生成情节发展脉络',
  '完善世界观设定',
  '优化章节安排',
  '润色蓝图细节',
]
const STAGE_AT = [0, 12, 28, 48, 70, 95]  // 各阶段预估开始秒数

let progressTimer: ReturnType<typeof setInterval> | null = null
let startTs = 0

// 渲染 Markdown
const renderedAiMessage = computed(() => {
  return marked.parse(props.aiMessage)
})

// 当前进行到第几个阶段（完成后等于 STAGES.length，即全部打勾）
const currentStageIndex = computed(() => {
  if (isDone.value) return STAGES.length
  let idx = 0
  for (let i = 0; i < STAGE_AT.length; i++) {
    if (timeElapsed.value >= STAGE_AT[i]) idx = i
  }
  return idx
})

// 进度条：按已进入的阶段推进，未完成时封顶 92%，真正完成才到 100%
const progress = computed(() => {
  if (isDone.value) return 100
  return Math.min(92, ((currentStageIndex.value + 1) / STAGES.length) * 92)
})

// 真实已用时间 MM:SS
const elapsedLabel = computed(() => {
  const s = Math.floor(timeElapsed.value)
  const m = Math.floor(s / 60)
  return `${m}:${String(s % 60).padStart(2, '0')}`
})

// 动态加载文本：当前阶段名；长时间停在末阶段时切到「深度打磨」提示
const loadingText = computed(() => {
  if (isDone.value) return '生成完成！正在准备展示…'
  const idx = currentStageIndex.value
  if (idx >= STAGES.length - 1 && timeElapsed.value > STAGE_AT[STAGE_AT.length - 1] + 25) {
    return 'AI 正在深度打磨蓝图，复杂设定需要更多时间…'
  }
  return `${STAGES[Math.min(idx, STAGES.length - 1)]}…`
})

const generateBlueprint = async () => {
  isGenerating.value = true
  isDone.value = false
  timeElapsed.value = 0
  startTs = Date.now()

  // 真实计时：按开始时间戳推进「已用时」，驱动阶段清单逐步打勾与进度条推进
  progressTimer = setInterval(() => {
    timeElapsed.value = (Date.now() - startTs) / 1000
  }, 200)

  // 超时由 API 层 AbortController 处理，此处不再设独立 setTimeout

  try {
    // 直接调用store中的API
    console.log('开始调用generateBlueprint API...')
    const response = await novelStore.generateBlueprint()
    console.log('API调用成功，收到响应:', response)

    // 成功：停表并标记完成（全部阶段打勾、进度到 100%）
    if (progressTimer) {
      clearInterval(progressTimer)
      progressTimer = null
    }
    isDone.value = true

    // 等待一下让用户看到100%完成状态，然后再切换界面
    await new Promise(resolve => setTimeout(resolve, 800))

    // 清理并重置状态
    clearTimers()
    isGenerating.value = false
    isDone.value = false

    // 通知父组件生成完成
    emit('blueprintGenerated', response)

  } catch (error) {
    console.error('生成蓝图失败:', error)
    clearTimers()
    isGenerating.value = false
    isDone.value = false
    // 蓝图生成不计费，billed:false 让文案不提「积分已退回」
    const human = humanizeGenerationError(
      error instanceof Error ? error.message : '未知错误',
      { billed: false },
    )
    globalAlert.showError(human.message, human.title)
  }
}

const clearTimers = () => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

onUnmounted(() => {
  clearTimers()
})
</script>

<style scoped>
@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.animate-shimmer {
  animation: shimmer 2s infinite;
}

/* 自定义动画增强 */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.fade-in {
  animation: fadeIn 0.6s ease-out;
}

/* 按钮悬停效果增强 */
.transform {
  transition: transform 0.2s ease-in-out;
}

.hover\:scale-105:hover {
  transform: scale(1.05);
}

/* 禁用状态样式 */
.disabled\:transform-none:disabled {
  transform: none !important;
}

/* Markdown 内容样式优化 */
.prose {
  text-align: left;
}

.prose strong {
  color: #374151;
  font-weight: 700;
}

.prose em {
  color: #4b5563;
  font-style: italic;
}

.prose p {
  margin-bottom: 0.75rem;
}

.prose p:last-child {
  margin-bottom: 0;
}

.prose a {
  color: #6366f1;
  text-decoration: none;
  transition: color 0.2s;
}

.prose a:hover {
  color: #4f46e5;
  text-decoration: underline;
}

.prose code {
  background-color: #f3f4f6;
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.875em;
  color: #1f2937;
}

.prose ul, .prose ol {
  margin-left: 1.5rem;
  margin-bottom: 0.75rem;
}

.prose li {
  margin-bottom: 0.25rem;
}
</style>
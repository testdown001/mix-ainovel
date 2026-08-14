<!-- AIMETA P=灵感加载_加载动画组件|R=加载动画+模拟进度条(真实已等待秒数)_支持阶段文案覆写|NR=不含业务逻辑|E=component:InspirationLoading|X=internal|A=加载组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="loading-root">
    <div class="loading-glow-wrap">
      <div class="loading-orb">
        <svg class="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="color:#fff;">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/>
        </svg>
      </div>
      <div class="loading-ring"></div>
    </div>

    <h2 class="loading-title">{{ title }}</h2>

    <!-- 进度条：底层是单次同步调用（LLM/联网检索），拿不到真实百分比，
         故用渐近模拟进度（最多到 95%，真正完成时父组件卸载本组件），
         配合「已等待秒数」给出真实可信的反馈。 -->
    <div class="loading-progress">
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: progress + '%' }"></div>
      </div>
      <div class="progress-meta">
        <span class="progress-phase">{{ phaseText }}</span>
        <span class="progress-time">已等待 {{ elapsed }}s</span>
      </div>
    </div>

    <p v-if="hintText" class="loading-hint">{{ hintText }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'

// 可覆写文案：灵感模式的「准备阶段」（建项目/联网检索参考小说）与「开场阶段」
// （首次 converse）复用同一套视觉，只换标题/阶段/提示，用户全程有动态反馈
const props = withDefaults(
  defineProps<{
    title?: string
    /** 覆写阶段文案；空串则按已等待时长走内置文案 */
    phaseOverride?: string
    /** 覆写超时提示；空串则按内置推理模型提示（15s 后出现），覆写值 8s 后出现 */
    hintOverride?: string
  }>(),
  { title: '正在为你准备灵感空间...', phaseOverride: '', hintOverride: '' }
)

const progress = ref(0) // 模拟进度 0-95
const elapsed = ref(0)  // 真实已等待秒数

let timer: ReturnType<typeof setInterval> | null = null
const startedAt = Date.now()

function pickPhase(sec: number): string {
  if (sec < 6) return '连接文思泉涌的 AI...'
  if (sec < 14) return '铺开创意的画卷，构思灵感切入点...'
  if (sec < 28) return '推理模型正在深度构思，请稍候...'
  return '马上就好，正在打磨最终表达...'
}

const phaseText = computed(() => props.phaseOverride || pickPhase(elapsed.value))

const hintText = computed(() => {
  if (props.hintOverride) {
    return elapsed.value >= 8 ? props.hintOverride : ''
  }
  return elapsed.value >= 15
    ? '推理模型（如 gpt-5 系列）思考较慢，复杂构思可能需要 30–60 秒，请耐心等待…'
    : ''
})

onMounted(() => {
  timer = setInterval(() => {
    elapsed.value = Math.floor((Date.now() - startedAt) / 1000)
    // 渐近逼近 95%：越接近越慢，绝不谎称 100%（真正完成由父组件卸载本组件）
    progress.value = Math.min(95, progress.value + (95 - progress.value) * 0.04)
  }, 150)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.loading-root {
  position: absolute;
  inset: 0;
  background: #0A0A0A;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 2rem;
}

.loading-glow-wrap {
  position: relative;
  width: 80px;
  height: 80px;
  margin-bottom: 2rem;
}

.loading-orb {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #FFE500 0%, #C084FC 50%, #4F46E5 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: orb-breathe 2s ease-in-out infinite;
  box-shadow: 0 0 40px rgba(192, 132, 252, 0.3), 0 0 80px rgba(255, 229, 0, 0.15);
}

.loading-ring {
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: #FFE500;
  border-right-color: #C084FC;
  animation: ring-spin 1.5s linear infinite;
}

.loading-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #EEEEEE;
  margin-bottom: 1.5rem;
  letter-spacing: 0.02em;
}

.loading-progress {
  width: 100%;
  max-width: 320px;
}

.progress-track {
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: #1E1E1E;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #FFE500 0%, #C084FC 60%, #4F46E5 100%);
  box-shadow: 0 0 12px rgba(192, 132, 252, 0.4);
  transition: width 0.2s ease-out;
}

.progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.6rem;
  font-size: 0.78rem;
  color: #888888;
}

.progress-phase {
  color: #BBBBBB;
}

.progress-time {
  flex-shrink: 0;
  margin-left: 0.75rem;
  font-variant-numeric: tabular-nums;
  color: #777777;
}

.loading-hint {
  max-width: 320px;
  margin-top: 1.25rem;
  font-size: 0.75rem;
  line-height: 1.5;
  color: #6B6B6B;
}

@keyframes orb-breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.06); }
}

@keyframes ring-spin {
  to { transform: rotate(360deg); }
}
</style>

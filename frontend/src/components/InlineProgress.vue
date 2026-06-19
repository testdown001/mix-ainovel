<!-- AIMETA P=内联进度条_等待反馈|R=可复用内联进度条(模拟进度+真实已等待秒数)|NR=不含业务逻辑|E=component:InlineProgress|X=internal|A=进度组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="inline-progress">
    <div class="ip-head">
      <span class="ip-spinner"></span>
      <span class="ip-label">{{ label }}</span>
      <span class="ip-time">{{ elapsed }}s</span>
    </div>
    <div class="ip-track">
      <div class="ip-fill" :style="{ width: progress + '%' }"></div>
    </div>
    <p v-if="hint && elapsed >= 12" class="ip-hint">{{ hint }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

// 用于「无法分解为真实百分比」的同步等待（如缪斯发散=多次 LLM 调用）：
// 渐近模拟进度（最多 95%，绝不谎称完成）+ 真实已等待秒数（诚实信号）。
defineProps<{ label: string; hint?: string }>()

const progress = ref(0)
const elapsed = ref(0)
let timer: ReturnType<typeof setInterval> | null = null
const startedAt = Date.now()

onMounted(() => {
  timer = setInterval(() => {
    elapsed.value = Math.floor((Date.now() - startedAt) / 1000)
    progress.value = Math.min(95, progress.value + (95 - progress.value) * 0.04)
  }, 150)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.inline-progress {
  width: 100%;
  padding: 14px 16px;
  background: #141414;
  border: 1px solid #2A2A2A;
  border-radius: 14px;
}

.ip-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
  font-size: 0.85rem;
  color: #DDDDDD;
}

.ip-label {
  flex: 1;
  min-width: 0;
}

.ip-time {
  flex-shrink: 0;
  font-size: 0.78rem;
  color: #777777;
  font-variant-numeric: tabular-nums;
}

.ip-spinner {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 2px solid #FFE50033;
  border-top-color: #FFE500;
  animation: ip-spin 0.8s linear infinite;
}

.ip-track {
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: #1E1E1E;
  overflow: hidden;
}

.ip-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #FFE500 0%, #C084FC 60%, #4F46E5 100%);
  box-shadow: 0 0 12px rgba(192, 132, 252, 0.4);
  transition: width 0.2s ease-out;
}

.ip-hint {
  margin: 0.75rem 0 0;
  font-size: 0.74rem;
  line-height: 1.5;
  color: #6B6B6B;
}

@keyframes ip-spin {
  to { transform: rotate(360deg); }
}
</style>

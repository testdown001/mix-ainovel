<!-- AIMETA P=统计面板_系统使用统计|R=统计图表|NR=不含数据修改|E=component:Statistics|X=ui|A=统计组件|D=vue,chart.js|S=dom,net|RD=./README.ai -->
<template>
  <div class="stats-panel">
    <div class="panel-header">
      <span class="panel-title">数据总览</span>
      <button class="refresh-btn" @click="fetchStats" :disabled="loading">
        <span v-if="loading" class="spinner" />
        <span v-else>刷新</span>
      </button>
    </div>

    <n-alert v-if="error" type="error" closable @close="error = null" class="stats-alert">
      {{ error }}
    </n-alert>

    <div v-if="loading && !stats" class="loading-state">
      <div class="spinner" />
    </div>

    <div class="stat-grid stagger-reveal" :class="{ 'stat-grid--mobile': isMobile }">
      <div class="stat-card stat-card--novels">
        <div class="stat-card__icon">📚</div>
        <div class="stat-card__body">
          <div class="stat-card__label">小说总数</div>
          <div class="stat-card__value">
            <span class="stat-number">{{ stats?.novel_count ?? 0 }}</span>
            <span class="stat-suffix">部</span>
          </div>
        </div>
        <div class="stat-card__glow" />
      </div>

      <div class="stat-card stat-card--users">
        <div class="stat-card__icon">👥</div>
        <div class="stat-card__body">
          <div class="stat-card__label">用户总数</div>
          <div class="stat-card__value">
            <span class="stat-number">{{ stats?.user_count ?? 0 }}</span>
            <span class="stat-suffix">人</span>
          </div>
        </div>
        <div class="stat-card__glow" />
      </div>

      <div class="stat-card stat-card--api">
        <div class="stat-card__icon">⚡</div>
        <div class="stat-card__body">
          <div class="stat-card__label">API 请求总数</div>
          <div class="stat-card__value">
            <span class="stat-number">{{ stats?.api_request_count ?? 0 }}</span>
            <span class="stat-suffix">次</span>
          </div>
        </div>
        <div class="stat-card__glow" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NGi,
  NGrid,
  NSpin,
  NStatistic,
  NSpace
} from 'naive-ui'

import { AdminAPI, type Statistics } from '@/api/admin'

const stats = ref<Statistics | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const isMobile = ref(false)

const updateLayout = () => {
  isMobile.value = window.innerWidth < 768
}

const gridCols = computed(() => (isMobile.value ? 1 : 3))

const fetchStats = async () => {
  loading.value = true
  error.value = null
  try {
    stats.value = await AdminAPI.getStatistics()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取统计数据失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  updateLayout()
  window.addEventListener('resize', updateLayout)
  fetchStats()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateLayout)
})
</script>

<style scoped>
.stats-panel {
  width: 100%;
  box-sizing: border-box;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: var(--ar-spacing-6);
}

.panel-title {
  font-family: var(--ar-font-display);
  font-size: var(--ar-text-h2);
  font-weight: 700;
  color: var(--ar-text-primary);
  letter-spacing: -0.01em;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  padding: 0 16px;
  border: 1px solid var(--ar-border);
  border-radius: var(--ar-radius-sm);
  background: transparent;
  color: var(--ar-text-secondary);
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-body-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--ar-duration-short) var(--ar-easing-standard);
}

.refresh-btn:hover:not(:disabled) {
  color: var(--ar-primary);
  border-color: rgba(250, 204, 21, 0.3);
  background: var(--ar-primary-muted);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.stats-alert {
  margin-bottom: var(--ar-spacing-4);
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ar-spacing-10);
}

.spinner {
  display: inline-block;
  width: 18px;
  height: 18px;
  border: 2px solid var(--ar-bg-highlight);
  border-top-color: var(--ar-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--ar-spacing-4);
}

.stat-grid--mobile {
  grid-template-columns: 1fr;
}

.stat-card {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: var(--ar-spacing-4);
  padding: var(--ar-spacing-6);
  background: var(--ar-bg-surface);
  border-radius: var(--ar-radius-sm);
  border: 1px solid var(--ar-border);
  overflow: hidden;
  transition: all var(--ar-duration-medium) var(--ar-easing-standard);
}

.stat-card:hover {
  background: var(--ar-bg-elevated);
  box-shadow: var(--ar-elevation-glow);
}

.stat-card__glow {
  position: absolute;
  top: -40px;
  right: -40px;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  opacity: 0.04;
  pointer-events: none;
  transition: opacity var(--ar-duration-medium) var(--ar-easing-standard);
}

.stat-card:hover .stat-card__glow {
  opacity: 0.08;
}

.stat-card--novels .stat-card__glow {
  background: var(--ar-primary);
}

.stat-card--users .stat-card__glow {
  background: var(--ar-secondary);
}

.stat-card--api .stat-card__glow {
  background: var(--ar-info);
}

.stat-card__icon {
  font-size: 28px;
  line-height: 1;
  flex-shrink: 0;
  margin-top: 2px;
}

.stat-card__body {
  flex: 1;
  min-width: 0;
}

.stat-card__label {
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-label);
  font-weight: 500;
  color: var(--ar-text-secondary);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: var(--ar-spacing-2);
}

.stat-card__value {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.stat-number {
  font-family: var(--ar-font-display);
  font-size: var(--ar-text-stat);
  font-weight: 700;
  line-height: 1.1;
  color: var(--ar-text-primary);
}

.stat-card--novels .stat-number {
  color: var(--ar-primary);
}

.stat-card--users .stat-number {
  color: var(--ar-secondary);
}

.stat-card--api .stat-number {
  color: var(--ar-info);
}

.stat-suffix {
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-body-sm);
  color: var(--ar-text-muted);
  font-weight: 500;
}

@media (max-width: 767px) {
  .panel-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .panel-title {
    font-size: var(--ar-text-h3);
  }

  .stat-card {
    padding: var(--ar-spacing-4);
  }
}
</style>

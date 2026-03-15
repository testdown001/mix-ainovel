<!-- AIMETA P=诊断报告面板|R=一键诊断_性能分析|NR=|E=DiagnosticPanel|X=ui|A=诊断组件|D=vue|S=dom -->
<template>
  <div class="diagnostic-panel">
    <!-- 诊断控制栏 -->
    <div class="diagnostic-header">
      <div class="header-left">
        <h3>🔧 诊断报告</h3>
        <span class="diagnostic-hint">{{ diagnosticModeHint }}</span>
      </div>
      <div class="header-right">
        <button
          class="btn-diagnostic"
          @click="runDiagnostic"
          :disabled="isRunning || !props.projectId"
        >
          <span v-if="isRunning">🔄 分析中...</span>
          <span v-else>▶️ 开始诊断</span>
        </button>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="errorMsg" class="diagnostic-error">
      <span>❌ {{ errorMsg }}</span>
    </div>

    <!-- 诊断结果 -->
    <div v-if="report" class="diagnostic-result">
      <!-- 概览 -->
      <div class="result-overview">
        <div class="overview-card" :class="overallStatus">
          <span class="overview-icon">{{ overallStatusIcon }}</span>
          <div class="overview-info">
            <span class="overview-title">{{ overallStatusText }}</span>
            <span class="overview-mode">{{ isChapterMode ? `第 ${props.chapterNumber} 章` : '全书总览' }}</span>
          </div>
          <span class="overview-score">{{ report.overall_score }}/100</span>
        </div>
      </div>

      <!-- 详细指标 -->
      <div class="result-metrics">
        <!-- 性能指标 - 单章模式 -->
        <div class="metric-section" v-if="isChapterMode">
          <h4>⚡ 性能分析</h4>
          <div class="metric-grid">
            <div class="metric-item">
              <span class="metric-label">总耗时</span>
              <span class="metric-value">{{ formatTime(report.performance.total_time_ms) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">LLM 调用次数</span>
              <span class="metric-value">{{ report.performance.llm_calls ?? '-' }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">Token 消耗</span>
              <span class="metric-value">{{ report.performance.total_tokens ?? '-' }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">RAG 命中率</span>
              <span class="metric-value">{{ formatRate(report.performance.rag_hit_rate) }}</span>
            </div>
          </div>
        </div>

        <!-- 正文指标 - 单章模式 -->
        <div class="metric-section" v-if="isChapterMode && contentMetrics">
          <h4>📝 正文分析</h4>
          <div class="metric-grid">
            <div class="metric-item">
              <span class="metric-label">正文字数</span>
              <span class="metric-value">{{ formatMetricValue(contentMetrics.word_count) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">段落数</span>
              <span class="metric-value">{{ formatMetricValue(contentMetrics.paragraph_count) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">最长段落</span>
              <span class="metric-value">{{ formatChars(contentMetrics.longest_paragraph_chars) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">平均段落</span>
              <span class="metric-value">{{ formatChars(contentMetrics.avg_paragraph_chars) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">对话占比</span>
              <span class="metric-value">{{ formatPercent(contentMetrics.dialogue_ratio) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">占位符残留</span>
              <span class="metric-value" :class="{ 'metric-alert': (contentMetrics.placeholder_count ?? 0) > 0 }">
                {{ formatMetricValue(contentMetrics.placeholder_count) }}
              </span>
            </div>
          </div>
        </div>

        <!-- 性能指标 - 全书模式 -->
        <div class="metric-section" v-else>
          <h4>⚡ 性能总览</h4>
          <div class="metric-grid">
            <div class="metric-item">
              <span class="metric-label">累计耗时</span>
              <span class="metric-value">{{ formatTime(report.performance.total_time_ms) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">平均章节耗时</span>
              <span class="metric-value">{{ formatTime(report.performance.avg_time_ms ?? 0) }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">已生成 / 总章节</span>
              <span class="metric-value">{{ report.performance.generated_chapters ?? 0 }} / {{ report.performance.total_chapters ?? 0 }}</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">平均 RAG 命中率</span>
              <span class="metric-value">{{ formatRate(report.performance.rag_hit_rate) }}</span>
            </div>
          </div>
        </div>

        <!-- 章节明细（全书模式） -->
        <div class="metric-section" v-if="!isChapterMode && report.chapter_details?.length">
          <h4>📖 章节明细</h4>
          <div class="chapter-detail-list">
            <div
              v-for="ch in report.chapter_details"
              :key="ch.chapter_number"
              class="chapter-detail-item"
              :class="getChapterScoreClass(ch.avg_score)"
            >
              <span class="ch-number">第{{ ch.chapter_number }}章</span>
              <span class="ch-title" :title="ch.title">{{ ch.title || '未命名' }}</span>
              <span class="ch-score" v-if="ch.avg_score > 0">{{ ch.avg_score }}分</span>
              <span class="ch-score empty" v-else>-</span>
              <span class="ch-time">{{ formatTime(ch.time_ms) }}</span>
            </div>
          </div>
        </div>

        <!-- 质量问题 -->
        <div class="metric-section">
          <h4>🎯 质量分析</h4>
          <div class="quality-list">
            <div
              v-for="(issue, idx) in report.quality.issues"
              :key="idx"
              class="quality-item"
              :class="issue.severity"
            >
              <span class="quality-icon">{{ getIssueIcon(issue.severity) }}</span>
              <div class="quality-content">
                <span class="quality-type">{{ issue.type }}</span>
                <span class="quality-desc">{{ issue.description }}</span>
              </div>
            </div>
            <div v-if="!report.quality.issues?.length" class="no-issues">
              ✅ 未发现质量问题
            </div>
          </div>
        </div>

        <!-- 建议 -->
        <div class="metric-section">
          <h4>💡 优化建议</h4>
          <ul class="suggestion-list">
            <li v-for="(suggestion, idx) in report.suggestions" :key="idx">
              {{ suggestion }}
            </li>
          </ul>
        </div>
      </div>

      <!-- 原始数据 -->
      <div class="result-raw" v-if="showRawData">
        <h4>📋 原始数据</h4>
        <pre>{{ JSON.stringify(report, null, 2) }}</pre>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!errorMsg" class="diagnostic-empty">
      <div class="empty-icon">🔍</div>
      <p>点击"开始诊断"生成诊断报告</p>
      <p class="empty-hint">{{ isChapterMode ? '诊断当前选中章节的生成质量' : '诊断全书整体生成质量' }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { diagnosticApi } from '@/api/novel'

interface DiagnosticReport {
  mode?: 'chapter' | 'project'
  overall_score: number
  performance: {
    total_time_ms: number
    avg_time_ms?: number
    llm_calls?: number
    total_tokens?: number
    total_chapters?: number
    generated_chapters?: number
    total_versions?: number
    rag_hit_rate: number
    stages?: Record<string, number>
  }
  quality: {
    issues: Array<{
      type: string
      severity: 'error' | 'warning' | 'info'
      description: string
    }>
    content_metrics?: {
      word_count?: number
      paragraph_count?: number
      longest_paragraph_chars?: number
      avg_paragraph_chars?: number
      dialogue_ratio?: number
      placeholder_count?: number
    }
    avg_score?: number
    evaluation_scores?: number[]
    version_count?: number
  }
  chapter_details?: Array<{
    chapter_number: number
    title: string
    time_ms: number
    avg_score: number
    rag_hit_rate: number
    version_count: number
  }>
  suggestions: string[]
}

interface Props {
  projectId?: string
  chapterNumber?: number
}

const props = defineProps<Props>()

const isRunning = ref(false)
const report = ref<DiagnosticReport | null>(null)
const showRawData = ref(false)
const errorMsg = ref('')

const isChapterMode = computed(() => !!props.chapterNumber)

const diagnosticModeHint = computed(() => {
  if (!props.projectId) return '请先打开一个项目'
  return isChapterMode.value
    ? `诊断第 ${props.chapterNumber} 章`
    : '诊断全书生成质量'
})

const overallStatus = computed(() => {
  if (!report.value) return 'unknown'
  const score = report.value.overall_score
  if (score >= 80) return 'good'
  if (score >= 60) return 'warning'
  return 'error'
})

const overallStatusIcon = computed(() => {
  const map: Record<string, string> = {
    good: '✅',
    warning: '⚠️',
    error: '❌',
    unknown: '❓',
  }
  return map[overallStatus.value]
})

const overallStatusText = computed(() => {
  const map: Record<string, string> = {
    good: '状态良好',
    warning: '需要优化',
    error: '存在问题',
    unknown: '等待诊断',
  }
  return map[overallStatus.value]
})

const contentMetrics = computed(() => report.value?.quality.content_metrics)

function formatTime(ms: number): string {
  if (!ms) return '-'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}min`
}

function formatRate(rate: number): string {
  if (!rate) return '-'
  return `${(rate * 100).toFixed(1)}%`
}

function formatMetricValue(value?: number): string {
  if (value === undefined || value === null) return '-'
  return String(value)
}

function formatChars(value?: number): string {
  if (value === undefined || value === null) return '-'
  return `${value} 字`
}

function formatPercent(value?: number): string {
  if (value === undefined || value === null) return '-'
  return `${(value * 100).toFixed(1)}%`
}

function getIssueIcon(severity: string): string {
  const map: Record<string, string> = {
    error: '🔴',
    warning: '🟡',
    info: '🔵',
  }
  return map[severity] || '⚪'
}

function getChapterScoreClass(score: number): string {
  if (!score) return ''
  if (score >= 80) return 'ch-good'
  if (score >= 60) return 'ch-warning'
  return 'ch-error'
}

async function runDiagnostic() {
  if (!props.projectId) {
    errorMsg.value = '请先打开一个项目'
    return
  }
  isRunning.value = true
  report.value = null
  errorMsg.value = ''

  try {
    let data: any
    if (isChapterMode.value) {
      data = await diagnosticApi.diagnoseChapter(props.projectId, props.chapterNumber!)
    } else {
      data = await diagnosticApi.diagnoseProject(props.projectId)
    }
    report.value = data as DiagnosticReport
  } catch (err: any) {
    errorMsg.value = err?.message || '诊断请求失败，请稍后重试'
  } finally {
    isRunning.value = false
  }
}
</script>

<style scoped>
.diagnostic-panel {
  background: var(--md-surface, #fff);
  border: 1px solid var(--md-outline-variant, #e0e0e0);
  border-radius: 12px;
  overflow: hidden;
}

.diagnostic-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  background: var(--md-surface-container, #f5f5f5);
  border-bottom: 1px solid var(--md-outline-variant, #e0e0e0);
}

.header-left h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.diagnostic-hint {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
}

.btn-diagnostic {
  padding: 8px 16px;
  background: var(--md-primary, #1976d2);
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.btn-diagnostic:hover:not(:disabled) {
  background: var(--md-primary, #1565c0);
}

.btn-diagnostic:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.diagnostic-result {
  padding: 16px;
}

.result-overview {
  margin-bottom: 20px;
}

.overview-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
}

.overview-card.good {
  background: var(--md-tertiary-container, #e8f5e9);
}

.overview-card.warning {
  background: var(--md-tertiary-container, #fff8e1);
}

.overview-card.error {
  background: var(--md-error-container, #ffebee);
}

.overview-icon {
  font-size: 32px;
}

.overview-info {
  display: flex;
  flex-direction: column;
}

.overview-title {
  font-size: 16px;
  font-weight: 600;
}

.overview-mode {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
}

.overview-score {
  margin-left: auto;
  font-size: 24px;
  font-weight: 700;
  color: var(--md-primary, #1976d2);
}

.result-metrics {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.metric-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--md-on-surface, #333);
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  padding: 12px;
  background: var(--md-surface-container-low, #fafafa);
  border-radius: 8px;
}

.metric-label {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
}

.metric-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--md-primary, #1976d2);
}

.metric-value.metric-alert {
  color: var(--md-error, #d32f2f);
}

/* 章节明细 */
.chapter-detail-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 240px;
  overflow-y: auto;
}

.chapter-detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--md-surface-container-low, #fafafa);
  font-size: 13px;
}

.chapter-detail-item.ch-error {
  background: var(--md-error-container, #ffebee);
}

.chapter-detail-item.ch-warning {
  background: var(--md-tertiary-container, #fff8e1);
}

.chapter-detail-item.ch-good {
  background: var(--md-tertiary-container, #e8f5e9);
}

.ch-number {
  font-weight: 600;
  min-width: 56px;
  color: var(--md-on-surface, #333);
}

.ch-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--md-on-surface-variant, #666);
}

.ch-score {
  font-weight: 600;
  min-width: 40px;
  text-align: right;
  color: var(--md-primary, #1976d2);
}

.ch-score.empty {
  color: var(--md-on-surface-variant, #999);
}

.ch-time {
  min-width: 50px;
  text-align: right;
  font-size: 12px;
  color: var(--md-on-surface-variant, #888);
}

.quality-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quality-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
}

.quality-item.error {
  background: var(--md-error-container, #ffebee);
}

.quality-item.warning {
  background: var(--md-tertiary-container, #fff8e1);
}

.quality-item.info {
  background: var(--md-primary-container, #e3f2fd);
}

.quality-icon {
  font-size: 16px;
}

.quality-content {
  display: flex;
  flex-direction: column;
}

.quality-type {
  font-size: 13px;
  font-weight: 500;
}

.quality-desc {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
}

.no-issues {
  padding: 16px;
  text-align: center;
  color: var(--md-tertiary, #4caf50);
}

.suggestion-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: var(--md-on-surface-variant, #666);
}

.suggestion-list li {
  margin-bottom: 6px;
}

.result-raw {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--md-outline-variant, #e0e0e0);
}

.result-raw h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
}

.result-raw pre {
  background: var(--md-surface-container, #f5f5f5);
  padding: 12px;
  border-radius: 8px;
  font-size: 11px;
  overflow-x: auto;
}

.diagnostic-error {
  padding: 16px;
  margin: 12px 16px;
  background: var(--md-error-container, #ffebee);
  border-radius: 8px;
  color: var(--md-on-error-container, #c62828);
  font-size: 13px;
}

.diagnostic-empty {
  padding: 40px;
  text-align: center;
  color: var(--md-on-surface-variant, #999);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.empty-hint {
  font-size: 12px;
  margin-top: 8px;
}
</style>

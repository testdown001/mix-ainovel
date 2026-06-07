<!-- AIMETA P=章节质量审核结果_审核展示|R=审核结果展示|NR=不含审核逻辑|GatekeeperResult|X=ui|A=审核展示|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="gatekeeper-result">
    <!-- 审核状态头部 -->
    <div class="result-header" :class="{ approved: review?.approved, rejected: !review?.approved }">
      <span class="result-icon">{{ review?.approved ? '✅' : '🚫' }}</span>
      <span class="result-title">{{ review?.approved ? '审核通过' : '需要修改' }}</span>
      <span class="score-badge">综合评分: {{ review?.overall_score || 0 }}</span>
    </div>

    <!-- 评分维度卡片 -->
    <div class="score-cards">
      <div
        v-for="(score, key) in review?.scores"
        :key="key"
        class="score-card"
        :class="getScoreClass(score)"
      >
        <div class="score-label">{{ dimensionLabels[key] || key }}</div>
        <div class="score-value">{{ score }}</div>
      </div>
    </div>

    <!-- 总体评价 -->
    <div v-if="review?.review_comment" class="review-comment">
      <h4>总体评价</h4>
      <p>{{ review.review_comment }}</p>
    </div>

    <!-- 问题列表 -->
    <div v-if="review?.issues?.length" class="issues-panel">
      <h4>发现问题 ({{ review.issues.length }})</h4>
      <div v-for="(issue, index) in review.issues" :key="index" class="issue-item">
        <div class="issue-header">
          <span class="issue-type" :class="issue.severity">{{ dimensionLabels[issue.type] || issue.type }}</span>
          <span class="issue-severity" :class="`severity-${issue.severity}`">
            {{ severityLabels[issue.severity] || issue.severity }}
          </span>
        </div>
        <p class="issue-desc">{{ issue.description }}</p>
        <p v-if="issue.suggestion" class="issue-suggestion">
          <span class="suggestion-label">建议:</span> {{ issue.suggestion }}
        </p>
      </div>
    </div>

    <!-- 操作按钮 -->
    <div class="action-buttons">
      <button
        v-if="!review?.approved"
        @click="$emit('regenerate')"
        class="md-btn md-btn-filled md-ripple"
        :disabled="loading"
      >
        <svg v-if="loading" class="w-4 h-4 animate-spin mr-2" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
        </svg>
        {{ loading ? '重新生成中...' : '重新生成' }}
      </button>
      <button
        @click="$emit('close')"
        class="md-btn md-btn-tonal md-ripple"
      >
        关闭
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Issue {
  type: string
  severity: 'low' | 'medium' | 'high'
  description: string
  suggestion?: string
}

interface Review {
  approved: boolean
  overall_score: number
  scores: Record<string, number>
  issues: Issue[]
  review_comment?: string
}

const props = defineProps<{
  review: Review | null
  loading?: boolean
}>()

defineEmits<{
  (e: 'close'): void
  (e: 'regenerate'): void
}>()

const dimensionLabels: Record<string, string> = {
  consistency: '剧情一致性',
  character_depth: '角色立体度',
  pacing: '节奏张力',
  foreshadowing: '伏笔呼应',
  prose_quality: '文笔质量',
  emotion_curve: '情绪曲线',
}

const severityLabels: Record<string, string> = {
  low: '轻微',
  medium: '中等',
  high: '严重',
}

function getScoreClass(score: number): string {
  if (score >= 80) return 'score-excellent'
  if (score >= 60) return 'score-good'
  if (score >= 40) return 'score-fair'
  return 'score-poor'
}
</script>

<style scoped>
.gatekeeper-result {
  padding: 16px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 16px;
}

.result-header.approved {
  background-color: var(--md-success-container, #e8f5e9);
  color: var(--md-on-success-container, #1b5e20);
}

.result-header.rejected {
  background-color: var(--md-error-container, #ffebee);
  color: var(--md-on-error-container, #b71c1c);
}

.result-icon {
  font-size: 24px;
}

.result-title {
  font-size: 18px;
  font-weight: 600;
}

.score-badge {
  margin-left: auto;
  padding: 4px 12px;
  border-radius: 16px;
  background-color: rgba(0, 0, 0, 0.1);
  font-weight: 500;
}

.score-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.score-card {
  padding: 12px;
  border-radius: 8px;
  text-align: center;
  background-color: var(--md-surface-container, #f5f5f5);
}

.score-card.score-excellent {
  background-color: var(--md-success-container, #e8f5e9);
}

.score-card.score-good {
  background-color: var(--md-secondary-container, #e3f2fd);
}

.score-card.score-fair {
  background-color: var(--md-tertiary-container, #fff3e0);
}

.score-card.score-poor {
  background-color: var(--md-error-container, #ffebee);
}

.score-label {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
  margin-bottom: 4px;
}

.score-value {
  font-size: 24px;
  font-weight: 700;
}

.review-comment {
  padding: 12px;
  border-radius: 8px;
  background-color: var(--md-surface-container, #f5f5f5);
  margin-bottom: 16px;
}

.review-comment h4 {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
}

.review-comment p {
  font-size: 14px;
  line-height: 1.6;
  color: var(--md-on-surface, #333);
}

.issues-panel {
  margin-bottom: 16px;
}

.issues-panel h4 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--md-on-surface, #333);
}

.issue-item {
  padding: 12px;
  border-radius: 8px;
  background-color: var(--md-surface-container, #f5f5f5);
  margin-bottom: 8px;
}

.issue-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.issue-type {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  background-color: var(--md-primary-container, #e3f2fd);
  color: var(--md-on-primary-container, #1565c0);
}

.issue-severity {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
}

.issue-severity.severity-high {
  background-color: var(--md-error-container, #ffebee);
  color: var(--md-on-error-container, #b71c1c);
}

.issue-severity.severity-medium {
  background-color: var(--md-tertiary-container, #fff3e0);
  color: var(--md-on-tertiary-container, #e65100);
}

.issue-severity.severity-low {
  background-color: var(--md-secondary-container, #e3f2fd);
  color: var(--md-on-secondary-container, #1565c0);
}

.issue-desc {
  font-size: 14px;
  color: var(--md-on-surface, #333);
  margin-bottom: 8px;
}

.issue-suggestion {
  font-size: 13px;
  color: var(--md-on-surface-variant, #666);
  padding: 8px;
  border-radius: 4px;
  background-color: rgba(0, 0, 0, 0.05);
}

.suggestion-label {
  font-weight: 600;
  color: var(--md-primary, #1976d2);
}

.action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid var(--md-outline-variant, #e0e0e0);
}

@media (max-width: 600px) {
  .score-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>

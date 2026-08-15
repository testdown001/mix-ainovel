<!-- AIMETA P=蓝图审稿卡|R=商业量表审稿报告暗色渲染|NR=不含生成|E=component:BlueprintReviewCard|X=ui|A=审稿卡|D=vue|S=dom|RD=./README.ai -->
<template>
  <div v-if="report" class="review-card">
    <div class="review-head">
      <div class="review-score" :style="{ color: scoreColor }">{{ score }}</div>
      <div class="review-verdict">
        <span v-if="report.revised" class="review-chip">已经过一轮定向修订</span>
        <p>{{ report.verdict || '暂无总评' }}</p>
      </div>
    </div>
    <div v-if="dimEntries.length" class="review-dims">
      <div v-for="[key, value] in dimEntries" :key="key" class="review-dim">
        <span>{{ dimLabel(key) }}</span>
        <strong :style="{ color: numColor(Number(value)) }">{{ value }}</strong>
      </div>
    </div>
    <div v-if="report.issues?.length" class="review-issues">
      <h4>待改进（{{ report.issues.length }}）</h4>
      <div v-for="(issue, i) in report.issues" :key="i" class="review-issue">
        <div class="review-issue-meta">
          <span class="review-chip" :class="severityClass(issue.severity)">{{ issue.severity || '低' }}</span>
          <span>{{ issue.target }}</span>
        </div>
        <p>{{ issue.problem }}</p>
        <p v-if="issue.fix_hint" class="review-hint">修订方向：{{ issue.fix_hint }}</p>
      </div>
    </div>
    <div v-if="report.strengths?.length" class="review-strengths">
      <h4>亮点</h4>
      <p v-for="(s, i) in report.strengths" :key="i">· {{ s }}</p>
    </div>
  </div>
  <p v-else class="review-empty">快速成纲未跑审稿，深度打磨后会出现商业量表报告。</p>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BlueprintReviewReport } from '@/api/novel'

const props = defineProps<{ report?: BlueprintReviewReport | null }>()

const LABELS: Record<string, string> = {
  hook: '开篇钩子',
  coolpoint_density: '爽点密度',
  conflict_sustain: '冲突可持续',
  character_want: '人物欲望',
  golden_finger: '金手指',
  foreshadow: '伏笔',
  volume_rhythm: '分卷节奏',
  anticipation_delivery: '期待感兑现',
  toxic_recheck: '毒点复查',
}

const score = computed(() => Number(props.report?.total_score) || 0)
const scoreColor = computed(() => numColor(score.value))
const dimEntries = computed(() =>
  Object.entries(props.report?.dimension_scores || {}).filter(([, v]) => typeof v === 'number'),
)

function dimLabel(key: string) {
  return LABELS[key] || key
}
function numColor(n: number) {
  if (n >= 70) return '#34d399'
  if (n >= 55) return '#fbbf24'
  return '#f87171'
}
function severityClass(severity?: string) {
  if ((severity || '').includes('高')) return 'sev-high'
  if ((severity || '').includes('中')) return 'sev-mid'
  return 'sev-low'
}
</script>

<style scoped>
.review-card { display: flex; flex-direction: column; gap: 12px; }
.review-head { display: flex; gap: 14px; align-items: flex-start; }
.review-score { font-size: 2.2rem; font-weight: 800; line-height: 1; }
.review-verdict { color: var(--md-on-surface-variant); font-size: 0.875rem; }
.review-chip {
  display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 999px;
  background: #1e1b4b; color: #c7d2fe; margin-bottom: 6px;
}
.sev-high { background: #3f1d1d; color: #fca5a5; }
.sev-mid { background: #3d2e12; color: #fcd34d; }
.sev-low { background: #1f2937; color: #9ca3af; }
.review-dims { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.review-dim {
  background: var(--md-surface-container); border-radius: 8px; padding: 8px;
  display: flex; justify-content: space-between; font-size: 12px; color: var(--md-on-surface-variant);
}
.review-issues h4, .review-strengths h4 { font-size: 13px; margin-bottom: 8px; color: var(--md-on-surface); }
.review-issue {
  border: 1px solid var(--md-outline-variant); border-radius: 8px; padding: 8px; margin-bottom: 8px;
  font-size: 13px; color: var(--md-on-surface);
}
.review-issue-meta { display: flex; gap: 8px; font-size: 11px; color: var(--md-on-surface-variant); margin-bottom: 4px; }
.review-hint { color: #6ee7b7; font-size: 12px; margin-top: 4px; }
.review-strengths p { color: #6ee7b7; font-size: 13px; }
.review-empty { color: var(--md-on-surface-variant); font-size: 13px; text-align: center; padding: 24px 8px; }
</style>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NCollapse, NCollapseItem } from 'naive-ui'
import type { ChapterVersion } from '@/api/novel'
import { chapterContentHash, readerReviewMatchesContent } from '@/utils/readerReviewFreshness'

const props = defineProps<{ version?: ChapterVersion }>()
const reviews = computed(() => props.version?.metadata?.review_summaries ?? {})
const finalReview = computed(() => reviews.value.quality_detection?.status === 'completed'
  ? reviews.value.quality_detection.emotional_review : null)
const revision = computed(() => reviews.value.combined_revision)
const review = computed(() => finalReview.value ?? revision.value?.emotional_review)
const issues = computed(() => Array.isArray(review.value?.issues) ? review.value.issues : [])
const passages = computed(() => Array.isArray(review.value?.protected_passages) ? review.value.protected_passages : [])
const edits = computed(() => revision.value?.applied && Array.isArray(revision.value.edits) ? revision.value.edits : [])
const labels: Record<string, string> = {
  stakes: '人物得失', character_choice: '选择依据', transition: '情绪转折', aftermath: '事件余波', subtext: '言外之意',
}
const contentHash = ref<string | null>(null)
let hashSequence = 0
watch(() => props.version?.content, async (content) => {
  const sequence = ++hashSequence
  contentHash.value = null
  if (typeof content !== 'string') return
  const hash = await chapterContentHash(content)
  if (sequence === hashSequence) contentHash.value = hash
}, { immediate: true, flush: 'sync' })
const readerSource = computed(() => reviews.value.reader_simulator)
const readerReport = computed(() => readerReviewMatchesContent(readerSource.value, contentHash.value)
  ? readerSource.value : null)
const readerLabels: Record<string, string> = {
  casual: '休闲读者', hardcore: '逻辑读者', emotional: '情感读者', thrill_seeker: '爽点读者', critic: '文字读者',
}
const textItems = (value: unknown): string[] => Array.isArray(value)
  ? value.filter((item): item is string => typeof item === 'string' && !!item.trim()) : []
const readerFeedbacks = computed(() => Object.entries(readerReport.value?.reader_feedbacks ?? {})
  .filter(([, feedback]) => feedback && typeof feedback === 'object' && (feedback as Record<string, unknown>).status !== 'unavailable')
  .map(([type, raw]) => {
    const feedback = raw as Record<string, unknown>
    return {
      type,
      label: readerLabels[type] ?? '模拟读者',
      wouldContinue: typeof feedback.would_continue === 'boolean' ? feedback.would_continue : null,
      risk: typeof feedback.abandon_risk === 'number' && Number.isFinite(feedback.abandon_risk)
        && feedback.abandon_risk >= 0 && feedback.abandon_risk <= 10 ? feedback.abandon_risk : null,
      comment: typeof feedback.comment === 'string' ? feedback.comment : '',
      complaints: textItems(feedback.complaints),
    }
  }))
</script>

<template>
  <NCollapse v-if="review || readerSource" class="review-panel">
    <NCollapseItem v-if="review" title="情感与节奏审校" name="emotional-review">
      <p class="review-note">{{ finalReview ? '针对生成完成时的正文' : '修订前的审校记录' }} · AI 意见供创作取舍参考</p>
      <p v-if="review.summary">{{ review.summary }}</p>
      <div v-for="(issue, index) in issues" :key="`issue-${index}`" class="review-entry">
        <strong>{{ labels[issue.dimension] ?? '情感表达' }}{{ issue.status === 'context_needed' ? ' · 需要核对前文' : '' }}</strong>
        <blockquote>{{ issue.quote }}</blockquote>
        <p>{{ issue.reason }}</p>
        <p>{{ issue.suggestion }}</p>
      </div>
      <div v-if="passages.length" class="review-entry">
        <strong>值得保留的表达</strong>
        <div v-for="(passage, index) in passages" :key="`passage-${index}`">
          <blockquote>{{ passage.quote }}</blockquote>
          <p>{{ passage.reason }}</p>
        </div>
      </div>
      <div v-if="edits.length" class="review-entry">
        <strong>本次局部修订对照</strong>
        <p class="review-note">记录修订当时的变化，之后可能经过一致性校对或润色。</p>
        <div v-for="(edit, index) in edits" :key="`edit-${index}`" class="review-edit">
          <p>{{ edit.reason }}</p>
          <p><span class="review-note">原句：</span>{{ edit.before }}</p>
          <p><span class="review-note">改为：</span>{{ edit.after || '删除这处冗余' }}</p>
        </div>
      </div>
    </NCollapseItem>
    <NCollapseItem v-if="readerSource" title="AI 试读：人物牵挂与追读" name="reader-simulation">
      <p class="review-note">AI 模拟阅读意见，供创作取舍参考；不代表真实读者的留存或追读率。</p>
      <p v-if="!readerReport" class="review-note">这份试读尚未核对到当前正文，暂不展示结论。</p>
      <template v-else>
        <p v-if="readerReport.status === 'partial'" class="review-note">部分模拟读者未能完成试读，仅展示已返回的意见。</p>
        <div v-for="feedback in readerFeedbacks" :key="feedback.type" class="review-entry">
          <strong>{{ feedback.label }}</strong>
          <p>继续阅读：{{ feedback.wouldContinue === null ? '未提供判断' : feedback.wouldContinue ? '想继续' : '兴趣不足' }}<span v-if="feedback.risk !== null"> · AI 判断的弃读风险 {{ feedback.risk }}/10</span></p>
          <p v-if="feedback.comment">{{ feedback.comment }}</p>
          <template v-if="feedback.complaints.length">
            <p class="review-note">具体意见（未提供逐字定位，需结合正文核对）</p>
            <ul><li v-for="(complaint, index) in feedback.complaints" :key="index">{{ complaint }}</li></ul>
          </template>
        </div>
        <p v-if="!readerFeedbacks.length" class="review-note">本次没有可用的模拟读者意见。</p>
      </template>
    </NCollapseItem>
  </NCollapse>
</template>

<style scoped>
.review-panel { padding: 1rem; border: 1px solid var(--md-outline-variant); border-radius: var(--md-radius-lg); }
.review-note { color: var(--md-on-surface-variant); font-size: 0.85rem; }
.review-entry { margin-top: 1rem; }
.review-entry p { margin: 0.4rem 0; }
.review-edit { margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px solid var(--md-outline-variant); }
blockquote { margin: 0.75rem 0; padding-left: 0.75rem; border-left: 3px solid var(--md-outline-variant); white-space: pre-wrap; }
</style>

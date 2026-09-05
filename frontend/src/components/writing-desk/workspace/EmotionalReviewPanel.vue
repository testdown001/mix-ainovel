<script setup lang="ts">
import { computed } from 'vue'
import { NCollapse, NCollapseItem } from 'naive-ui'
import type { ChapterVersion } from '@/api/novel'

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
</script>

<template>
  <NCollapse v-if="review" class="review-panel">
    <NCollapseItem title="情感与节奏审校" name="emotional-review">
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

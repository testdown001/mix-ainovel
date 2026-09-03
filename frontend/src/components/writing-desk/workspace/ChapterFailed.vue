<!-- AIMETA P=生成失败_生成错误状态|R=错误提示_重试_剧情推演|NR=不含生成逻辑|E=component:ChapterFailed|X=internal|A=错误状态|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="h-full overflow-y-auto">
    <!-- 失败后保留情节梳理供高级排查，但主动作始终是重试正文 -->
    <div v-if="prediction" class="p-6 space-y-4">
      <!-- 失败提示 -->
      <div class="md-card md-card-outlined p-4 flex items-center gap-3" style="border-radius: var(--md-radius-lg); border-color: var(--md-error);">
        <svg class="w-5 h-5 shrink-0" style="color: var(--md-error);" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
        </svg>
        <p class="md-body-medium md-on-surface-variant">上次正文生成失败，可直接重试；系统会自动复用或更新情节梳理。</p>
      </div>

      <h3 class="md-title-medium font-semibold mb-3">情节梳理（高级）</h3>
      <div v-for="section in predictionSections" :key="section.key" class="md-card md-card-outlined p-4" style="border-radius: var(--md-radius-lg);">
        <h4 class="md-title-small font-medium mb-2" :style="{ color: section.color }">{{ section.label }}</h4>
        <ul class="space-y-1">
          <li v-for="(item, i) in section.items" :key="i" class="md-body-medium md-on-surface-variant flex gap-2">
            <span class="shrink-0">{{ section.icon }}</span>
            <span>{{ item }}</span>
          </li>
        </ul>
      </div>

      <div class="flex items-center gap-3 pt-2">
        <button
          @click="handleGenerate"
          :disabled="predictionGenerating"
          class="md-btn md-btn-tonal md-ripple flex items-center gap-2 disabled:opacity-50"
        >
          {{ predictionGenerating ? '梳理中...' : '重新梳理' }}
        </button>
        <button
          @click="$emit('generateChapter', chapterNumber)"
          :disabled="predictionGenerating || generatingChapter === chapterNumber"
          class="md-btn md-btn-filled md-ripple flex items-center gap-2 disabled:opacity-50"
        >
          {{ generatingChapter === chapterNumber ? '重试中...' : '重试生成' }}
        </button>
      </div>
    </div>

    <!-- 无推演时的失败状态 -->
    <div v-else class="h-full flex items-center justify-center">
      <div class="md-card md-card-outlined p-8 text-center max-w-md" style="border-radius: var(--md-radius-xl);">
        <div class="w-16 h-16 rounded-full mx-auto flex items-center justify-center mb-5" style="background-color: var(--md-error-container);">
          <svg class="w-7 h-7" style="color: var(--md-error);" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
          </svg>
        </div>
        <h3 class="md-headline-small font-semibold mb-3">第{{ chapterNumber }}章生成失败</h3>
        <p class="md-body-medium md-on-surface-variant mb-6">直接重试即可；系统会先自动梳理情节，再生成正文并进行一致性检查。</p>
        <div class="flex items-center gap-3 justify-center">
          <button
            @click="$emit('generateChapter', chapterNumber)"
            :disabled="predictionGenerating || generatingChapter === chapterNumber"
            class="md-btn md-btn-filled md-ripple flex items-center gap-2 disabled:opacity-50"
            style="background-color: var(--md-error); color: var(--md-on-error);"
          >
            {{ predictionGenerating ? '正在梳理情节...' : generatingChapter === chapterNumber ? '重试中...' : '重试生成正文' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChapterOutline, ChapterPrediction } from '@/api/novel'

interface Props {
  chapterNumber: number
  generatingChapter: number | null
  outline?: ChapterOutline | null
  projectId?: string
  predictionGenerating?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['generateChapter', 'requestPrediction'])

const prediction = computed<ChapterPrediction | null>(
  () => props.outline?.metadata?.prediction ?? null
)

const predictionSections = computed(() => {
  const p = prediction.value
  if (!p) return []
  return [
    { key: 'key_points', label: '章节要点', icon: '•', color: 'var(--md-primary)', items: p.key_points || [] },
    { key: 'cool_points', label: '爽点设计', icon: '⚡', color: 'var(--md-tertiary)', items: p.cool_points || [] },
    { key: 'foreshadowing_hooks', label: '伏笔/钩子', icon: '🪝', color: 'var(--md-secondary)', items: p.foreshadowing_hooks || [] },
    { key: 'foreshadowing_targets', label: '需回收伏笔', icon: '🎯', color: 'var(--md-error)', items: p.foreshadowing_targets || [] },
    { key: 'limitations', label: '章节限制', icon: '⚠', color: 'var(--md-on-surface-variant)', items: p.limitations || [] },
  ].filter(s => s.items.length > 0)
})

const handleGenerate = async () => {
  if (!props.projectId || props.predictionGenerating) return
  emit('requestPrediction', props.chapterNumber)
}
</script>

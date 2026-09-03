<!-- AIMETA P=空章节_未选择章节状态|R=空状态提示_剧情推演|NR=不含内容展示|E=component:ChapterEmpty|X=internal|A=空状态|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="h-full overflow-y-auto flex items-center justify-center p-6">
    <div class="w-full max-w-lg space-y-4">
      <div class="md-card md-card-outlined p-8 text-center" style="border-radius: var(--md-radius-xl);">
        <div class="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4" style="background-color: var(--md-surface-container);">
          <svg class="w-7 h-7" style="color: var(--md-on-surface-variant);" fill="currentColor" viewBox="0 0 20 20">
            <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
          </svg>
        </div>
        <h3 class="md-title-medium font-semibold mb-2">生成本章正文</h3>

        <div v-if="canGenerate">
          <p class="md-body-medium md-on-surface-variant mb-4">
            系统会自动梳理情节、生成正文并完成一致性检查。
          </p>
          <div class="w-full mb-4 text-left">
            <label class="md-label-large font-medium mb-1 block" style="color: var(--md-on-surface);">作者备注（可选）</label>
            <textarea v-model="writingNotes" rows="2" class="md-textarea w-full"
              placeholder="例如：这章用倒叙手法、重点刻画反派心理..."></textarea>
          </div>
          <button
            @click="$emit('generateChapter', chapterNumber, writingNotes || undefined)"
            :disabled="generationBusy"
            class="md-btn md-btn-filled md-ripple inline-flex items-center gap-2 disabled:opacity-50"
          >
            {{ generationButtonLabel }}
          </button>
        </div>

        <div v-else>
          <p class="md-body-medium md-on-surface-variant mb-4">请先完成前面的章节，才能生成此章节</p>
          <div class="md-chip md-chip-assist">按顺序生成</div>
        </div>
      </div>

      <details class="md-card md-card-outlined p-4" style="border-radius: var(--md-radius-lg);">
        <summary class="md-label-large cursor-pointer" style="color: var(--md-on-surface-variant);">
          高级选项 · {{ prediction ? '查看情节梳理' : '提前梳理情节' }}
        </summary>
        <div class="pt-4 space-y-3">
          <template v-if="prediction">
            <div v-for="section in predictionSections" :key="section.key" class="md-card md-card-filled p-3">
              <h4 class="md-title-small font-medium mb-2" :style="{ color: section.color }">{{ section.label }}</h4>
              <ul class="space-y-1">
                <li v-for="(item, i) in section.items" :key="i" class="md-body-small md-on-surface-variant flex gap-2">
                  <span>{{ section.icon }}</span><span>{{ item }}</span>
                </li>
              </ul>
            </div>
            <div v-if="prediction.beats?.length" class="space-y-2">
              <h4 class="md-title-small font-medium">节拍编排</h4>
              <div v-for="(beat, i) in prediction.beats" :key="i" class="flex items-start gap-2">
                <span class="shrink-0 w-5 h-5 rounded-full text-xs flex items-center justify-center text-white font-medium" :style="{ backgroundColor: beatColor(beat.type) }">{{ i + 1 }}</span>
                <p class="md-body-small md-on-surface-variant">
                  <strong :style="{ color: beatColor(beat.type) }">{{ beatLabel(beat.type) }}</strong>
                  {{ beat.content }} <span style="color: var(--md-outline);">{{ beat.emotion }}</span>
                </p>
              </div>
            </div>
          </template>
          <p v-else class="md-body-small md-on-surface-variant">无需提前操作；点击生成正文时系统会自动完成。</p>
          <button
            type="button"
            @click="handleGenerate"
            :disabled="generationBusy"
            class="md-btn md-btn-tonal md-ripple disabled:opacity-50"
          >
            {{ predictionGenerating ? '正在梳理…' : prediction ? '重新梳理情节' : '提前梳理情节' }}
          </button>
        </div>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { ChapterOutline, ChapterPrediction } from '@/api/novel'

const beatColorMap: Record<string, string> = {
  setup: '#6B7280', provoke: '#F59E0B', twist: '#8B5CF6', payoff: '#EF4444', hook: '#3B82F6'
}
const beatLabelMap: Record<string, string> = {
  setup: '铺垫', provoke: '激化', twist: '转折', payoff: '爆发', hook: '悬念'
}
const beatColor = (type: string) => beatColorMap[type] || '#6B7280'
const beatLabel = (type: string) => beatLabelMap[type] || type

interface Props {
  chapterNumber: number
  generatingChapter: number | null
  canGenerate: boolean
  outline?: ChapterOutline | null
  projectId?: string
  templatePrompt?: string
  predictionGenerating?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['generateChapter', 'requestPrediction'])
const writingNotes = ref('')

watch(() => props.templatePrompt, (val) => {
  if (val) {
    writingNotes.value = writingNotes.value
      ? writingNotes.value + '\n' + val
      : val
  }
})

const prediction = computed<ChapterPrediction | null>(
  () => props.outline?.metadata?.prediction ?? null
)
const generationBusy = computed(
  () => props.predictionGenerating || props.generatingChapter === props.chapterNumber,
)
const generationButtonLabel = computed(() => {
  if (props.predictionGenerating) return '正在梳理情节…'
  if (props.generatingChapter === props.chapterNumber) return '正在生成正文…'
  return '生成本章正文'
})

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

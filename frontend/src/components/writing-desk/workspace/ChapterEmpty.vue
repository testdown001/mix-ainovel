<!-- AIMETA P=空章节_未选择章节状态|R=空状态提示_剧情推演|NR=不含内容展示|E=component:ChapterEmpty|X=internal|A=空状态|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="h-full overflow-y-auto">
    <!-- 剧情推演区域 -->
    <div v-if="prediction" class="p-6 space-y-4">
      <h3 class="md-title-medium font-semibold mb-3">剧情推演</h3>

      <div v-for="section in predictionSections" :key="section.key" class="md-card md-card-outlined p-4" style="border-radius: var(--md-radius-lg);">
        <h4 class="md-title-small font-medium mb-2" :style="{ color: section.color }">{{ section.label }}</h4>
        <ul class="space-y-1">
          <li v-for="(item, i) in section.items" :key="i" class="md-body-medium md-on-surface-variant flex gap-2">
            <span class="shrink-0">{{ section.icon }}</span>
            <span>{{ item }}</span>
          </li>
        </ul>
      </div>

      <!-- Beats 节拍编排 -->
      <div v-if="prediction?.beats?.length" class="md-card md-card-outlined p-4" style="border-radius: var(--md-radius-lg);">
        <h4 class="md-title-small font-medium mb-2" style="color: var(--md-primary)">节拍编排</h4>
        <div class="space-y-2">
          <div v-for="(beat, i) in prediction.beats" :key="i" class="flex items-start gap-2">
            <span class="shrink-0 w-5 h-5 rounded-full text-xs flex items-center justify-center text-white font-medium"
                  :style="{ backgroundColor: beatColor(beat.type) }">{{ i + 1 }}</span>
            <div>
              <span class="md-label-small font-medium" :style="{ color: beatColor(beat.type) }">{{ beatLabel(beat.type) }}</span>
              <span class="md-body-small md-on-surface-variant ml-1">{{ beat.content }}</span>
              <span class="md-label-small ml-1" style="color: var(--md-outline);">({{ beat.emotion }})</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 作者备注 -->
      <div v-if="canGenerate" class="md-card md-card-outlined p-4" style="border-radius: var(--md-radius-lg);">
        <label class="md-label-large font-medium mb-2 block" style="color: var(--md-on-surface);">作者备注（可选）</label>
        <textarea v-model="writingNotes" rows="2" class="md-textarea w-full"
          placeholder="例如：这章用倒叙手法、重点刻画反派心理..."></textarea>
      </div>

      <!-- 操作按钮 -->
      <div class="flex items-center gap-3 pt-2">
        <button
          @click="handleGenerate"
          :disabled="generating"
          class="md-btn md-btn-tonal md-ripple flex items-center gap-2 disabled:opacity-50"
        >
          <svg v-if="generating" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
          </svg>
          {{ generating ? '推演中...' : '重新推演' }}
        </button>
        <button
          v-if="canGenerate"
          @click="$emit('generateChapter', chapterNumber, writingNotes || undefined)"
          :disabled="generatingChapter === chapterNumber"
          class="md-btn md-btn-filled md-ripple flex items-center gap-2 disabled:opacity-50"
        >
          {{ generatingChapter === chapterNumber ? '生成中...' : '开始创作' }}
        </button>
      </div>
    </div>

    <!-- 无推演时的空状态 -->
    <div v-else class="h-full flex items-center justify-center">
      <div class="md-card md-card-outlined p-8 text-center max-w-md" style="border-radius: var(--md-radius-xl);">
        <div class="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4" style="background-color: var(--md-surface-container);">
          <svg class="w-7 h-7" style="color: var(--md-on-surface-variant);" fill="currentColor" viewBox="0 0 20 20">
            <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
          </svg>
        </div>
        <h3 class="md-title-medium font-semibold mb-2">开始创作</h3>

        <div v-if="canGenerate">
          <p class="md-body-medium md-on-surface-variant mb-4">可先生成剧情推演，再开始创作</p>
          <div class="w-full mb-4 text-left">
            <label class="md-label-large font-medium mb-1 block" style="color: var(--md-on-surface);">作者备注（可选）</label>
            <textarea v-model="writingNotes" rows="2" class="md-textarea w-full"
              placeholder="例如：这章用倒叙手法、重点刻画反派心理..."></textarea>
          </div>
          <div class="flex items-center gap-3 justify-center">
            <button
              @click="handleGenerate"
              :disabled="generating"
              class="md-btn md-btn-tonal md-ripple flex items-center gap-2 disabled:opacity-50"
            >
              {{ generating ? '推演中...' : '剧情推演' }}
            </button>
            <button
              @click="$emit('generateChapter', chapterNumber, writingNotes || undefined)"
              :disabled="generatingChapter === chapterNumber"
              class="md-btn md-btn-filled md-ripple flex items-center gap-2 disabled:opacity-50"
            >
              {{ generatingChapter === chapterNumber ? '生成中...' : '开始创作' }}
            </button>
          </div>
        </div>

        <div v-else>
          <p class="md-body-medium md-on-surface-variant mb-4">请先完成前面的章节，才能生成此章节</p>
          <div class="md-chip md-chip-assist">
            <svg class="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clip-rule="evenodd"></path>
            </svg>
            按顺序生成
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { NovelAPI } from '@/api/novel'
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
}

const props = defineProps<Props>()
defineEmits(['generateChapter'])

const generating = ref(false)
const writingNotes = ref('')

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
  if (!props.projectId || generating.value) return
  generating.value = true
  try {
    const result = await NovelAPI.generatePrediction(props.projectId, props.chapterNumber)
    // 直接更新 outline.metadata 以触发响应式更新
    if (props.outline) {
      props.outline.metadata = { ...props.outline.metadata, prediction: result }
    }
  } catch (e: any) {
    console.error('剧情推演失败:', e)
  } finally {
    generating.value = false
  }
}
</script>

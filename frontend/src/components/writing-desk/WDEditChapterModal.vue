<!-- AIMETA P=编辑章节弹窗_章节信息编辑|R=章节编辑表单|NR=不含内容生成|E=component:WDEditChapterModal|X=ui|A=编辑弹窗|D=vue|S=dom|RD=./README.ai -->
<template>
  <div v-if="show" class="md-dialog-overlay" @click.self="$emit('close')">
    <div class="md-dialog w-full max-w-lg m3-edit-dialog p-8 max-h-[85vh] overflow-y-auto" :class="show ? 'scale-100 opacity-100' : 'scale-95 opacity-0'">
      <div class="flex justify-between items-center mb-6">
        <h2 class="md-headline-small font-semibold">编辑章节大纲</h2>
        <button @click="$emit('close')" class="md-icon-btn md-ripple">
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </div>

      <div v-if="editableChapter" class="space-y-6">
        <div>
          <label for="chapter-title" class="md-text-field-label mb-2">章节标题</label>
          <input
            type="text"
            id="chapter-title"
            v-model="editableChapter.title"
            class="md-text-field-input w-full"
            placeholder="请输入章节标题"
          />
        </div>
        <div>
          <label for="chapter-summary" class="md-text-field-label mb-2">章节摘要</label>
          <textarea
            id="chapter-summary"
            v-model="editableChapter.summary"
            rows="5"
            class="md-textarea w-full"
            placeholder="请输入章节摘要"
          ></textarea>
        </div>

        <!-- 剧情推演区域 -->
        <div class="border-t" style="border-color: var(--md-outline-variant); padding-top: 1.5rem;">
          <div class="flex items-center justify-between mb-3">
            <label class="md-text-field-label">剧情推演</label>
            <button
              @click="handleGenerate"
              :disabled="generating"
              class="md-btn md-btn-tonal md-ripple flex items-center gap-2 disabled:opacity-50"
            >
              <svg v-if="generating" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
              {{ generating ? '推演中...' : (prediction ? '重新推演' : '生成推演') }}
            </button>
          </div>

          <div v-if="prediction" class="space-y-3">
            <div v-for="section in predictionSections" :key="section.key" class="md-card md-card-outlined p-3" style="border-radius: var(--md-radius-lg);">
              <h4 class="md-title-small font-medium mb-2" :style="{ color: section.color }">{{ section.label }}</h4>
              <ul class="space-y-1">
                <li v-for="(item, i) in section.items" :key="i" class="md-body-medium md-on-surface-variant flex gap-2">
                  <span class="shrink-0">{{ section.icon }}</span>
                  <span>{{ item }}</span>
                </li>
              </ul>
            </div>

            <!-- Beats 节拍编排 -->
            <div v-if="prediction.beats?.length" class="md-card md-card-outlined p-3" style="border-radius: var(--md-radius-lg);">
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
          </div>

          <p v-else class="md-body-small md-on-surface-variant">暂无剧情推演，点击右侧按钮生成</p>
        </div>
      </div>

      <div class="mt-8 flex justify-end gap-4">
        <button @click="$emit('close')" class="md-btn md-btn-outlined md-ripple">
          取消
        </button>
        <button @click="saveChanges" class="md-btn md-btn-filled md-ripple disabled:opacity-50" :disabled="!isChanged">
          保存更改
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
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
  show: boolean
  chapter: ChapterOutline | null
  projectId: string
}

const props = defineProps<Props>()
const emit = defineEmits(['close', 'save'])

const editableChapter = ref<ChapterOutline | null>(null)
const generating = ref(false)

watch(() => props.chapter, (newChapter) => {
  if (newChapter) {
    editableChapter.value = { ...newChapter }
  } else {
    editableChapter.value = null
  }
}, { deep: true, immediate: true })

const isChanged = computed(() => {
  if (!props.chapter || !editableChapter.value) {
    return false
  }
  return props.chapter.title !== editableChapter.value.title || props.chapter.summary !== editableChapter.value.summary
})

const prediction = computed<ChapterPrediction | null>(
  () => editableChapter.value?.metadata?.prediction ?? null
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
  if (!props.projectId || !editableChapter.value || generating.value) return
  generating.value = true
  try {
    const result = await NovelAPI.generatePrediction(props.projectId, editableChapter.value.chapter_number)
    if (editableChapter.value) {
      editableChapter.value.metadata = { ...editableChapter.value.metadata, prediction: result }
    }
    if (props.chapter) {
      props.chapter.metadata = { ...props.chapter.metadata, prediction: result }
    }
  } catch (e: any) {
    console.error('剧情推演失败:', e)
  } finally {
    generating.value = false
  }
}

const saveChanges = () => {
  if (editableChapter.value && isChanged.value) {
    emit('save', editableChapter.value)
  }
}
</script>

<style scoped>
.m3-edit-dialog {
  border-radius: var(--md-radius-xl);
  max-width: min(560px, calc(100vw - 32px));
}
</style>

<!-- AIMETA P=编辑章节弹窗_章节信息编辑|R=章节编辑表单_AI推演|NR=不含内容生成|E=component:WDEditChapterModal|X=ui|A=编辑弹窗|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div v-if="show" class="md-dialog-overlay" @click.self="$emit('close')">
    <div class="md-dialog w-full max-w-lg m3-edit-dialog" :class="show ? 'scale-100 opacity-100' : 'scale-95 opacity-0'" style="overflow: visible;">
      <!-- 内部滚动容器 -->
      <div class="m3-edit-dialog-inner">
      <!-- 固定头部 -->
      <div class="flex justify-between items-center px-8 pt-8 pb-4">
        <h2 class="md-headline-small font-semibold">编辑章节大纲</h2>
        <button @click="$emit('close')" class="md-icon-btn md-ripple">
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </div>

      <!-- 内容区 -->
      <div v-if="editableChapter" class="space-y-6 px-8">
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

        <!-- AI推演大纲区域 -->
        <div class="border-t" style="border-color: var(--md-outline-variant); padding-top: 1.5rem;">
          <div class="flex items-center justify-between mb-3">
            <label class="md-text-field-label">AI推演大纲</label>
            <button
              @click="handleAiInfer"
              :disabled="aiInferring"
              class="md-btn md-btn-tonal md-ripple flex items-center gap-2 disabled:opacity-50"
              style="color: var(--md-primary);"
            >
              <svg v-if="aiInferring" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
              <svg v-else class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              {{ aiInferButtonText }}
            </button>
          </div>

          <!-- 排除内容（可折叠） -->
          <div class="mb-3">
            <button
              type="button"
              class="flex items-center gap-1 md-label-medium md-on-surface-variant"
              @click="showExclusions = !showExclusions"
            >
              <svg
                class="w-3.5 h-3.5 transition-transform duration-200"
                :class="{ 'rotate-90': showExclusions }"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
              </svg>
              排除内容（可选）
            </button>
            <textarea
              v-if="showExclusions"
              v-model="exclusions"
              placeholder="禁止推演出现的内容，例如：不要后宫、不要重生穿越..."
              rows="2"
              class="mt-1.5 md-textarea w-full"
            ></textarea>
          </div>

          <p v-if="aiInferError" class="md-body-small" style="color: var(--md-error);">{{ aiInferError }}</p>
          <p v-if="aiInferStep === 'done'" class="md-body-small" style="color: var(--md-primary);">推演完成，标题和摘要已更新，伏笔已同步</p>
          <p v-else class="md-body-small md-on-surface-variant">根据蓝图和上下文，AI自动生成本章标题和摘要</p>
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

          <!-- 排除内容（可折叠） -->
          <div class="mb-3">
            <button
              type="button"
              class="flex items-center gap-1 md-label-medium md-on-surface-variant"
              @click="showPredictionExclusions = !showPredictionExclusions"
            >
              <svg
                class="w-3.5 h-3.5 transition-transform duration-200"
                :class="{ 'rotate-90': showPredictionExclusions }"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
              </svg>
              排除内容（可选）
            </button>
            <textarea
              v-if="showPredictionExclusions"
              v-model="predictionExclusions"
              placeholder="禁止推演出现的内容，例如：不要后宫、不要重生穿越..."
              rows="2"
              class="mt-1.5 md-textarea w-full"
            ></textarea>
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

      <!-- 底部按钮 -->
      <div class="flex justify-end gap-4 px-8 pt-4 pb-8" style="border-top: 1px solid var(--md-outline-variant);">
        <button @click="$emit('close')" class="md-btn md-btn-outlined md-ripple">
          取消
        </button>
        <button @click="saveChanges" class="md-btn md-btn-filled md-ripple disabled:opacity-50" :disabled="!isChanged">
          保存更改
        </button>
      </div>
      </div><!-- /.m3-edit-dialog-inner -->
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { NovelAPI } from '@/api/novel'
import type { ChapterOutline, ChapterPrediction } from '@/api/novel'
import { useNovelStore } from '@/stores/novel'

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
const emit = defineEmits(['close', 'save', 'predictionUpdated'])
const novelStore = useNovelStore()

const editableChapter = ref<ChapterOutline | null>(null)
const generating = ref(false)

// AI推演大纲相关状态
const aiInferring = ref(false)
const aiInferStep = ref<'idle' | 'generating' | 'syncing' | 'done'>('idle')
const aiInferError = ref('')
const showExclusions = ref(false)
const exclusions = ref('')

// 剧情推演排除内容
const showPredictionExclusions = ref(false)
const predictionExclusions = ref('')

const aiInferButtonText = computed(() => {
  switch (aiInferStep.value) {
    case 'generating': return '推演中...'
    case 'syncing': return '同步伏笔中...'
    default: return 'AI推演'
  }
})

watch(() => props.chapter, (newChapter) => {
  if (newChapter) {
    editableChapter.value = { ...newChapter }
  } else {
    editableChapter.value = null
  }
  // 重置推演状态
  aiInferStep.value = 'idle'
  aiInferError.value = ''
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
    const result = await NovelAPI.generatePrediction(
      props.projectId,
      editableChapter.value.chapter_number,
      predictionExclusions.value.trim() || undefined
    )
    if (editableChapter.value) {
      // 替换整个 ref value 以确保 Vue 响应性完整触发（仅修改 .metadata 可能不触发 computed 更新）
      editableChapter.value = {
        ...editableChapter.value,
        metadata: { ...editableChapter.value.metadata, prediction: result }
      }
    }
    // 从后端刷新项目数据，确保 store 与 DB 一致（侧栏推演颜色指示器等）
    await novelStore.loadProject(props.projectId, true)
    // 通知父组件推演已更新，触发知识库刷新等后续动作
    emit('predictionUpdated')
  } catch (e: any) {
    console.error('剧情推演失败:', e)
  } finally {
    generating.value = false
  }
}

const handleAiInfer = async () => {
  if (!props.projectId || !editableChapter.value || aiInferring.value) return
  aiInferring.value = true
  aiInferStep.value = 'generating'
  aiInferError.value = ''

  try {
    const chapterNum = editableChapter.value.chapter_number

    // 拼装 userPrompt，将排除内容以创作禁区标记注入
    let userPrompt = ''
    if (exclusions.value.trim()) {
      userPrompt = `【创作禁区】以下内容禁止出现在大纲中：\n${exclusions.value.trim()}`
    }

    // 调用已有的大纲生成API（只生成1章）
    const result = await NovelAPI.generateChapterOutline(
      props.projectId,
      chapterNum,
      1,
      undefined,
      userPrompt || undefined
    )

    // 从返回的大纲中找到当前章节，更新标题和摘要
    const newOutlines = result.blueprint?.chapter_outline || []
    const matched = newOutlines.find(o => o.chapter_number === chapterNum)
    if (matched && editableChapter.value) {
      editableChapter.value.title = matched.title
      editableChapter.value.summary = matched.summary
    }

    // 自动同步伏笔（同时清理无效角色伏笔）
    aiInferStep.value = 'syncing'
    try {
      await NovelAPI.generateForeshadowings(props.projectId)
    } catch (e) {
      console.warn('伏笔同步失败（不影响大纲推演结果）:', e)
    }

    aiInferStep.value = 'done'
    setTimeout(() => {
      if (aiInferStep.value === 'done') aiInferStep.value = 'idle'
    }, 3000)
  } catch (e: any) {
    console.error('AI推演失败:', e)
    aiInferError.value = e instanceof Error ? e.message : 'AI推演失败，请重试'
    aiInferStep.value = 'idle'
  } finally {
    aiInferring.value = false
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
.m3-edit-dialog-inner {
  max-height: calc(100vh - 96px);
  overflow-y: auto;
  border-radius: inherit;
  background-color: var(--md-surface);
}
</style>

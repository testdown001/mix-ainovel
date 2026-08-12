<!-- AIMETA P=写作台工作区_主编辑区域|R=章节编辑_生成|NR=不含侧边栏|E=component:WDWorkspace|X=ui|A=工作区|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="flex-1 min-w-0 h-full">
    <div class="md-card md-card-elevated h-full flex flex-col" style="border-radius: var(--md-radius-xl);">
      <!-- 章节工作区头部 -->
      <div v-if="selectedChapterNumber" class="md-card-header flex-shrink-0">
        <div class="flex items-center justify-between">
          <div>
            <div class="flex items-center gap-3 mb-2">
              <h2 class="md-title-large font-semibold">第{{ selectedChapterNumber }}章</h2>
              <span
                :class="[
                  'md-chip',
                  isChapterCompleted(selectedChapterNumber)
                    ? 'm3-chip-success'
                    : 'm3-chip-neutral'
                ]"
              >
                {{ isChapterCompleted(selectedChapterNumber) ? '已完成' : '未完成' }}
              </span>
            </div>
            <h3 class="md-title-medium md-on-surface mb-1">{{ selectedChapterOutline?.title || '未知标题' }}</h3>
            <p class="md-body-small md-on-surface-variant">{{ selectedChapterOutline?.summary || '暂无章节描述' }}</p>

            <!-- 推演入口（紧凑按钮，仅在头部显示） -->
            <div v-if="canShowPredictionPanel" class="mt-2 flex items-center gap-2">
              <button
                @click="showPrediction = !showPrediction"
                class="md-btn md-btn-text md-ripple flex items-center gap-1 !px-2 !py-1"
                style="font-size: 0.8125rem;"
              >
                <svg
                  class="w-4 h-4 transition-transform"
                  :class="showPrediction ? 'rotate-90' : ''"
                  fill="currentColor" viewBox="0 0 20 20"
                >
                  <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"></path>
                </svg>
                剧情推演
                <span v-if="outlinePrediction" class="md-body-small md-on-surface-variant ml-1">(已有)</span>
              </button>
              <button
                v-if="isChapterCompleted(selectedChapterNumber)"
                @click="handleGeneratePrediction"
                :disabled="generatingPrediction"
                class="md-btn md-btn-tonal md-ripple flex items-center gap-1 !px-2 !py-1 disabled:opacity-50"
                style="font-size: 0.8125rem;"
              >
                <svg v-if="generatingPrediction" class="w-3.5 h-3.5 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                </svg>
                {{ generatingPrediction ? '推演中...' : (outlinePrediction ? '重新推演' : '生成推演') }}
              </button>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <!-- 写作模板按钮 -->
            <button
              @click="showTemplateSelector = true"
              class="md-btn md-btn-tonal md-ripple flex items-center gap-2 whitespace-nowrap"
              title="使用写作模板"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clip-rule="evenodd"></path>
              </svg>
              写作模板
            </button>
            <button
              @click="$emit('toggleCodex')"
              class="md-btn md-btn-tonal md-ripple flex items-center gap-2 whitespace-nowrap"
              title="世界观设定典"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z"></path>
              </svg>
              设定典
            </button>
            <button
              v-if="isChapterCompleted(selectedChapterNumber)"
              @click="openEditModal"
              class="md-btn md-btn-tonal md-ripple flex items-center gap-2 whitespace-nowrap"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
              </svg>
              手动编辑
            </button>
            <button
              @click="confirmRegenerateChapter"
              :disabled="generatingChapter === selectedChapterNumber"
              class="md-btn md-btn-filled md-ripple flex items-center gap-2 whitespace-nowrap disabled:opacity-50"
            >
              <svg v-if="generatingChapter === selectedChapterNumber" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
              <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
              {{ generatingChapter === selectedChapterNumber ? '生成中...' : '重新生成' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 章节内容展示区 -->
      <div class="md-card-content flex-1 overflow-y-auto">
        <!-- 推演详情面板（在内容区域内，可跟随滚动） -->
        <div v-if="showPrediction && outlinePrediction && canShowPredictionPanel" ref="predictionPanelRef" class="m3-prediction-panel mb-4">
          <div class="md-card md-card-outlined p-4" style="border-radius: var(--md-radius-xl);">
            <div class="flex items-center justify-between mb-3">
              <h4 class="md-title-small font-semibold flex items-center gap-2">
                <svg class="w-4 h-4" style="color: var(--md-primary);" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clip-rule="evenodd"></path>
                </svg>
                剧情推演详情
              </h4>
              <button
                @click="showPrediction = false"
                class="md-icon-btn md-ripple !w-7 !h-7"
                title="收起推演"
              >
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clip-rule="evenodd"></path>
                </svg>
              </button>
            </div>
            <div class="max-h-80 overflow-y-auto space-y-2 pr-1">
              <div v-for="section in predictionSections" :key="section.key" class="md-card md-card-filled p-3" style="border-radius: var(--md-radius-md);">
                <h4 class="md-label-large font-medium mb-1.5" :style="{ color: section.color }">{{ section.label }}</h4>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in section.items" :key="i" class="md-body-small md-on-surface-variant flex gap-2">
                    <span class="shrink-0">{{ section.icon }}</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>

              <!-- Beats 节拍编排 -->
              <div v-if="outlinePrediction.beats?.length" class="md-card md-card-filled p-3" style="border-radius: var(--md-radius-md);">
                <h4 class="md-label-large font-medium mb-1.5" style="color: var(--md-primary)">节拍编排</h4>
                <div class="space-y-1.5">
                  <div v-for="(beat, i) in outlinePrediction.beats" :key="i" class="flex items-start gap-2">
                    <span class="shrink-0 w-4 h-4 rounded-full text-[10px] flex items-center justify-center text-white font-medium"
                          :style="{ backgroundColor: beatColor(beat.type) }">{{ i + 1 }}</span>
                    <div>
                      <span class="md-label-small font-medium" :style="{ color: beatColor(beat.type) }">{{ beatLabel(beat.type) }}</span>
                      <span class="md-body-small md-on-surface-variant ml-1">{{ beat.content }}</span>
                      <span class="md-label-small ml-1" style="color: var(--md-outline);">{{ beat.emotion }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <component
          :is="currentComponent"
          v-bind="currentComponentProps"
          @hideVersionSelector="$emit('hideVersionSelector')"
          @update:selectedVersionIndex="$emit('update:selectedVersionIndex', $event)"
          @showVersionDetail="$emit('showVersionDetail', $event)"
          @openVersionCompare="$emit('openVersionCompare')"
          @confirmVersionSelection="$emit('confirmVersionSelection')"
          @generateChapter="(...args: any[]) => $emit('generateChapter', ...args)"
          @showVersionSelector="$emit('showVersionSelector')"
          @openSkillApply="$emit('openSkillApply')"
          @requestPrediction="$emit('requestPrediction', $event)"
          @regenerateChapter="$emit('regenerateChapter')"
          @evaluateChapter="$emit('evaluateChapter')"
          @showEvaluationDetail="$emit('showEvaluationDetail')"
        />
      </div>
    </div>

    <!-- 编辑章节内容模态框 -->
    <div v-if="showEditModal" class="md-dialog-overlay">
      <div class="md-dialog w-full h-full max-w-5xl m3-editor-dialog">
        <!-- 模态框头部 -->
        <div class="flex items-center justify-between p-6 border-b" style="border-bottom-color: var(--md-outline-variant);">
          <h3 class="md-title-large font-semibold">
            编辑第{{ selectedChapterNumber }}章内容
          </h3>
          <button
            @click="closeEditModal"
            class="md-icon-btn md-ripple"
          >
            <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
            </svg>
          </button>
        </div>

        <!-- 模态框内容 -->
        <div class="flex-1 p-6 overflow-hidden">
          <div class="flex flex-col h-full">
            <label class="md-text-field-label mb-2">
              章节内容
            </label>
            <textarea
              v-model="editingContent"
              class="md-textarea flex-1 w-full resize-none"
              placeholder="请输入章节内容..."
              :disabled="isSaving"
            ></textarea>
            <div class="md-body-small md-on-surface-variant mt-2">
              字数统计: {{ editingContent.length }}
            </div>
          </div>
        </div>

        <!-- 模态框底部 -->
        <div class="flex items-center justify-end gap-3 p-6 border-t" style="border-top-color: var(--md-outline-variant);">
          <button
            @click="closeEditModal"
            :disabled="isSaving"
            class="md-btn md-btn-outlined md-ripple disabled:opacity-50"
          >
            取消
          </button>
          <button
            @click="saveEditedContent"
            :disabled="isSaving || !editingContent.trim()"
            class="md-btn md-btn-filled md-ripple disabled:opacity-50 flex items-center gap-2"
          >
            <svg v-if="isSaving" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
            </svg>
            {{ isSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 写作模板选择器模态框 -->
    <Teleport to="body">
      <div v-if="showTemplateSelector" class="modal-overlay" @click.self="showTemplateSelector = false">
        <div class="modal-content">
          <TemplateSelector
            :project-id="project?.id ?? ''"
            :chapter-number="selectedChapterNumber ?? 0"
            @apply="handleTemplateApply"
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch, onUnmounted } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import type { Chapter, ChapterOutline, ChapterGenerationResponse, ChapterVersion, NovelProject, ChapterPrediction } from '@/api/novel'
import TemplateSelector from './TemplateSelector.vue'

const beatColorMap: Record<string, string> = {
  setup: '#6B7280', provoke: '#F59E0B', twist: '#8B5CF6', payoff: '#EF4444', hook: '#3B82F6'
}
const beatLabelMap: Record<string, string> = {
  setup: '铺垫', provoke: '激化', twist: '转折', payoff: '爆发', hook: '悬念'
}
const beatColor = (type: string) => beatColorMap[type] || '#6B7280'
const beatLabel = (type: string) => beatLabelMap[type] || type
import WorkspaceInitial from './workspace/WorkspaceInitial.vue'
import ChapterGenerating from './workspace/ChapterGenerating.vue'
import VersionSelector from './workspace/VersionSelector.vue'
import ChapterContent from './workspace/ChapterContent.vue'
import ChapterFailed from './workspace/ChapterFailed.vue'
import ChapterEmpty from './workspace/ChapterEmpty.vue'

interface Props {
  project: NovelProject | null
  selectedChapterNumber: number | null
  openPredictionTick?: number
  generatingChapter: number | null
  predictionGeneratingChapter?: number | null
  evaluatingChapter: number | null
  showVersionSelector: boolean
  chapterGenerationResult: ChapterGenerationResponse | null
  selectedVersionIndex: number
  availableVersions: ChapterVersion[]
  isSelectingVersion?: boolean
  streamingDraftText?: string
  streamingStage?: string | null
}

const props = defineProps<Props>()

const emit = defineEmits([
  'regenerateChapter',
  'evaluateChapter',
  'hideVersionSelector',
  'update:selectedVersionIndex',
  'showVersionDetail',
  'openVersionCompare',
  'confirmVersionSelection',
  'generateChapter',
  'showVersionSelector',
  'openSkillApply',
  'requestPrediction',
  'showEvaluationDetail',
  'fetchChapterStatus',
  'editChapter',
  'toggleCodex'
])

const confirmRegenerateChapter = async () => {
  const confirmed = await globalAlert.showConfirm('重新生成会覆盖当前章节的现有内容，确定继续吗？', '重新生成确认')
  if (confirmed) {
    emit('regenerateChapter')
  }
}

// 剧情推演
const showPrediction = ref(false)
const showTemplateSelector = ref(false)
const templatePrompt = ref('')
const generatingPrediction = computed(
  () => props.predictionGeneratingChapter === props.selectedChapterNumber
)
const predictionPanelBlockedStatuses: Chapter['generation_status'][] = [
  'waiting_for_confirm',
  'evaluation_failed',
  'evaluating',
  'selecting'
]

const outlinePrediction = computed<ChapterPrediction | null>(
  () => selectedChapterOutline.value?.metadata?.prediction ?? null
)
const selectedChapterStatus = computed<Chapter['generation_status'] | null>(() => {
  if (props.selectedChapterNumber === null || !props.project?.chapters) {
    return null
  }
  return props.project.chapters.find(
    chapter => chapter.chapter_number === props.selectedChapterNumber
  )?.generation_status ?? null
})
const canShowPredictionPanel = computed(() => {
  if (props.selectedChapterNumber === null) return false
  if (
    selectedChapterStatus.value &&
    predictionPanelBlockedStatuses.includes(selectedChapterStatus.value)
  ) {
    return false
  }
  return isChapterCompleted(props.selectedChapterNumber) || !!outlinePrediction.value
})
const predictionPanelRef = ref<HTMLElement | null>(null)

const predictionSections = computed(() => {
  const p = outlinePrediction.value
  if (!p) return []
  return [
    { key: 'key_points', label: '章节要点', icon: '•', color: 'var(--md-primary)', items: p.key_points || [] },
    { key: 'cool_points', label: '爽点设计', icon: '⚡', color: 'var(--md-tertiary)', items: p.cool_points || [] },
    { key: 'foreshadowing_hooks', label: '伏笔/钩子', icon: '🪝', color: 'var(--md-secondary)', items: p.foreshadowing_hooks || [] },
    { key: 'foreshadowing_targets', label: '需回收伏笔', icon: '🎯', color: 'var(--md-error)', items: p.foreshadowing_targets || [] },
    { key: 'limitations', label: '章节限制', icon: '⚠', color: 'var(--md-on-surface-variant)', items: p.limitations || [] },
  ].filter(s => s.items.length > 0)
})

const handleGeneratePrediction = () => {
  if (!props.selectedChapterNumber || generatingPrediction.value) return
  emit('requestPrediction', props.selectedChapterNumber)
}

// 处理模板应用
const handleTemplateApply = (prompt: string) => {
  showTemplateSelector.value = false
  templatePrompt.value = prompt
  globalAlert.showAlert('模板已应用，写作指令已更新', 'info')
}

const openPredictionPanel = async () => {
  await nextTick()
  if (!outlinePrediction.value || !canShowPredictionPanel.value) return
  showPrediction.value = true
  await nextTick()
  predictionPanelRef.value?.scrollIntoView({
    behavior: 'smooth',
    block: 'nearest',
  })
}

// 编辑模态框状态
const showEditModal = ref(false)
const editingContent = ref('')
const isSaving = ref(false)

// 清理版本内容的辅助函数
const cleanVersionContent = (content: string): string => {
  if (!content) return ''
  try {
    const parsed = JSON.parse(content)
    const extractContent = (value: any): string | null => {
      if (!value) return null
      if (typeof value === 'string') return value
      if (Array.isArray(value)) {
        for (const item of value) {
          const nested = extractContent(item)
          if (nested) return nested
        }
        return null
      }
      if (typeof value === 'object') {
        for (const key of ['content', 'chapter_content', 'chapter_text', 'text', 'body', 'story']) {
          if (value[key]) {
            const nested = extractContent(value[key])
            if (nested) return nested
          }
        }
      }
      return null
    }
    const extracted = extractContent(parsed)
    if (extracted) {
      content = extracted
    }
  } catch (error) {
    // not a json
  }
  let cleaned = content.replace(/^"|"$/g, '')
  cleaned = cleaned.replace(/\\n/g, '\n')
  cleaned = cleaned.replace(/\\"/g, '"')
  cleaned = cleaned.replace(/\\t/g, '\t')
  cleaned = cleaned.replace(/\\\\/g, '\\')
  return cleaned
}

const openEditModal = () => {
  if (selectedChapter.value?.content) {
    editingContent.value = cleanVersionContent(selectedChapter.value.content)
    showEditModal.value = true
  }
}

const closeEditModal = () => {
  showEditModal.value = false
  editingContent.value = ''
  isSaving.value = false
}

const saveEditedContent = async () => {
  if (!props.selectedChapterNumber || !editingContent.value.trim()) return
  
  isSaving.value = true
  try {
    emit('editChapter', {
      chapterNumber: props.selectedChapterNumber,
      content: editingContent.value
    })
    closeEditModal()
  } catch (error) {
    console.error('保存章节内容失败:', error)
  } finally {
    isSaving.value = false
  }
}

const selectedChapter = computed(() => {
  if (!props.project || props.selectedChapterNumber === null) return null
  return props.project.chapters.find(ch => ch.chapter_number === props.selectedChapterNumber) || null
})

const selectedChapterOutline = computed(() => {
  if (!props.project?.blueprint?.chapter_outline || props.selectedChapterNumber === null) return null
  return props.project.blueprint.chapter_outline.find(ch => ch.chapter_number === props.selectedChapterNumber) || null
})

const isChapterCompleted = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'successful'
}

const isChapterGenerating = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'generating'
}

const isChapterFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const isChapterEvaluationFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'evaluation_failed'
}

const canGenerateChapter = (chapterNumber: number | null) => {
  if (chapterNumber === null || !props.project?.blueprint?.chapter_outline) return false

  const outlines = props.project.blueprint.chapter_outline.sort((a, b) => a.chapter_number - b.chapter_number)
  
  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break
    
    const chapter = props.project?.chapters.find(ch => ch.chapter_number === outline.chapter_number)
    if (!chapter || chapter.generation_status !== 'successful') {
      return false
    }
  }

  const currentChapter = props.project?.chapters.find(ch => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true
  }

  return true
}

const currentComponent = computed(() => {
  if (!props.selectedChapterNumber) {
    return WorkspaceInitial
  }

  const status = selectedChapter.value?.generation_status
  if (status === 'generating' || status === 'evaluating' || status === 'selecting') {
    return ChapterGenerating // Use a generic "in-progress" component
  }

  if (status === 'waiting_for_confirm' || status === 'evaluation_failed') {
    return VersionSelector
  }

  if (selectedChapter.value?.content) {
    return ChapterContent
  }
  if (isChapterFailed(props.selectedChapterNumber)) {
    return ChapterFailed
  }
  return ChapterEmpty
})

// Polling for chapter status updates
const pollingTimer = ref<number | null>(null)

const startPolling = () => {
  stopPolling()
  pollingTimer.value = window.setInterval(() => {
    emit('fetchChapterStatus')
  }, 10000)
}

const stopPolling = () => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

watch(
  () => [selectedChapter.value?.generation_status, props.evaluatingChapter, props.isSelectingVersion, props.selectedChapterNumber],
  ([status, evaluating, selecting, chapterNumber]) => {
    if (chapterNumber === null) {
      stopPolling()
      return
    }

    const isEvaluating = evaluating === chapterNumber
    // Poll when generating, evaluating, or selecting a version
    const needsPolling = status === 'generating' || status === 'evaluating' || status === 'selecting'

    if (needsPolling) {
      startPolling()
    } else {
      stopPolling()
    }
  },
  { immediate: true }
)

watch(
  () => props.openPredictionTick,
  async (current, previous) => {
    if (current === undefined || current === previous) return
    await openPredictionPanel()
  }
)

onUnmounted(() => {
  stopPolling()
})

const currentComponentProps = computed(() => {
  if (!props.selectedChapterNumber) {
    return {}
  }
  const status = selectedChapter.value?.generation_status
  if (status === 'generating' || status === 'evaluating' || status === 'selecting') {
    return {
      chapterNumber: props.selectedChapterNumber,
      status: status,
      streamingDraftText: props.streamingDraftText || '',
      streamingStage: props.streamingStage || null,
      projectId: props.project?.id
    }
  }

  if (status === 'waiting_for_confirm' || status === 'evaluation_failed') {
    return {
      selectedChapter: selectedChapter.value,
      chapterGenerationResult: props.chapterGenerationResult,
      availableVersions: props.availableVersions,
      selectedVersionIndex: props.selectedVersionIndex,
      isSelectingVersion: props.isSelectingVersion,
      evaluatingChapter: props.evaluatingChapter,
      isEvaluationFailed: isChapterEvaluationFailed(props.selectedChapterNumber)
    }
  }
  if (selectedChapter.value?.content) {
    return { 
      selectedChapter: selectedChapter.value,
      projectId: props.project?.id
    }
  }
  if (isChapterFailed(props.selectedChapterNumber)) {
    return {
      chapterNumber: props.selectedChapterNumber,
      generatingChapter: props.generatingChapter,
      predictionGenerating: generatingPrediction.value,
      outline: selectedChapterOutline.value,
      projectId: props.project?.id
    }
  }
  return {
    chapterNumber: props.selectedChapterNumber,
    generatingChapter: props.generatingChapter,
    predictionGenerating: generatingPrediction.value,
    canGenerate: canGenerateChapter(props.selectedChapterNumber),
    outline: selectedChapterOutline.value,
    projectId: props.project?.id,
    templatePrompt: templatePrompt.value
  }
})
</script>

<style scoped>
.m3-chip-success {
  background-color: var(--md-success-container);
  color: var(--md-on-success-container);
}

.m3-chip-neutral {
  background-color: var(--md-surface-container);
  color: var(--md-on-surface-variant);
}

.m3-editor-dialog {
  max-width: min(1200px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  border-radius: var(--md-radius-xl);
}

.m3-prediction-panel {
  animation: m3-slide-down 0.25s ease-out both;
}

@keyframes m3-slide-down {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  overflow: auto;
  padding: 1rem;
}

.modal-content {
  background: #0A0A0A;
  border: 1px solid #2A2A2A;
  border-radius: 12px;
  width: 100%;
  max-width: 900px;
  max-height: 90vh;
  overflow-x: hidden;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
  margin: auto;
  flex-shrink: 0;
}

.m3-prediction-panel ::-webkit-scrollbar {
  width: 4px;
}

.m3-prediction-panel ::-webkit-scrollbar-thumb {
  background: var(--md-outline);
  border-radius: 2px;
}
</style>

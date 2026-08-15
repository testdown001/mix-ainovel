<!-- AIMETA P=章节内容_章节文本展示编辑|R=内容展示_编辑|NR=不含版本管理|E=component:ChapterContent|X=internal|A=内容组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-6">
    <div class="md-card md-card-filled p-4 mb-6" style="border-radius: var(--md-radius-lg); background-color: var(--md-success-container);">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2" style="color: var(--md-on-success-container);">
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
          </svg>
          <span class="font-medium">这个章节已经完成</span>
        </div>

        <button
          v-if="selectedChapter.versions && selectedChapter.versions.length > 0"
          @click="$emit('showVersionSelector', true)"
          class="md-btn md-btn-text md-ripple flex items-center gap-1"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"></path>
            <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"></path>
          </svg>
          查看所有版本
        </button>
      </div>
    </div>

    <div class="md-card md-card-outlined p-6" style="border-radius: var(--md-radius-xl);">
      <div class="flex items-center justify-between mb-4 gap-3">
        <h4 class="md-title-medium font-semibold">章节内容</h4>
        <div class="flex items-center gap-3">
          <div class="md-body-small md-on-surface-variant">
            约 {{ Math.round(cleanVersionContent(selectedChapter.content || '').length / 100) * 100 }} 字
          </div>
          <!-- 分层优化按钮 -->
          <button
            class="md-btn md-btn-tonal md-ripple flex items-center gap-1"
            @click="showOptimizer = true"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
            </svg>
            分层优化
          </button>
          <button
            class="md-btn md-btn-tonal md-ripple flex items-center gap-1"
            :class="selectedChapter.content ? '' : 'opacity-50 cursor-not-allowed'"
            :disabled="!selectedChapter.content"
            @click="$emit('openSkillApply')"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            应用技能
          </button>
          <button
            class="md-btn md-btn-outlined md-ripple flex items-center gap-1"
            :class="selectedChapter.content ? '' : 'opacity-50 cursor-not-allowed'"
            :disabled="!selectedChapter.content"
            @click="exportChapterAsTxt(selectedChapter)"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v16h16V4m-4 4l-4-4-4 4m4-4v12" />
            </svg>
            导出TXT
          </button>
        </div>
      </div>
      <div class="prose max-w-none relative">
        <p class="md-body-small md-on-surface-variant mb-2">选中一段可扩写 / 改写 / 去 AI 味，不必重滚整章。</p>
        <div
          ref="proseEl"
          class="whitespace-pre-wrap leading-relaxed"
          style="color: var(--md-on-surface);"
          @mouseup="onSelectText"
        >
          <template v-if="hasRange">
            <span>{{ proseBefore }}</span><mark class="transform-mark">{{ proseSelected }}</mark><span>{{ proseAfter }}</span>
          </template>
          <template v-else>{{ chapterText }}</template>
        </div>
        <div
          v-if="hasRange && !previewText"
          class="transform-bar"
          @mousedown.prevent
          :style="{ top: toolbarY + 'px', left: toolbarX + 'px' }"
        >
          <button class="md-btn md-btn-filled !px-2 !py-1 text-xs" :disabled="transforming" @click="runTransform('expand')">
            {{ transforming ? '处理中…' : `扩写 +${prices.expand}` }}
          </button>
          <button class="md-btn md-btn-tonal !px-2 !py-1 text-xs" :disabled="transforming" @click="runTransform('rewrite')">
            改写 +{{ prices.rewrite }}
          </button>
          <button class="md-btn md-btn-tonal !px-2 !py-1 text-xs" :disabled="transforming" @click="runTransform('de_ai')">
            去AI味 +{{ prices.de_ai }}
          </button>
        </div>
      </div>
      <div v-if="previewText" class="mt-4 md-card md-card-outlined p-4" style="border-radius: var(--md-radius-lg);">
        <h5 class="md-title-small mb-3">选区对照（尚未写入正文）</h5>
        <div class="grid sm:grid-cols-2 gap-3 mb-3">
          <div class="p-3 rounded-md" style="background: var(--md-surface-container);">
            <p class="md-label-small md-on-surface-variant mb-1">原文</p>
            <p class="whitespace-pre-wrap md-body-medium">{{ selection }}</p>
          </div>
          <div class="p-3 rounded-md" style="background: var(--md-primary-container);">
            <p class="md-label-small mb-1" style="color: var(--md-on-primary-container);">改写后</p>
            <p class="whitespace-pre-wrap md-body-medium">{{ previewText }}</p>
          </div>
        </div>
        <div class="flex gap-2">
          <button class="md-btn md-btn-filled" :disabled="applyingTransform" @click="applyPreview">
            {{ applyingTransform ? '写入中…' : '采用改写' }}
          </button>
          <button class="md-btn md-btn-outlined" @click="discardPreview">丢弃</button>
        </div>
      </div>
    </div>

    <!-- 分层优化弹窗 -->
    <Teleport to="body">
      <div
        v-if="showOptimizer"
        class="md-dialog-overlay"
        @click.self="showOptimizer = false"
      >
        <div class="md-dialog m3-optimizer-dialog">
          <div class="p-6">
            <!-- 优化面板头部 -->
            <div class="flex items-center justify-between mb-6">
              <div>
                <h3 class="md-headline-small font-semibold">✨ 分层优化</h3>
                <p class="md-body-small md-on-surface-variant mt-1">选择一个维度进行深度优化，让文字更有灵魂</p>
              </div>
              <button
                @click="showOptimizer = false"
                class="md-icon-btn md-ripple"
              >
                <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                </svg>
              </button>
            </div>

            <!-- 优化维度选择 -->
            <div class="grid grid-cols-2 gap-4 mb-6">
              <button
                v-for="dim in optimizeDimensions"
                :key="dim.key"
                @click="selectedDimension = dim.key"
                :class="[
                  'md-card md-card-outlined p-4 text-left transition-all duration-200',
                  selectedDimension === dim.key
                    ? 'm3-option-selected'
                    : 'm3-option'
                ]"
              >
                <div class="flex items-center gap-3 mb-2">
                  <span class="text-2xl">{{ dim.icon }}</span>
                  <span class="md-title-small font-semibold">{{ dim.label }}</span>
                </div>
                <p class="md-body-small md-on-surface-variant">{{ dim.description }}</p>
              </button>
            </div>

            <!-- 额外说明 -->
            <div class="mb-6">
              <label class="md-text-field-label mb-2">
                额外优化指令（可选）
              </label>
              <textarea
                v-model="additionalNotes"
                rows="3"
                class="md-textarea w-full resize-none"
                placeholder="例如：加强主角内心的挣扎感，让对话更有张力..."
              ></textarea>
            </div>

            <!-- 操作按钮 -->
            <div class="flex justify-end gap-3">
              <button
                @click="showOptimizer = false"
                class="md-btn md-btn-outlined md-ripple"
              >
                取消
              </button>
              <button
                @click="startOptimize"
                :disabled="!selectedDimension || isOptimizing"
                class="md-btn md-btn-filled md-ripple disabled:opacity-50 flex items-center gap-2"
              >
                <svg v-if="isOptimizing" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                </svg>
                {{ isOptimizing ? '优化中...' : '开始优化' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 优化结果预览弹窗 -->
    <Teleport to="body">
      <div
        v-if="showOptimizeResult"
        class="md-dialog-overlay"
        @click.self="showOptimizeResult = false"
      >
        <div class="md-dialog m3-result-dialog flex flex-col">
          <div class="p-6 border-b" style="border-bottom-color: var(--md-outline-variant);">
            <div class="flex items-center justify-between">
              <div>
                <h3 class="md-headline-small font-semibold">优化结果预览</h3>
                <p class="md-body-small md-on-surface-variant mt-1">{{ optimizeResultNotes }}</p>
              </div>
              <button
                @click="showOptimizeResult = false"
                class="md-icon-btn md-ripple"
              >
                <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                </svg>
              </button>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto p-6">
            <div class="prose max-w-none">
              <div class="whitespace-pre-wrap leading-relaxed" style="color: var(--md-on-surface);">{{ optimizedContent }}</div>
            </div>
          </div>
          <div class="p-6 border-t flex justify-end gap-3" style="border-top-color: var(--md-outline-variant);">
            <button
              @click="showOptimizeResult = false"
              class="md-btn md-btn-outlined md-ripple"
            >
              取消
            </button>
            <button
              @click="applyOptimization"
              :disabled="isApplying"
              class="md-btn md-btn-filled md-ripple disabled:opacity-50 flex items-center gap-2"
              style="background-color: var(--md-success); color: var(--md-on-success);"
            >
              <svg v-if="isApplying" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
              {{ isApplying ? '应用中...' : '应用优化' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import { useNovelStore } from '@/stores/novel'
import type { Chapter } from '@/api/novel'
import { NovelAPI, OptimizerAPI } from '@/api/novel'
import { ModelCatalogAPI } from '@/api/model_catalog'
import { detectUpgradeHint } from '@/utils/upgradeHint'

interface Props {
  selectedChapter: Chapter
  projectId?: string
}

const props = defineProps<Props>()

defineEmits(['showVersionSelector', 'openSkillApply'])

const novelStore = useNovelStore()
const proseEl = ref<HTMLElement | null>(null)
const selection = ref('')
const selStart = ref(-1)
const selEnd = ref(-1)
const toolbarX = ref(0)
const toolbarY = ref(0)
const transforming = ref(false)
const applyingTransform = ref(false)
const previewText = ref('')
const prices = ref({ expand: 3, rewrite: 3, de_ai: 2 })

const chapterText = computed(() => cleanVersionContent(props.selectedChapter.content || ''))
const hasRange = computed(() => selStart.value >= 0 && selEnd.value > selStart.value)
const proseBefore = computed(() => chapterText.value.slice(0, selStart.value))
const proseSelected = computed(() => chapterText.value.slice(selStart.value, selEnd.value))
const proseAfter = computed(() => chapterText.value.slice(selEnd.value))

onMounted(async () => {
  try {
    const avail = await ModelCatalogAPI.getAvailable()
    if (avail.transform_prices) prices.value = avail.transform_prices
  } catch {
    /* keep defaults */
  }
})

watch(
  () => `${props.selectedChapter.chapter_number}\0${props.selectedChapter.content || ''}`,
  () => discardPreview(),
)

function rangeOffsets(root: HTMLElement, range: Range): { start: number; end: number } {
  const pre = range.cloneRange()
  pre.selectNodeContents(root)
  pre.setEnd(range.startContainer, range.startOffset)
  const start = pre.toString().length
  return { start, end: start + range.toString().length }
}

function onSelectText() {
  const sel = window.getSelection()
  const text = sel?.toString() || ''
  if (!text.trim() || !proseEl.value || !sel || sel.rangeCount === 0) {
    if (!previewText.value) {
      selection.value = ''
      selStart.value = -1
      selEnd.value = -1
    }
    return
  }
  const range = sel.getRangeAt(0)
  if (!proseEl.value.contains(range.commonAncestorContainer)) {
    return
  }
  const { start, end } = rangeOffsets(proseEl.value, range)
  selStart.value = start
  selEnd.value = end
  selection.value = chapterText.value.slice(start, end)
  previewText.value = ''
  const rect = range.getBoundingClientRect()
  const host = proseEl.value.getBoundingClientRect()
  toolbarX.value = Math.min(Math.max(0, rect.left - host.left), Math.max(0, host.width - 220))
  toolbarY.value = Math.max(0, rect.top - host.top - 44)
}

function resolveRange(original: string): { start: number; end: number } | null {
  if (selStart.value >= 0 && original.slice(selStart.value, selEnd.value) === selection.value) {
    return { start: selStart.value, end: selEnd.value }
  }
  const first = original.indexOf(selection.value)
  if (first < 0) return null
  if (original.indexOf(selection.value, first + 1) >= 0) return null
  return { start: first, end: first + selection.value.length }
}

async function runTransform(action: 'expand' | 'rewrite' | 'de_ai') {
  if (!props.projectId || !selection.value) return
  transforming.value = true
  try {
    const res = await NovelAPI.transformSelection(props.projectId, {
      chapter_number: props.selectedChapter.chapter_number,
      action,
      selected_text: selection.value,
    })
    previewText.value = res.result_text
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    globalAlert.showError(detectUpgradeHint(msg) === 'credits' ? '积分不足，可改选更短选区或购买加油包。' : msg, '选区改写')
  } finally {
    transforming.value = false
  }
}

async function applyPreview() {
  if (!props.projectId || !selection.value || !previewText.value) return
  applyingTransform.value = true
  try {
    const original = chapterText.value
    const range = resolveRange(original)
    if (!range) {
      globalAlert.showError('选区已对不上原文（可能出现多次）。请重新划选后再采用。', '选区改写')
      return
    }
    const next = original.slice(0, range.start) + previewText.value + original.slice(range.end)
    await NovelAPI.editChapterContent(props.projectId, props.selectedChapter.chapter_number, next)
    await novelStore.loadChapter(props.selectedChapter.chapter_number)
    discardPreview()
    globalAlert.showSuccess('已写入本章，原文其余部分未动。', '选区已采用')
  } catch (err) {
    globalAlert.showError(err instanceof Error ? err.message : '采用失败', '选区改写')
  } finally {
    applyingTransform.value = false
  }
}

function discardPreview() {
  previewText.value = ''
  selection.value = ''
  selStart.value = -1
  selEnd.value = -1
}

// 优化相关状态
const showOptimizer = ref(false)
const showOptimizeResult = ref(false)
const selectedDimension = ref<string>('')
const additionalNotes = ref('')
const isOptimizing = ref(false)
const isApplying = ref(false)
const optimizedContent = ref('')
const optimizeResultNotes = ref('')

// 优化维度配置
const optimizeDimensions = [
  {
    key: 'dialogue',
    icon: '💬',
    label: '对话优化',
    description: '让每句对话都有独特的声音和潜台词'
  },
  {
    key: 'environment',
    icon: '🌄',
    label: '环境描写',
    description: '让场景氛围与情绪完美融合'
  },
  {
    key: 'psychology',
    icon: '🧠',
    label: '心理活动',
    description: '深入角色内心，展现复杂情感'
  },
  {
    key: 'rhythm',
    icon: '🎵',
    label: '节奏韵律',
    description: '优化文字节奏，增强阅读体验'
  }
]

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

const sanitizeFileName = (name: string): string => {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

const exportChapterAsTxt = (chapter?: Chapter | null) => {
  if (!chapter) return

  const title = chapter.title?.trim() || `第${chapter.chapter_number}章`
  const safeTitle = sanitizeFileName(title) || `chapter-${chapter.chapter_number}`
  const content = cleanVersionContent(chapter.content || '')
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${safeTitle}.txt`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const startOptimize = async () => {
  if (!selectedDimension.value || !props.projectId) {
    globalAlert.showError('请选择优化维度')
    return
  }

  isOptimizing.value = true
  showOptimizer.value = false

  try {
    const result = await OptimizerAPI.optimizeChapter({
      project_id: props.projectId,
      chapter_number: props.selectedChapter.chapter_number,
      dimension: selectedDimension.value as 'dialogue' | 'environment' | 'psychology' | 'rhythm',
      additional_notes: additionalNotes.value || undefined
    })

    optimizedContent.value = result.optimized_content
    optimizeResultNotes.value = result.optimization_notes
    showOptimizeResult.value = true
  } catch (error: any) {
    console.error('优化失败:', error)
    globalAlert.showError(error.message || '优化失败，请稍后重试')
  } finally {
    isOptimizing.value = false
  }
}

const applyOptimization = async () => {
  if (!optimizedContent.value || !props.projectId) return

  isApplying.value = true

  try {
    await OptimizerAPI.applyOptimization(
      props.projectId,
      props.selectedChapter.chapter_number,
      optimizedContent.value
    )

    globalAlert.showSuccess('优化内容已应用')
    showOptimizeResult.value = false

    // 重置状态
    selectedDimension.value = ''
    additionalNotes.value = ''
    optimizedContent.value = ''
    optimizeResultNotes.value = ''

    // 通过 store 重新加载章节，获取最新内容
    try {
      await novelStore.loadChapter(props.selectedChapter.chapter_number)
    } catch {
      // 静默失败，内容已保存到后端
    }
  } catch (error: any) {
    console.error('应用优化失败:', error)
    globalAlert.showError(error.message || '应用优化失败，请稍后重试')
  } finally {
    isApplying.value = false
  }
}
</script>

<style scoped>
.m3-optimizer-dialog {
  max-width: min(720px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  border-radius: var(--md-radius-xl);
}

.m3-result-dialog {
  max-width: min(900px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  border-radius: var(--md-radius-xl);
}

.m3-option {
  border-color: var(--md-outline-variant);
}

.m3-option-selected {
  border-color: var(--md-primary);
  background-color: var(--md-primary-container);
  box-shadow: var(--md-elevation-1);
}

.transform-bar {
  position: absolute;
  z-index: 5;
  display: flex;
  gap: 6px;
  padding: 4px;
  border-radius: 8px;
  background: var(--md-surface);
  box-shadow: var(--md-elevation-2);
  border: 1px solid var(--md-outline-variant);
}

.transform-mark {
  background: rgba(255, 229, 0, 0.35);
  color: inherit;
  padding: 0 1px;
  border-radius: 2px;
}
</style>

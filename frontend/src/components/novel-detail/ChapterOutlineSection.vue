<!-- AIMETA P=章节大纲区_大纲展示|R=大纲列表_重新生成|NR=不含编辑功能|E=component:ChapterOutlineSection|X=ui|A=大纲组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">章节大纲</h2>
        <p class="text-sm text-slate-500">故事结构与章节节奏一目了然</p>
      </div>
      <div v-if="editable" class="flex items-center gap-2 flex-wrap">
        <button
          v-if="hasCompletedChapters && uncompletedCount > 0"
          type="button"
          class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-lg transition-colors"
          :disabled="regenerating"
          @click="handleRegenerateAll"
        >
          <svg v-if="regenerating" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <svg v-else class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {{ regenerating ? '生成中...' : `重新生成未完成大纲 (${uncompletedCount})` }}
        </button>
        <button
          v-if="regeneratedNumbers.size > 0"
          type="button"
          class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-sky-600 bg-sky-50 hover:bg-sky-100 rounded-lg transition-colors"
          @click="clearRegenerated"
        >
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
          </svg>
          清除新生成标记
        </button>
        <button
          type="button"
          class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg"
          @click="$emit('add')"
        >
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
          </svg>
          新增章节
        </button>
        <button
          type="button"
          class="flex items-center gap-1 px-3 py-2 text-sm text-gray-500 hover:text-indigo-600 transition-colors"
          @click="emitEdit('chapter_outline', '章节大纲', outline)"
        >
          <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
            <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
          </svg>
          编辑大纲
        </button>
      </div>
    </div>

    <!-- 生成结果提示 -->
    <div
      v-if="regenerateResult"
      class="flex items-start gap-3 px-4 py-3 rounded-lg text-sm"
      :class="regenerateResult.updated === regenerateResult.total
        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
        : 'bg-amber-50 text-amber-800 border border-amber-200'"
    >
      <svg class="h-5 w-5 flex-shrink-0 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
        <path v-if="regenerateResult.updated === regenerateResult.total" fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
        <path v-else fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
      </svg>
      <span>
        已重新生成 {{ regenerateResult.updated }}/{{ regenerateResult.total }} 个章节大纲。
        <template v-if="regenerateResult.updated < regenerateResult.total">
          有 {{ regenerateResult.total - regenerateResult.updated }} 个章节未能生成，可尝试再次重新生成。
        </template>
        带有 <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-sky-100 text-sky-700">新</span> 标记的是本次更新的大纲。
      </span>
      <button
        type="button"
        class="ml-auto flex-shrink-0 text-current opacity-60 hover:opacity-100"
        @click="regenerateResult = null"
      >
        <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>

    <ol class="relative border-l border-slate-200 ml-3 space-y-8">
      <li
        v-for="chapter in outline"
        :key="chapter.chapter_number"
        class="ml-6"
      >
        <span
          class="absolute -left-3 mt-1 flex h-6 w-6 items-center justify-center rounded-full text-white text-xs font-semibold"
          :class="isCompleted(chapter.chapter_number) ? 'bg-emerald-500' : 'bg-indigo-500'"
        >
          <template v-if="isCompleted(chapter.chapter_number)">
            <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
          </template>
          <template v-else>{{ chapter.chapter_number }}</template>
        </span>
        <div
          class="rounded-2xl border shadow-sm p-5 transition-all duration-300"
          :class="[
            isCompleted(chapter.chapter_number)
              ? 'bg-emerald-50/50 border-emerald-200'
              : isRegenerated(chapter.chapter_number)
                ? 'bg-sky-50/60 border-sky-300 ring-2 ring-sky-200'
                : 'bg-white/95 border-slate-200'
          ]"
        >
          <div class="flex items-center justify-between gap-4">
            <div class="flex items-center gap-2 min-w-0">
              <h3 class="text-lg font-semibold text-slate-900 truncate">{{ chapter.title || `第${chapter.chapter_number}章` }}</h3>
              <span
                v-if="isCompleted(chapter.chapter_number)"
                class="flex-shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700"
              >
                已完成
              </span>
              <span
                v-if="isRegenerated(chapter.chapter_number)"
                class="flex-shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-sky-100 text-sky-700 animate-pulse"
              >
                <svg class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M5 2a1 1 0 011 1v1h1a1 1 0 010 2H6v1a1 1 0 01-2 0V6H3a1 1 0 010-2h1V3a1 1 0 011-1zm0 10a1 1 0 011 1v1h1a1 1 0 110 2H6v1a1 1 0 11-2 0v-1H3a1 1 0 110-2h1v-1a1 1 0 011-1zM12 2a1 1 0 01.967.744L14.146 7.2 17.5 9.134a1 1 0 010 1.732l-3.354 1.935-1.18 4.455a1 1 0 01-1.933 0L9.854 12.8 6.5 10.866a1 1 0 010-1.732l3.354-1.935 1.18-4.455A1 1 0 0112 2z" clip-rule="evenodd" />
                </svg>
                新
              </span>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <button
                v-if="editable && !isCompleted(chapter.chapter_number) && hasCompletedChapters"
                type="button"
                class="p-1.5 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors"
                title="根据已完成章节重新生成此章大纲"
                :disabled="regenerating"
                @click="handleRegenerateSingle(chapter.chapter_number)"
              >
                <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
              <span class="text-xs text-slate-400">#{{ chapter.chapter_number }}</span>
            </div>
          </div>
          <p class="mt-3 text-sm text-slate-600 leading-6 whitespace-pre-line">{{ chapter.summary || '暂无摘要' }}</p>
        </div>
      </li>
      <li v-if="!outline.length" class="ml-6 text-slate-400 text-sm">暂无章节大纲</li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

interface OutlineItem {
  chapter_number: number
  title: string
  summary: string
}

interface ChapterItem {
  chapter_number: number
  generation_status?: string
}

const props = defineProps<{
  outline: OutlineItem[]
  chapters?: ChapterItem[]
  editable?: boolean
}>()

const regenerating = ref(false)
const regeneratedNumbers = ref<Set<number>>(new Set())
const regenerateResult = ref<{ updated: number; total: number } | null>(null)

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
  (e: 'add'): void
  (e: 'regenerate', payload: { chapterNumbers?: number[] }): void
}>()

const completedNumbers = computed(() => {
  if (!props.chapters) return new Set<number>()
  return new Set(
    props.chapters
      .filter(ch => ch.generation_status === 'successful')
      .map(ch => ch.chapter_number)
  )
})

const hasCompletedChapters = computed(() => completedNumbers.value.size > 0)

const uncompletedCount = computed(() => {
  return props.outline.filter(o => !completedNumbers.value.has(o.chapter_number)).length
})

const isCompleted = (chapterNumber: number): boolean => {
  return completedNumbers.value.has(chapterNumber)
}

const isRegenerated = (chapterNumber: number): boolean => {
  return regeneratedNumbers.value.has(chapterNumber)
}

const clearRegenerated = () => {
  regeneratedNumbers.value = new Set()
  regenerateResult.value = null
}

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}

const handleRegenerateAll = () => {
  if (regenerating.value) return
  emit('regenerate', {})
}

const handleRegenerateSingle = (chapterNumber: number) => {
  if (regenerating.value) return
  emit('regenerate', { chapterNumbers: [chapterNumber] })
}

const markRegenerated = (updatedChapters: number[], totalTarget: number) => {
  regeneratedNumbers.value = new Set(updatedChapters)
  regenerateResult.value = { updated: updatedChapters.length, total: totalTarget }
}

defineExpose({
  setRegenerating: (v: boolean) => { regenerating.value = v },
  markRegenerated,
})
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChapterOutlineSection'
})
</script>

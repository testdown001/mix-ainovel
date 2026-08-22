<template>
  <div class="reference-input-wrap">
    <div class="header-row">
      <h3 class="title">本书参考小说（可选，最多 3 本）</h3>
      <button
        v-if="rows.length < 3"
        type="button"
        class="add-btn"
        @click="addRow"
      >
        + 添加
      </button>
    </div>

    <transition-group name="fade-slide" tag="div" class="rows">
      <div
        v-for="(name, index) in rows"
        :key="`reference-${index}`"
        class="input-block"
      >
        <!-- Input + inline mini buttons -->
        <div class="input-row">
          <input
            :value="name"
            type="text"
            class="novel-input"
            placeholder="例如：斗破苍穹"
            @input="onInput(index, ($event.target as HTMLInputElement).value)"
          />
          <button
            v-if="name"
            type="button"
            class="clear-btn"
            @click="clearRow(index)"
            title="清空"
          >✕</button>
          <button
            v-if="rows.length > 1"
            type="button"
            class="remove-btn"
            @click="removeRow(index)"
            title="删除该行"
          >删除</button>
        </div>

        <!-- Library select link — sits below the input row -->
        <button
          type="button"
          class="select-link"
          @click="openLibrary(index)"
        >
          <svg class="select-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
          {{ name ? '管理本书参考' : '添加本书参考' }}
        </button>
      </div>
    </transition-group>

    <transition name="fade">
      <p
        v-if="searchStatus !== 'idle' || statusMessage"
        :class="['status-text', `status-${searchStatus}`]"
      >
        {{ renderedStatus }}
      </p>
    </transition>

    <ReferenceNovelLibrary
      v-model:show="libraryVisible"
      :selected-novel-ids="selectedNovelIds"
      @select="handleLibrarySelect"
      @remove="handleLibraryRemove"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ReferenceNovelSummary } from '@/api/novel'
import ReferenceNovelLibrary from './ReferenceNovelLibrary.vue'
import { addLibraryReference } from '@/utils/referenceNovelSelection'

type SearchStatus = 'idle' | 'searching' | 'success' | 'error' | 'skipped'

const props = withDefaults(
  defineProps<{
    modelValue?: string[]
    searchStatus?: SearchStatus
    statusMessage?: string
  }>(),
  {
    modelValue: () => [],
    searchStatus: 'idle',
    statusMessage: ''
  }
)

interface LibrarySelection {
  index: number
  id: number | null
  title: string
}

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
  'library-selection-change': [selections: LibrarySelection[]]
}>()

const rows = ref<string[]>([''])
const librarySelections = ref<(number | null)[]>([null])
const libraryVisible = ref(false)
const libraryRowIndex = ref(0)
const selectedNovelIds = computed(() =>
  librarySelections.value.filter((id): id is number => id !== null),
)

const normalizeRows = (values: string[] | undefined): string[] => {
  const target = Array.isArray(values) ? values.slice(0, 3) : []
  return target.length > 0 ? target : ['']
}

const syncLibrarySelections = () => {
  while (librarySelections.value.length < rows.value.length) {
    librarySelections.value.push(null)
  }
  if (librarySelections.value.length > rows.value.length) {
    librarySelections.value.splice(rows.value.length)
  }
}

const emitRows = () => {
  emit('update:modelValue', rows.value.slice(0, 3))
}

const emitLibrarySelection = () => {
  const selections: LibrarySelection[] = rows.value.map((title, idx) => ({
    index: idx,
    id: librarySelections.value[idx] ?? null,
    title: title ?? ''
  }))
  emit('library-selection-change', selections)
}

watch(
  () => props.modelValue,
  (next) => {
    rows.value = normalizeRows(next)
    syncLibrarySelections()
    emitLibrarySelection()
  },
  { immediate: true, deep: true }
)

const addRow = () => {
  if (rows.value.length >= 3) return
  rows.value.push('')
  librarySelections.value.push(null)
  emitRows()
  emitLibrarySelection()
}

const removeRow = (index: number) => {
  rows.value.splice(index, 1)
  librarySelections.value.splice(index, 1)
  if (rows.value.length === 0) {
    rows.value.push('')
    librarySelections.value.push(null)
  }
  emitRows()
  emitLibrarySelection()
}

const clearRow = (index: number) => {
  rows.value[index] = ''
  librarySelections.value[index] = null
  emitRows()
  emitLibrarySelection()
}

const onInput = (index: number, value: string) => {
  rows.value[index] = value
  librarySelections.value[index] = null
  emitRows()
  emitLibrarySelection()
}

const openLibrary = (index: number) => {
  libraryRowIndex.value = index
  libraryVisible.value = true
}

const handleLibrarySelect = (novel: ReferenceNovelSummary) => {
  const next = addLibraryReference(
    { rows: rows.value, selectedIds: librarySelections.value },
    libraryRowIndex.value,
    novel,
  )
  rows.value = next.rows
  librarySelections.value = next.selectedIds
  emitRows()
  emitLibrarySelection()
  libraryVisible.value = false
}

const handleLibraryRemove = (novelId: number) => {
  const index = librarySelections.value.findIndex((id) => id === novelId)
  if (index >= 0) removeRow(index)
}

const renderedStatus = computed(() => {
  if (props.statusMessage) return props.statusMessage
  if (props.searchStatus === 'searching') return '正在搜索参考小说信息...'
  if (props.searchStatus === 'success') return '参考小说搜索完成'
  if (props.searchStatus === 'error') return '参考小说搜索失败，已自动降级'
  if (props.searchStatus === 'skipped') return '未启用搜索模型，已跳过'
  return ''
})
</script>

<style scoped>
.reference-input-wrap {
  margin: 0 auto 1.5rem;
  text-align: left;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}

.add-btn {
  flex-shrink: 0;
  border: 1px solid #2A2A2A;
  border-radius: 9999px;
  background: #1C1C1C;
  color: #FFE500;
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
}

.add-btn:hover {
  background: #2A2A2A;
}

.rows {
  display: grid;
  gap: 10px;
}

/* Each novel row is a column block: input row + library link */
.input-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.input-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.novel-input {
  flex: 1;
  min-width: 0;
  border: 1px solid #2A2A2A;
  border-radius: 10px;
  padding: 9px 12px;
  font-size: 13px;
  color: #fff;
  background: #1C1C1C;
  outline: none;
  transition: border-color 0.15s;
}

.novel-input:focus {
  border-color: #FFE500;
  box-shadow: 0 0 0 2px rgba(255, 229, 0, 0.12);
}

.novel-input::placeholder {
  color: #555;
}

.clear-btn {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #2A2A2A;
  border-radius: 8px;
  background: #1C1C1C;
  color: #666;
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s, background 0.15s;
  padding: 0;
}

.clear-btn:hover {
  background: #2A2A2A;
  color: #fff;
}

.remove-btn {
  flex-shrink: 0;
  border: 1px solid rgba(255, 71, 87, 0.2);
  border-radius: 8px;
  padding: 4px 8px;
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
  background: rgba(255, 71, 87, 0.08);
  color: #FF4757;
  transition: background 0.15s;
}

.remove-btn:hover {
  background: rgba(255, 71, 87, 0.18);
}

/* Library link — sits below the input, left-aligned */
.select-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: none;
  border: none;
  cursor: pointer;
  color: #888;
  font-size: 12px;
  padding: 0 2px;
  transition: color 0.15s;
  text-align: left;
}

.select-link:hover {
  color: #FFE500;
}

.select-icon {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
}

.status-text {
  margin: 10px 0 0;
  font-size: 12px;
}

.status-idle  { color: #888; }
.status-searching { color: #FFE500; }
.status-success   { color: #2ED573; }
.status-error     { color: #FF4757; }
.status-skipped   { color: #888; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.fade-slide-enter-active, .fade-slide-leave-active { transition: all 0.22s ease; }
.fade-slide-enter-from, .fade-slide-leave-to { opacity: 0; transform: translateY(-6px); }
</style>

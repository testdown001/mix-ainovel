<template>
  <div class="reference-input-wrap">
    <div class="header-row">
      <h3 class="title">参考小说（可选，最多 3 本）</h3>
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
        class="input-row"
      >
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
        >
          清空
        </button>
        <button
          v-if="rows.length > 1"
          type="button"
          class="remove-btn"
          @click="removeRow(index)"
        >
          删除
        </button>
        <button
          type="button"
          class="select-btn"
          @click="openLibrary(index)"
        >
          从库中选择
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
      @select="handleLibrarySelect"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ReferenceNovelSummary } from '@/api/novel'
import ReferenceNovelLibrary from './ReferenceNovelLibrary.vue'

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
  const index = libraryRowIndex.value
  if (index >= rows.value.length) {
    rows.value.push(novel.title)
    librarySelections.value.push(novel.id)
  } else {
    rows.value[index] = novel.title
    librarySelections.value[index] = novel.id
  }
  emitRows()
  emitLibrarySelection()
  libraryVisible.value = false
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
  max-width: 760px;
  text-align: left;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 0.75rem;
}

.title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: #374151;
}

.add-btn {
  border: 0;
  border-radius: 9999px;
  background: #e0f2fe;
  color: #0369a1;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.35rem 0.85rem;
  cursor: pointer;
}

.add-btn:hover {
  background: #bae6fd;
}

.rows {
  display: grid;
  gap: 0.6rem;
}

.input-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.novel-input {
  flex: 1;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 0.6rem 0.8rem;
  font-size: 0.92rem;
  color: #111827;
  background: rgba(255, 255, 255, 0.95);
}

.novel-input:focus {
  outline: none;
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.2);
}

.clear-btn,
.remove-btn {
  border: 0;
  border-radius: 8px;
  padding: 0.45rem 0.65rem;
  font-size: 0.78rem;
  cursor: pointer;
}

.clear-btn {
  background: #f3f4f6;
  color: #4b5563;
}

.clear-btn:hover {
  background: #e5e7eb;
}

.remove-btn {
  background: #fee2e2;
  color: #b91c1c;
}

.remove-btn:hover {
  background: #fecaca;
}

.select-btn {
  background: #e0e7ff;
  color: #3730a3;
  border-radius: 8px;
  border: 0;
  padding: 0.45rem 0.65rem;
  font-size: 0.78rem;
  cursor: pointer;
}

.select-btn:hover {
  background: #c7d2fe;
}

.status-text {
  margin: 0.8rem 0 0;
  font-size: 0.85rem;
}

.status-idle {
  color: #6b7280;
}

.status-searching {
  color: #2563eb;
}

.status-success {
  color: #047857;
}

.status-error {
  color: #b91c1c;
}

.status-skipped {
  color: #6b7280;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.22s ease;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 767px) {
  .input-row {
    flex-wrap: wrap;
  }
}
</style>

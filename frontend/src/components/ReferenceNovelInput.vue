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
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

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

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const rows = ref<string[]>([''])

const normalizeRows = (values: string[] | undefined): string[] => {
  const target = Array.isArray(values) ? values.slice(0, 3) : []
  return target.length > 0 ? target : ['']
}

watch(
  () => props.modelValue,
  (next) => {
    rows.value = normalizeRows(next)
  },
  { immediate: true, deep: true }
)

const emitRows = () => {
  emit('update:modelValue', rows.value.slice(0, 3))
}

const addRow = () => {
  if (rows.value.length >= 3) return
  rows.value.push('')
  emitRows()
}

const removeRow = (index: number) => {
  rows.value.splice(index, 1)
  if (rows.value.length === 0) {
    rows.value.push('')
  }
  emitRows()
}

const clearRow = (index: number) => {
  rows.value[index] = ''
  emitRows()
}

const onInput = (index: number, value: string) => {
  rows.value[index] = value
  emitRows()
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

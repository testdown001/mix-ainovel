<!-- AIMETA P=概览区_小说基本信息|R=基本信息展示|NR=不含编辑功能|E=component:OverviewSection|X=ui|A=概览组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-5">
    <!-- 核心摘要 -->
    <div class="rounded-2xl border border-[#2A2A2A] bg-[#141414] p-6">
      <div class="flex items-start justify-between gap-4 mb-3">
        <div>
          <h3 class="text-xs font-semibold text-[#FFE500] uppercase tracking-widest mb-1">核心摘要</h3>
          <p class="text-[#555] text-xs">快速了解项目的定位与调性</p>
        </div>
        <button
          v-if="editable"
          type="button"
          class="text-[#555] hover:text-[#FFE500] transition-colors"
          @click="emitEdit('one_sentence_summary', '核心摘要', data?.one_sentence_summary)">
          <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
            <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
      <p class="text-white text-base leading-relaxed min-h-[2.5rem]">{{ data?.one_sentence_summary || '暂无' }}</p>
    </div>

    <!-- 四格信息 -->
    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      <div v-for="(item, key) in metaFields" :key="key" class="rounded-2xl border border-[#2A2A2A] bg-[#141414] p-4">
        <h4 class="text-xs font-semibold text-[#666] uppercase tracking-wide mb-2">{{ item.label }}</h4>
        <p class="text-sm font-medium text-white min-h-[1.5rem]">{{ item.value || '暂无' }}</p>
      </div>
    </div>

    <!-- 完整剧情梗概 -->
    <div class="rounded-2xl border border-[#2A2A2A] bg-[#141414] p-6">
      <div class="flex items-start justify-between gap-4 mb-4">
        <h3 class="text-base font-semibold text-white">完整剧情梗概</h3>
        <button
          v-if="editable"
          type="button"
          class="text-[#555] hover:text-[#FFE500] transition-colors flex-shrink-0"
          @click="emitEdit('full_synopsis', '完整剧情梗概', data?.full_synopsis)">
          <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
            <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
      <div class="text-sm text-[#aaa] leading-7 whitespace-pre-line">
        <p>{{ data?.full_synopsis || '暂无' }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface OverviewData {
  one_sentence_summary?: string | null
  target_audience?: string | null
  genre?: string | null
  style?: string | null
  tone?: string | null
  full_synopsis?: string | null
}

const props = defineProps<{
  data: OverviewData | null
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
}>()

const metaFields = computed(() => [
  { label: '目标受众', value: props.data?.target_audience },
  { label: '类型', value: props.data?.genre },
  { label: '风格', value: props.data?.style },
  { label: '基调', value: props.data?.tone },
])

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'OverviewSection'
})
</script>

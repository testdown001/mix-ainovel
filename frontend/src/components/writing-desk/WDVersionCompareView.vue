<!-- AIMETA P=版本对比分屏|R=两版本并排全文对比+直接选用(写作场景最高频决策动作)|NR=不含生成逻辑|E=component:WDVersionCompareView|X=ui|A=对比视图|D=vue|S=dom -->
<template>
  <div v-if="show" class="fixed inset-0 z-50 flex flex-col" style="background: rgba(8, 8, 8, 0.98);">
    <!-- 顶栏 -->
    <div class="flex items-center justify-between px-5 h-14 border-b flex-shrink-0"
      style="border-color: #2a2a2a; background: #141414;">
      <div class="flex items-center gap-3 min-w-0">
        <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2"
          viewBox="0 0 24 24" style="color: #ffe500;">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 4v16m6-16v16M4 4h16v16H4z"/>
        </svg>
        <h3 class="text-sm font-semibold text-white">版本对比</h3>
        <span class="text-xs hidden sm:block" style="color: #666;">左右独立滚动 · 选定即确认为本章正文</span>
      </div>
      <button @click="$emit('close')" class="p-2 rounded-lg transition-colors compare-close" title="关闭(Esc)">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- 双栏 -->
    <div class="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-2">
      <section v-for="side in sides" :key="side"
        class="flex flex-col min-h-0 compare-col">
        <!-- 栏头：版本切换 + 元信息 + 选用 -->
        <div class="flex items-center gap-2.5 px-4 py-2.5 border-b flex-shrink-0 flex-wrap"
          style="border-color: #1f1f1f; background: #101010;">
          <select :value="indices[side]" @change="onPick(side, $event)" class="compare-select">
            <option v-for="(v, i) in versions" :key="i" :value="i" :disabled="i === indices[otherOf(side)]">
              版本 {{ i + 1 }}{{ isBest(i) ? '（AI推荐）' : '' }}
            </option>
          </select>
          <span class="text-xs" style="color: #666;">
            约 {{ wordCountOf(indices[side]) }} 字 · {{ styleOf(indices[side]) }}
          </span>
          <span v-if="isBest(indices[side])" class="compare-tag" style="color: #ffe500; border-color: #ffe50040;">AI推荐</span>
          <span v-if="isCurrent(indices[side])" class="compare-tag" style="color: #2ed573; border-color: #2ed57340;">当前选中</span>
          <span class="flex-1"></span>
          <button class="compare-use-btn" :disabled="isCurrent(indices[side]) || selecting"
            @click="$emit('select', indices[side])">
            {{ selecting ? '确认中…' : isCurrent(indices[side]) ? '当前版本' : '选用此版本' }}
          </button>
        </div>
        <!-- 正文 -->
        <div class="flex-1 overflow-y-auto px-6 py-5 compare-scroll">
          <div class="whitespace-pre-wrap"
            style="color: #cccccc; font-size: 15px; line-height: 1.9; max-width: 720px; margin: 0 auto;">
            {{ contentOf(indices[side]) }}
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, watch } from 'vue'
import type { ChapterVersion } from '@/api/novel'
import { cleanVersionContent } from '@/utils/versionContent'

const props = defineProps<{
  show: boolean
  versions: ChapterVersion[]
  /** 章节当前定稿内容，用于标注「当前选中」 */
  currentContent: string | null
  selecting?: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'select', index: number): void
}>()

const sides = ['left', 'right'] as const
type Side = (typeof sides)[number]

const indices = reactive<Record<Side, number>>({ left: 0, right: 1 })
const otherOf = (s: Side): Side => (s === 'left' ? 'right' : 'left')

const isBest = (i: number): boolean =>
  Boolean((props.versions[i]?.metadata as any)?.ai_review?.is_best)

const contentOf = (i: number): string => cleanVersionContent(props.versions[i]?.content || '')

const wordCountOf = (i: number): number => Math.round(contentOf(i).length / 100) * 100

const styleOf = (i: number): string => (props.versions[i] as any)?.style || '标准'

const isCurrent = (i: number): boolean => {
  if (!props.currentContent || !props.versions[i]?.content) return false
  return cleanVersionContent(props.currentContent) === contentOf(i)
}

const onPick = (side: Side, e: Event) => {
  indices[side] = Number((e.target as HTMLSelectElement).value)
}

// 打开时初始化：左 = AI 推荐（或版本1），右 = 另一个版本
watch(
  () => props.show,
  (visible) => {
    if (!visible) return
    const best = props.versions.findIndex((_, i) => isBest(i))
    const left = best >= 0 ? best : 0
    indices.left = left
    const right = props.versions.findIndex((_, i) => i !== left)
    indices.right = right >= 0 ? right : left
  },
)

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && props.show) emit('close')
}
onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.compare-col + .compare-col {
  border-left: 1px solid #1f1f1f;
}
@media (max-width: 767px) {
  .compare-col + .compare-col {
    border-left: none;
    border-top: 1px solid #1f1f1f;
  }
}
.compare-select {
  padding: 5px 8px;
  border-radius: 8px;
  font-size: 12px;
  color: #fff;
  background: #1c1c1c;
  border: 1px solid #2a2a2a;
  outline: none;
}
.compare-select:focus {
  border-color: #ffe500;
}
.compare-tag {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 999px;
  border: 1px solid;
  white-space: nowrap;
}
.compare-use-btn {
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  background: #ffe500;
  color: #000;
  border: none;
  cursor: pointer;
  white-space: nowrap;
  transition: opacity 0.15s;
}
.compare-use-btn:disabled {
  background: transparent;
  border: 1px solid #2a2a2a;
  color: #666;
  cursor: not-allowed;
}
.compare-close {
  color: #888;
}
.compare-close:hover {
  color: #fff;
}
.compare-scroll::-webkit-scrollbar {
  width: 6px;
}
.compare-scroll::-webkit-scrollbar-track {
  background: transparent;
}
.compare-scroll::-webkit-scrollbar-thumb {
  background: #2a2a2a;
  border-radius: 6px;
}
</style>

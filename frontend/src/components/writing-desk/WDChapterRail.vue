<!-- AIMETA P=写作台章节轨_紧凑章节导航|R=章节选择_状态展示_工具入口|NR=不含章节编辑|E=component:WDChapterRail|X=ui|A=导航组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <aside class="chapter-rail">
    <div class="rail-head">
      <div>
        <p class="rail-kicker">MANUSCRIPT</p>
        <h2>章节目录</h2>
      </div>
      <div class="rail-actions">
        <button type="button" title="写作台工具" @click="emit('openTools')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <circle cx="12" cy="5" r="1.2" /><circle cx="12" cy="12" r="1.2" /><circle cx="12" cy="19" r="1.2" />
          </svg>
        </button>
        <button type="button" title="生成或调整大纲" @click="emit('generateOutline')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
      </div>
    </div>

    <div ref="listEl" class="rail-list">
      <button
        v-for="outline in visibleOutlines"
        :key="outline.chapter_number"
        :ref="(el) => setRowRef(outline.chapter_number, el)"
        type="button"
        class="chapter-row"
        :class="{ active: outline.chapter_number === selectedChapterNumber }"
        @click="emit('selectChapter', outline.chapter_number)"
      >
        <span class="row-accent"></span>
        <span class="chapter-index" :class="statusClass(outline.chapter_number)">
          <svg v-if="statusOf(outline.chapter_number) === 'done'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <path d="m6.5 12.5 3.3 3.3 7.7-8" />
          </svg>
          <svg v-else-if="statusOf(outline.chapter_number) === 'working'" class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20 12a8 8 0 1 1-2.35-5.65" /><path d="M20 5v7h-7" />
          </svg>
          <span v-else>{{ String(outline.chapter_number).padStart(2, '0') }}</span>
        </span>
        <span class="chapter-copy">
          <span class="chapter-title">第{{ outline.chapter_number }}章 · {{ outline.title }}</span>
          <span class="chapter-summary">{{ outline.summary || '尚未填写章节摘要' }}</span>
        </span>
        <span class="chapter-state" :class="statusClass(outline.chapter_number)">
          {{ statusLabel(outline.chapter_number) }}
        </span>
      </button>

      <button v-if="canExpand" type="button" class="expand-button" @click="expanded = !expanded">
        <span>{{ expanded ? '收起章节' : '展开更多' }}</span>
        <svg :class="{ rotated: expanded }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="m8 10 4 4 4-4" />
        </svg>
      </button>
    </div>

    <div class="rail-foot">
      <div class="progress-copy">
        <span>全书进度</span>
        <strong>{{ completedCount }} / {{ outlines.length }}</strong>
      </div>
      <div class="progress-track"><span :style="{ width: progress + '%' }"></span></div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch, type ComponentPublicInstance } from 'vue'
import type { Chapter, ChapterOutline, NovelProject } from '@/api/novel'

const props = defineProps<{
  project: NovelProject
  selectedChapterNumber: number | null
  generatingChapter: number | null
  evaluatingChapter: number | null
}>()

const emit = defineEmits<{
  selectChapter: [chapterNumber: number]
  generateOutline: []
  openTools: []
}>()

const expanded = ref(false)
const listEl = ref<HTMLElement | null>(null)
const rowRefs = new Map<number, HTMLElement>()

const outlines = computed(() =>
  [...(props.project.blueprint?.chapter_outline || [])].sort(
    (left, right) => left.chapter_number - right.chapter_number,
  ),
)

const canExpand = computed(() => outlines.value.length > 7)

const visibleOutlines = computed<ChapterOutline[]>(() => {
  if (expanded.value || !canExpand.value) return outlines.value
  const selectedIndex = Math.max(
    0,
    outlines.value.findIndex((item) => item.chapter_number === props.selectedChapterNumber),
  )
  const start = Math.max(0, Math.min(selectedIndex - 2, outlines.value.length - 7))
  return outlines.value.slice(start, start + 7)
})

const completedCount = computed(
  () => props.project.chapters.filter((chapter) => chapter.generation_status === 'successful').length,
)
const progress = computed(() =>
  outlines.value.length ? Math.round((completedCount.value / outlines.value.length) * 100) : 0,
)

function chapterOf(chapterNumber: number): Chapter | undefined {
  return props.project.chapters.find((chapter) => chapter.chapter_number === chapterNumber)
}

function statusOf(chapterNumber: number): 'done' | 'working' | 'predicted' | 'planned' {
  const chapter = chapterOf(chapterNumber)
  if (chapter?.generation_status === 'successful') return 'done'
  if (
    props.generatingChapter === chapterNumber ||
    props.evaluatingChapter === chapterNumber ||
    ['generating', 'evaluating', 'selecting', 'waiting_for_confirm'].includes(
      chapter?.generation_status || '',
    )
  ) {
    return 'working'
  }
  const outline = outlines.value.find((item) => item.chapter_number === chapterNumber)
  return outline?.metadata?.prediction ? 'predicted' : 'planned'
}

function statusLabel(chapterNumber: number): string {
  const status = statusOf(chapterNumber)
  if (status === 'done') return '已完成'
  if (status === 'working') return '进行中'
  if (status === 'predicted') return '已推演'
  return '规划中'
}

function statusClass(chapterNumber: number): string {
  return `is-${statusOf(chapterNumber)}`
}

function setRowRef(chapterNumber: number, element: Element | ComponentPublicInstance | null) {
  if (element instanceof HTMLElement) rowRefs.set(chapterNumber, element)
}

watch(
  () => props.selectedChapterNumber,
  async (chapterNumber) => {
    await nextTick()
    if (chapterNumber !== null) {
      rowRefs.get(chapterNumber)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  },
)
</script>

<style scoped>
.chapter-rail {
  display: flex;
  width: 306px;
  min-width: 306px;
  height: 100%;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid #242521;
  border-radius: 18px;
  background: rgba(17, 18, 16, 0.96);
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.28);
}
.rail-head { display: flex; align-items: center; justify-content: space-between; padding: 22px 18px 15px 22px; }
.rail-kicker { margin: 0 0 4px; color: #5f625b; font-size: 9px; font-weight: 800; letter-spacing: .17em; }
.rail-head h2 { margin: 0; color: #f5f5ef; font-size: 17px; font-weight: 680; }
.rail-actions { display: flex; gap: 5px; }
.rail-actions button { display: grid; width: 30px; height: 30px; place-items: center; border: 1px solid #2a2c27; border-radius: 8px; color: #898c84; background: #191a18; transition: .18s ease; }
.rail-actions button:hover { border-color: #4a4c42; color: #ffe500; }
.rail-actions svg { width: 16px; height: 16px; }
.rail-list { flex: 1; min-height: 0; overflow-y: auto; padding: 4px 10px 16px; scrollbar-width: thin; scrollbar-color: #33352f transparent; }
.chapter-row { position: relative; display: grid; width: 100%; grid-template-columns: 37px minmax(0,1fr); gap: 11px; min-height: 82px; margin-bottom: 4px; padding: 13px 11px; overflow: hidden; border: 1px solid transparent; border-radius: 12px; color: inherit; text-align: left; background: transparent; transition: .18s ease; }
.chapter-row:hover { background: #191a17; }
.chapter-row.active { border-color: #30322c; background: #20211d; box-shadow: inset 0 1px rgba(255,255,255,.015); }
.row-accent { position: absolute; top: 13px; bottom: 13px; left: 0; width: 3px; border-radius: 0 4px 4px 0; background: transparent; }
.chapter-row.active .row-accent { background: #ffe500; box-shadow: 0 0 16px rgba(255,229,0,.24); }
.chapter-index { display: grid; width: 36px; height: 36px; place-items: center; border: 1px solid #343630; border-radius: 50%; color: #858880; font-size: 11px; font-weight: 750; font-variant-numeric: tabular-nums; background: #20211e; }
.chapter-index svg { width: 17px; height: 17px; }
.chapter-index.is-done { border-color: rgba(48,211,124,.25); color: #36d885; background: rgba(25,126,75,.15); }
.chapter-index.is-working { border-color: rgba(255,229,0,.25); color: #ffe500; background: rgba(255,229,0,.08); }
.chapter-row.active .chapter-index.is-planned,
.chapter-row.active .chapter-index.is-predicted { border-color: #ffe500; color: #0d0e0c; background: #ffe500; }
.chapter-copy { display: flex; min-width: 0; flex-direction: column; padding-right: 48px; }
.chapter-title { overflow: hidden; color: #ebebe5; font-size: 13px; font-weight: 650; line-height: 20px; text-overflow: ellipsis; white-space: nowrap; }
.chapter-summary { display: -webkit-box; margin-top: 5px; overflow: hidden; color: #797c75; font-size: 11px; line-height: 17px; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.chapter-state { position: absolute; top: 14px; right: 10px; color: #71746d; font-size: 9px; font-weight: 650; }
.chapter-state.is-done { color: #35ca7e; }
.chapter-state.is-working, .chapter-state.is-predicted { color: #d5c61d; }
.expand-button { display: flex; width: calc(100% - 12px); align-items: center; justify-content: center; gap: 6px; margin: 10px 6px 0; padding: 9px; border: 1px dashed #30322c; border-radius: 9px; color: #74776f; font-size: 11px; background: transparent; }
.expand-button:hover { color: #d8d8cf; background: #191a17; }
.expand-button svg { width: 14px; height: 14px; transition: .18s ease; }
.expand-button svg.rotated { transform: rotate(180deg); }
.rail-foot { padding: 15px 20px 18px; border-top: 1px solid #23241f; background: #121310; }
.progress-copy { display: flex; align-items: center; justify-content: space-between; margin-bottom: 9px; color: #777a72; font-size: 10px; }
.progress-copy strong { color: #c8c9c0; font-size: 10px; }
.progress-track { height: 3px; overflow: hidden; border-radius: 99px; background: #292a26; }
.progress-track span { display: block; height: 100%; border-radius: inherit; background: #ffe500; transition: width .3s ease; }
.spin { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 1279px) { .chapter-rail { width: 270px; min-width: 270px; } }
</style>

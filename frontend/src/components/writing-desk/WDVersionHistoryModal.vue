<!-- AIMETA P=M3版本历史弹窗|R=历史浏览_两版Diff_恢复快照|NR=不直接编辑历史正文|E=component:WDVersionHistoryModal|X=ui|A=版本追溯|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <Teleport to="body">
    <div v-if="show" class="history-mask" @click.self="emit('close')">
      <section class="history-dialog" aria-modal="true" aria-label="章节修订历史">
        <header class="history-header">
          <div>
            <small>不可变修订记录</small>
            <h3>第 {{ chapterNumber }} 章 · 修订历史</h3>
            <p>历史正文只读；共 {{ totalCount }} 个版本，正文约 {{ formattedStorage }}。</p>
          </div>
          <button type="button" class="close-button" aria-label="关闭" @click="emit('close')">×</button>
        </header>

        <div v-if="loading" class="history-empty">正在读取历史版本…</div>
        <div v-else-if="error" class="history-empty history-error">{{ error }}</div>
        <div v-else-if="!items.length" class="history-empty">本章暂时还没有可查看的版本。</div>
        <div v-else class="history-body">
          <aside class="history-list">
            <article
              v-for="item in items"
              :key="item.id"
              class="history-item"
              :class="{ current: item.is_selected }"
            >
              <div class="history-item__title">
                <strong>{{ item.source_label }}</strong>
                <span v-if="item.is_selected">当前正文</span>
              </div>
              <p>{{ formatTime(item.created_at) }} · {{ item.word_count }} 字</p>
              <p v-if="item.change_note" class="history-item__note">{{ item.change_note }}</p>
              <div class="history-item__actions">
                <button type="button" :class="{ picked: leftId === item.id }" @click="leftId = item.id; compare()">左侧</button>
                <button type="button" :class="{ picked: rightId === item.id }" @click="rightId = item.id; compare()">右侧</button>
                <button
                  type="button"
                  class="restore"
                  :disabled="restoring || item.is_selected || !contentHash"
                  @click="restore(item)"
                >
                  {{ item.is_selected ? '当前版本' : '恢复为新版本' }}
                </button>
              </div>
            </article>
            <button
              v-if="hasMore"
              type="button"
              class="history-load-more"
              :disabled="loadingMore"
              @click="loadMore"
            >
              {{ loadingMore ? '正在加载…' : '加载更早版本' }}
            </button>
          </aside>

          <main class="diff-pane">
            <div class="diff-toolbar">
              <span>{{ comparison ? '红色为左版删改，绿色为右版新增' : '从左侧和右侧各选择一个版本进行比较' }}</span>
              <span v-if="comparing">计算差异中…</span>
            </div>
            <div v-if="comparison" class="diff-columns">
              <section class="diff-column">
                <header>{{ versionName(leftId) }}</header>
                <p class="diff-text"><span v-for="(segment, index) in comparison.left_segments" :key="index" :class="`diff-${segment.kind}`">{{ segment.text }}</span></p>
              </section>
              <section class="diff-column">
                <header>{{ versionName(rightId) }}</header>
                <p class="diff-text"><span v-for="(segment, index) in comparison.right_segments" :key="index" :class="`diff-${segment.kind}`">{{ segment.text }}</span></p>
              </section>
            </div>
          </main>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import { NovelAPI, type ChapterVersionDiff, type ChapterVersionHistoryItem } from '@/api/novel'
import { useNovelStore } from '@/stores/novel'

const props = defineProps<{
  show: boolean
  projectId: string
  chapterNumber: number
  revisionId: number
  contentHash: string | null | undefined
}>()

const emit = defineEmits<{ close: []; restored: [] }>()
const novelStore = useNovelStore()
const items = ref<ChapterVersionHistoryItem[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const comparing = ref(false)
const restoring = ref(false)
const error = ref('')
const leftId = ref<number | null>(null)
const rightId = ref<number | null>(null)
const comparison = ref<ChapterVersionDiff | null>(null)
const totalCount = ref(0)
const totalContentBytes = ref(0)
const hasMore = ref(false)
const nextBeforeId = ref<number | null>(null)

const formattedStorage = computed(() => {
  const bytes = totalContentBytes.value
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
})

const itemById = computed(() => new Map(items.value.map((item) => [item.id, item])))

function formatTime(value?: string | null) {
  if (!value) return '时间未知'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function versionName(id: number | null) {
  const item = id ? itemById.value.get(id) : null
  return item ? `${item.source_label} · ${formatTime(item.created_at)}` : '未选择版本'
}

async function loadHistory() {
  if (!props.projectId || !props.chapterNumber) return
  loading.value = true
  error.value = ''
  comparison.value = null
  try {
    const page = await NovelAPI.listChapterVersionHistory(props.projectId, props.chapterNumber)
    items.value = page.items
    totalCount.value = page.total_count
    totalContentBytes.value = page.total_content_bytes
    hasMore.value = page.has_more
    nextBeforeId.value = page.next_before_id
    const selected = items.value.find((item) => item.is_selected) || items.value[0]
    leftId.value = selected?.id || null
    rightId.value = items.value.find((item) => item.id !== leftId.value)?.id || leftId.value
    await compare()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '读取历史版本失败'
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (!props.projectId || !props.chapterNumber || !hasMore.value || !nextBeforeId.value || loadingMore.value) return
  loadingMore.value = true
  try {
    const page = await NovelAPI.listChapterVersionHistory(props.projectId, props.chapterNumber, {
      beforeId: nextBeforeId.value,
    })
    items.value.push(...page.items)
    totalCount.value = page.total_count
    totalContentBytes.value = page.total_content_bytes
    hasMore.value = page.has_more
    nextBeforeId.value = page.next_before_id
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载更早版本失败'
  } finally {
    loadingMore.value = false
  }
}

async function compare() {
  if (!props.projectId || !leftId.value || !rightId.value) return
  comparing.value = true
  try {
    comparison.value = await NovelAPI.compareChapterVersions(props.projectId, leftId.value, rightId.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '计算版本差异失败'
  } finally {
    comparing.value = false
  }
}

async function restore(item: ChapterVersionHistoryItem) {
  if (!props.projectId || !props.contentHash || restoring.value) return
  const confirmed = await globalAlert.showConfirm(
    `将“${item.source_label}”恢复为新的当前正文。旧版本会完整保留。`,
    '恢复历史版本',
  )
  if (!confirmed) return
  restoring.value = true
  try {
    await novelStore.restoreChapterVersion(props.projectId, item.id, {
      expected_revision_id: props.revisionId,
      expected_content_hash: props.contentHash,
    })
    globalAlert.showSuccess('已创建恢复版本，历史记录保持不变。', '恢复完成')
    emit('restored')
    await loadHistory()
  } catch (err) {
    globalAlert.showError(err instanceof Error ? err.message : '恢复失败，请刷新后重试。', '恢复历史版本')
  } finally {
    restoring.value = false
  }
}

watch(
  () => [props.show, props.projectId, props.chapterNumber] as const,
  ([show]) => { if (show) void loadHistory() },
  { immediate: true },
)
</script>

<style scoped>
.history-mask { position: fixed; inset: 0; z-index: 2100; display: grid; place-items: center; padding: 18px; background: rgba(0,0,0,.68); backdrop-filter: blur(5px); }
.history-dialog { display: flex; width: min(1180px, 100%); max-height: min(780px, calc(100vh - 36px)); flex-direction: column; overflow: hidden; border: 1px solid #35372f; border-radius: 16px; color: #d7d9d1; background: #12130f; box-shadow: 0 30px 100px rgba(0,0,0,.6); }
.history-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 20px 22px 16px; border-bottom: 1px solid #2f312b; }
.history-header small { color: #8a8122; font-size: 9px; font-weight: 800; letter-spacing: .13em; }.history-header h3 { margin: 5px 0 4px; color: #f6f6ef; font-size: 18px; }.history-header p { margin: 0; color: #85887e; font-size: 11px; }.close-button { border: 0; color: #8b8e85; font-size: 26px; line-height: 1; background: transparent; }
.history-body { display: grid; min-height: 0; flex: 1; grid-template-columns: 310px minmax(0, 1fr); }.history-list { overflow-y: auto; border-right: 1px solid #2f312b; background: #161713; }.history-item { padding: 13px 14px; border-bottom: 1px solid #292b25; }.history-item.current { background: rgba(255,229,0,.06); }.history-item__title, .history-item__actions { display: flex; align-items: center; gap: 7px; }.history-item__title strong { color: #e7e8df; font-size: 12px; }.history-item__title span { padding: 2px 5px; border-radius: 4px; color: #0e100d; font-size: 9px; font-weight: 800; background: #ffe500; }.history-item p { margin: 5px 0 0; color: #777a71; font-size: 10px; }.history-item__note { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.history-item__actions { margin-top: 10px; }.history-item button { padding: 4px 7px; border: 1px solid #34362f; border-radius: 5px; color: #a6a99f; font-size: 10px; background: #1c1d19; }.history-item button.picked { border-color: #877d20; color: #f2df24; }.history-item button.restore { margin-left: auto; border-color: #58531d; color: #e9d727; }.history-item button:disabled { opacity: .45; cursor: not-allowed; }.history-load-more { display: block; width: calc(100% - 28px); margin: 14px; padding: 9px; border: 1px solid #45472e; border-radius: 7px; color: #d9cb30; font-size: 11px; background: #202018; }.history-load-more:disabled { opacity: .5; }
.diff-pane { display: flex; min-width: 0; flex-direction: column; overflow: hidden; }.diff-toolbar { display: flex; justify-content: space-between; gap: 12px; padding: 11px 16px; border-bottom: 1px solid #2b2d27; color: #85887e; font-size: 10px; }.diff-columns { display: grid; min-height: 0; flex: 1; grid-template-columns: repeat(2, minmax(0, 1fr)); overflow: auto; }.diff-column { min-width: 0; padding: 16px; }.diff-column + .diff-column { border-left: 1px solid #2b2d27; }.diff-column header { margin-bottom: 12px; color: #c8cabf; font-size: 11px; font-weight: 700; }.diff-text { margin: 0; color: #c4c6bd; font-size: 13px; line-height: 1.9; white-space: pre-wrap; word-break: break-word; }.diff-delete { border-radius: 2px; color: #ffb3ae; background: rgba(255,71,87,.2); }.diff-insert { border-radius: 2px; color: #b8f5cf; background: rgba(49,209,117,.19); }.history-empty { padding: 48px; color: #85887e; text-align: center; }.history-error { color: #f39c9d; }
@media (max-width: 780px) { .history-body { grid-template-columns: 1fr; overflow-y: auto; }.history-list { max-height: 280px; border-right: 0; border-bottom: 1px solid #2f312b; }.diff-columns { min-height: 460px; }.history-header p { max-width: 270px; }.history-dialog { max-height: calc(100vh - 20px); } }
</style>

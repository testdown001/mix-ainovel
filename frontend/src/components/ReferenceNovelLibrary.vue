<template>
  <!-- Dark custom modal overlay — no Naive UI -->
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="visible" class="modal-overlay" @click.self="visible = false">
        <div class="modal-card">

          <!-- Header -->
          <div class="modal-header">
            <div class="modal-title">
              <span class="modal-icon">📚</span>
              参考小说库
            </div>
            <button class="modal-close" @click="visible = false">
              <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Body -->
          <div class="modal-body">

            <!-- LEFT: list panel -->
            <div class="list-panel">

              <!-- Toolbar -->
              <div class="toolbar">
                <div class="search-wrap">
                  <svg class="search-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    v-model="searchTerm"
                    class="search-input"
                    placeholder="搜索参考小说..."
                    @input="loadNovelsDeferred"
                  />
                </div>
                <button class="btn-primary" @click="showAddForm = !showAddForm" :disabled="showAddForm">
                  <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M12 4v16m8-8H4" />
                  </svg>
                  添加
                </button>
                <button class="btn-ghost" @click="loadNovels" :disabled="loading">
                  <svg class="spin-icon" :class="{ spinning: loading }" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  刷新
                </button>
              </div>

              <!-- Inline add form -->
              <div v-if="showAddForm" class="add-form">
                <p class="add-form-title">添加参考小说</p>
                <input
                  ref="addTitleInputEl"
                  v-model="newTitle"
                  class="form-input"
                  placeholder="小说标题（必填）"
                  @keyup.enter="handleCreate"
                  @keyup.escape="cancelAdd"
                />
                <input
                  v-model="newAuthor"
                  class="form-input"
                  placeholder="作者（可选）"
                  @keyup.enter="handleCreate"
                  @keyup.escape="cancelAdd"
                />
                <input
                  v-model="newGenre"
                  class="form-input"
                  placeholder="题材（可选）"
                  @keyup.enter="handleCreate"
                  @keyup.escape="cancelAdd"
                />
                <div class="add-form-actions">
                  <button class="btn-primary" @click="handleCreate" :disabled="!newTitle.trim() || creating">
                    {{ creating ? '添加中...' : '确认添加' }}
                  </button>
                  <button class="btn-ghost" @click="cancelAdd">取消</button>
                </div>
              </div>

              <!-- Novel list -->
              <div class="novel-list" :class="{ 'has-form': showAddForm }">
                <!-- Loading -->
                <div v-if="loading && !filteredNovels.length" class="list-empty">
                  <div class="loading-dots">
                    <span></span><span></span><span></span>
                  </div>
                  <p>加载中...</p>
                </div>

                <!-- Empty -->
                <div v-else-if="!filteredNovels.length" class="list-empty">
                  <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                  <p>{{ searchTerm ? '未找到匹配的参考小说' : '暂无参考小说' }}</p>
                  <button v-if="!showAddForm && !searchTerm" class="btn-primary" @click="showAddForm = true">
                    添加第一本参考小说
                  </button>
                </div>

                <!-- Novel cards -->
                <div
                  v-for="novel in filteredNovels"
                  :key="novel.id"
                  class="novel-card"
                  :class="{ active: selectedNovelId === novel.id }"
                  @click="selectedNovelId = novel.id"
                >
                  <div class="card-top">
                    <div class="card-info">
                      <h4 class="card-title-text">{{ novel.title }}</h4>
                      <p class="card-meta">
                        {{ novel.author || '未知作者' }}
                        <span v-if="novel.genre"> · {{ novel.genre }}</span>
                      </p>
                    </div>
                    <span class="status-badge" :class="`status-${novel.status}`">
                      {{ statusLabel(novel.status) }}
                    </span>
                  </div>
                  <div class="card-actions">
                    <button class="action-primary" @click.stop="selectNovel(novel)">
                      ✓ 选择绑定
                    </button>
                    <button
                      v-if="novel.status !== 'ready' && novel.status !== 'analyzing'"
                      class="action-warn"
                      @click.stop="handleAnalyze(novel.id)"
                      :disabled="loadingAnalyze === novel.id"
                    >
                      {{ loadingAnalyze === novel.id ? '分析中...' : '⚡ 分析' }}
                    </button>
                    <button class="action-danger" @click.stop="handleDelete(novel.id)">
                      删除
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- RIGHT: detail panel -->
            <div class="detail-panel">
              <div v-if="!selectedNovelId" class="detail-empty">
                <svg width="40" height="40" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="color: #2A2A2A; margin-bottom: 12px;">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p>选择左侧小说后查看或编辑其档案。</p>
              </div>
              <ReferenceNovelDetail
                v-else
                :novel-id="selectedNovelId ?? undefined"
                @saved="loadNovels"
              />
            </div>

          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import {
  NovelAPI,
  type ReferenceNovelSummary,
  type ReferenceNovelCreatePayload
} from '@/api/novel'
import ReferenceNovelDetail from '@/components/ReferenceNovelDetail.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits<{
  'update:show': [boolean]
  select: [ReferenceNovelSummary]
}>()

const visible = ref(false)
const novels = ref<ReferenceNovelSummary[]>([])
const searchTerm = ref('')
const newTitle = ref('')
const newAuthor = ref('')
const newGenre = ref('')
const selectedNovelId = ref<number | null>(null)
const loading = ref(false)
const creating = ref(false)
const loadingAnalyze = ref<number | null>(null)
const showAddForm = ref(false)
const addTitleInputEl = ref<HTMLInputElement | null>(null)

watch(
  () => props.show,
  (value) => {
    visible.value = value
  }
)

watch(visible, (value) => {
  emit('update:show', value)
  if (value) {
    loadNovels()
  } else {
    showAddForm.value = false
    newTitle.value = ''
    newAuthor.value = ''
    newGenre.value = ''
  }
})

watch(showAddForm, async (value) => {
  if (value) {
    await nextTick()
    addTitleInputEl.value?.focus()
  }
})

const filteredNovels = computed(() => {
  if (!searchTerm.value.trim()) {
    return novels.value
  }
  const lower = searchTerm.value.trim().toLowerCase()
  return novels.value.filter((novel) => novel.title.toLowerCase().includes(lower))
})

const loadNovels = async () => {
  loading.value = true
  try {
    novels.value = await NovelAPI.listReferenceNovelLibrary(searchTerm.value)
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

let debounceId: number | null = null
const loadNovelsDeferred = () => {
  if (debounceId) {
    clearTimeout(debounceId)
  }
  debounceId = window.setTimeout(loadNovels, 220)
}

const handleCreate = async () => {
  if (!newTitle.value.trim()) return
  const payload: ReferenceNovelCreatePayload = {
    title: newTitle.value.trim(),
    author: newAuthor.value.trim() || undefined,
    genre: newGenre.value.trim() || undefined
  }
  creating.value = true
  try {
    const created = await NovelAPI.createReferenceNovel(payload)
    newTitle.value = ''
    newAuthor.value = ''
    newGenre.value = ''
    showAddForm.value = false
    await loadNovels()
    selectedNovelId.value = created.id
  } finally {
    creating.value = false
  }
}

const cancelAdd = () => {
  showAddForm.value = false
  newTitle.value = ''
  newAuthor.value = ''
  newGenre.value = ''
}

const handleDelete = async (novelId: number) => {
  if (!confirm('确定删除该参考小说？')) return
  await NovelAPI.deleteReferenceNovel(novelId)
  novels.value = novels.value.filter((novel) => novel.id !== novelId)
  if (selectedNovelId.value === novelId) {
    selectedNovelId.value = null
  }
}

const handleAnalyze = async (novelId: number) => {
  loadingAnalyze.value = novelId
  try {
    await NovelAPI.analyzeReferenceNovel(novelId)
    loadNovels()
  } finally {
    loadingAnalyze.value = null
  }
}

const selectNovel = (novel: ReferenceNovelSummary) => {
  emit('select', novel)
  visible.value = false
}

const statusLabel = (status: string) => {
  if (status === 'ready') return '已就绪'
  if (status === 'analyzing') return '分析中'
  if (status === 'failed') return '失败'
  return '待分析'
}
</script>

<style scoped>
/* ──────── Overlay ──────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  backdrop-filter: blur(4px);
}

.modal-card {
  width: 100%;
  max-width: 900px;
  max-height: 88vh;
  background: #141414;
  border: 1px solid #2A2A2A;
  border-radius: 18px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.6);
}

/* ──────── Header ──────── */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px;
  border-bottom: 1px solid #2A2A2A;
  flex-shrink: 0;
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 16px;
  font-weight: 700;
  color: #FFFFFF;
}

.modal-icon { font-size: 18px; }

.modal-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid #2A2A2A;
  background: #1C1C1C;
  color: #888;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.modal-close:hover { color: #fff; border-color: #444; }

/* ──────── Body ──────── */
.modal-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  flex: 1;
  overflow: hidden;
}

/* ──────── Left Panel ──────── */
.list-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-right: 1px solid #2A2A2A;
  overflow: hidden;
}

/* Toolbar */
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.search-wrap {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 10px;
  width: 14px;
  height: 14px;
  color: #555;
  pointer-events: none;
  flex-shrink: 0;
}

.search-input {
  width: 100%;
  padding: 7px 10px 7px 32px;
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
  border-radius: 8px;
  color: #FFFFFF;
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
}

.search-input:focus { border-color: #FFE500; }
.search-input::placeholder { color: #555; }

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  background: #FFE500;
  color: #000;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: opacity 0.15s;
  flex-shrink: 0;
}

.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary:not(:disabled):hover { opacity: 0.88; }

.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  background: #1C1C1C;
  color: #888;
  border: 1px solid #2A2A2A;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: color 0.15s, border-color 0.15s;
}

.btn-ghost:hover { color: #CCC; border-color: #444; }
.btn-ghost:disabled { opacity: 0.5; cursor: not-allowed; }

.spin-icon { transition: none; }
.spinning { animation: spin 0.8s linear infinite; }

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Add form */
.add-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: rgba(255, 229, 0, 0.04);
  border: 1px solid rgba(255, 229, 0, 0.15);
  border-radius: 10px;
  flex-shrink: 0;
}

.add-form-title {
  font-size: 12px;
  font-weight: 600;
  color: #FFE500;
  margin: 0;
}

.form-input {
  width: 100%;
  padding: 8px 10px;
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
  border-radius: 8px;
  color: #FFFFFF;
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.form-input:focus { border-color: #FFE500; }
.form-input::placeholder { color: #555; }

.add-form-actions {
  display: flex;
  gap: 8px;
}

/* Novel list */
.novel-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-right: 2px;
}

.novel-list::-webkit-scrollbar { width: 4px; }
.novel-list::-webkit-scrollbar-track { background: transparent; }
.novel-list::-webkit-scrollbar-thumb { background: #2A2A2A; border-radius: 4px; }

.list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px 16px;
  color: #555;
  font-size: 13px;
  text-align: center;
}

.empty-icon {
  width: 36px;
  height: 36px;
  color: #333;
}

/* Loading dots */
.loading-dots {
  display: flex;
  gap: 5px;
}

.loading-dots span {
  width: 6px;
  height: 6px;
  background: #444;
  border-radius: 50%;
  animation: dot-pulse 1.2s ease-in-out infinite;
}

.loading-dots span:nth-child(2) { animation-delay: 0.2s; }
.loading-dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dot-pulse {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* Novel card */
.novel-card {
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
  border-radius: 10px;
  padding: 11px 12px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.novel-card:hover { border-color: #444; background: #222; }
.novel-card.active { border-color: #FFE500; background: rgba(255, 229, 0, 0.04); }

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.card-info { flex: 1; min-width: 0; }

.card-title-text {
  margin: 0 0 2px;
  font-size: 13px;
  font-weight: 600;
  color: #FFFFFF;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  margin: 0;
  font-size: 11px;
  color: #888;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-badge {
  flex-shrink: 0;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}

.status-ready    { background: rgba(46,213,115,0.15); color: #2ED573; }
.status-analyzing { background: rgba(255,229,0,0.15); color: #FFE500; }
.status-failed   { background: rgba(255,71,87,0.15); color: #FF4757; }
.status-pending  { background: rgba(136,136,136,0.15); color: #888; }

.card-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.action-primary {
  padding: 3px 10px;
  background: #FFE500;
  color: #000;
  border: none;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.15s;
}

.action-primary:hover { opacity: 0.85; }

.action-warn {
  padding: 3px 10px;
  background: rgba(255,165,0,0.12);
  color: #FFA500;
  border: 1px solid rgba(255,165,0,0.2);
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.action-warn:disabled { opacity: 0.5; cursor: not-allowed; }
.action-warn:not(:disabled):hover { background: rgba(255,165,0,0.2); }

.action-danger {
  padding: 3px 10px;
  background: transparent;
  color: #666;
  border: 1px solid #2A2A2A;
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.action-danger:hover { color: #FF4757; border-color: rgba(255,71,87,0.4); }

/* ──────── Right Detail Panel ──────── */
.detail-panel {
  overflow-y: auto;
  padding: 16px;
}

.detail-panel::-webkit-scrollbar { width: 4px; }
.detail-panel::-webkit-scrollbar-track { background: transparent; }
.detail-panel::-webkit-scrollbar-thumb { background: #2A2A2A; border-radius: 4px; }

.detail-empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #555;
  font-size: 13px;
  gap: 4px;
}

/* ──────── Transitions ──────── */
.modal-fade-enter-active, .modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-active .modal-card,
.modal-fade-leave-active .modal-card {
  transition: transform 0.22s ease, opacity 0.2s ease;
}
.modal-fade-enter-from { opacity: 0; }
.modal-fade-enter-from .modal-card { transform: translateY(12px); opacity: 0; }
.modal-fade-leave-to { opacity: 0; }
.modal-fade-leave-to .modal-card { transform: translateY(6px); opacity: 0; }

/* ──────── Responsive ──────── */
@media (max-width: 640px) {
  .modal-body { grid-template-columns: 1fr; }
  .detail-panel { display: none; }
}
</style>

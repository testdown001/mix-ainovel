<template>
  <n-modal
    v-model:show="visible"
    preset="card"
    size="large"
    title="参考小说库"
    mask-closable
    :style="{ width: '900px', maxWidth: '95vw' }"
  >
    <div class="library-body">
      <!-- 左侧列表 -->
      <div class="library-list-panel">
        <div class="list-toolbar">
          <n-input
            v-model:value="searchTerm"
            placeholder="搜索参考小说..."
            size="small"
            clearable
            class="flex-1"
            @clear="loadNovels"
            @input="loadNovelsDeferred"
          >
            <template #prefix>
              <svg class="w-4 h-4 text-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </template>
          </n-input>
          <n-button size="small" type="primary" @click="showAddForm = true" :disabled="showAddForm">
            <template #icon>
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
              </svg>
            </template>
            添加
          </n-button>
          <n-button size="small" quaternary @click="loadNovels" :loading="loading">
            刷新
          </n-button>
        </div>

        <!-- 内联添加表单 -->
        <div v-if="showAddForm" class="add-form">
          <div class="add-form-title">添加参考小说</div>
          <n-input
            ref="addTitleInput"
            v-model:value="newTitle"
            placeholder="输入小说标题（必填）"
            size="small"
            @keyup.enter="handleCreate"
            @keyup.escape="cancelAdd"
          />
          <n-input
            v-model:value="newAuthor"
            placeholder="作者（可选）"
            size="small"
            @keyup.enter="handleCreate"
            @keyup.escape="cancelAdd"
          />
          <n-input
            v-model:value="newGenre"
            placeholder="题材（可选）"
            size="small"
            @keyup.enter="handleCreate"
            @keyup.escape="cancelAdd"
          />
          <div class="add-form-actions">
            <n-button size="small" type="primary" @click="handleCreate" :loading="creating" :disabled="!newTitle.trim()">
              确认添加
            </n-button>
            <n-button size="small" quaternary @click="cancelAdd">取消</n-button>
          </div>
        </div>

        <!-- 小说列表 -->
        <div class="library-list" :class="{ 'has-add-form': showAddForm }">
          <div v-for="novel in filteredNovels" :key="novel.id" class="library-card">
            <div class="card-heading">
              <div class="card-info">
                <h4>{{ novel.title }}</h4>
                <p class="card-meta">{{ novel.author || '未知作者' }} <span v-if="novel.genre"> · {{ novel.genre }}</span></p>
              </div>
              <n-tag :type="statusTag(novel.status)" size="small">{{ statusLabel(novel.status) }}</n-tag>
            </div>
            <div class="card-actions">
              <n-button size="tiny" type="primary" @click="selectNovel(novel)">选择绑定</n-button>
              <n-button size="tiny" @click="selectedNovelId = novel.id">详情</n-button>
              <n-button
                v-if="novel.status !== 'ready' && novel.status !== 'analyzing'"
                size="tiny"
                type="warning"
                @click="handleAnalyze(novel.id)"
                :loading="loadingAnalyze === novel.id"
              >
                分析
              </n-button>
              <n-button size="tiny" type="error" quaternary @click="handleDelete(novel.id)">删除</n-button>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-if="!filteredNovels.length && !loading" class="empty-state">
            <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <p class="empty-text">{{ searchTerm ? '未找到匹配的参考小说' : '暂无参考小说' }}</p>
            <n-button v-if="!showAddForm && !searchTerm" size="small" type="primary" @click="showAddForm = true">
              添加第一本参考小说
            </n-button>
          </div>

          <div v-if="loading && !filteredNovels.length" class="empty-state">
            <p class="empty-text">加载中...</p>
          </div>
        </div>
      </div>

      <!-- 右侧详情 -->
      <div class="library-detail">
        <ReferenceNovelDetail
          :novel-id="selectedNovelId ?? undefined"
          @saved="loadNovels"
        />
      </div>
    </div>

    <template #footer>
      <n-button size="small" @click="visible = false">关闭</n-button>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import type { InputInst } from 'naive-ui'
import { NButton, NInput, NModal, NTag } from 'naive-ui'
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
const addTitleInput = ref<InputInst | null>(null)

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
    addTitleInput.value?.focus()
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

const statusTag = (status: string) => {
  if (status === 'ready') return 'success'
  if (status === 'analyzing') return 'info'
  if (status === 'failed') return 'error'
  return 'warning'
}

const statusLabel = (status: string) => {
  if (status === 'ready') return '已就绪'
  if (status === 'analyzing') return '分析中'
  if (status === 'failed') return '失败'
  return '待分析'
}
</script>

<style scoped>
.library-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  min-height: 400px;
}

.library-list-panel {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.list-toolbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.add-form {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  border-radius: 0.75rem;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.add-form-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: #1e40af;
}

.add-form-actions {
  display: flex;
  gap: 0.5rem;
}

.library-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 48vh;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.library-list.has-add-form {
  max-height: 36vh;
}

.library-card {
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;
  padding: 0.75rem;
  background: #ffffff;
  transition: box-shadow 0.15s ease;
}

.library-card:hover {
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
}

.card-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}

.card-info h4 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  line-height: 1.4;
}

.card-meta {
  margin: 0;
  font-size: 0.75rem;
  color: #6b7280;
}

.card-actions {
  margin-top: 0.5rem;
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.library-detail {
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;
  padding: 0.75rem;
  background: #fafafa;
  max-height: 55vh;
  overflow-y: auto;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
  gap: 0.75rem;
}

.empty-icon {
  width: 3rem;
  height: 3rem;
  color: #9ca3af;
}

.empty-text {
  margin: 0;
  font-size: 0.85rem;
  color: #6b7280;
}
</style>

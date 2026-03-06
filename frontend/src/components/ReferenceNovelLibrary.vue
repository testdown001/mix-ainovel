<template>
  <n-modal
    v-model:show="visible"
    preset="card"
    size="large"
    title="参考小说库"
    mask-closable
  >
    <template #header>
      <div class="library-header">
        <n-input
          v-model:value="searchTerm"
          placeholder="按标题或关键词过滤"
          size="small"
          clearable
          @clear="loadNovels"
          @input="loadNovelsDeferred"
        />
        <div class="header-actions">
          <n-input
            v-model:value="newTitle"
            placeholder="新建参考小说标题"
            size="small"
            class="flex-1"
          />
          <n-button size="small" type="primary" @click="handleCreate" :loading="creating" :disabled="!newTitle.trim()">
            新建
          </n-button>
          <n-button size="small" type="info" @click="loadNovels" :loading="loading">
            刷新
          </n-button>
        </div>
      </div>
    </template>

    <div class="library-body">
      <div class="library-list">
        <div v-for="novel in filteredNovels" :key="novel.id" class="library-card">
          <div class="card-heading">
            <div>
              <h4>{{ novel.title }}</h4>
              <p class="text-sm text-gray-500">{{ novel.author || '未知作者' }}</p>
            </div>
            <n-tag :type="statusTag(novel.status)" size="small">{{ novel.status }}</n-tag>
          </div>
          <div class="card-actions">
            <n-button size="tiny" @click="selectNovel(novel)">选择</n-button>
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
            <n-button size="tiny" type="error" @click="handleDelete(novel.id)">删除</n-button>
          </div>
        </div>
        <div v-if="!filteredNovels.length" class="empty-state">
          当前无符合条件的参考小说。
        </div>
      </div>
      <div class="library-detail">
        <ReferenceNovelDetail
          :novel-id="selectedNovelId ?? undefined"
          @saved="loadNovels"
        />
      </div>
    </div>

    <template #footer>
      <n-button size="small" type="default" @click="visible = false">关闭</n-button>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
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
const selectedNovelId = ref<number | null>(null)
const loading = ref(false)
const creating = ref(false)
const loadingAnalyze = ref<number | null>(null)

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
  const payload: ReferenceNovelCreatePayload = { title: newTitle.value.trim() }
  creating.value = true
  try {
    await NovelAPI.createReferenceNovel(payload)
    newTitle.value = ''
    loadNovels()
  } finally {
    creating.value = false
  }
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
</script>

<style scoped>
.library-header {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.header-actions {
  display: flex;
  gap: 0.5rem;
}
.library-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-top: 1rem;
}
.library-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 52vh;
  overflow-y: auto;
  padding-right: 0.25rem;
}
.library-card {
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;
  padding: 0.75rem;
  background: #ffffff;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
}
.card-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}
.card-heading h4 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}
.card-actions {
  margin-top: 0.5rem;
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.library-detail {
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;
  padding: 0.75rem;
  background: #fafafa;
  max-height: 52vh;
  overflow-y: auto;
}
.empty-state {
  padding: 1rem;
  text-align: center;
  color: #9ca3af;
}
</style>

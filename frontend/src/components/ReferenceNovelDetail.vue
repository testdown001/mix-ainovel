<template>
  <div class="reference-detail">
    <div v-if="loading && !novel" class="loading-overlay">
      <p>加载中...</p>
    </div>
    <div v-if="novel" class="detail-card">
      <div class="detail-header">
        <h3>{{ novel.title }}</h3>
        <n-tag :type="statusType">{{ statusLabel }}</n-tag>
      </div>

      <div v-if="novel.status === 'analyzing'" class="analyzing-hint">
        正在分析中，每 5 秒自动刷新...
      </div>
      <div v-if="novel.status === 'failed' && novel.error_message" class="error-hint">
        分析失败：{{ novel.error_message }}
      </div>

      <div class="detail-section">
        <label>大纲 / 人物档案</label>
        <textarea v-model="outline" rows="4" />
      </div>
      <div class="detail-section">
        <label>风格样本（10 段）</label>
        <textarea v-model="styleSamples" rows="5" />
      </div>
      <div class="detail-section">
        <label>记忆卡（JSON）</label>
        <textarea v-model="memoryCardJson" rows="8" />
      </div>
      <div class="detail-footer">
        <n-button size="small" type="primary" @click="save" :loading="saving">保存</n-button>
        <n-button size="small" type="default" @click="refresh" :disabled="loading">刷新</n-button>
        <n-button v-if="novel.status === 'failed'" size="small" type="warning" @click="retryAnalyze" :loading="retrying">重新分析</n-button>
        <span v-if="message" class="detail-message">{{ message }}</span>
      </div>
    </div>
    <div v-else-if="!loading" class="empty-state">
      请选择参考小说后查看或编辑其档案。
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onUnmounted } from 'vue'
import { NButton, NTag } from 'naive-ui'
import { NovelAPI, type MemoryCard, type ReferenceNovelDetail, type ReferenceNovelUpdatePayload } from '@/api/novel'

const props = defineProps<{ novelId?: number }>()
const emit = defineEmits<{
  saved: []
}>()

const novel = ref<ReferenceNovelDetail | null>(null)
const outline = ref('')
const styleSamples = ref('')
const memoryCardJson = ref('')
const loading = ref(false)
const saving = ref(false)
const retrying = ref(false)
const message = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null

const statusType = computed(() => {
  if (!novel.value) return 'info'
  if (novel.value.status === 'ready') return 'success'
  if (novel.value.status === 'failed') return 'error'
  if (novel.value.status === 'analyzing') return 'info'
  return 'warning'
})

const statusLabel = computed(() => {
  if (!novel.value) return ''
  const map: Record<string, string> = {
    pending: '待分析',
    analyzing: '分析中...',
    ready: '已就绪',
    failed: '分析失败',
  }
  return map[novel.value.status] || novel.value.status
})

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    if (props.novelId && novel.value?.status === 'analyzing') {
      loadDetail(props.novelId, true)
    } else {
      stopPolling()
    }
  }, 5000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onUnmounted(() => stopPolling())

const loadDetail = async (id: number, silent = false) => {
  if (!silent) loading.value = true
  message.value = ''
  try {
    const data = await NovelAPI.getReferenceNovel(id)
    novel.value = data
    outline.value = data.outline_content || ''
    styleSamples.value = data.style_samples_content || ''
    memoryCardJson.value = JSON.stringify(data.memory_card || {}, null, 2)

    if (data.status === 'analyzing') {
      if (!pollTimer) startPolling()
    } else {
      stopPolling()
    }
  } catch (err: any) {
    message.value = err instanceof Error ? err.message : '加载失败'
  } finally {
    if (!silent) loading.value = false
  }
}

const refresh = () => {
  if (props.novelId) {
    loadDetail(props.novelId)
  }
}

const retryAnalyze = async () => {
  if (!novel.value) return
  retrying.value = true
  message.value = ''
  try {
    await NovelAPI.analyzeReferenceNovel(novel.value.id)
    message.value = '已重新触发分析'
    await loadDetail(novel.value.id)
  } catch (err: any) {
    message.value = err instanceof Error ? err.message : '触发分析失败'
  } finally {
    retrying.value = false
  }
}

watch(
  () => props.novelId,
  (id) => {
    stopPolling()
    if (id) {
      loadDetail(id)
    } else {
      novel.value = null
      outline.value = ''
      styleSamples.value = ''
      memoryCardJson.value = ''
      message.value = ''
    }
  },
  { immediate: true }
)

const save = async () => {
  if (!novel.value) return
  saving.value = true
  message.value = ''
  let parsedMemory: MemoryCard
  try {
    parsedMemory = JSON.parse(memoryCardJson.value || '{}') as MemoryCard
  } catch (err) {
    message.value = '记忆卡必须是合法 JSON'
    saving.value = false
    return
  }

  const payload: ReferenceNovelUpdatePayload = {
    outline_content: outline.value,
    style_samples_content: styleSamples.value,
    memory_card: parsedMemory
  }

  try {
    await NovelAPI.updateReferenceNovel(novel.value.id, payload)
    message.value = '保存成功'
    emit('saved')
  } catch (err: any) {
    message.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.reference-detail {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.75rem 0;
}
.detail-card {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.detail-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}
.analyzing-hint {
  font-size: 0.82rem;
  color: #2563eb;
  padding: 0.4rem 0.6rem;
  background: #eff6ff;
  border-radius: 0.4rem;
}
.error-hint {
  font-size: 0.82rem;
  color: #dc2626;
  padding: 0.4rem 0.6rem;
  background: #fef2f2;
  border-radius: 0.4rem;
  word-break: break-all;
}
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.detail-section label {
  font-size: 0.75rem;
  color: #6b7280;
}
.detail-section textarea {
  width: 100%;
  min-height: 64px;
  resize: vertical;
  padding: 0.5rem;
  border-radius: 0.5rem;
  border: 1px solid #d1d5db;
  font-size: 0.85rem;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
}
.detail-footer {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.detail-message {
  color: #2563eb;
  font-size: 0.85rem;
}
.empty-state {
  font-size: 0.9rem;
  color: #9ca3af;
  text-align: center;
  padding: 1rem;
}
.loading-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9rem;
  font-weight: 500;
}
</style>

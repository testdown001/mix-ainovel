<template>
  <div class="reference-detail">
    <div v-if="loading && !novel" class="loading-overlay">
      <p>加载中...</p>
    </div>
    <div v-if="novel" class="detail-card">
      <div class="detail-header">
        <div class="detail-header-info">
          <h3>{{ novel.title }}</h3>
          <div class="detail-header-meta">
            <n-input
              v-model:value="author"
              placeholder="作者"
              size="small"
              class="meta-input"
            />
            <n-input
              v-model:value="genre"
              placeholder="题材"
              size="small"
              class="meta-input"
            />
          </div>
        </div>
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
        <label>风格样本（AI 仿写语感示例，非原文摘录）</label>
        <textarea v-model="styleSamples" rows="5" />
      </div>

      <!-- 写法基准：可执行的写法约束，绑定项目后正文生成默认注入 -->
      <div class="detail-section">
        <label>写法基准（正文生成默认注入，只约束「怎么写」）</label>
        <dl v-if="styleGuideEntries.length" class="beat-fields style-guide">
          <template v-for="entry in styleGuideEntries" :key="entry[0]">
            <dt>{{ entry[0] }}</dt><dd>{{ entry[1] }}</dd>
          </template>
        </dl>
        <div v-else-if="novel.status === 'ready'" class="beat-empty">
          尚无写法基准（旧数据或资料不足），点「重新分析」提取。
        </div>
      </div>
      <div class="detail-section">
        <label>记忆卡（JSON）</label>
        <textarea v-model="memoryCardJson" rows="8" />
      </div>

      <!-- 桥段库：情境→手法的可检索条目，生成章节时按本章情境选取注入。
           只读展示（编辑走重新分析）；老数据没有桥段库时给补齐入口。 -->
      <div class="detail-section">
        <label>桥段库（{{ beats.length }} 条，按章节情境检索注入正文生成）</label>
        <div v-if="beats.length" class="beat-list">
          <details v-for="(beat, index) in beats" :key="index" class="beat-item">
            <summary>
              <span class="beat-name">{{ beat.name || '未命名桥段' }}</span>
              <span class="beat-tags" v-if="beat.tags?.length">{{ beat.tags.join(' / ') }}</span>
            </summary>
            <dl class="beat-fields">
              <template v-if="beat.situation"><dt>适用局面</dt><dd>{{ beat.situation }}</dd></template>
              <template v-if="beat.setup"><dt>铺垫</dt><dd>{{ beat.setup }}</dd></template>
              <template v-if="beat.turn"><dt>转折</dt><dd>{{ beat.turn }}</dd></template>
              <template v-if="beat.payoff"><dt>兑现</dt><dd>{{ beat.payoff }}</dd></template>
              <template v-if="beat.pitfalls"><dt>勿踩</dt><dd>{{ beat.pitfalls }}</dd></template>
            </dl>
          </details>
        </div>
        <div v-else-if="novel.status === 'ready'" class="beat-empty">
          该书是在桥段库功能上线前分析的，点「重新分析」补齐（会重新联网检索并覆盖现有档案）。
        </div>
        <div v-if="beatStructureText" class="beat-structure">
          <label>全书结构手法（蓝图排章纲时参考）</label>
          <p>{{ beatStructureText }}</p>
        </div>
      </div>

      <div class="detail-footer">
        <n-button size="small" type="primary" @click="save" :loading="saving">保存</n-button>
        <n-button size="small" type="default" @click="refresh" :disabled="loading">刷新</n-button>
        <n-button
          v-if="novel.status === 'failed' || novel.status === 'ready'"
          size="small"
          type="warning"
          @click="retryAnalyze"
          :loading="retrying"
        >重新分析</n-button>
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
import { NButton, NTag, NInput } from 'naive-ui'
import { NovelAPI, type MemoryCard, type ReferenceNovelDetail, type ReferenceNovelUpdatePayload } from '@/api/novel'

const props = defineProps<{ novelId?: number }>()
const emit = defineEmits<{
  saved: []
}>()

const novel = ref<ReferenceNovelDetail | null>(null)
const outline = ref('')
const styleSamples = ref('')
const memoryCardJson = ref('')
const author = ref('')
const genre = ref('')
const loading = ref(false)
const saving = ref(false)
const retrying = ref(false)
const message = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null

const beats = computed(() => novel.value?.beat_library?.beats || [])

const STYLE_GUIDE_LABELS: Array<[keyof NonNullable<ReferenceNovelDetail['style_guide']>, string]> = [
  ['narrative_pov', '叙事视角'],
  ['sentence_rhythm', '句式节奏'],
  ['dialogue_style', '对白'],
  ['description_density', '描写密度'],
  ['paragraphing', '分段'],
  ['emotion_expression', '情绪表达'],
  ['signature_devices', '标志性手法'],
  ['forbidden', '禁用写法'],
]

const styleGuideEntries = computed<Array<[string, string]>>(() => {
  const guide = novel.value?.style_guide
  if (!guide) return []
  const entries: Array<[string, string]> = []
  for (const [key, label] of STYLE_GUIDE_LABELS) {
    const value = guide[key]
    if (Array.isArray(value) && value.length) entries.push([label, value.join('；')])
    else if (typeof value === 'string' && value.trim()) entries.push([label, value])
  }
  return entries
})

const beatStructureText = computed(() => {
  const structure = novel.value?.beat_library?.structure
  if (!structure) return ''
  const parts: string[] = []
  if (structure.volume_rhythm) parts.push(`分卷节奏：${structure.volume_rhythm}`)
  if (structure.conflict_escalation) parts.push(`冲突升级：${structure.conflict_escalation}`)
  if (structure.hook_pattern) parts.push(`章末钩子：${structure.hook_pattern}`)
  return parts.join('　')
})

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

const compactJsonValue = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    const compacted = value
      .map((item) => compactJsonValue(item))
      .filter((item) => item !== undefined)
    return compacted.length > 0 ? compacted : undefined
  }

  if (value && typeof value === 'object') {
    const compactedEntries = Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => [key, compactJsonValue(item)] as const)
      .filter(([, item]) => item !== undefined)
    return compactedEntries.length > 0 ? Object.fromEntries(compactedEntries) : undefined
  }

  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed ? trimmed : undefined
  }

  if (value === null || value === undefined) {
    return undefined
  }

  return value
}

const compactMemoryCard = (value: MemoryCard | Record<string, unknown> | null | undefined) => {
  const compacted = compactJsonValue(value)
  if (compacted && typeof compacted === 'object' && !Array.isArray(compacted)) {
    return compacted as Record<string, unknown>
  }
  return {}
}

const loadDetail = async (id: number, silent = false) => {
  if (!silent) loading.value = true
  message.value = ''
  try {
    const data = await NovelAPI.getReferenceNovel(id)
    novel.value = data
    outline.value = data.outline_content || ''
    styleSamples.value = data.style_samples_content || ''
    memoryCardJson.value = JSON.stringify(compactMemoryCard(data.memory_card), null, 2)
    author.value = data.author || ''
    genre.value = data.genre || ''

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
      author.value = ''
      genre.value = ''
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
    parsedMemory = compactMemoryCard(JSON.parse(memoryCardJson.value || '{}')) as MemoryCard
  } catch (err) {
    message.value = '记忆卡必须是合法 JSON'
    saving.value = false
    return
  }

  const payload: ReferenceNovelUpdatePayload = {
    outline_content: outline.value,
    style_samples_content: styleSamples.value,
    memory_card: parsedMemory,
    author: author.value || undefined,
    genre: genre.value || undefined
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
  align-items: flex-start;
  gap: 0.75rem;
}
.detail-header-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
}
.detail-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}
.detail-header-meta {
  display: flex;
  gap: 0.5rem;
}
.meta-input {
  width: 120px;
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
.beat-list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.beat-item {
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  padding: 0.4rem 0.6rem;
  font-size: 0.85rem;
}
.beat-item summary {
  cursor: pointer;
  display: flex;
  gap: 0.5rem;
  align-items: baseline;
  flex-wrap: wrap;
}
.beat-name {
  font-weight: 600;
}
.beat-tags {
  font-size: 0.75rem;
  color: #6b7280;
}
.beat-fields {
  margin: 0.5rem 0 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.25rem 0.6rem;
}
.beat-fields dt {
  color: #6b7280;
  font-size: 0.75rem;
  white-space: nowrap;
}
.beat-fields dd {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.5;
}
.beat-empty {
  font-size: 0.82rem;
  color: #92400e;
  padding: 0.4rem 0.6rem;
  background: #fffbeb;
  border-radius: 0.4rem;
}
.beat-structure {
  margin-top: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.beat-structure p {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.6;
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

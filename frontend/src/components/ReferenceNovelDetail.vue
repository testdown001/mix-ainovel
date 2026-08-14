<!-- AIMETA P=参考小说档案面板_暗色读优先视图|R=档案展示_编辑_重新分析|NR=不含列表管理|E=component:ReferenceNovelDetail|X=ui|A=面板组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="reference-detail">
    <div v-if="loading && !novel" class="loading-state">
      <div class="loading-dots"><span></span><span></span><span></span></div>
      <p>加载档案中...</p>
    </div>

    <div v-if="novel" class="detail-card">
      <!-- 头部：标题 + 状态 + 元信息 -->
      <div class="detail-header">
        <div class="detail-header-info">
          <h3 class="detail-title">{{ novel.title }}</h3>
          <div class="detail-header-meta">
            <input v-model="author" class="meta-input" placeholder="作者" />
            <input v-model="genre" class="meta-input" placeholder="题材" />
          </div>
        </div>
        <span class="status-badge" :class="`status-${novel.status}`">{{ statusLabel }}</span>
      </div>

      <div v-if="novel.status === 'analyzing'" class="hint-bar hint-analyzing">
        <span class="hint-pulse"></span>
        正在联网检索并提取档案，约需 1-2 分钟，每 5 秒自动刷新
      </div>
      <div v-if="novel.status === 'failed' && novel.error_message" class="hint-bar hint-error">
        分析失败：{{ novel.error_message }}
      </div>

      <!-- 大纲 / 人物档案 -->
      <section class="detail-section">
        <div class="section-head">
          <label>大纲 / 人物档案</label>
          <button class="btn-text" @click="editingOutline = !editingOutline">
            {{ editingOutline ? '完成' : '编辑' }}
          </button>
        </div>
        <textarea
          v-if="editingOutline"
          v-model="outline"
          rows="10"
          class="edit-area"
          placeholder="剧情大纲、人物档案..."
        />
        <div v-else-if="outlineDisplay" class="read-view">{{ outlineDisplay }}</div>
        <p v-else class="section-empty">{{ emptyHint }}</p>
      </section>

      <!-- 风格样本 -->
      <section class="detail-section">
        <div class="section-head">
          <label>风格样本 <span class="label-note">AI 仿写语感示例，非原文摘录</span></label>
          <button class="btn-text" @click="editingSamples = !editingSamples">
            {{ editingSamples ? '完成' : '编辑' }}
          </button>
        </div>
        <textarea
          v-if="editingSamples"
          v-model="styleSamples"
          rows="10"
          class="edit-area"
          placeholder="每段样本之间用 --- 分隔..."
        />
        <div v-else-if="sampleSegments.length" class="sample-list">
          <blockquote v-for="(seg, i) in sampleSegments" :key="i" class="sample-card">{{ seg }}</blockquote>
        </div>
        <p v-else class="section-empty">{{ emptyHint }}</p>
      </section>

      <!-- 写法基准 -->
      <section class="detail-section">
        <div class="section-head">
          <label>写法基准 <span class="label-note">正文生成默认注入，只约束「怎么写」</span></label>
        </div>
        <dl v-if="styleGuideEntries.length" class="guide-grid">
          <template v-for="entry in styleGuideEntries" :key="entry[0]">
            <dt>{{ entry[0] }}</dt>
            <dd>{{ entry[1] }}</dd>
          </template>
        </dl>
        <p v-else-if="novel.status === 'ready'" class="section-empty">
          尚无写法基准（旧数据或资料不足），点「重新分析」提取。
        </p>
      </section>

      <!-- 桥段库 -->
      <section class="detail-section">
        <div class="section-head">
          <label>桥段库 <span class="label-note">{{ beats.length }} 条 · 按章节情境检索注入正文生成</span></label>
        </div>
        <div v-if="beats.length" class="beat-list">
          <details v-for="(beat, index) in beats" :key="index" class="beat-item">
            <summary>
              <span class="beat-name">{{ beat.name || '未命名桥段' }}</span>
              <span class="beat-tags" v-if="beat.tags?.length">{{ beat.tags.join(' / ') }}</span>
            </summary>
            <dl class="guide-grid beat-fields">
              <template v-if="beat.situation"><dt>适用局面</dt><dd>{{ beat.situation }}</dd></template>
              <template v-if="beat.setup"><dt>铺垫</dt><dd>{{ beat.setup }}</dd></template>
              <template v-if="beat.turn"><dt>转折</dt><dd>{{ beat.turn }}</dd></template>
              <template v-if="beat.payoff"><dt>兑现</dt><dd>{{ beat.payoff }}</dd></template>
              <template v-if="beat.pitfalls"><dt>勿踩</dt><dd>{{ beat.pitfalls }}</dd></template>
            </dl>
          </details>
        </div>
        <p v-else-if="novel.status === 'ready'" class="section-empty">
          该书是在桥段库功能上线前分析的，点「重新分析」补齐（会重新联网检索并覆盖现有档案）。
        </p>
        <div v-if="beatStructureText" class="beat-structure">
          <span class="label-note">全书结构手法（蓝图排章纲时参考）</span>
          <p>{{ beatStructureText }}</p>
        </div>
      </section>

      <!-- 记忆卡：高级编辑入口，默认收起 -->
      <details class="detail-section json-section">
        <summary class="section-head json-summary">
          <label>记忆卡 <span class="label-note">JSON · 高级编辑</span></label>
        </summary>
        <textarea v-model="memoryCardJson" rows="10" class="edit-area mono" />
      </details>

      <!-- 底部操作 -->
      <div class="detail-footer">
        <button class="btn-primary" @click="save" :disabled="saving">
          {{ saving ? '保存中...' : '保存' }}
        </button>
        <button class="btn-ghost" @click="refresh" :disabled="loading">刷新</button>
        <button
          v-if="novel.status === 'failed' || novel.status === 'ready'"
          class="btn-warn"
          @click="retryAnalyze"
          :disabled="retrying"
        >
          {{ retrying ? '触发中...' : '重新分析' }}
        </button>
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
const editingOutline = ref(false)
const editingSamples = ref(false)
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

// 阅读视图：把 LLM 输出里的 markdown 噪音（### 标题头、**加粗**、列表星号）
// 还原成可读纯文本；编辑视图仍保留原始内容，保存不受影响
const stripMarkdownNoise = (raw: string): string =>
  raw
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/^\s*[-*]\s+/gm, '· ')
    .trim()

const outlineDisplay = computed(() => stripMarkdownNoise(outline.value || ''))

const sampleSegments = computed(() =>
  (styleSamples.value || '')
    .split(/\n\s*-{3,}\s*\n|\n\s*\n/)
    .map((seg) => stripMarkdownNoise(seg))
    .filter(Boolean)
)

const emptyHint = computed(() =>
  novel.value?.status === 'ready'
    ? '暂无内容，点「重新分析」重新提取，或点「编辑」手动补充。'
    : '分析完成后自动填充，也可点「编辑」手动录入。'
)

const beatStructureText = computed(() => {
  const structure = novel.value?.beat_library?.structure
  if (!structure) return ''
  const parts: string[] = []
  if (structure.volume_rhythm) parts.push(`分卷节奏：${structure.volume_rhythm}`)
  if (structure.conflict_escalation) parts.push(`冲突升级：${structure.conflict_escalation}`)
  if (structure.hook_pattern) parts.push(`章末钩子：${structure.hook_pattern}`)
  return parts.join('　')
})

const statusLabel = computed(() => {
  if (!novel.value) return ''
  const map: Record<string, string> = {
    pending: '待分析',
    analyzing: '分析中',
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
    editingOutline.value = false
    editingSamples.value = false
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
    editingOutline.value = false
    editingSamples.value = false
    emit('saved')
  } catch (err: any) {
    message.value = err instanceof Error ? err.message : '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
/* 与 ReferenceNovelLibrary 弹窗同一套暗色语言：#141414 / #1C1C1C / #2A2A2A / #FFE500 */
.reference-detail {
  display: flex;
  flex-direction: column;
  color: #ccc;
}

.detail-card {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ──────── 头部 ──────── */
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.detail-header-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.detail-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  font-family: 'Space Grotesk', sans-serif;
}

.detail-header-meta {
  display: flex;
  gap: 8px;
}

.meta-input {
  width: 128px;
  padding: 6px 10px;
  background: #1c1c1c;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  color: #fff;
  font-size: 12px;
  outline: none;
  transition: border-color 0.15s;
}

.meta-input:focus { border-color: #ffe500; }
.meta-input::placeholder { color: #555; }

.status-badge {
  flex-shrink: 0;
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 999px;
  font-weight: 600;
  white-space: nowrap;
}

.status-ready     { background: rgba(46, 213, 115, 0.15); color: #2ed573; }
.status-analyzing { background: rgba(255, 229, 0, 0.15); color: #ffe500; }
.status-failed    { background: rgba(255, 71, 87, 0.15); color: #ff4757; }
.status-pending   { background: rgba(136, 136, 136, 0.15); color: #888; }

/* ──────── 提示条 ──────── */
.hint-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  line-height: 1.5;
}

.hint-analyzing {
  color: #ffe500;
  background: rgba(255, 229, 0, 0.06);
  border: 1px solid rgba(255, 229, 0, 0.18);
}

.hint-pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ffe500;
  flex-shrink: 0;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.35; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}

.hint-error {
  color: #ff8a95;
  background: rgba(255, 71, 87, 0.08);
  border: 1px solid rgba(255, 71, 87, 0.2);
  word-break: break-all;
}

/* ──────── 分节 ──────── */
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.section-head label {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}

.label-note {
  font-size: 11px;
  font-weight: 400;
  color: #777;
  margin-left: 6px;
}

.btn-text {
  padding: 2px 10px;
  background: transparent;
  border: 1px solid #2a2a2a;
  border-radius: 6px;
  color: #888;
  font-size: 11px;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.btn-text:hover { color: #ffe500; border-color: rgba(255, 229, 0, 0.4); }

/* 阅读视图 */
.read-view {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.8;
  color: #ccc;
  background: #1c1c1c;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
  padding: 12px 14px;
  max-height: 320px;
  overflow-y: auto;
}

.read-view::-webkit-scrollbar { width: 4px; }
.read-view::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 4px; }

/* 样本卡片 */
.sample-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
  padding-right: 2px;
}

.sample-list::-webkit-scrollbar { width: 4px; }
.sample-list::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 4px; }

.sample-card {
  margin: 0;
  padding: 10px 14px;
  background: #1c1c1c;
  border: 1px solid #2a2a2a;
  border-left: 3px solid rgba(255, 229, 0, 0.5);
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.8;
  color: #ccc;
  white-space: pre-wrap;
}

/* 编辑视图 */
.edit-area {
  width: 100%;
  resize: vertical;
  padding: 10px 12px;
  background: #1c1c1c;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
  color: #eee;
  font-size: 13px;
  line-height: 1.7;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.edit-area:focus { border-color: #ffe500; }
.edit-area.mono {
  font-family: 'Fira Code', 'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
  font-size: 12px;
}

.section-empty {
  margin: 0;
  font-size: 12px;
  color: #777;
  background: #1c1c1c;
  border: 1px dashed #2a2a2a;
  border-radius: 8px;
  padding: 10px 12px;
  line-height: 1.6;
}

/* 写法基准 / 桥段字段表 */
.guide-grid {
  margin: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 14px;
  background: #1c1c1c;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
  padding: 12px 14px;
}

.guide-grid dt {
  color: #888;
  font-size: 12px;
  white-space: nowrap;
  line-height: 1.7;
}

.guide-grid dd {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #ccc;
}

/* 桥段库 */
.beat-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.beat-item {
  background: #1c1c1c;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
}

.beat-item[open] { border-color: #3a3a3a; }

.beat-item summary {
  cursor: pointer;
  display: flex;
  gap: 8px;
  align-items: baseline;
  flex-wrap: wrap;
  list-style: none;
  color: #ccc;
}

.beat-item summary::-webkit-details-marker { display: none; }
.beat-item summary::before {
  content: '▸';
  color: #555;
  font-size: 11px;
  transition: transform 0.15s;
  display: inline-block;
}

.beat-item[open] summary::before { transform: rotate(90deg); }

.beat-name {
  font-weight: 600;
  color: #fff;
}

.beat-tags {
  font-size: 11px;
  color: #777;
}

.beat-fields {
  margin-top: 10px;
  background: transparent;
  border: none;
  padding: 0 0 0 16px;
}

.beat-structure {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 2px;
}

.beat-structure p {
  margin: 0;
  font-size: 12px;
  line-height: 1.7;
  color: #aaa;
}

/* 记忆卡折叠区 */
.json-section { gap: 8px; }

.json-summary {
  cursor: pointer;
  list-style: none;
  user-select: none;
}

.json-summary::-webkit-details-marker { display: none; }
.json-summary label { cursor: pointer; }
.json-summary label::before {
  content: '▸ ';
  color: #555;
  font-size: 11px;
}

.json-section[open] .json-summary label::before { content: '▾ '; }

/* ──────── 底部 ──────── */
.detail-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding-top: 2px;
}

.btn-primary {
  padding: 6px 16px;
  background: #ffe500;
  color: #000;
  border: none;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary:not(:disabled):hover { opacity: 0.88; }

.btn-ghost {
  padding: 6px 14px;
  background: #1c1c1c;
  color: #888;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.btn-ghost:hover { color: #ccc; border-color: #444; }
.btn-ghost:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-warn {
  padding: 6px 14px;
  background: rgba(255, 165, 0, 0.12);
  color: #ffa500;
  border: 1px solid rgba(255, 165, 0, 0.2);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-warn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-warn:not(:disabled):hover { background: rgba(255, 165, 0, 0.2); }

.detail-message {
  color: #ffe500;
  font-size: 12px;
}

/* 空态与加载 */
.empty-state {
  font-size: 13px;
  color: #555;
  text-align: center;
  padding: 24px 0;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 40px 0;
  color: #555;
  font-size: 13px;
}

.loading-dots { display: flex; gap: 5px; }

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
</style>

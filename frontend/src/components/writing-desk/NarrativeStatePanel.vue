<template>
  <details class="narrative-panel" @toggle="onToggle">
    <summary>章前正史与人物牵挂 <small>按需读取</small></summary>
    <p class="hint">只展示本章之前、作者采用版本中的可核验证据，不读取未来正文，不调用模型。</p>
    <button type="button" :disabled="loading || !chapterNumber" @click="load">{{ loading ? '读取中…' : '刷新正史' }}</button>
    <p v-if="error" role="status">{{ error }}</p>
    <template v-if="state">
      <p class="hint">覆盖 {{ state.coverage.ready_chapters }} / {{ state.coverage.total_chapters }} 章；缺失不代表没有发生变化。</p>
      <details v-if="gaps.length">
        <summary>覆盖缺口（{{ gaps.length }}）</summary>
        <p v-for="item in gaps" :key="item.chapter_number" class="hint">
          第 {{ item.chapter_number }} 章 · {{ coverageLabel(item.status) }}{{ item.reason ? `：${item.reason}` : '' }}
        </p>
      </details>
      <h4>人物关系</h4>
      <p v-if="!state.relationships.length" class="hint">暂无可核验的关系变化。</p>
      <article v-for="(fact, index) in state.relationships" :key="`relation-${index}`">
        <strong>{{ fact.entity }} · {{ fact.attribute }}</strong><p>{{ fact.value }}</p>
        <blockquote>{{ fact.evidence }}</blockquote>
        <button type="button" @click="emit('locateSource', fact.source_chapter)">定位第 {{ fact.source_chapter }} 章 · 版本 {{ fact.source_version ?? '未知' }}</button>
      </article>
      <details><summary>已确认事实（{{ state.facts.length }}）</summary>
        <article v-for="(fact, index) in state.facts" :key="`fact-${index}`">
          <strong>{{ fact.entity }} · {{ fact.attribute }}</strong><p>{{ fact.value }}</p>
          <blockquote>{{ fact.evidence }}</blockquote>
          <button type="button" @click="emit('locateSource', fact.source_chapter)">定位第 {{ fact.source_chapter }} 章 · 版本 {{ fact.source_version ?? '未知' }}</button>
        </article>
      </details>
      <h4>开放承诺（{{ state.open_promises.length }}）</h4>
      <p v-if="!state.open_promises.length" class="hint">暂无已登记的开放承诺；请结合覆盖缺口判断。</p>
      <article v-for="item in state.open_promises" :key="item.id">
        <strong>{{ item.character }} · {{ item.question }}</strong>
        <p v-if="item.expected_payoff_chapter">预计第 {{ item.expected_payoff_chapter }} 章兑现（规划，不是已发生事实）</p>
        <blockquote>{{ item.evidence }}</blockquote>
        <button type="button" @click="emit('locateSource', item.source_chapter)">定位打开承诺的第 {{ item.source_chapter }} 章</button>
      </article>
      <details><summary>已兑现承诺（{{ state.closed_promises.length }}）</summary>
        <article v-for="item in state.closed_promises" :key="item.id">
          <strong>{{ item.question }}</strong><p>{{ item.resolution?.change }}</p>
          <blockquote>{{ item.resolution?.evidence }}</blockquote>
          <button v-if="item.resolved_chapter" type="button" @click="emit('locateSource', item.resolved_chapter)">定位第 {{ item.resolved_chapter }} 章</button>
        </article>
      </details>
      <p v-if="state.conflicts.length" class="hint">{{ state.conflicts.length }} 项冲突已隔离，不作为确定事实注入。</p>
      <details v-if="state.reference_contract"><summary>参考来源与分工 · {{ state.reference_contract.status }}</summary>
        <p class="hint">搜索资料 / AI 分析；不代表已读原著全文。作者声音和本书人物逻辑优先。</p>
        <p v-for="source in state.reference_contract.sources" :key="source.id">{{ source.title }} · {{ source.status }}</p>
        <article v-for="(item, index) in state.reference_contract.structure_references" :key="index">
          <strong>{{ item.from || item.source }} · {{ item.role }}</strong>
          <p>借鉴：{{ item.take }}</p><p>改造：{{ item.adapt }}</p><p class="hint">依据：{{ item.evidence }}</p>
        </article>
        <p class="hint">{{ state.reference_contract.evidence_limits }}</p>
      </details>
      <details><summary>版本谱系</summary><code>{{ state.lineage }}</code></details>
    </template>
  </details>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { narrativeStateApi, type NarrativeCoverageStatus, type NarrativeStateView } from '@/api/novel'

const props = defineProps<{ projectId: string; chapterNumber: number | null; revisionKey?: string }>()
const emit = defineEmits<{ locateSource: [chapterNumber: number] }>()
const state = ref<NarrativeStateView | null>(null)
const loading = ref(false)
const error = ref('')
const opened = ref(false)
let requestSequence = 0
const gaps = computed(() => state.value?.coverage.chapters.filter((item) => item.status !== 'ready') || [])

function coverageLabel(status: NarrativeCoverageStatus) {
  return { ready: '可用', missing: '尚缺增量', invalid: '证据无效', stale: '前文或版本已变化', not_requested: '未提取 / 未采用' }[status]
}
async function load() {
  const sequence = ++requestSequence
  if (!props.chapterNumber) return
  loading.value = true
  error.value = ''
  state.value = null
  try {
    const result = await narrativeStateApi.get(props.projectId, props.chapterNumber)
    if (sequence === requestSequence) state.value = result
  } catch (cause) {
    if (sequence === requestSequence) error.value = cause instanceof Error ? cause.message : '正史暂时不可用，可继续写作。'
  } finally {
    if (sequence === requestSequence) loading.value = false
  }
}
function onToggle(event: Event) {
  opened.value = (event.target as HTMLDetailsElement).open
  if (opened.value && !state.value && !loading.value) void load()
}
watch(() => [props.projectId, props.chapterNumber, props.revisionKey], () => {
  requestSequence++
  state.value = null
  error.value = ''
  loading.value = false
  if (opened.value) void load()
})
</script>

<style scoped>
.narrative-panel { padding: 12px 0; border-bottom: 1px solid var(--md-outline-variant, #333); font-size: 12px; }
summary, button { cursor: pointer; }
summary { font-weight: 600; }
small, .hint { color: var(--md-on-surface-variant, #999); font-size: 11px; line-height: 1.7; }
h4 { margin-top: 12px; }
article { margin: 10px 0; }
article p { margin: 4px 0; }
blockquote { margin: 6px 0; padding-left: 8px; border-left: 2px solid var(--md-outline-variant, #555); white-space: pre-wrap; }
button { color: var(--md-primary, #b9caea); text-align: left; font-size: 11px; }
code { display: block; overflow-wrap: anywhere; font-size: 10px; margin: 6px 0; }
</style>

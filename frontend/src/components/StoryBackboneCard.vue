<!-- AIMETA P=故事去向卡_倒推规划骨架展示与编辑|R=终局与高潮节点线_前置条件列表_分块编辑_重算|NR=不含蓝图生成|E=component:StoryBackboneCard|X=internal|A=确认页子卡 -->
<template>
  <section v-if="visible" class="d-block d-block-backbone">
    <div class="d-block-head">
      <span class="d-block-tag">故事去向</span>
      <div class="bb-head-actions">
        <span v-if="resp?.stale" class="bb-stale">立项书已变动</span>
        <button
          class="d-edit-btn"
          :disabled="regenerating || loading || altLoading || isApplying || isEditingLocked"
          :title="isEditingLocked ? '请先保存或取消当前编辑' : ''"
          @click="loadAlternatives(true)"
        >
          {{ altLoading ? '构思中…' : '换个结局' }}
        </button>
        <button
          class="d-edit-btn"
          :disabled="regenerating || loading || isApplying || isEditingLocked"
          :title="isEditingLocked ? '请先保存或取消当前编辑' : ''"
          @click="regenerate"
        >
          {{ regenerating ? '倒推中…' : '重新倒推' }}
        </button>
      </div>
    </div>

    <!-- 「已变动」只放在 title 里触屏看不到；改成可见的一行提示（2026-10-23 审计） -->
    <p v-if="resp?.stale && !loading" class="bb-stale-hint">
      立项书在骨架生成后被改过，当前骨架可能已不对应。点「重新倒推」按最新立项书重算，你改过的节点会保留。
    </p>
    <p v-if="isEditingLocked && !loading" class="bb-edit-hint">正在编辑节点：保存或取消后才能重新倒推 / 换结局。</p>

    <div v-if="loading" class="bb-loading">
      <span class="bb-spinner"></span>
      正在从终局倒推各卷高潮与前置条件…首次约 30-60 秒
    </div>

    <div v-else-if="failed" class="bb-failed">
      <span>故事骨架加载失败{{ loadError ? `：${loadError}` : '' }}。不影响生成蓝图，但章纲将没有倒推的高潮与伏笔约束。</span>
      <button class="d-edit-btn" @click="load">重试</button>
    </div>

    <template v-else-if="backbone">
      <p class="bb-intro">
        先定结局，再倒推每一卷的高潮，每个高潮都列出「读者在此之前必须已经见过什么」——这些就是伏笔，蓝图会按窗口把它们埋进章纲。全书预计 {{ backbone.total_chapters || '—' }} 章。
      </p>

      <!-- 备选终局：选一个方向后以它为锚点重新倒推 -->
      <div v-if="alternatives.length" class="bb-alts">
        <div class="bb-alts-head">
          <span class="bb-alts-title">备选结局方向</span>
          <button class="d-edit-btn" :disabled="isApplying" @click="alternatives = []">收起</button>
        </div>
        <div class="bb-alt-grid">
          <div v-for="alt in alternatives" :key="alt.id" class="bb-alt">
            <p class="bb-alt-label">{{ alt.label || alt.id }}</p>
            <p class="bb-alt-line"><b>最后一战</b>{{ alt.endgame?.final_confrontation || '—' }}</p>
            <p v-if="alt.endgame?.core_answer" class="bb-alt-line"><b>答案</b>{{ alt.endgame.core_answer }}</p>
            <p v-if="alt.endgame?.cost" class="bb-alt-line"><b>代价</b>{{ alt.endgame.cost }}</p>
            <ol v-if="(alt.climax_events || []).length" class="bb-alt-climaxes">
              <li v-for="(ev, i) in alt.climax_events" :key="i">第 {{ i + 1 }} 卷：{{ ev }}</li>
            </ol>
            <p v-if="alt.why_different" class="bb-alt-why">{{ alt.why_different }}</p>
            <button class="d-save-btn" :disabled="isApplying" @click="applyAlternative(alt)">
              {{ applying === alt.id ? '倒推中…' : '采用此方向' }}
            </button>
          </div>
        </div>
        <p class="bb-alts-hint">采用后会按新方向重新倒推各卷高潮与前置条件，约 30-60 秒；你之后仍可逐节点修改。</p>
      </div>

      <!-- 终局 -->
      <div class="bb-endgame">
        <div class="bb-node-head">
          <span class="bb-node-kind bb-kind-end">终局</span>
          <button class="d-edit-btn" @click="toggleEdit('endgame')">{{ editing === 'endgame' ? '取消' : '编辑' }}</button>
        </div>
        <template v-if="editing === 'endgame'">
          <div v-for="f in ENDGAME_FIELDS" :key="f.key" class="d-field-edit">
            <label>{{ f.label }}</label>
            <textarea v-model="buffer[f.key]" class="d-textarea" rows="2"></textarea>
          </div>
          <div class="d-edit-actions">
            <button class="d-save-btn" :disabled="saving" @click="saveEndgame">{{ saving ? '保存中…' : '保存' }}</button>
          </div>
        </template>
        <dl v-else class="d-kv">
          <div v-for="f in ENDGAME_FIELDS" :key="f.key" class="d-kv-row">
            <dt>{{ f.label }}</dt><dd>{{ (backbone.endgame as any)?.[f.key] || '—' }}</dd>
          </div>
        </dl>
        <SetupList :setups="backbone.endgame?.setups || []" />
      </div>

      <!-- 节点线 -->
      <ol class="bb-timeline">
        <li v-for="node in nodes" :key="node.key" class="bb-node" :class="{ 'bb-node-open': expanded === node.key }">
          <button class="bb-node-row" type="button" @click="expanded = expanded === node.key ? null : node.key">
            <span class="bb-node-kind" :class="node.kindClass">{{ node.kind }}</span>
            <span class="bb-node-ch">第 {{ node.data.chapter }} 章</span>
            <span class="bb-node-event">{{ node.data.event || '（未规划）' }}</span>
            <span class="bb-node-count">{{ (node.data.setups || []).length }} 条前置</span>
          </button>

          <div v-if="expanded === node.key" class="bb-node-body">
            <div class="bb-node-head">
              <span v-if="node.data.volume_theme" class="bb-theme">{{ node.data.volume_theme }}</span>
              <button class="d-edit-btn" @click="toggleEdit(node.key)">{{ editing === node.key ? '取消' : '编辑' }}</button>
            </div>
            <template v-if="editing === node.key">
              <div class="d-field-edit">
                <label>高潮落在第几章</label>
                <input v-model="buffer.chapter" class="d-textarea bb-input" type="number" min="1" />
              </div>
              <div v-for="f in NODE_FIELDS" :key="f.key" class="d-field-edit">
                <label>{{ f.label }}</label>
                <textarea v-model="buffer[f.key]" class="d-textarea" rows="2"></textarea>
              </div>
              <div class="d-edit-actions">
                <button class="d-save-btn" :disabled="saving" @click="saveNode(node)">{{ saving ? '保存中…' : '保存' }}</button>
              </div>
            </template>
            <dl v-else class="d-kv">
              <div v-for="f in NODE_FIELDS" :key="f.key" class="d-kv-row">
                <dt>{{ f.label }}</dt><dd>{{ (node.data as any)[f.key] || '—' }}</dd>
              </div>
            </dl>
            <SetupList :setups="node.data.setups || []" />
          </div>
        </li>
      </ol>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, defineComponent, h } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import {
  NovelAPI,
  type BackboneAlternative,
  type BackboneClimax,
  type BackboneResponse,
  type BackboneSetup,
  type StoryBackbone,
} from '@/api/novel'

const props = defineProps<{ projectId: string }>()

const resp = ref<BackboneResponse | null>(null)
const loading = ref(false)
const regenerating = ref(false)
const failed = ref(false)
const loadError = ref('')
const backbone = computed<StoryBackbone | null>(() => resp.value?.backbone ?? null)
// 无立项书 / 开关关闭时整卡不显示，流程照旧；加载失败则显示一行错误和「重试」，不再悄悄消失
const visible = computed(() => loading.value || failed.value || !!backbone.value)

/** 去掉 http.ts 包装的「请求失败(409): 」前缀，用户只需要看后端的那句话。 */
const humanError = (error: unknown, fallback = '请稍后重试'): string => {
  const raw = error instanceof Error ? error.message : ''
  const stripped = raw.replace(/^请求失败\(\d{3}\):\s*/, '').replace(/^请求失败，状态码:\s*\d{3}$/, '').trim()
  return stripped || fallback
}

const ENDGAME_FIELDS = [
  { key: 'final_confrontation', label: '最后一战' },
  { key: 'core_answer', label: '冲突的答案' },
  { key: 'protagonist_becomes', label: '主角成为' },
  { key: 'cost', label: '代价' },
] as const

const NODE_FIELDS = [
  { key: 'event', label: '发生什么' },
  { key: 'reversal', label: '翻转/揭示' },
  { key: 'cost', label: '代价' },
  { key: 'protagonist_state_after', label: '之后的主角' },
] as const

interface NodeView {
  key: string
  kind: string
  kindClass: string
  data: BackboneClimax
  patchKey: 'first_promise' | 'midpoint' | 'climaxes'
  index?: number
}

const nodes = computed<NodeView[]>(() => {
  const bb = backbone.value
  if (!bb) return []
  const list: NodeView[] = []
  if (bb.first_promise) {
    list.push({ key: 'first_promise', kind: '第一次兑现', kindClass: 'bb-kind-first', data: bb.first_promise, patchKey: 'first_promise' })
  }
  ;(bb.climaxes || []).forEach((c, i) => {
    list.push({ key: `climaxes.${i + 1}`, kind: `第 ${c.volume_index || i + 1} 卷高潮`, kindClass: 'bb-kind-vol', data: c, patchKey: 'climaxes', index: c.volume_index || i + 1 })
  })
  if (bb.midpoint && bb.midpoint.event) {
    list.push({ key: 'midpoint', kind: '中点翻案', kindClass: 'bb-kind-mid', data: bb.midpoint, patchKey: 'midpoint' })
  }
  return list.sort((a, b) => (a.data.chapter || 0) - (b.data.chapter || 0))
})

const expanded = ref<string | null>(null)
const editing = ref<string | null>(null)
const saving = ref(false)
// 编辑中 / 保存中禁用「重新倒推」「换个结局」：两者都会把 editing 清空，正在改的节点会无声丢掉
const isEditingLocked = computed(() => editing.value !== null || saving.value)
const buffer = ref<Record<string, any>>({})

const toggleEdit = (key: string) => {
  if (editing.value === key) {
    editing.value = null
    return
  }
  const next: Record<string, any> = {}
  if (key === 'endgame') {
    ENDGAME_FIELDS.forEach((f) => (next[f.key] = (backbone.value?.endgame as any)?.[f.key] || ''))
  } else {
    const node = nodes.value.find((n) => n.key === key)
    if (!node) return
    next.chapter = node.data.chapter || 1
    NODE_FIELDS.forEach((f) => (next[f.key] = (node.data as any)[f.key] || ''))
  }
  buffer.value = next
  editing.value = key
}

const applyPatch = async (partial: Record<string, any>) => {
  saving.value = true
  try {
    resp.value = await NovelAPI.patchStoryBackbone(props.projectId, partial)
    editing.value = null
  } catch (error) {
    globalAlert.showError(`保存失败: ${humanError(error)}`, '故事去向')
  } finally {
    saving.value = false
  }
}

const saveEndgame = () =>
  applyPatch({ endgame: Object.fromEntries(ENDGAME_FIELDS.map((f) => [f.key, buffer.value[f.key] || ''])) })

const saveNode = (node: NodeView) => {
  const body: Record<string, any> = Object.fromEntries(NODE_FIELDS.map((f) => [f.key, buffer.value[f.key] || '']))
  const chapter = Number(buffer.value.chapter)
  if (Number.isFinite(chapter) && chapter >= 1) body.chapter = Math.round(chapter)
  if (node.patchKey === 'climaxes') return applyPatch({ climaxes: { [String(node.index)]: body } })
  return applyPatch({ [node.patchKey]: body })
}

// ── 备选终局 ──
const alternatives = ref<BackboneAlternative[]>([])
const altLoading = ref(false)
const applying = ref<string | null>(null)
const isApplying = computed(() => applying.value !== null)

const loadAlternatives = async (generate: boolean) => {
  altLoading.value = true
  try {
    const res = generate
      ? await NovelAPI.generateBackboneAlternatives(props.projectId)
      : await NovelAPI.listBackboneAlternatives(props.projectId)
    alternatives.value = res.alternatives || []
  } catch (error) {
    if (generate) globalAlert.showError(`生成备选方向失败: ${humanError(error)}`, '故事去向')
  } finally {
    altLoading.value = false
  }
}

const applyAlternative = async (alt: BackboneAlternative) => {
  applying.value = alt.id
  try {
    resp.value = await NovelAPI.applyBackboneAlternative(props.projectId, alt.id)
    alternatives.value = []
    editing.value = null
    expanded.value = null
    globalAlert.showSuccess(`已按「${alt.label || alt.id}」重新倒推，各卷高潮与前置条件已更新。`, '故事去向')
  } catch (error) {
    globalAlert.showError(`采用失败: ${humanError(error)}`, '故事去向')
  } finally {
    applying.value = null
  }
}

const load = async () => {
  loading.value = true
  failed.value = false
  loadError.value = ''
  try {
    resp.value = await NovelAPI.getStoryBackbone(props.projectId)
    if (resp.value?.backbone) void loadAlternatives(false)
  } catch (error) {
    console.error('拉取故事骨架失败:', error)
    failed.value = true
    loadError.value = humanError(error, '')
  } finally {
    loading.value = false
  }
}

const regenerate = async () => {
  regenerating.value = true
  try {
    resp.value = await NovelAPI.regenerateStoryBackbone(props.projectId)
    editing.value = null
    globalAlert.showSuccess('已按最新立项书重新倒推，你改过的节点已保留。', '故事去向')
  } catch (error) {
    globalAlert.showError(`重算失败: ${humanError(error)}`, '故事去向')
  } finally {
    regenerating.value = false
  }
}

onMounted(load)

// 前置条件列表：终局与各节点共用
const SetupList = defineComponent({
  props: { setups: { type: Array as () => BackboneSetup[], default: () => [] } },
  setup(p) {
    return () =>
      p.setups.length
        ? h('div', { class: 'bb-setups' }, [
            h('p', { class: 'bb-setups-title' }, '读者在此之前必须已经见过'),
            h(
              'ul',
              { class: 'bb-setup-list' },
              p.setups.map((s, i) =>
                h('li', { key: i, class: ['bb-setup', s.tier === '核心' ? 'bb-setup-core' : ''] }, [
                  h('div', { class: 'bb-setup-head' }, [
                    h('span', { class: 'bb-setup-name' }, s.name || '未命名'),
                    h('span', { class: 'bb-setup-tier' }, s.tier || '支线'),
                    h('span', { class: 'bb-setup-window' }, `第 ${s.plant_from ?? '?'}–${s.plant_to ?? '?'} 章之间埋下`),
                  ]),
                  h('p', { class: 'bb-setup-what' }, s.what_must_be_established || ''),
                  s.why_needed ? h('p', { class: 'bb-setup-why' }, `不埋会怎样：${s.why_needed}`) : null,
                ]),
              ),
            ),
          ])
        : h('p', { class: 'bb-setups-empty' }, '这个节点还没有前置条件，蓝图会按正向方式处理。')
  },
})
</script>

<style scoped>
.d-block { background: #1c1c1c; border: 1px solid #2a2a2a; border-radius: 12px; padding: 16px 18px; }
.d-block-backbone { border-color: rgba(125, 211, 168, 0.3); }
.d-block-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.d-block-tag { font-size: 12px; font-weight: 600; color: #ffe500; letter-spacing: 0.05em; }
.bb-head-actions { display: flex; align-items: center; gap: 10px; }
.bb-stale { font-size: 11px; color: #ffb800; background: rgba(255, 184, 0, 0.1); border-radius: 999px; padding: 2px 9px; }
.bb-stale-hint { font-size: 12px; color: #ffb800; line-height: 1.6; margin: 0 0 10px; }
.bb-edit-hint { font-size: 12px; color: #888; line-height: 1.6; margin: 0 0 10px; }
.bb-failed {
  display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
  font-size: 12px; color: #ff8a80; line-height: 1.6; padding: 8px 0;
}
.d-edit-btn {
  background: transparent; border: 1px solid #333; color: #888; font-size: 12px;
  border-radius: 6px; padding: 3px 10px; cursor: pointer; transition: all 0.15s;
}
.d-edit-btn:hover { color: #ffe500; border-color: #ffe500; }
.d-edit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.bb-loading { display: flex; align-items: center; gap: 10px; font-size: 13px; color: #999; padding: 8px 0; }
.bb-spinner {
  width: 14px; height: 14px; border-radius: 50%; border: 2px solid #333; border-top-color: #7dd3a8;
  animation: bb-spin 0.8s linear infinite; flex-shrink: 0;
}
@keyframes bb-spin { to { transform: rotate(360deg); } }
.bb-intro { font-size: 12px; color: #888; line-height: 1.7; margin-bottom: 14px; }

.bb-alts { border: 1px dashed rgba(255, 184, 0, 0.4); border-radius: 10px; padding: 12px 14px; margin-bottom: 14px; }
.bb-alts-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.bb-alts-title { font-size: 12px; font-weight: 600; color: #ffb800; }
.bb-alt-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; }
.bb-alt { background: #181818; border: 1px solid #2a2a2a; border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; }
.bb-alt-label { font-size: 14px; font-weight: 700; color: #eee; }
.bb-alt-line { font-size: 12px; color: #ccc; line-height: 1.6; }
.bb-alt-line b { color: #888; font-weight: 500; margin-right: 6px; }
.bb-alt-climaxes { margin: 0; padding-left: 18px; font-size: 12px; color: #bbb; line-height: 1.6; }
.bb-alt-why { font-size: 12px; color: #7dd3a8; line-height: 1.6; }
.bb-alt .d-save-btn { align-self: flex-end; margin-top: 4px; }
.bb-alts-hint { margin-top: 10px; font-size: 11px; color: #666; }

.bb-endgame { border: 1px solid rgba(255, 229, 0, 0.25); border-radius: 10px; padding: 12px 14px; margin-bottom: 14px; }
.bb-node-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.bb-node-kind { font-size: 11px; font-weight: 700; border-radius: 4px; padding: 2px 8px; flex-shrink: 0; }
.bb-kind-end { color: #ffe500; background: rgba(255, 229, 0, 0.12); }
.bb-kind-first { color: #7dd3a8; background: rgba(125, 211, 168, 0.12); }
.bb-kind-vol { color: #9bb8ff; background: rgba(155, 184, 255, 0.12); }
.bb-kind-mid { color: #ffb800; background: rgba(255, 184, 0, 0.12); }
.bb-theme { font-size: 12px; color: #aaa; }

.bb-timeline { list-style: none; margin: 0; padding: 0 0 0 14px; border-left: 2px solid #2a2a2a; display: flex; flex-direction: column; gap: 8px; }
.bb-node { position: relative; }
.bb-node::before {
  content: ''; position: absolute; left: -20px; top: 12px; width: 10px; height: 10px; border-radius: 50%;
  background: #2a2a2a; border: 2px solid #444;
}
.bb-node-open::before { background: #7dd3a8; border-color: #7dd3a8; }
.bb-node-row {
  width: 100%; display: flex; align-items: center; gap: 10px; text-align: left; background: #181818;
  border: 1px solid #2a2a2a; border-radius: 8px; padding: 8px 12px; cursor: pointer; color: #ddd;
}
.bb-node-row:hover { border-color: #444; }
.bb-node-ch { font-size: 12px; color: #888; flex-shrink: 0; }
.bb-node-event { font-size: 13px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bb-node-open .bb-node-event { white-space: normal; }
.bb-node-count { font-size: 11px; color: #666; flex-shrink: 0; }
.bb-node-body { padding: 10px 12px 4px; }

.d-kv { display: flex; flex-direction: column; gap: 8px; }
.d-kv-row { display: flex; gap: 12px; font-size: 13px; line-height: 1.65; }
.d-kv-row dt { flex-shrink: 0; width: 76px; color: #888; }
.d-kv-row dd { color: #ddd; }
.d-textarea {
  width: 100%; background: #111; border: 1px solid #333; border-radius: 8px; color: #eee;
  font-size: 13px; padding: 8px 10px; line-height: 1.6; resize: vertical; font-family: inherit;
}
.d-textarea:focus { outline: none; border-color: #ffe500; }
.bb-input { width: 120px; resize: none; }
.d-field-edit { margin-bottom: 10px; }
.d-field-edit label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
.d-edit-actions { margin-top: 10px; text-align: right; }
.d-save-btn {
  background: #ffe500; color: #111; border: none; border-radius: 6px; padding: 6px 16px;
  font-size: 13px; font-weight: 600; cursor: pointer;
}
.d-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.bb-setups { margin-top: 10px; padding-top: 10px; border-top: 1px dashed #2a2a2a; }
.bb-setups-title { font-size: 12px; color: #7dd3a8; font-weight: 600; margin-bottom: 8px; }
.bb-setups-empty { font-size: 12px; color: #666; margin-top: 8px; }
.bb-setup-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.bb-setup { border: 1px solid #2a2a2a; border-radius: 8px; padding: 8px 10px; }
.bb-setup-core { border-color: rgba(125, 211, 168, 0.35); }
.bb-setup-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.bb-setup-name { font-size: 13px; font-weight: 600; color: #eee; }
.bb-setup-tier { font-size: 10px; color: #7dd3a8; border: 1px solid rgba(125, 211, 168, 0.4); border-radius: 4px; padding: 0 5px; }
.bb-setup-window { font-size: 11px; color: #888; margin-left: auto; }
.bb-setup-what { font-size: 12px; color: #ccc; line-height: 1.6; margin-top: 4px; }
.bb-setup-why { font-size: 12px; color: #888; line-height: 1.6; margin-top: 2px; }
</style>

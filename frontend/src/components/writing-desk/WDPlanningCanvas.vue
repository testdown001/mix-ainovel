<!-- AIMETA P=写作台章节规划画布|R=目标约束_情节拍_引用_推进工作流|NR=不含右侧上下文|E=component:WDPlanningCanvas|X=ui|A=规划组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <main class="planning-canvas">
    <header class="canvas-head">
      <div class="chapter-heading">
        <span class="chapter-badge">第{{ selectedChapterNumber }}章</span>
        <div>
          <div class="title-line">
            <h1>{{ outline?.title || '未命名章节' }}</h1>
            <span class="stage-pill">已规划</span>
          </div>
          <p>{{ outline?.summary || '为这一章补充目标、情节节拍和登场引用。' }}</p>
        </div>
      </div>
      <button
        type="button"
        class="primary-action"
        :disabled="generationBusy"
        @click="requestGenerate"
      >
        <svg v-if="generationBusy" class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 12a8 8 0 1 1-2.35-5.65" /><path d="M20 5v7h-7" />
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9">
          <path d="m13 2-9 12h7l-1 8 9-12h-7z" />
        </svg>
        {{ generationButtonLabel }}
      </button>
    </header>

    <div class="canvas-scroll">
      <section class="planning-card goal-card">
        <div class="section-head">
          <div>
            <span class="section-index">01</span>
            <h2>目标与约束</h2>
          </div>
          <button v-if="!editingPlanning" type="button" class="text-action" @click="beginPlanningEdit">
            编辑规划
          </button>
          <div v-else class="edit-actions">
            <button type="button" class="text-action" @click="editingPlanning = false">取消</button>
            <button type="button" class="save-action" :disabled="planningSaving" @click="savePlanning">
              {{ planningSaving ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>

        <div v-if="!editingPlanning" class="goal-grid">
          <div class="goal-item">
            <span class="goal-icon target"><i></i></span>
            <div><label>本章功能</label><p>{{ planning.chapter_function || '推进核心冲突并承接上一章结果' }}</p></div>
          </div>
          <div class="goal-item">
            <span class="goal-icon spark">✦</span>
            <div><label>预期爽点</label><p>{{ planning.coolpoint || '尚未设定，可在生成正文前补充' }}</p></div>
          </div>
          <div class="goal-item wide">
            <span class="goal-icon ban">／</span>
            <div><label>禁写与边界</label><p>{{ mustNotLabel }}</p></div>
          </div>
        </div>

        <div v-else class="planning-form">
          <label>本章功能<input v-model="planningDraft.chapter_function" placeholder="例如：完成阵营转折，推动主角作出选择" /></label>
          <label>预期爽点<input v-model="planningDraft.coolpoint" placeholder="例如：信息差反制、身份揭晓" /></label>
          <label class="full">禁写与边界<textarea v-model="mustNotDraft" rows="2" placeholder="每行一条，避免跑偏或提前揭底" /></label>
        </div>
      </section>

      <section class="planning-card beats-card">
        <div class="section-head">
          <div>
            <span class="section-index">02</span>
            <h2>情节拍</h2>
            <span class="section-note">{{ beats.length ? `${beats.length} 个节拍` : '生成正文时自动梳理' }}</span>
          </div>
          <button v-if="beats.length && !editingBeats" type="button" class="text-action" @click="beginBeatsEdit">编辑节拍</button>
          <div v-else-if="editingBeats" class="edit-actions">
            <button type="button" class="text-action" @click="editingBeats = false">取消</button>
            <button type="button" class="save-action" :disabled="beatsSaving" @click="saveBeats">
              {{ beatsSaving ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>

        <div v-if="beats.length && !editingBeats" class="beat-list">
          <div v-for="(beat, index) in beats" :key="`${beat.type}-${index}`" class="beat-row">
            <span class="beat-order">{{ String(index + 1).padStart(2, '0') }}</span>
            <span class="beat-type" :class="`beat-${beat.type}`">{{ beatLabel(beat.type) }}</span>
            <p>{{ beat.content }}</p>
            <span v-if="beat.emotion" class="beat-emotion">{{ beat.emotion }}</span>
          </div>
        </div>

        <div v-else-if="editingBeats" class="beat-editor">
          <div v-for="(beat, index) in beatsDraft" :key="index" class="beat-edit-row">
            <select v-model="beat.type">
              <option value="setup">铺垫</option><option value="provoke">激化</option>
              <option value="twist">转折</option><option value="payoff">爆发</option><option value="hook">悬念</option>
            </select>
            <input v-model="beat.content" placeholder="节拍内容" />
            <input v-model="beat.emotion" class="emotion-input" placeholder="情绪" />
            <button type="button" title="删除节拍" @click="beatsDraft.splice(index, 1)">×</button>
          </div>
          <button type="button" class="add-beat" @click="addBeat">＋ 添加一个情节拍</button>
        </div>

        <div v-else class="beats-empty">
          <span class="empty-orbit"><i></i></span>
          <div><strong>正文生成时自动梳理</strong><p>AI 会先把本章摘要整理成铺垫、转折、爆发与悬念节拍，再无缝进入正文创作。</p></div>
        </div>

        <details class="advanced-options">
          <summary>高级选项</summary>
          <div>
            <p>需要在生成正文前单独查看或调整情节节拍时，可以提前重新梳理。</p>
            <button
              type="button"
              :disabled="generationBusy"
              @click="emit('requestPrediction', selectedChapterNumber)"
            >
              {{ predictionGenerating ? '正在梳理…' : prediction ? '重新梳理情节' : '提前梳理情节' }}
            </button>
          </div>
        </details>
      </section>

      <section class="planning-card reference-card">
        <div class="section-head">
          <div><span class="section-index">03</span><h2>登场与引用</h2></div>
          <span class="section-note">自动从蓝图中匹配</span>
        </div>
        <div class="reference-grid">
          <div class="reference-group">
            <label>登场人物</label>
            <div class="chip-row">
              <span v-for="character in relatedCharacters" :key="character.name" class="reference-chip character-chip">
                <i>{{ character.name.slice(0, 1) }}</i>{{ character.name }}
              </span>
              <span v-if="!relatedCharacters.length" class="empty-chip">本章摘要暂未提及人物</span>
            </div>
          </div>
          <div class="reference-group">
            <label>设定引用</label>
            <div class="chip-row">
              <span v-for="setting in settingLabels" :key="setting" class="reference-chip">{{ setting }}</span>
              <span v-if="!settingLabels.length" class="empty-chip">从右侧上下文选择</span>
            </div>
          </div>
          <div class="reference-group">
            <label>伏笔操作</label>
            <div class="chip-row">
              <span v-for="item in foreshadowingLabels" :key="item" class="reference-chip foreshadow-chip">{{ item }}</span>
              <span v-if="!foreshadowingLabels.length" class="empty-chip">无指定伏笔操作</span>
            </div>
          </div>
        </div>
      </section>

      <footer class="canvas-footer">
        <div>
          <span>下一步</span>
          <p>生成正文时将自动完成情节梳理与一致性检查。</p>
        </div>
        <div class="footer-actions">
          <button type="button" class="secondary-action" @click="emit('openCodex')">与 AI 讨论本章</button>
          <button type="button" class="primary-action" :disabled="generationBusy" @click="requestGenerate">
            {{ generationButtonLabel }}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M5 12h14m-5-5 5 5-5 5" /></svg>
          </button>
        </div>
      </footer>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useNovelStore } from '@/stores/novel'
import { globalAlert } from '@/composables/useAlert'
import { invalidatePrediction } from '@/utils/writingWorkflow'
import type {
  ChapterBeat,
  ChapterPlanning,
  Character,
  NovelProject,
} from '@/api/novel'

const props = defineProps<{
  project: NovelProject
  selectedChapterNumber: number
  generatingChapter?: number | null
  predictionGeneratingChapter?: number | null
}>()

const emit = defineEmits<{
  requestPrediction: [chapterNumber: number]
  generateChapter: [chapterNumber: number]
  openCodex: []
}>()

const novelStore = useNovelStore()
const editingPlanning = ref(false)
const planningSaving = ref(false)
const planningDraft = ref<ChapterPlanning>({})
const mustNotDraft = ref('')
const editingBeats = ref(false)
const beatsSaving = ref(false)
const beatsDraft = ref<ChapterBeat[]>([])

const outline = computed(() =>
  props.project.blueprint?.chapter_outline?.find(
    (item) => item.chapter_number === props.selectedChapterNumber,
  ),
)
const planning = computed<ChapterPlanning>(() => outline.value?.metadata?.planning || {})
const prediction = computed(() => outline.value?.metadata?.prediction || null)
const beats = computed<ChapterBeat[]>(() => prediction.value?.beats || [])
const predictionGenerating = computed(
  () => props.predictionGeneratingChapter === props.selectedChapterNumber,
)
const chapterGenerating = computed(() => props.generatingChapter === props.selectedChapterNumber)
const generationBusy = computed(() => predictionGenerating.value || chapterGenerating.value)
const chapterCompleted = computed(() =>
  props.project.chapters?.some(
    (chapter) => chapter.chapter_number === props.selectedChapterNumber && !!chapter.content,
  ),
)
const generationButtonLabel = computed(() => {
  if (predictionGenerating.value) return '正在梳理情节…'
  if (chapterGenerating.value) return '正在生成正文…'
  return chapterCompleted.value ? '重新生成正文' : '生成本章正文'
})
const mustNotLabel = computed(() =>
  planning.value.must_not_include?.length
    ? planning.value.must_not_include.join(' · ')
    : '不提前揭示核心谜底，保持角色动机一致',
)

const relatedCharacters = computed<Character[]>(() => {
  const characters = props.project.blueprint?.characters || []
  const source = `${outline.value?.title || ''} ${outline.value?.summary || ''}`
  const matched = characters.filter((character) => source.includes(character.name))
  return (matched.length ? matched : characters).slice(0, 4)
})

const settingLabels = computed(() => {
  const world = props.project.blueprint?.world_setting
  if (!world || typeof world !== 'object' || Array.isArray(world)) return []
  return Object.keys(world).slice(0, 3).map((key) => formatKey(key))
})

const foreshadowingLabels = computed(() => {
  const operations = planning.value.foreshadowing_ops || []
  if (operations.length) return operations.slice(0, 3).map((item) => `${item.op} · ${item.name}`)
  return (props.project.blueprint?.foreshadowings || [])
    .filter((item) => {
      const planted = item.planted_chapter || 1
      const target = item.target_chapter || Number.MAX_SAFE_INTEGER
      return planted <= props.selectedChapterNumber && target >= props.selectedChapterNumber
    })
    .slice(0, 2)
    .map((item) => item.name || item.description || '未命名伏笔')
})

function formatKey(key: string): string {
  const labels: Record<string, string> = {
    power_system: '力量体系',
    geography: '地理与势力',
    factions: '阵营势力',
    social_structure: '社会结构',
    rules: '世界规则',
    core_rule: '核心规则',
    core_rules: '核心规则',
    key_location: '关键地点',
    key_locations: '关键地点',
    era: '时代背景',
  }
  return labels[key] || key.replace(/_/g, ' ')
}

function beatLabel(type: ChapterBeat['type']): string {
  return { setup: '铺垫', provoke: '激化', twist: '转折', payoff: '爆发', hook: '悬念' }[type]
}

function beginPlanningEdit() {
  planningDraft.value = { ...planning.value }
  mustNotDraft.value = (planning.value.must_not_include || []).join('\n')
  editingPlanning.value = true
}

async function savePlanning() {
  if (!outline.value) return
  planningSaving.value = true
  try {
    const updatedPlanning: ChapterPlanning = {
      ...planning.value,
      ...planningDraft.value,
      must_not_include: mustNotDraft.value.split('\n').map((item) => item.trim()).filter(Boolean),
    }
    const metadata = invalidatePrediction(outline.value.metadata)
    await novelStore.updateChapterOutline({
      ...outline.value,
      metadata: { ...metadata, planning: updatedPlanning },
    })
    editingPlanning.value = false
    globalAlert.showSuccess('本章规划已保存；生成正文时会自动更新情节梳理。', '规划已更新')
  } catch (error) {
    globalAlert.showError(error instanceof Error ? error.message : '保存失败', '章节规划')
  } finally {
    planningSaving.value = false
  }
}

function beginBeatsEdit() {
  beatsDraft.value = beats.value.map((beat) => ({ ...beat }))
  editingBeats.value = true
}

function addBeat() {
  beatsDraft.value.push({ type: 'setup', content: '', emotion: '' })
}

async function requestGenerate() {
  if (generationBusy.value) return
  if (chapterCompleted.value) {
    const confirmed = await globalAlert.showConfirm(
      '重新生成会覆盖当前章节的生成结果，确定继续吗？',
      '重新生成正文',
    )
    if (!confirmed) return
  }
  emit('generateChapter', props.selectedChapterNumber)
}

async function saveBeats() {
  if (!outline.value) return
  beatsSaving.value = true
  try {
    const nextPrediction = {
      key_points: prediction.value?.key_points || [],
      cool_points: prediction.value?.cool_points || [],
      foreshadowing_hooks: prediction.value?.foreshadowing_hooks || [],
      foreshadowing_targets: prediction.value?.foreshadowing_targets || [],
      limitations: prediction.value?.limitations || [],
      beats: beatsDraft.value.filter((beat) => beat.content.trim()),
    }
    await novelStore.updateChapterOutline({
      ...outline.value,
      metadata: { ...(outline.value.metadata || {}), prediction: nextPrediction },
    })
    editingBeats.value = false
    globalAlert.showSuccess('情节拍已保存', '规划已更新')
  } catch (error) {
    globalAlert.showError(error instanceof Error ? error.message : '保存失败', '情节拍')
  } finally {
    beatsSaving.value = false
  }
}

watch(
  () => props.selectedChapterNumber,
  () => {
    editingPlanning.value = false
    editingBeats.value = false
  },
)
</script>

<style scoped>
.planning-canvas { display: flex; min-width: 0; height: 100%; flex: 1; flex-direction: column; overflow: hidden; border: 1px solid #242521; border-radius: 18px; background: rgba(16,17,15,.97); box-shadow: 0 24px 70px rgba(0,0,0,.2); }
.canvas-head { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 25px 27px 22px; border-bottom: 1px solid #242520; }
.chapter-heading { display: flex; min-width: 0; align-items: flex-start; gap: 16px; }
.chapter-badge { display: inline-flex; height: 30px; flex-shrink: 0; align-items: center; padding: 0 10px; border: 1px solid #373930; border-radius: 7px; color: #d7d8cf; font-size: 11px; font-weight: 700; background: #1d1e1a; }
.title-line { display: flex; min-width: 0; align-items: center; gap: 10px; }
.title-line h1 { margin: 0; overflow: hidden; color: #f7f7f1; font-size: 22px; font-weight: 690; letter-spacing: -.02em; text-overflow: ellipsis; white-space: nowrap; }
.stage-pill { padding: 4px 8px; border-radius: 99px; color: #999b93; font-size: 9px; background: #242521; }
.chapter-heading p { max-width: 760px; margin: 8px 0 0; overflow: hidden; color: #858880; font-size: 11px; line-height: 18px; text-overflow: ellipsis; white-space: nowrap; }
.primary-action, .secondary-action { display: inline-flex; height: 38px; flex-shrink: 0; align-items: center; justify-content: center; gap: 8px; padding: 0 16px; border-radius: 9px; font-size: 11px; font-weight: 750; transition: .18s ease; }
.primary-action { border: 1px solid #ffe500; color: #0c0d0b; background: #ffe500; box-shadow: 0 7px 22px rgba(255,229,0,.08); }
.primary-action:hover { background: #fff143; transform: translateY(-1px); }
.primary-action:disabled { opacity: .55; cursor: wait; transform: none; }
.primary-action svg { width: 15px; height: 15px; }
.secondary-action { border: 1px solid #343630; color: #b9bbb2; background: #1a1b18; }
.secondary-action:hover { border-color: #525449; color: #f1f1e9; }
.canvas-scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 18px 20px 24px; scrollbar-width: thin; scrollbar-color: #33352f transparent; }
.planning-card { margin-bottom: 12px; padding: 19px 20px; border: 1px solid #282a25; border-radius: 13px; background: #141512; }
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 17px; }
.section-head > div:first-child { display: flex; align-items: center; gap: 9px; }
.section-index { color: #d1c31d; font-size: 9px; font-weight: 850; letter-spacing: .09em; }
.section-head h2 { margin: 0; color: #ecece5; font-size: 14px; font-weight: 680; }
.section-note { color: #696c65; font-size: 9px; }
.text-action { padding: 4px 1px; border: 0; color: #85887f; font-size: 10px; background: transparent; }
.text-action:hover { color: #ffe500; }
.edit-actions { display: flex; align-items: center; gap: 10px; }
.save-action { padding: 6px 10px; border: 1px solid #5a5420; border-radius: 6px; color: #f1df26; font-size: 10px; background: rgba(255,229,0,.07); }
.goal-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 9px; }
.goal-item { display: flex; min-width: 0; align-items: flex-start; gap: 11px; padding: 12px 13px; border: 1px solid #272924; border-radius: 9px; background: #11120f; }
.goal-item.wide { grid-column: 1/-1; }
.goal-item label, .reference-group > label { display: block; margin-bottom: 4px; color: #686b64; font-size: 9px; font-weight: 650; letter-spacing: .02em; }
.goal-item p { margin: 0; color: #b5b7af; font-size: 11px; line-height: 18px; }
.goal-icon { display: grid; width: 25px; height: 25px; flex-shrink: 0; place-items: center; border-radius: 7px; color: #c8b918; font-size: 11px; background: rgba(255,229,0,.07); }
.goal-icon.target i { width: 8px; height: 8px; border: 2px solid currentColor; border-radius: 50%; box-shadow: 0 0 0 3px rgba(255,229,0,.08); }
.goal-icon.ban { color: #a1a39b; background: #23241f; }
.planning-form { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 10px; }
.planning-form label { color: #777a72; font-size: 10px; }
.planning-form label.full { grid-column: 1/-1; }
.planning-form input, .planning-form textarea, .beat-edit-row input, .beat-edit-row select { width: 100%; margin-top: 6px; padding: 9px 10px; border: 1px solid #33352f; border-radius: 7px; outline: none; color: #e4e5de; font-size: 11px; background: #10110f; }
.planning-form input:focus, .planning-form textarea:focus, .beat-edit-row input:focus { border-color: #81771c; }
.beat-list { overflow: hidden; border: 1px solid #272924; border-radius: 9px; }
.beat-row { display: grid; grid-template-columns: 30px 48px minmax(0,1fr) auto; align-items: center; gap: 10px; min-height: 47px; padding: 8px 12px; border-bottom: 1px solid #252722; background: #11120f; }
.beat-row:last-child { border-bottom: 0; }
.beat-order { color: #555850; font-size: 9px; font-weight: 750; }
.beat-type { justify-self: start; padding: 4px 7px; border-radius: 5px; color: #94978f; font-size: 9px; font-weight: 700; background: #252621; }
.beat-type.beat-twist, .beat-type.beat-payoff { color: #ebda29; background: rgba(255,229,0,.09); }
.beat-type.beat-hook { color: #8eadc7; background: rgba(76,130,175,.1); }
.beat-row p { margin: 0; color: #b9bbb3; font-size: 11px; line-height: 17px; }
.beat-emotion { color: #666961; font-size: 9px; }
.beats-empty { display: flex; align-items: center; gap: 12px; padding: 15px; border: 1px dashed #30322c; border-radius: 9px; background: #11120f; }
.empty-orbit { display: grid; width: 32px; height: 32px; place-items: center; border: 1px solid #45473e; border-radius: 50%; }
.empty-orbit i { width: 6px; height: 6px; border-radius: 50%; background: #ffe500; box-shadow: 0 0 13px #ffe500; }
.beats-empty div { flex: 1; }
.beats-empty strong { color: #cfd0c8; font-size: 11px; }
.beats-empty p { margin: 3px 0 0; color: #6c6f67; font-size: 10px; }
.beats-empty button, .add-beat { padding: 7px 10px; border: 1px solid #494a3c; border-radius: 6px; color: #d7c91f; font-size: 10px; background: rgba(255,229,0,.04); }
.advanced-options { margin-top: 12px; border-top: 1px solid #272924; color: #777a72; }
.advanced-options summary { width: fit-content; padding-top: 11px; cursor: pointer; color: #777a72; font-size: 10px; }
.advanced-options > div { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 10px 0 2px; }
.advanced-options p { margin: 0; color: #676a63; font-size: 10px; line-height: 16px; }
.advanced-options button { flex-shrink: 0; padding: 7px 10px; border: 1px solid #3b3d36; border-radius: 6px; color: #b9bbb2; font-size: 10px; background: #1a1b18; }
.advanced-options button:hover { border-color: #625d24; color: #eddd2b; }
.advanced-options button:disabled { opacity: .5; cursor: wait; }
.beat-editor { display: flex; flex-direction: column; gap: 7px; }
.beat-edit-row { display: grid; grid-template-columns: 86px minmax(0,1fr) 100px 28px; align-items: end; gap: 7px; }
.beat-edit-row input, .beat-edit-row select { margin: 0; }
.beat-edit-row button { height: 32px; border: 1px solid #3b302e; border-radius: 6px; color: #b06f68; background: #1d1716; }
.add-beat { align-self: flex-start; }
.reference-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 18px; }
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.reference-chip, .empty-chip { display: inline-flex; height: 26px; align-items: center; gap: 5px; padding: 0 8px; border: 1px solid #30322c; border-radius: 7px; color: #a9aba3; font-size: 9px; background: #191a17; }
.reference-chip i { display: grid; width: 16px; height: 16px; place-items: center; border-radius: 50%; color: #0d0e0c; font-size: 8px; font-style: normal; font-weight: 750; background: #cac21e; }
.foreshadow-chip { color: #9fb2c1; }
.empty-chip { color: #5f625b; border-style: dashed; background: transparent; }
.canvas-footer { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 4px 2px 0; }
.canvas-footer > div:first-child span { color: #5e615a; font-size: 9px; font-weight: 700; letter-spacing: .08em; }
.canvas-footer p { margin: 3px 0 0; color: #93968e; font-size: 10px; }
.footer-actions { display: flex; align-items: center; gap: 8px; }
.spin { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 1100px) { .reference-grid { grid-template-columns: 1fr; } .chapter-heading p { max-width: 420px; } }
@media (max-width: 760px) { .canvas-head { align-items: flex-start; padding: 18px; } .chapter-heading { flex-direction: column; gap: 8px; } .canvas-head > .primary-action { display: none; } .goal-grid, .planning-form { grid-template-columns: 1fr; } .goal-item.wide, .planning-form label.full { grid-column: auto; } .beat-row { grid-template-columns: 25px 42px minmax(0,1fr); } .beat-emotion { display: none; } .canvas-footer { align-items: flex-start; flex-direction: column; } }
</style>

<!-- AIMETA P=蓝图确认_立项书决策面|R=立项书分块展示编辑_压力推演报告_采纳修复返回对话生成蓝图三动作|NR=不含蓝图渲染|E=component:BlueprintConfirmation|X=internal|A=决策面|D=vue,api/novel|S=dom|RD=./README.ai -->
<template>
  <div class="dossier-shell">
    <!-- ═══ 头部 ═══ -->
    <div class="dossier-head">
      <h2 class="dossier-title">故事立项书</h2>
      <p class="dossier-sub">
        对话共识已蒸馏为结构化立项书{{ dossierResp?.stress_available ? '，并经白金主编压力推演' : '' }}。确认或修改后再生成蓝图，越早改越省返工。
      </p>
    </div>

    <!-- ═══ 立项书加载中 ═══ -->
    <div v-if="dossierLoading" class="dossier-loading">
      <div class="loading-ring-wrap">
        <div class="loading-ring"></div>
        <div class="loading-core">✦</div>
      </div>
      <p class="loading-title">{{ dossierStageText }}</p>
      <p class="loading-sub">已用时 {{ elapsedLabel(dossierElapsed) }} · 首次蒸馏约需 30-90 秒</p>
      <ul class="loading-stages">
        <li
          v-for="(stage, i) in DOSSIER_STAGES"
          :key="i"
          :class="i < dossierStageIndex ? 'st-done' : i === dossierStageIndex ? 'st-active' : 'st-wait'"
        >
          <span class="st-dot"></span>{{ stage }}
        </li>
      </ul>
    </div>

    <!-- ═══ 蓝图生成中 ═══ -->
    <div v-else-if="isGenerating" class="dossier-loading">
      <div class="loading-ring-wrap">
        <div class="loading-ring" :class="{ 'ring-done': genDone }"></div>
        <div class="loading-core">{{ genDone ? '✓' : '✎' }}</div>
      </div>
      <p class="loading-title">{{ genStageText }}</p>
      <p class="loading-sub">已用时 {{ elapsedLabel(genElapsed) }} · {{ genEtaHint }}</p>
      <ul class="loading-stages">
        <li
          v-for="(stage, i) in genStages"
          :key="i"
          :class="i < genStageIndex ? 'st-done' : i === genStageIndex ? 'st-active' : 'st-wait'"
        >
          <span class="st-dot"></span>{{ stage }}
        </li>
      </ul>
      <div class="loading-bar">
        <div class="loading-bar-fill" :style="{ width: `${genProgress}%` }"></div>
      </div>
      <p class="loading-hint">步骤为预估节奏，已用时为真实计时。请勿关闭页面。</p>
    </div>

    <!-- ═══ 立项书主体 ═══ -->
    <template v-else>
      <!-- 无立项书降级：不阻断生成 -->
      <div v-if="!dossier" class="dossier-absent">
        <p class="absent-title">立项书生成未完成</p>
        <p class="absent-sub">{{ aiMessage || '已收集到足够信息。' }}</p>
        <p class="absent-hint">可以直接生成蓝图（走原始对话链路），也可以返回对话再聊几轮后重试。</p>
      </div>

      <div v-else class="dossier-body">
        <!-- 核心卖点 -->
        <section class="d-block d-block-hero">
          <div class="d-block-head">
            <span class="d-block-tag">核心卖点</span>
            <button class="d-edit-btn" @click="startEdit('selling')">{{ editing === 'selling' ? '取消' : '编辑' }}</button>
          </div>
          <template v-if="editing === 'selling'">
            <textarea v-model="buffer.core_selling_line" class="d-textarea" rows="3"></textarea>
            <div class="d-edit-actions">
              <button class="d-save-btn" :disabled="saving" @click="saveEdit({ core_selling_line: buffer.core_selling_line })">{{ saving ? '保存中…' : '保存' }}</button>
            </div>
          </template>
          <p v-else class="d-hero-text">{{ dossier.core_selling_line || '（未提炼）' }}</p>
          <div class="d-meta-row">
            <span v-if="dossier.genre" class="d-chip">{{ dossier.genre }}</span>
            <span v-if="dossier.audience" class="d-chip">{{ dossier.audience }}</span>
            <span v-if="dossier.platform_mode" class="d-chip">{{ dossier.platform_mode }}</span>
          </div>
        </section>

        <!-- 主角三件套 -->
        <section class="d-block">
          <div class="d-block-head">
            <span class="d-block-tag">主角三件套</span>
            <button class="d-edit-btn" @click="startEdit('protagonist')">{{ editing === 'protagonist' ? '取消' : '编辑' }}</button>
          </div>
          <template v-if="editing === 'protagonist'">
            <div v-for="f in PROTAGONIST_FIELDS" :key="f.key" class="d-field-edit">
              <label>{{ f.label }}</label>
              <textarea v-model="buffer[f.key]" class="d-textarea" rows="2"></textarea>
            </div>
            <div class="d-edit-actions">
              <button class="d-save-btn" :disabled="saving" @click="saveProtagonist">{{ saving ? '保存中…' : '保存' }}</button>
            </div>
          </template>
          <dl v-else class="d-kv">
            <template v-for="f in PROTAGONIST_FIELDS" :key="f.key">
              <div v-if="protagonistValue(f.key)" class="d-kv-row">
                <dt>{{ f.label }}</dt>
                <dd>{{ protagonistValue(f.key) }}</dd>
              </div>
            </template>
          </dl>
        </section>

        <!-- 冲突与矛盾发动机 -->
        <section class="d-block">
          <div class="d-block-head">
            <span class="d-block-tag">核心冲突与矛盾发动机</span>
            <button class="d-edit-btn" @click="startEdit('conflict')">{{ editing === 'conflict' ? '取消' : '编辑' }}</button>
          </div>
          <template v-if="editing === 'conflict'">
            <div class="d-field-edit"><label>核心冲突</label><textarea v-model="buffer.core_conflict" class="d-textarea" rows="2"></textarea></div>
            <div class="d-field-edit"><label>矛盾发动机（冲突为什么打不完）</label><textarea v-model="buffer.conflict_engine" class="d-textarea" rows="3"></textarea></div>
            <div class="d-edit-actions">
              <button class="d-save-btn" :disabled="saving" @click="saveEdit({ core_conflict: buffer.core_conflict, conflict_engine: buffer.conflict_engine })">{{ saving ? '保存中…' : '保存' }}</button>
            </div>
          </template>
          <dl v-else class="d-kv">
            <div v-if="dossier.core_conflict" class="d-kv-row"><dt>核心冲突</dt><dd>{{ dossier.core_conflict }}</dd></div>
            <div v-if="dossier.conflict_engine" class="d-kv-row"><dt>矛盾发动机</dt><dd>{{ dossier.conflict_engine }}</dd></div>
          </dl>
        </section>

        <!-- 金手指 -->
        <section v-if="hasGoldenFinger || editing === 'golden'" class="d-block">
          <div class="d-block-head">
            <span class="d-block-tag">金手指</span>
            <button class="d-edit-btn" @click="startEdit('golden')">{{ editing === 'golden' ? '取消' : '编辑' }}</button>
          </div>
          <template v-if="editing === 'golden'">
            <div v-for="f in GOLDEN_FIELDS" :key="f.key" class="d-field-edit">
              <label>{{ f.label }}</label>
              <textarea v-model="buffer[f.key]" class="d-textarea" rows="2"></textarea>
            </div>
            <div class="d-edit-actions">
              <button class="d-save-btn" :disabled="saving" @click="saveGolden">{{ saving ? '保存中…' : '保存' }}</button>
            </div>
          </template>
          <dl v-else class="d-kv">
            <template v-for="f in GOLDEN_FIELDS" :key="f.key">
              <div v-if="goldenValue(f.key)" class="d-kv-row">
                <dt>{{ f.label }}</dt>
                <dd>{{ goldenValue(f.key) }}</dd>
              </div>
            </template>
          </dl>
        </section>

        <!-- 期待感承诺 -->
        <section class="d-block">
          <div class="d-block-head">
            <span class="d-block-tag">期待感承诺</span>
            <button class="d-edit-btn" @click="startEdit('anticipation')">{{ editing === 'anticipation' ? '取消' : '编辑' }}</button>
          </div>
          <template v-if="editing === 'anticipation'">
            <div v-for="f in ANTICIPATION_FIELDS" :key="f.key" class="d-field-edit">
              <label>{{ f.label }}</label>
              <textarea v-model="buffer[f.key]" class="d-textarea" rows="2"></textarea>
            </div>
            <div class="d-edit-actions">
              <button class="d-save-btn" :disabled="saving" @click="saveAnticipation">{{ saving ? '保存中…' : '保存' }}</button>
            </div>
          </template>
          <dl v-else class="d-kv">
            <template v-for="f in ANTICIPATION_FIELDS" :key="f.key">
              <div v-if="anticipationValue(f.key)" class="d-kv-row">
                <dt>{{ f.label }}</dt>
                <dd>{{ anticipationValue(f.key) }}</dd>
              </div>
            </template>
          </dl>
        </section>

        <!-- 爽点链 -->
        <section v-if="(dossier.coolpoint_chain || []).length || editing === 'coolpoints'" class="d-block">
          <div class="d-block-head">
            <span class="d-block-tag">爽点链</span>
            <button class="d-edit-btn" @click="startEdit('coolpoints')">{{ editing === 'coolpoints' ? '取消' : '编辑' }}</button>
          </div>
          <template v-if="editing === 'coolpoints'">
            <p class="d-edit-hint">一行一个爽点</p>
            <textarea v-model="buffer.coolpoint_chain" class="d-textarea" rows="6"></textarea>
            <div class="d-edit-actions">
              <button class="d-save-btn" :disabled="saving" @click="saveCoolpoints">{{ saving ? '保存中…' : '保存' }}</button>
            </div>
          </template>
          <ol v-else class="d-coolpoints">
            <li v-for="(cp, i) in dossier.coolpoint_chain" :key="i">{{ cp }}</li>
          </ol>
        </section>

        <!-- 书名候选 -->
        <section v-if="(dossier.title_candidates || []).length" class="d-block">
          <div class="d-block-head"><span class="d-block-tag">书名候选</span></div>
          <div class="d-meta-row">
            <span v-for="(t, i) in dossier.title_candidates" :key="i" class="d-chip d-chip-title">{{ t }}</span>
          </div>
        </section>

        <!-- ═══ 压力推演报告 ═══ -->
        <section v-if="stressReport" class="d-block d-block-stress">
          <div class="d-block-head">
            <span class="d-block-tag d-tag-stress">压力推演报告</span>
            <span class="d-verdict" :class="verdictClass(stressReport.overall_verdict)">{{ stressReport.overall_verdict || '已推演' }}</span>
          </div>
          <p v-if="stressReport.summary" class="d-stress-summary">{{ stressReport.summary }}</p>

          <div v-if="stressReport.conflict_sustainability" class="d-stress-sub">
            <p class="d-stress-sub-title">
              冲突可持续性
              <span class="d-verdict-mini" :class="verdictClass(stressReport.conflict_sustainability.verdict)">{{ stressReport.conflict_sustainability.verdict }}</span>
            </p>
            <ul class="d-stress-list">
              <li v-if="stressReport.conflict_sustainability.at_50"><b>第 50 章</b>{{ stressReport.conflict_sustainability.at_50 }}</li>
              <li v-if="stressReport.conflict_sustainability.at_100"><b>第 100 章</b>{{ stressReport.conflict_sustainability.at_100 }}</li>
              <li v-if="stressReport.conflict_sustainability.at_300"><b>第 300 章</b>{{ stressReport.conflict_sustainability.at_300 }}</li>
            </ul>
          </div>

          <div v-if="stressReport.golden_finger_collapse?.verdict" class="d-stress-sub">
            <p class="d-stress-sub-title">
              金手指崩坏推演
              <span class="d-verdict-mini" :class="verdictClass(stressReport.golden_finger_collapse.verdict)">{{ stressReport.golden_finger_collapse.verdict }}</span>
            </p>
            <p class="d-stress-text">
              <template v-if="(stressReport.golden_finger_collapse.stall_chapter || 0) > 0">预测失速章：第 {{ stressReport.golden_finger_collapse.stall_chapter }} 章。</template>
              {{ stressReport.golden_finger_collapse.stall_reason || stressReport.golden_finger_collapse.analysis }}
            </p>
          </div>

          <div v-if="(stressReport.toxic_points || []).length" class="d-stress-sub">
            <p class="d-stress-sub-title">毒点扫描（{{ stressReport.toxic_points!.length }} 项）</p>
            <div v-for="(tp, i) in stressReport.toxic_points" :key="i" class="d-toxic" :class="severityClass(tp.severity)">
              <div class="d-toxic-head">
                <span class="d-toxic-severity">{{ tp.severity || '低危' }}</span>
                <span class="d-toxic-issue">{{ tp.issue }}</span>
              </div>
              <p v-if="tp.reason" class="d-toxic-reason">{{ tp.reason }}</p>
              <p v-if="tp.fix_suggestion" class="d-toxic-fix">修复建议：{{ tp.fix_suggestion }}</p>
            </div>
          </div>
        </section>
      </div>

      <!-- ═══ 生成档位 ═══ -->
      <div class="depth-picker">
        <p class="depth-picker-label">生成方式</p>
        <div class="depth-options">
          <button
            type="button"
            class="depth-opt"
            :class="{
              'depth-opt-active': selectedDepth === 'deep' && deepAvailable,
              'depth-opt-locked': !deepAvailable
            }"
            @click="chooseDepth('deep')"
          >
            <span class="depth-opt-title">
              深度打磨
              <span v-if="deepAvailable" class="depth-rec">推荐</span>
              <span v-if="deepCreditPrice > 0" class="depth-price">{{ deepCreditPrice }} 积分</span>
              <span v-if="!deepAvailable" class="lock-hint">
                <svg class="lock-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <rect x="5" y="11" width="14" height="9" rx="2"/>
                  <path stroke-linecap="round" d="M8 11V8a4 4 0 118 0v3"/>
                </svg>
                创作者档
              </span>
            </span>
            <span class="depth-opt-desc">总编审稿 + 不达标定向修订，约 5-8 分钟</span>
          </button>
          <button
            type="button"
            class="depth-opt"
            :class="{ 'depth-opt-active': selectedDepth === 'fast' }"
            @click="chooseDepth('fast')"
          >
            <span class="depth-opt-title">
              快速成纲
              <span class="depth-price depth-price-free">免费</span>
            </span>
            <span class="depth-opt-desc">跳过深度审稿，先出结构蓝图，约 2-3 分钟</span>
          </button>
        </div>
        <p v-if="deepCreditShort" class="depth-credit-warn">
          当前积分不足（需 {{ deepCreditPrice }}，剩余 {{ creditTotal ?? 0 }}）。可购买加油包或改选快速成纲。
        </p>
      </div>

      <!-- ═══ 三动作 ═══ -->
      <div class="dossier-actions">
        <button class="act-btn act-secondary" @click="$emit('back')">返回对话</button>
        <button
          v-if="hasFixSuggestions"
          class="act-btn act-fix"
          :disabled="applyingFixes"
          @click="applyFixes"
        >
          {{ applyingFixes ? '修订中…' : '采纳修复建议' }}
        </button>
        <button class="act-btn act-primary" :disabled="isGenerating" @click="generateBlueprint">
          锁定设定并生成蓝图
        </button>
      </div>
    </template>

    <UpgradePrompt
      :show="showUpgrade"
      :kind="upgradeKind"
      :message="upgradeMessage"
      @close="showUpgrade = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useNovelStore } from '@/stores/novel'
import { globalAlert } from '@/composables/useAlert'
import { humanizeGenerationError } from '@/utils/errorHumanize'
import { detectUpgradeHint, type UpgradeHintKind } from '@/utils/upgradeHint'
import UpgradePrompt from '@/components/UpgradePrompt.vue'
import { ModelCatalogAPI } from '@/api/model_catalog'
import {
  NovelAPI,
  type BlueprintDepth,
  type ConceptDossier,
  type DossierResponse,
  type StressReport
} from '@/api/novel'

interface Props {
  aiMessage: string
  projectId: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  blueprintGenerated: [response: any]
  back: []
}>()

const novelStore = useNovelStore()

// ── 立项书状态 ──
const dossierResp = ref<DossierResponse | null>(null)
const dossierLoading = ref(false)
const dossierElapsed = ref(0)
const dossier = computed<ConceptDossier | null>(() => dossierResp.value?.dossier ?? null)
const stressReport = computed<StressReport | null>(() => dossierResp.value?.stress_report ?? null)
const deepAvailable = computed(() => !!dossierResp.value?.deep_available)
const deepCreditPrice = computed(() => Math.max(0, Number(dossierResp.value?.deep_credit_price || 0)))
const creditTotal = ref<number | null>(null)
const selectedDepth = ref<BlueprintDepth>('fast')
const showUpgrade = ref(false)
const upgradeKind = ref<UpgradeHintKind>('tier')
const upgradeMessage = ref(
  '深度打磨（总编审稿 + 定向修订）为创作者档能力。升级后开书蓝图会先过商业量表，不达标再定向改一轮。',
)
const deepWillBill = computed(
  () => deepAvailable.value && selectedDepth.value === 'deep' && deepCreditPrice.value > 0,
)
const deepCreditShort = computed(
  () =>
    deepWillBill.value &&
    creditTotal.value !== null &&
    creditTotal.value < deepCreditPrice.value,
)

const lastDepthKey = () => `arboris.blueprint_depth.${props.projectId}`

const restoreLastDepth = () => {
  let last: BlueprintDepth | null = null
  try {
    const raw = sessionStorage.getItem(lastDepthKey())
    if (raw === 'fast' || raw === 'deep') last = raw
  } catch {
    /* sessionStorage 不可用时忽略 */
  }
  if (!deepAvailable.value) {
    selectedDepth.value = 'fast'
    return
  }
  selectedDepth.value = last || 'deep'
}

const chooseDepth = (depth: BlueprintDepth) => {
  if (depth === 'deep' && !deepAvailable.value) {
    upgradeKind.value = 'tier'
    upgradeMessage.value =
      '深度打磨（总编审稿 + 定向修订）为创作者档能力。升级后开书蓝图会先过商业量表，不达标再定向改一轮。'
    showUpgrade.value = true
    return
  }
  selectedDepth.value = depth
}

watch(deepAvailable, restoreLastDepth)

const hasGoldenFinger = computed(() => !!(dossier.value?.golden_finger?.name || '').trim())
const hasFixSuggestions = computed(() =>
  (stressReport.value?.toxic_points || []).some((tp) => (tp.fix_suggestion || '').trim())
)

const PROTAGONIST_FIELDS = [
  { key: 'name', label: '主角' },
  { key: 'identity', label: '身份处境' },
  { key: 'desire', label: '欲望' },
  { key: 'flaw', label: '缺陷' },
  { key: 'predicament', label: '困境' },
  { key: 'charm_point', label: '代入点' }
] as const

const GOLDEN_FIELDS = [
  { key: 'name', label: '名称' },
  { key: 'source', label: '来源' },
  { key: 'mechanism', label: '机制' },
  { key: 'limitations', label: '限制与代价' },
  { key: 'growth_curve', label: '成长曲线' }
] as const

const ANTICIPATION_FIELDS = [
  { key: 'ten_chapters', label: '前 10 章' },
  { key: 'fifty_chapters', label: '前 50 章' },
  { key: 'long_term', label: '长线' }
] as const

const protagonistValue = (key: string) => (dossier.value?.protagonist as any)?.[key] || ''
const goldenValue = (key: string) => (dossier.value?.golden_finger as any)?.[key] || ''
const anticipationValue = (key: string) => (dossier.value?.anticipation as any)?.[key] || ''

// ── 加载阶段（真实计时，阶段为预估节奏）──
const DOSSIER_STAGES = ['整理对话共识', '提炼卖点与主角三件套', '构建矛盾发动机与爽点链', '压力推演与毒点扫描', '整理推演报告']
const DOSSIER_STAGE_AT = [0, 10, 22, 40, 70]
const dossierStageIndex = computed(() => {
  let idx = 0
  for (let i = 0; i < DOSSIER_STAGE_AT.length; i++) {
    if (dossierElapsed.value >= DOSSIER_STAGE_AT[i]) idx = i
  }
  return idx
})
const dossierStageText = computed(() => `${DOSSIER_STAGES[dossierStageIndex.value]}…`)

// ── 蓝图生成阶段（按档位区分假进度文案）──
const GEN_STAGES_DEEP = [
  '生成世界观与角色设定',
  '规划分卷与伏笔',
  '分批生成章纲与章级规划',
  '商业量表审稿',
  '定向修订与复审',
  '落库与宪法播种'
]
const GEN_STAGES_FAST = [
  '生成世界观与角色设定',
  '规划分卷与伏笔',
  '分批生成章纲',
  '落库与宪法播种'
]
const GEN_STAGE_AT_DEEP = [0, 30, 60, 150, 210, 280]
const GEN_STAGE_AT_FAST = [0, 25, 50, 120]
const genStages = computed(() => (selectedDepth.value === 'deep' ? GEN_STAGES_DEEP : GEN_STAGES_FAST))
const genStageAt = computed(() => (selectedDepth.value === 'deep' ? GEN_STAGE_AT_DEEP : GEN_STAGE_AT_FAST))
const genEtaHint = computed(() =>
  selectedDepth.value === 'deep'
    ? '深度打磨含总编审稿与定向修订，约 5-8 分钟'
    : '快速成纲跳过审稿打磨，约 2-3 分钟'
)
const isGenerating = ref(false)
const genDone = ref(false)
const genElapsed = ref(0)
const genStageIndex = computed(() => {
  if (genDone.value) return genStages.value.length
  let idx = 0
  for (let i = 0; i < genStageAt.value.length; i++) {
    if (genElapsed.value >= genStageAt.value[i]) idx = i
  }
  return idx
})
const genStageText = computed(() => {
  if (genDone.value) return '生成完成！正在准备展示…'
  const lastAt = genStageAt.value[genStageAt.value.length - 1]
  if (genStageIndex.value >= genStages.value.length - 1 && genElapsed.value > lastAt + 60) {
    return selectedDepth.value === 'deep'
      ? 'AI 正在深度打磨蓝图，复杂设定需要更多时间…'
      : '章纲还在收尾，请再稍候…'
  }
  return `${genStages.value[Math.min(genStageIndex.value, genStages.value.length - 1)]}…`
})
const genProgress = computed(() => {
  if (genDone.value) return 100
  return Math.min(92, ((genStageIndex.value + 1) / genStages.value.length) * 92)
})

let dossierTimer: ReturnType<typeof setInterval> | null = null
let genTimer: ReturnType<typeof setInterval> | null = null

const elapsedLabel = (seconds: number) => {
  const s = Math.floor(seconds)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

// ── 立项书拉取 ──
const loadDossier = async () => {
  dossierLoading.value = true
  dossierElapsed.value = 0
  const start = Date.now()
  dossierTimer = setInterval(() => {
    dossierElapsed.value = (Date.now() - start) / 1000
  }, 250)
  try {
    const [dossier, available] = await Promise.all([
      NovelAPI.getConceptDossier(props.projectId),
      ModelCatalogAPI.getAvailable().catch(() => null),
    ])
    dossierResp.value = dossier
    if (available?.credit) {
      creditTotal.value =
        available.credit.total ??
        (available.credit.balance ?? 0) + (available.credit.purchased ?? 0)
    }
    restoreLastDepth()
  } catch (error) {
    console.error('拉取立项书失败:', error)
    dossierResp.value = null
  } finally {
    if (dossierTimer) {
      clearInterval(dossierTimer)
      dossierTimer = null
    }
    dossierLoading.value = false
  }
}

// ── 分块编辑 ──
const editing = ref<string | null>(null)
const saving = ref(false)
const buffer = ref<Record<string, string>>({})

const startEdit = (block: string) => {
  if (editing.value === block) {
    editing.value = null
    return
  }
  const d = dossier.value || {}
  const next: Record<string, string> = {}
  if (block === 'selling') next.core_selling_line = d.core_selling_line || ''
  if (block === 'protagonist') PROTAGONIST_FIELDS.forEach((f) => (next[f.key] = protagonistValue(f.key)))
  if (block === 'conflict') {
    next.core_conflict = d.core_conflict || ''
    next.conflict_engine = d.conflict_engine || ''
  }
  if (block === 'golden') GOLDEN_FIELDS.forEach((f) => (next[f.key] = goldenValue(f.key)))
  if (block === 'anticipation') ANTICIPATION_FIELDS.forEach((f) => (next[f.key] = anticipationValue(f.key)))
  if (block === 'coolpoints') next.coolpoint_chain = (d.coolpoint_chain || []).join('\n')
  buffer.value = next
  editing.value = block
}

const saveEdit = async (partial: Record<string, any>) => {
  saving.value = true
  try {
    const resp = await NovelAPI.patchConceptDossier(props.projectId, partial)
    if (dossierResp.value) dossierResp.value.dossier = resp.dossier
    editing.value = null
  } catch (error) {
    globalAlert.showError(`保存失败: ${error instanceof Error ? error.message : '请稍后重试'}`, '立项书')
  } finally {
    saving.value = false
  }
}

const saveProtagonist = () =>
  saveEdit({ protagonist: Object.fromEntries(PROTAGONIST_FIELDS.map((f) => [f.key, buffer.value[f.key] || ''])) })
const saveGolden = () =>
  saveEdit({ golden_finger: Object.fromEntries(GOLDEN_FIELDS.map((f) => [f.key, buffer.value[f.key] || ''])) })
const saveAnticipation = () =>
  saveEdit({ anticipation: Object.fromEntries(ANTICIPATION_FIELDS.map((f) => [f.key, buffer.value[f.key] || ''])) })
const saveCoolpoints = () =>
  saveEdit({
    coolpoint_chain: (buffer.value.coolpoint_chain || '')
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean)
  })

// ── 采纳修复建议 ──
const applyingFixes = ref(false)
const applyFixes = async () => {
  applyingFixes.value = true
  try {
    const resp = await NovelAPI.applyDossierFixes(props.projectId)
    if (dossierResp.value) {
      dossierResp.value.dossier = resp.dossier
      dossierResp.value.stress_report = resp.stress_report
    }
    globalAlert.showSuccess('修复建议已应用到立项书，可再次检查后生成蓝图。', '立项书已修订')
  } catch (error) {
    globalAlert.showError(
      `采纳修复失败: ${error instanceof Error ? error.message : '请稍后重试'}`,
      '立项书'
    )
  } finally {
    applyingFixes.value = false
  }
}

// ── 生成蓝图（沿用 store 的异步任务优先链路）──
const generateBlueprint = async () => {
  isGenerating.value = true
  genDone.value = false
  genElapsed.value = 0
  const start = Date.now()
  genTimer = setInterval(() => {
    genElapsed.value = (Date.now() - start) / 1000
  }, 250)
  try {
    const depth: BlueprintDepth = deepAvailable.value ? selectedDepth.value : 'fast'
    try {
      sessionStorage.setItem(lastDepthKey(), depth)
    } catch {
      /* ignore */
    }
    const response = await novelStore.generateBlueprint(depth)
    if (genTimer) {
      clearInterval(genTimer)
      genTimer = null
    }
    genDone.value = true
    await new Promise((resolve) => setTimeout(resolve, 800))
    isGenerating.value = false
    genDone.value = false
    emit('blueprintGenerated', response)
  } catch (error) {
    console.error('生成蓝图失败:', error)
    if (genTimer) {
      clearInterval(genTimer)
      genTimer = null
    }
    isGenerating.value = false
    genDone.value = false
    const errMessage = error instanceof Error ? error.message : '未知错误'
    const hint = detectUpgradeHint(errMessage)
    if (hint) {
      upgradeKind.value = hint
      upgradeMessage.value = errMessage
      showUpgrade.value = true
      return
    }
    // 402 从未开跑，不提退款；已扣费的深度打磨失败才说「积分已退回」
    const human = humanizeGenerationError(errMessage, { billed: deepWillBill.value })
    globalAlert.showError(human.message, human.title)
  }
}

// ── 判定/毒点配色 ──
const verdictClass = (verdict?: string) => {
  const v = verdict || ''
  if (/(供血不足|必然崩坏|高危|重构)/.test(v)) return 'v-bad'
  if (/(勉强|隐患|修订)/.test(v)) return 'v-warn'
  if (/(充足|健康|可开工)/.test(v)) return 'v-good'
  return 'v-neutral'
}
const severityClass = (severity?: string) => {
  const s = severity || ''
  if (s.includes('高')) return 'toxic-high'
  if (s.includes('中')) return 'toxic-mid'
  return 'toxic-low'
}

onMounted(loadDossier)
onUnmounted(() => {
  if (dossierTimer) clearInterval(dossierTimer)
  if (genTimer) clearInterval(genTimer)
})
</script>

<style scoped>
.dossier-shell {
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 16px;
  padding: 28px;
  color: #e5e5e5;
  animation: dossierFadeIn 0.5s ease-out;
}
@keyframes dossierFadeIn {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

.dossier-head { text-align: center; margin-bottom: 22px; }
.dossier-title { font-size: 22px; font-weight: 700; color: #fff; }
.dossier-sub { margin-top: 8px; font-size: 13px; color: #888; line-height: 1.6; }

/* ── 加载 ── */
.dossier-loading { text-align: center; padding: 36px 0; }
.loading-ring-wrap { position: relative; width: 64px; height: 64px; margin: 0 auto 18px; }
.loading-ring {
  position: absolute; inset: 0; border-radius: 50%;
  border: 3px solid #2a2a2a; border-top-color: #ffe500;
  animation: spin 1s linear infinite;
}
.loading-ring.ring-done { border-color: #4ade80; animation: none; }
.loading-core {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  color: #ffe500; font-size: 20px;
}
@keyframes spin { to { transform: rotate(360deg); } }
.loading-title { font-size: 16px; font-weight: 600; color: #fff; }
.loading-sub { margin-top: 6px; font-size: 12px; color: #888; }
.loading-stages { max-width: 320px; margin: 18px auto 0; text-align: left; display: flex; flex-direction: column; gap: 8px; }
.loading-stages li { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.st-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.st-done { color: #aaa; }
.st-done .st-dot { background: #4ade80; }
.st-active { color: #ffe500; font-weight: 500; }
.st-active .st-dot { background: #ffe500; animation: pulse 1.2s ease-in-out infinite; }
.st-wait { color: #555; }
.st-wait .st-dot { background: #333; }
@keyframes pulse { 50% { opacity: 0.35; } }
.loading-bar { max-width: 320px; height: 4px; margin: 18px auto 0; background: #2a2a2a; border-radius: 2px; overflow: hidden; }
.loading-bar-fill { height: 100%; background: linear-gradient(90deg, #ffe500, #ffb800); border-radius: 2px; transition: width 0.7s ease-out; }
.loading-hint { margin-top: 14px; font-size: 12px; color: #666; }

/* ── 降级 ── */
.dossier-absent { text-align: center; padding: 20px 0 8px; }
.absent-title { font-size: 15px; font-weight: 600; color: #fff; }
.absent-sub { margin-top: 10px; font-size: 13px; color: #aaa; line-height: 1.7; white-space: pre-wrap; }
.absent-hint { margin-top: 10px; font-size: 12px; color: #666; }

/* ── 分块 ── */
.dossier-body { display: flex; flex-direction: column; gap: 14px; }
.d-block { background: #1c1c1c; border: 1px solid #2a2a2a; border-radius: 12px; padding: 16px 18px; }
.d-block-hero { border-color: rgba(255, 229, 0, 0.25); }
.d-block-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.d-block-tag { font-size: 12px; font-weight: 600; color: #ffe500; letter-spacing: 0.05em; }
.d-tag-stress { color: #ff9f43; }
.d-edit-btn {
  font-size: 12px; color: #888; background: none; border: 1px solid #333;
  border-radius: 6px; padding: 2px 10px; cursor: pointer; transition: all 0.2s;
}
.d-edit-btn:hover { color: #ffe500; border-color: #ffe500; }
.d-hero-text { font-size: 15px; line-height: 1.7; color: #fff; }
.d-meta-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.d-chip {
  font-size: 12px; color: #ccc; background: #2a2a2a; border-radius: 999px; padding: 3px 12px;
}
.d-chip-title { color: #ffe500; background: rgba(255, 229, 0, 0.08); }
.d-kv { display: flex; flex-direction: column; gap: 8px; }
.d-kv-row { display: flex; gap: 12px; font-size: 13px; line-height: 1.65; }
.d-kv-row dt { flex-shrink: 0; width: 76px; color: #888; }
.d-kv-row dd { color: #ddd; }
.d-coolpoints { list-style: none; counter-reset: cp; display: flex; flex-direction: column; gap: 8px; }
.d-coolpoints li {
  counter-increment: cp; font-size: 13px; color: #ddd; line-height: 1.6;
  padding-left: 30px; position: relative;
}
.d-coolpoints li::before {
  content: counter(cp); position: absolute; left: 0; top: 1px;
  width: 20px; height: 20px; border-radius: 6px; background: rgba(255, 229, 0, 0.1);
  color: #ffe500; font-size: 11px; display: flex; align-items: center; justify-content: center;
}

/* ── 编辑态 ── */
.d-textarea {
  width: 100%; background: #0a0a0a; border: 1px solid #333; border-radius: 8px;
  color: #e5e5e5; font-size: 13px; line-height: 1.6; padding: 10px 12px; resize: vertical;
}
.d-textarea:focus { outline: none; border-color: #ffe500; }
.d-field-edit { margin-bottom: 10px; }
.d-field-edit label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
.d-edit-hint { font-size: 12px; color: #666; margin-bottom: 6px; }
.d-edit-actions { margin-top: 10px; text-align: right; }
.d-save-btn {
  font-size: 13px; font-weight: 600; color: #0a0a0a; background: #ffe500;
  border: none; border-radius: 8px; padding: 6px 18px; cursor: pointer;
}
.d-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── 推演报告 ── */
.d-block-stress { border-color: rgba(255, 159, 67, 0.3); }
.d-verdict { font-size: 12px; font-weight: 600; border-radius: 999px; padding: 3px 12px; }
.d-verdict-mini { font-size: 11px; font-weight: 600; border-radius: 999px; padding: 1px 8px; margin-left: 8px; }
.v-good { color: #4ade80; background: rgba(74, 222, 128, 0.1); }
.v-warn { color: #ffb800; background: rgba(255, 184, 0, 0.1); }
.v-bad { color: #ff6b6b; background: rgba(255, 107, 107, 0.12); }
.v-neutral { color: #aaa; background: #2a2a2a; }
.d-stress-summary { font-size: 13px; color: #ccc; line-height: 1.7; margin-bottom: 12px; }
.d-stress-sub { margin-top: 12px; padding-top: 12px; border-top: 1px dashed #2a2a2a; }
.d-stress-sub-title { font-size: 13px; font-weight: 600; color: #eee; margin-bottom: 8px; }
.d-stress-list { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #bbb; line-height: 1.6; }
.d-stress-list b { color: #ffe500; font-weight: 600; margin-right: 8px; }
.d-stress-text { font-size: 13px; color: #bbb; line-height: 1.6; }
.d-toxic { border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; border: 1px solid; }
.toxic-high { border-color: rgba(255, 107, 107, 0.4); background: rgba(255, 107, 107, 0.06); }
.toxic-mid { border-color: rgba(255, 184, 0, 0.35); background: rgba(255, 184, 0, 0.05); }
.toxic-low { border-color: #2a2a2a; background: #181818; }
.d-toxic-head { display: flex; align-items: center; gap: 10px; }
.d-toxic-severity { font-size: 11px; font-weight: 700; border-radius: 4px; padding: 1px 7px; flex-shrink: 0; }
.toxic-high .d-toxic-severity { color: #ff6b6b; background: rgba(255, 107, 107, 0.15); }
.toxic-mid .d-toxic-severity { color: #ffb800; background: rgba(255, 184, 0, 0.12); }
.toxic-low .d-toxic-severity { color: #888; background: #2a2a2a; }
.d-toxic-issue { font-size: 13px; font-weight: 600; color: #eee; }
.d-toxic-reason { margin-top: 6px; font-size: 12px; color: #999; line-height: 1.6; }
.d-toxic-fix { margin-top: 4px; font-size: 12px; color: #7dd3a8; line-height: 1.6; }

/* ── 动作 ── */
.dossier-actions {
  display: flex; justify-content: center; gap: 12px; margin-top: 22px; flex-wrap: wrap;
}
.act-btn {
  font-size: 14px; font-weight: 600; border-radius: 999px; padding: 10px 28px;
  cursor: pointer; border: none; transition: all 0.25s;
}
.act-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.act-secondary { color: #ccc; background: #2a2a2a; }
.act-secondary:hover { background: #333; }
.act-fix { color: #ffb800; background: rgba(255, 184, 0, 0.1); border: 1px solid rgba(255, 184, 0, 0.35); }
.act-fix:hover:not(:disabled) { background: rgba(255, 184, 0, 0.18); }
.act-primary { color: #0a0a0a; background: linear-gradient(135deg, #ffe500, #ffb800); }
.act-primary:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(255, 229, 0, 0.25); }

/* ── 档位选择 ── */
.depth-picker { margin-top: 22px; }
.depth-picker-label { font-size: 12px; font-weight: 600; color: #888; letter-spacing: 0.06em; margin-bottom: 10px; text-align: center; }
.depth-options { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.depth-opt {
  text-align: left; background: #1c1c1c; border: 1px solid #2a2a2a; border-radius: 12px;
  padding: 14px 16px; cursor: pointer; transition: all 0.2s; color: inherit;
}
.depth-opt:hover { border-color: #444; }
.depth-opt-active { border-color: #ffe500; background: rgba(255, 229, 0, 0.06); }
.depth-opt-locked { opacity: 0.72; }
.depth-opt-title { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; color: #fff; }
.depth-opt-desc { display: block; margin-top: 6px; font-size: 12px; color: #888; line-height: 1.55; }
.depth-rec {
  font-size: 10px; font-weight: 700; color: #0a0a0a; background: #ffe500;
  border-radius: 999px; padding: 1px 7px;
}
.depth-price {
  font-size: 11px; font-weight: 600; color: #ffe500;
  background: rgba(255, 229, 0, 0.1); border-radius: 999px; padding: 1px 8px;
}
.depth-price-free { color: #4ade80; background: rgba(74, 222, 128, 0.1); }
.depth-credit-warn {
  margin-top: 10px; text-align: center; font-size: 12px; color: #ffb800; line-height: 1.55;
}
.lock-hint { font-size: 11px; opacity: 0.75; display: inline-flex; align-items: center; gap: 3px; color: #9aa0a6; }
.lock-ico { width: 10px; height: 10px; flex-shrink: 0; }
@media (max-width: 560px) {
  .depth-options { grid-template-columns: 1fr; }
}
</style>

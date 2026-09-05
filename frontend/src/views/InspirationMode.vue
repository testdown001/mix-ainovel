<!-- AIMETA P=灵感模式_AI对话创作|R=对话创作界面|NR=不含写作台功能|E=route:/inspiration#component:InspirationMode|X=ui|A=对话界面|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="inspiration-shell">
    <header class="studio-header">
      <div class="studio-brand">
        <button type="button" class="icon-button back-button" aria-label="返回首页" @click="goBack">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9">
            <path d="m15 18-6-6 6-6" />
          </svg>
        </button>
        <span class="brand-mark">✦</span>
        <div class="brand-copy">
          <h1>灵感工坊</h1>
          <p>从一个念头，长成一本小说</p>
        </div>
      </div>

      <div class="header-actions">
        <span class="save-state">
          <i></i>
          {{ conversationStarted ? '第 ' + currentTurn + ' 轮已保存' : '灵感草稿自动保存' }}
        </span>
        <button v-if="conversationStarted" type="button" class="header-button" @click="handleRestart">
          重新开始
        </button>
        <button type="button" class="icon-button" :aria-label="conversationStarted ? '退出灵感模式' : '返回首页'" @click="conversationStarted ? exitConversation() : goBack()">
          <svg v-if="conversationStarted" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9">
            <path d="M9 18 3 12l6-6M3 12h13M15 5h4a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-4" />
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9">
            <path d="M5 12h14m-5-5 5 5-5 5" />
          </svg>
        </button>
      </div>
    </header>

    <nav class="studio-flow" aria-label="灵感创作进度">
      <div v-for="step in workflowSteps" :key="step.id" class="flow-step" :class="{ active: workflowStage === step.id, done: workflowStage > step.id }">
        <strong>{{ String(step.id).padStart(2, '0') }}</strong>
        <span>{{ step.label }}</span>
      </div>
    </nav>

    <div class="studio-workspace">
      <aside class="studio-panel material-rail">
        <header class="rail-heading">
          <p>INSPIRATION KIT</p>
          <h2>{{ conversationStarted ? '本次灵感' : '灵感素材' }}</h2>
        </header>

        <template v-if="!conversationStarted">
          <section class="rail-section reference-section">
            <div class="section-title">
              <div><h3>参考小说</h3><span>可选，最多 3 本</span></div>
            </div>
            <ReferenceNovelInput
              v-model="referenceNovels"
              :search-status="referenceSearchStatus"
              :status-message="referenceSearchMessage"
              @library-selection-change="handleLibrarySelectionChange"
            />
            <p v-if="librarySelectionsWithNames.length" class="selection-note">
              已选：{{ librarySelectionsWithNames.join(' / ') }}
            </p>
            <div v-if="boundReferenceNovels.length" class="bound-list">
              <span v-for="novel in boundReferenceNovels" :key="novel.id">
                <b>{{ novel.title }}</b><small>{{ novel.status }}</small>
              </span>
            </div>
          </section>

          <section class="rail-section boundary-section">
            <button type="button" class="section-toggle" @click="showExclusions = !showExclusions">
              <span><i class="section-dot boundary-dot"></i>创作禁区</span>
              <svg :class="{ open: showExclusions }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9">
                <path d="m9 18 6-6-6-6" />
              </svg>
            </button>
            <transition name="rail-fold">
              <div v-if="showExclusions" class="boundary-editor">
                <textarea v-model="exclusions" rows="4" placeholder="例如：不要后宫、不要提前揭示核心谜底……"></textarea>
                <p>会贯穿灵感对话、蓝图与正文创作。</p>
              </div>
            </transition>
          </section>

          <section class="rail-section muse-section">
            <div class="section-title">
              <div><h3>缪斯人格</h3><span>决定 AI 的提问方式</span></div>
              <span class="tier-badge" :class="'tier-' + userTier">
                {{ userTier === 'flagship' ? '旗舰' : userTier === 'creator' ? '创作者' : '免费' }}
              </span>
            </div>
            <div class="muse-list">
              <button
                v-for="persona in musePersonas"
                :key="persona.key"
                type="button"
                class="muse-card"
                :class="{ selected: selectedPersona === persona.key, locked: !canUsePersona && persona.key !== 'default' }"
                :disabled="!canUsePersona && persona.key !== 'default'"
                @click="selectedPersona = persona.key"
              >
                <span class="muse-avatar">{{ persona.label.slice(0, 1) }}</span>
                <span class="muse-copy"><strong>{{ persona.label }}</strong><small>{{ persona.blurb || '灵感发散与故事提炼' }}</small></span>
                <svg v-if="!canUsePersona && persona.key !== 'default'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" />
                </svg>
              </button>
            </div>
            <div class="muse-switches">
              <label :class="{ disabled: !canUseMuseSearch }">
                <input type="checkbox" :checked="canUseMuseSearch && !disableMuseSearch" :disabled="!canUseMuseSearch" @change="disableMuseSearch = !($event.target as HTMLInputElement).checked" />
                <span><strong>跨界找素材</strong><small>{{ canUseMuseSearch ? '开场联网寻找陌生素材' : '创作者档可用' }}</small></span>
              </label>
              <label>
                <input type="checkbox" :checked="!disableSpark" @change="disableSpark = !($event.target as HTMLInputElement).checked" />
                <span><strong>灵感扰动</strong><small>每轮随机激发新联想</small></span>
              </label>
            </div>
          </section>
        </template>

        <template v-else>
          <section class="rail-section">
            <div class="conversation-state">
              <span class="state-pulse"><i></i></span>
              <div><strong>{{ conversationStatus }}</strong><small>第 {{ currentTurn }} 轮对话</small></div>
            </div>
            <div class="turn-progress" role="progressbar" aria-label="蓝图解锁进度" :aria-valuenow="Math.min(currentTurn, 3)" aria-valuemin="0" aria-valuemax="3">
              <span :style="{ width: (Math.min(currentTurn / 3, 1) * 100) + '%' }"></span>
            </div>
            <p class="turn-hint">{{ nextActionLabel }}</p>
          </section>

          <section v-if="normalizedReferenceNovels.length" class="rail-section">
            <div class="section-title"><div><h3>参考小说</h3><span>{{ normalizedReferenceNovels.length }} 本已挂载</span></div></div>
            <div class="compact-chip-list"><span v-for="novel in normalizedReferenceNovels" :key="novel">▣ {{ novel }}</span></div>
          </section>

          <section v-if="exclusions.trim()" class="rail-section">
            <div class="section-title"><div><h3>创作禁区</h3><span>全流程生效</span></div></div>
            <p class="boundary-summary">{{ exclusions }}</p>
          </section>

          <section class="rail-section">
            <div class="section-title"><div><h3>当前缪斯</h3><span>{{ currentMuse?.blurb || '灵感搭档' }}</span></div></div>
            <div class="active-muse">
              <span class="muse-avatar">{{ currentMuse?.label?.slice(0, 1) || '文' }}</span>
              <div><strong>{{ currentMuse?.label || '文思' }}</strong><small>{{ museSearchEnabled ? '跨界素材已开启' : '专注当前对话' }}</small></div>
            </div>
          </section>

          <div class="rail-bottom-actions">
            <button type="button" @click="handleRestart">重新开始</button>
            <button type="button" @click="exitConversation">退出灵感模式</button>
          </div>
        </template>
      </aside>

      <main class="studio-panel idea-stage">
        <InspirationLoading
          v-if="!conversationStarted && isPreparingConversation"
          class="stage-loading"
          :title="preparingTitle"
          :phase-override="preparingPhase"
          :hint-override="preparingHint"
        />

        <template v-else-if="!conversationStarted">
          <section class="idea-hero">
            <span class="hero-mark">✦</span>
            <p class="hero-kicker">YOUR NEXT STORY STARTS HERE</p>
            <h2>今天，想写一个什么样的故事？</h2>
            <p>不用准备完整设定。一个画面、一句台词，甚至一种情绪都可以。文思会通过几轮追问，帮你找到最值得写的故事核心。</p>
          </section>

          <section class="starter-area">
            <div class="starter-grid">
              <button v-for="starter in ideaStarters" :key="starter.title" type="button" class="starter-card" :class="{ selected: initialIdea === starter.prompt }" @click="initialIdea = starter.prompt">
                <span class="starter-icon" v-html="starter.icon"></span>
                <strong>{{ starter.title }}</strong>
                <small>{{ starter.description }}</small>
              </button>
            </div>

            <div class="idea-composer">
              <textarea
                v-model="initialIdea"
                rows="4"
                placeholder="写下脑海中的一句话、一个人物或一幅画面……"
                @keydown.ctrl.enter.prevent="startConversation"
                @keydown.meta.enter.prevent="startConversation"
              ></textarea>
              <div class="composer-footer">
                <span>文思会先追问，不会急着替你定稿</span>
                <button type="button" :disabled="novelStore.isLoading || isPreparingConversation" @click="startConversation">
                  {{ startButtonText }}
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M5 12h14m-5-5 5 5-5 5" /></svg>
                </button>
              </div>
            </div>
          </section>
        </template>

        <template v-else>
          <header class="conversation-header">
            <div>
              <p>{{ showBlueprint ? 'BLUEPRINT READY' : showBlueprintConfirmation ? 'STORY LOCK' : 'IDEA EXPLORATION' }}</p>
              <h2>{{ showBlueprint ? '故事蓝图' : showBlueprintConfirmation ? '锁定你的故事' : '与文思继续探索' }}</h2>
            </div>
            <span>{{ currentTurn }}/3 轮</span>
          </header>

          <div class="chat-scroll" ref="chatArea">
            <transition name="fade">
              <InspirationLoading
                v-if="isInitialLoading"
                class="chat-loading"
                :hint-override="museSearchEnabled ? '已开启跨界找素材：文思会先联网寻找陌生素材再开场，通常需要多等 20-30 秒。' : ''"
              />
            </transition>

            <ChatBubble v-for="(message, index) in chatMessages" :key="index" :message="message.content" :type="message.type" />

            <div v-if="showBlueprintConfirmation" class="inline-blueprint-wrap">
              <BlueprintConfirmation
                :ai-message="confirmationMessage"
                :project-id="novelStore.currentProject?.id || ''"
                @blueprint-generated="handleBlueprintGenerated"
                @back="backToConversation"
              />
            </div>

            <div v-if="showBlueprint" class="inline-blueprint-wrap">
              <BlueprintDisplay
                :blueprint="completedBlueprint"
                :ai-message="blueprintMessage"
                @confirm="handleConfirmBlueprint"
                @regenerate="handleRegenerateBlueprint"
              />
            </div>
          </div>

          <section v-if="divergeSeeds.length" class="diverge-results">
            <div class="diverge-results-head">
              <div><strong>缪斯发散方向</strong><span>可以连续选择多个方向继续讨论</span></div>
              <button type="button" @click="dismissDivergeSeeds">清除本轮</button>
            </div>
            <div class="diverge-cards">
              <button v-for="seed in divergeSeeds" :key="seed.id" type="button" class="diverge-card" :class="{ picked: pickedSeedIds.includes(seed.id) }" @click="pickDivergeSeed(seed)">
                <div><strong>{{ seed.title || '未命名方向' }}</strong><span v-if="typeof seed.score === 'number'">{{ seed.score }}/{{ seed.score_max || 30 }}</span></div>
                <p>{{ seed.logline }}</p>
                <small v-if="seed.hook">钩子 · {{ seed.hook }}</small>
                <small v-if="seed.twist">转折 · {{ seed.twist }}</small>
                <small v-if="seed.emotional_hook">牵挂 · {{ seed.emotional_hook }}</small>
                <b v-if="pickedSeedIds.includes(seed.id)">已投喂</b>
              </button>
            </div>
          </section>

          <footer v-if="!showBlueprintConfirmation && !showBlueprint" class="conversation-footer">
            <button v-if="canUseDivergence" type="button" class="diverge-trigger" :disabled="isDiverging || novelStore.isLoading" @click="handleDiverge">
              {{ isDiverging ? '缪斯发散中…' : '✦ 给我 5 个狂点子' }}
            </button>
            <InlineProgress v-if="isDiverging" label="缪斯正在发散 5 个迥异方向并打分…" hint="需要两次模型调用，请勿离开页面。" />
            <ConversationInput v-else :ui-control="currentUIControl" :loading="novelStore.isLoading" @submit="handleUserInput" />
          </footer>
        </template>
      </main>

      <aside class="studio-panel idea-board">
        <header class="rail-heading">
          <p>IDEA BOARD</p>
          <h2>灵感看板</h2>
        </header>

        <section class="live-idea-card" :class="{ active: conversationStarted || initialIdea.trim() }">
          <div><span>当前灵感</span><b>{{ conversationStarted ? '正在生长' : initialIdea.trim() ? '等待开启' : '等待输入' }}</b></div>
          <h3>{{ currentIdeaTitle }}</h3>
          <p>{{ currentIdeaSummary }}</p>
        </section>

        <section class="board-section">
          <p>创作进度</p>
          <div class="board-progress-list">
            <div v-for="step in workflowSteps" :key="'board-' + step.id" :class="{ active: workflowStage === step.id, done: workflowStage > step.id }">
              <span>{{ String(step.id).padStart(2, '0') }}</span>
              <div><strong>{{ step.label }}</strong><small>{{ step.description }}</small></div>
            </div>
          </div>
        </section>

        <section class="board-section">
          <p>文思已捕捉</p>
          <div class="insight-list">
            <div>
              <span class="insight-icon">◎</span>
              <div><strong>故事种子</strong><small>{{ ideaSeedLabel }}</small></div>
            </div>
            <div>
              <span class="insight-icon">◈</span>
              <div><strong>参考基因</strong><small>{{ referenceInsight }}</small></div>
            </div>
            <div>
              <span class="insight-icon">◇</span>
              <div><strong>创作边界</strong><small>{{ boundaryInsight }}</small></div>
            </div>
          </div>
        </section>

        <section v-if="divergeSeeds.length" class="board-section">
          <p>候选方向</p>
          <div class="direction-list">
            <button v-for="seed in divergeSeeds.slice(0, 3)" :key="'board-seed-' + seed.id" type="button" @click="pickDivergeSeed(seed)">
              <span>{{ String(divergeSeeds.indexOf(seed) + 1).padStart(2, '0') }}</span>
              <div><strong>{{ seed.title || '未命名方向' }}</strong><small>{{ seed.logline }}</small></div>
            </button>
          </div>
        </section>

        <div class="board-next">
          <span>下一步</span>
          <p>{{ nextActionLabel }}</p>
        </div>
      </aside>
    </div>

    <UpgradePrompt :show="showUpgrade" :kind="upgradeKind" :message="upgradeMessage" @close="showUpgrade = false" />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { NovelAPI, type ReferenceNovelSummary, type UIControl, type Blueprint, type MusePersona, type DivergeSeed } from '@/api/novel'
import ChatBubble from '@/components/ChatBubble.vue'
import ConversationInput from '@/components/ConversationInput.vue'
import InlineProgress from '@/components/InlineProgress.vue'
import BlueprintConfirmation from '@/components/BlueprintConfirmation.vue'
import BlueprintDisplay from '@/components/BlueprintDisplay.vue'
import InspirationLoading from '@/components/InspirationLoading.vue'
import ReferenceNovelInput from '@/components/ReferenceNovelInput.vue'
import { globalAlert } from '@/composables/useAlert'
import { humanizeGenerationError } from '@/utils/errorHumanize'
import { detectUpgradeHint, type UpgradeHintKind } from '@/utils/upgradeHint'
import UpgradePrompt from '@/components/UpgradePrompt.vue'

interface ChatMessage {
  content: string
  type: 'user' | 'ai'
}

interface LibrarySelection {
  index: number
  id: number | null
  title: string
}

const router = useRouter()
const route = useRoute()
const novelStore = useNovelStore()

const conversationStarted = ref(false)
const isPreparingConversation = ref(false)
// 准备阶段细分：project=建项目（秒级）；reference=联网检索参考小说（首次 30-60s，
// 是「正在准备」里真正耗时的一步，必须让用户看到在干什么）
const preparingStage = ref<'idle' | 'project' | 'reference'>('idle')
const isInitialLoading = ref(false)
const showBlueprintConfirmation = ref(false)
const showBlueprint = ref(false)
const showUpgrade = ref(false)
const upgradeKind = ref<UpgradeHintKind>('credits')
const upgradeMessage = ref('')
const chatMessages = ref<ChatMessage[]>([])
const currentUIControl = ref<UIControl | null>(null)
const currentTurn = ref(0)
const completedBlueprint = ref<Blueprint | null>(null)
const confirmationMessage = ref('')
const blueprintMessage = ref('')
const chatArea = ref<HTMLElement>()
const referenceNovels = ref<string[]>([''])
const referenceContext = ref('')
const referenceSearchStatus = ref<'idle' | 'searching' | 'success' | 'error' | 'skipped'>('idle')
const referenceSearchMessage = ref('')
const exclusions = ref('')
const showExclusions = ref(false)
const initialIdea = ref('')

const workflowSteps = [
  { id: 1, label: '捕捉灵感', description: '写下第一句故事种子' },
  { id: 2, label: '探索方向', description: '通过追问寻找核心冲突' },
  { id: 3, label: '锁定故事', description: '确认题材、人物与情绪承诺' },
  { id: 4, label: '生成蓝图', description: '沉淀为可编辑立项蓝图' },
]

const ideaStarters = [
  {
    title: '从一个画面开始',
    description: '描述你脑海里最清晰的一幕',
    prompt: '我脑中有一个画面：',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9" r="1.5"/><path d="m21 15-5-5L5 20"/></svg>',
  },
  {
    title: '从一个人物开始',
    description: '告诉我他最想得到什么',
    prompt: '我想写一个这样的人：',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
  },
  {
    title: '从一个“如果”开始',
    description: '抛出你最大胆的世界假设',
    prompt: '如果有一天，',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M9.8 9a2.3 2.3 0 1 1 3.4 2c-.8.5-1.2 1-1.2 2M12 17h.01"/></svg>',
  },
]

// ── 缪斯高级特性（分档：免费 / 创作者 / 旗舰）──
const musePersonas = ref<MusePersona[]>([])
const selectedPersona = ref('default')
const userTier = ref<'free' | 'creator' | 'flagship'>('free')
const featureAccess = ref({ muse_persona: false, muse_search: false, muse_divergence: false })
const disableMuseSearch = ref(false) // 「一键找素材」开关（默认开启=找）
const disableSpark = ref(false)      // 「灵感扰动」开关（默认开启）
const divergeSeeds = ref<DivergeSeed[]>([])
const pickedSeedIds = ref<number[]>([])  // 已投喂给文思的方向 id（用于标记「已投喂」，其余方向仍保留可选）
const isDiverging = ref(false)

const canUsePersona = computed(() => featureAccess.value.muse_persona)
const canUseMuseSearch = computed(() => featureAccess.value.muse_search)
const canUseDivergence = computed(() => featureAccess.value.muse_divergence)
const museSearchEnabled = computed(() => canUseMuseSearch.value && !disableMuseSearch.value)

// ── 准备阶段的动态文案（按钮 + 右侧加载视图共用） ──
const startButtonText = computed(() => {
  if (preparingStage.value === 'reference') return '检索参考小说中...'
  if (isPreparingConversation.value || novelStore.isLoading) return '正在准备...'
  return initialIdea.value.trim() ? '开始构思' : '开启灵感模式'
})

const preparingTitle = computed(() =>
  preparingStage.value === 'reference' ? '正在研读参考小说...' : '正在为你准备灵感空间...'
)

const preparingPhase = computed(() => {
  if (preparingStage.value === 'project') return '正在创建项目...'
  if (preparingStage.value === 'reference') {
    return `正在联网检索《${normalizedReferenceNovels.value.join('》《')}》的题材与写法...`
  }
  return ''
})

const preparingHint = computed(() =>
  preparingStage.value === 'reference'
    ? '首次检索一本书约需 30-60 秒，结果会缓存、之后秒开；即使检索失败也会自动降级为普通灵感模式，不会卡住。'
    : ''
)

const normalizedReferenceNovels = computed(() =>
  referenceNovels.value
    .map((name) => (name || '').trim())
    .filter(Boolean)
    .slice(0, 3)
)
const librarySelections = ref<LibrarySelection[]>([])
const librarySelectionsWithNames = computed(() =>
  librarySelections.value
    .filter((selection) => selection.title && selection.id !== null)
    .map((selection) => selection.title.trim())
)
const selectedReferenceNovelIds = computed(() =>
  librarySelections.value
    .map((selection) => selection.id)
    .filter((id): id is number => id !== null)
)
const boundReferenceNovels = computed(() => novelStore.projectReferenceNovels || [])
const currentMuse = computed(() =>
  musePersonas.value.find((persona) => persona.key === selectedPersona.value)
    || musePersonas.value.find((persona) => persona.key === 'default')
    || null,
)
const workflowStage = computed(() => {
  if (showBlueprint.value) return 4
  if (showBlueprintConfirmation.value || currentTurn.value >= 3) return 3
  if (conversationStarted.value) return 2
  return 1
})
const conversationStatus = computed(() => {
  if (showBlueprint.value) return '蓝图已生成'
  if (showBlueprintConfirmation.value) return '故事等待锁定'
  if (isInitialLoading.value || novelStore.isLoading) return '文思正在思考'
  return '灵感对话进行中'
})
const firstUserIdea = computed(() =>
  chatMessages.value.find((message) => message.type === 'user')?.content?.trim() || '',
)
const effectiveIdea = computed(() => initialIdea.value.trim() || firstUserIdea.value)
const currentIdeaTitle = computed(() => {
  const rawIdea = effectiveIdea.value
  const text = rawIdea
    .replace(/^(我脑中有一个画面：|我想写一个这样的人：|如果有一天，)/, '')
    .trim()
  if (!text) return rawIdea.replace(/[：:]$/, '') || '等待第一句灵感'
  return text.split(/[。！？!?；;\n]/)[0].slice(0, 20) || '一个正在生长的故事'
})
const currentIdeaSummary = computed(() => {
  if (!effectiveIdea.value) return '从一个画面、人物或大胆假设开始，文思会帮你逐步提炼题材与冲突。'
  return effectiveIdea.value.length > 72
    ? `${effectiveIdea.value.slice(0, 72)}…`
    : effectiveIdea.value
})
const ideaSeedLabel = computed(() =>
  effectiveIdea.value ? currentIdeaTitle.value : '等待你给出第一句点子',
)
const referenceInsight = computed(() =>
  normalizedReferenceNovels.value.length
    ? `${normalizedReferenceNovels.value.length} 本参考小说已挂载`
    : '尚未挂载参考小说',
)
const exclusionCount = computed(() =>
  exclusions.value.split(/[\n；;]/).map((item) => item.trim()).filter(Boolean).length,
)
const boundaryInsight = computed(() =>
  exclusionCount.value ? `${exclusionCount.value} 条创作禁区已生效` : '暂未设置创作禁区',
)
const nextActionLabel = computed(() => {
  if (showBlueprint.value) return '确认蓝图后进入章节规划与正文创作。'
  if (showBlueprintConfirmation.value || currentTurn.value >= 3) return '检查故事核心，准备生成可编辑蓝图。'
  if (conversationStarted.value) return `再聊 ${Math.max(3 - currentTurn.value, 0)} 轮，逐步锁定故事。`
  return initialIdea.value.trim() ? '点击开启灵感模式，与文思开始第一轮对话。' : '先写下一句话、一个人物或一幅画面。'
})

const goBack = () => {
  router.push('/home')
}

const handleLibrarySelectionChange = (selections: LibrarySelection[]) => {
  librarySelections.value = selections
}

const applyBoundReferencesToInputs = (list: ReferenceNovelSummary[]) => {
  if (!list.length) return
  const sanitized = list.slice(0, 3)
  const hasUserInput = referenceNovels.value.some((name) => name && name.trim())
  if (!hasUserInput) {
    referenceNovels.value = sanitized.map((novel) => novel.title)
    librarySelections.value = sanitized.map((novel, index) => ({
      index,
      id: novel.id,
      title: novel.title
    }))
  }
}

watch(
  () => novelStore.currentProject?.id,
  async (projectId) => {
    if (!projectId) {
      // 重新开始时会短暂清空 currentProject，但参考书输入会被保留；此时也要保留
      // 对应的书库 ID，供新项目在首轮构思前重新绑定。
      if (!referenceNovels.value.some((name) => name && name.trim())) {
        librarySelections.value = []
      }
      return
    }
    try {
      const list = await novelStore.loadProjectReferenceNovels(projectId)
      applyBoundReferencesToInputs(list)
    } catch (err) {
      console.error('加载项目参考小说失败:', err)
    }
  },
  { immediate: true }
)

const bindReferencesIfNeeded = async (referenceNovelIds = selectedReferenceNovelIds.value) => {
  const projectId = novelStore.currentProject?.id
  if (!projectId) return
  const ids = [...new Set(referenceNovelIds)].slice(0, 3)
  if (!ids.length) return
  try {
    await novelStore.bindProjectReferenceNovels(projectId, ids)
  } catch (err) {
    globalAlert.showError(
      `绑定参考小说失败: ${err instanceof Error ? err.message : '请稍后重试'}`,
      '参考小说'
    )
  }
}

const resetInspirationMode = (options: {
  keepReferenceNovels?: boolean
  keepExclusions?: boolean
  keepInitialIdea?: boolean
} = {}) => {
  conversationStarted.value = false
  isPreparingConversation.value = false
  isInitialLoading.value = false
  showBlueprintConfirmation.value = false
  showBlueprint.value = false
  chatMessages.value = []
  currentUIControl.value = null
  currentTurn.value = 0
  completedBlueprint.value = null
  confirmationMessage.value = ''
  blueprintMessage.value = ''
  referenceContext.value = ''
  referenceSearchStatus.value = 'idle'
  referenceSearchMessage.value = ''
  if (!options.keepReferenceNovels) {
    referenceNovels.value = ['']
  }
  if (!options.keepExclusions) {
    exclusions.value = ''
    showExclusions.value = false
  }
  if (!options.keepInitialIdea) {
    initialIdea.value = ''
  }

  novelStore.setCurrentProject(null)
  novelStore.currentConversationState = {}
}

const exitConversation = async () => {
  const confirmed = await globalAlert.showConfirm('确定要退出灵感模式吗？当前进度可能会丢失。', '退出确认')
  if (confirmed) {
    resetInspirationMode()
    router.push('/home')
  }
}

const handleRestart = async () => {
  const confirmed = await globalAlert.showConfirm('确定要重新开始吗？当前对话内容将会丢失。', '重新开始确认')
  if (confirmed) {
    await startConversation()
  }
}

const backToConversation = () => {
  showBlueprintConfirmation.value = false
}

const startConversation = async () => {
  const selectedReferenceNovels = [...normalizedReferenceNovels.value]
  // resetInspirationMode 会清空当前项目并触发监听器，必须在此之前保存书库 ID。
  // 绑定要发生在首轮对话和蓝图生成之前，后端才能持续注入参考资料与融合 DNA。
  const selectedReferenceIds = [...selectedReferenceNovelIds.value]
  const selectedInitialIdea = initialIdea.value.trim()

  resetInspirationMode({
    keepReferenceNovels: true,
    keepExclusions: true,
    keepInitialIdea: true,
  })
  isPreparingConversation.value = true
  preparingStage.value = 'project'

  try {
    await novelStore.createProject('未命名灵感', '开始灵感模式')

    if (selectedReferenceIds.length > 0) {
      await bindReferencesIfNeeded(selectedReferenceIds)
    }

    const readyReferenceTitles = new Set(
      novelStore.projectReferenceNovels.filter((novel) => novel.status === 'ready').map((novel) => novel.title.trim()),
    )
    const referencesToSearch = selectedReferenceNovels.filter((title) => !readyReferenceTitles.has(title))
    if (referencesToSearch.length > 0) {
      preparingStage.value = 'reference'
      referenceSearchStatus.value = 'searching'
      referenceSearchMessage.value = `正在补充检索 ${referencesToSearch.length} 本参考小说（首次约 30-60 秒）...`
      try {
        const result = await novelStore.searchReferenceNovels(referencesToSearch)
        referenceContext.value = result.reference_context || ''
        if (result.search_completed) {
          referenceSearchStatus.value = 'success'
        } else if (result.skipped) {
          referenceSearchStatus.value = 'skipped'
        } else {
          referenceSearchStatus.value = 'error'
        }
        referenceSearchMessage.value = result.message || ''
      } catch (error) {
        console.error('参考小说搜索失败:', error)
        referenceSearchStatus.value = 'error'
        referenceSearchMessage.value = '补充检索暂不可用，将使用已有参考资料继续构思'
        referenceContext.value = ''
      }
    }

    conversationStarted.value = true
    isInitialLoading.value = true

    await handleUserInput(selectedInitialIdea
      ? { id: 'initial_idea', value: selectedInitialIdea }
      : null, {
      referenceNovels: selectedReferenceNovels,
      referenceContext: referenceContext.value
    })
    // 手输书名会在首轮由后端解析并绑定，及时同步侧栏中的书目和分析状态。
    if (selectedReferenceNovels.length && novelStore.currentProject?.id) {
      await novelStore.loadProjectReferenceNovels(novelStore.currentProject.id).catch(console.error)
    }
  } catch (error) {
    console.error('启动灵感模式失败:', error)
    globalAlert.showError(`无法开始灵感模式: ${error instanceof Error ? error.message : '未知错误'}`, '启动失败')
    resetInspirationMode({
      keepReferenceNovels: true,
      keepExclusions: true,
      keepInitialIdea: true,
    })
  } finally {
    isPreparingConversation.value = false
    preparingStage.value = 'idle'
  }
}

const restoreConversation = async (projectId: string) => {
  try {
    await novelStore.loadProject(projectId)
    const project = novelStore.currentProject
    if (project && project.conversation_history) {
      conversationStarted.value = true
      chatMessages.value = project.conversation_history.map((item): ChatMessage | null => {
        if (item.role === 'user') {
          try {
            const userInput = JSON.parse(item.content)
            return { content: userInput.value, type: 'user' }
          } catch {
            return { content: item.content, type: 'user' }
          }
        } else {
          try {
            const assistantOutput = JSON.parse(item.content)
            return { content: assistantOutput.ai_message, type: 'ai' }
          } catch {
            return { content: item.content, type: 'ai' }
          }
        }
      }).filter((msg): msg is ChatMessage => msg !== null && msg.content !== null)

      const lastAssistantMsgStr = project.conversation_history.filter(m => m.role === 'assistant').pop()?.content
      if (lastAssistantMsgStr) {
        const lastAssistantMsg = JSON.parse(lastAssistantMsgStr)

        if (lastAssistantMsg.is_complete) {
          confirmationMessage.value = lastAssistantMsg.ai_message
          showBlueprintConfirmation.value = true
        } else {
          currentUIControl.value = lastAssistantMsg.ui_control
        }
      }
      currentTurn.value = project.conversation_history.filter(m => m.role === 'assistant').length
      await scrollToBottom()
    }
  } catch (error) {
    console.error('恢复对话失败:', error)
    globalAlert.showError(`无法恢复对话: ${error instanceof Error ? error.message : '未知错误'}`, '加载失败')
    resetInspirationMode()
  }
}

const handleUserInput = async (
  userInput: any,
  options: {
    referenceNovels?: string[]
    referenceContext?: string
    exclusions?: string
  } = {}
) => {
  try {
    if (userInput && userInput.value) {
      chatMessages.value.push({
        content: userInput.value,
        type: 'user'
      })
      await scrollToBottom()
    }

    const mergedOptions = {
      ...options,
      ...(normalizedReferenceNovels.value.length
        ? { referenceNovels: [...normalizedReferenceNovels.value] }
        : {}),
      ...(referenceContext.value.trim() ? { referenceContext: referenceContext.value.trim() } : {}),
      ...(exclusions.value.trim() ? { exclusions: exclusions.value.trim() } : {}),
      ...(canUsePersona.value && selectedPersona.value !== 'default' ? { musePersona: selectedPersona.value } : {}),
      disableSpark: disableSpark.value,
      disableMuseSearch: disableMuseSearch.value || !canUseMuseSearch.value
    }
    const response = await novelStore.sendConversation(userInput, mergedOptions)

    if (isInitialLoading.value) {
      isInitialLoading.value = false
    }

    chatMessages.value.push({
      content: response.ai_message,
      type: 'ai'
    })
    currentTurn.value++

    await scrollToBottom()

    if (response.is_complete && response.ready_for_blueprint) {
      confirmationMessage.value = response.ai_message
      showBlueprintConfirmation.value = true
      await scrollToBottom()
    } else if (response.is_complete) {
      await handleGenerateBlueprint()
    } else {
      currentUIControl.value = response.ui_control
    }
  } catch (error) {
    console.error('对话失败:', error)
    if (isInitialLoading.value) {
      isInitialLoading.value = false
    }
    globalAlert.showError(`抱歉，与AI连接时遇到问题: ${error instanceof Error ? error.message : '未知错误'}`, '通信失败')
    resetInspirationMode()
  }
}

const handleGenerateBlueprint = async () => {
  try {
    const response = await novelStore.generateBlueprint()
    await handleBlueprintGenerated(response)
  } catch (error) {
    console.error('生成蓝图失败:', error)
    const errMessage = error instanceof Error ? error.message : '未知错误'
    const hint = detectUpgradeHint(errMessage)
    if (hint) {
      upgradeKind.value = hint
      upgradeMessage.value = errMessage
      showUpgrade.value = true
      return
    }
    // 此自动路径默认 deep，但免费档会降级为免费快速成书；不臆测已扣费
    const human = humanizeGenerationError(errMessage, { billed: false })
    globalAlert.showError(human.message, human.title)
  }
}

const handleBlueprintGenerated = async (response: any) => {
  console.log('收到蓝图生成完成事件:', response)
  completedBlueprint.value = response.blueprint
  blueprintMessage.value = response.ai_message
  showBlueprintConfirmation.value = false
  showBlueprint.value = true
  await scrollToBottom()
}

const handleRegenerateBlueprint = () => {
  showBlueprint.value = false
  showBlueprintConfirmation.value = true
  scrollToBottom()
}

const handleConfirmBlueprint = async () => {
  if (!completedBlueprint.value) {
    globalAlert.showError('蓝图数据缺失，请重新生成或稍后重试。', '保存失败')
    return
  }
  try {
    await novelStore.saveBlueprint(completedBlueprint.value)
    if (novelStore.currentProject) {
      router.push(`/novel/${novelStore.currentProject.id}`)
    }
  } catch (error) {
    console.error('保存蓝图失败:', error)
    globalAlert.showError(`保存蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatArea.value) {
    chatArea.value.scrollTop = chatArea.value.scrollHeight
  }
}

async function loadMuseCapabilities() {
  try {
    const resp = await NovelAPI.listMusePersonas()
    musePersonas.value = resp.personas || []
    userTier.value = resp.tier || 'free'
    featureAccess.value = resp.features || { muse_persona: false, muse_search: false, muse_divergence: false }
    if (!canUsePersona.value) selectedPersona.value = 'default'
  } catch (error) {
    console.warn('加载缪斯人格/档位失败（不影响基础对话）:', error)
  }
}

const seedToText = (s: DivergeSeed): string => {
  const parts = [s.title, s.logline].filter(Boolean)
  let text = parts.join('：')
  if (s.hook) text += `（钩子：${s.hook}）`
  if (s.emotional_hook) text += `\n读者牵挂：${s.emotional_hook}`
  return text || s.logline || s.title
}

async function handleDiverge() {
  if (!canUseDivergence.value) {
    globalAlert.showError('N 路发散为旗舰档特性，升级旗舰版即可一次生成多个迥异世界观种子并智能评分。', '需要升级')
    return
  }
  if (!novelStore.currentProject) {
    globalAlert.showError('请先开启灵感模式（创建项目）再使用发散。', '提示')
    return
  }
  const seed = (referenceContext.value || '').trim()
    || normalizedReferenceNovels.value.join('、')
    || (chatMessages.value.find((m) => m.type === 'user')?.content || '').trim()
  if (!seed) {
    globalAlert.showError('请先在对话里给一个故事点子，再让缪斯发散。', '提示')
    return
  }
  isDiverging.value = true
  divergeSeeds.value = []
  pickedSeedIds.value = []
  try {
    const resp = await NovelAPI.divergeConcepts(novelStore.currentProject.id, seed, {
      exclusions: exclusions.value.trim() || undefined,
      n: 5,
      keep: 3
    })
    divergeSeeds.value = resp.seeds || []
    if (!divergeSeeds.value.length) {
      globalAlert.showError('这次没发散出可用种子，换个点子或稍后再试。', '提示')
    }
  } catch (error) {
    globalAlert.showError(`发散失败：${error instanceof Error ? error.message : '未知错误'}`, '失败')
  } finally {
    isDiverging.value = false
  }
}

function pickDivergeSeed(seed: DivergeSeed) {
  // 不清空其余方向：标记本方向「已投喂」后保留整组卡片，方便继续对比/再挑
  if (!pickedSeedIds.value.includes(seed.id)) {
    pickedSeedIds.value.push(seed.id)
  }
  // 把选中的种子作为用户输入投喂给「文思」继续落地
  handleUserInput({ id: 'diverge_pick', value: seedToText(seed) })
}

// 都不满意：清除这批发散方向，回到普通对话（不投喂任何方向）
function dismissDivergeSeeds() {
  divergeSeeds.value = []
  pickedSeedIds.value = []
}

onMounted(() => {
  loadMuseCapabilities()
  const projectId = route.query.project_id as string
  if (projectId) {
    restoreConversation(projectId)
  } else {
    resetInspirationMode()
  }
})
</script>

<style scoped>
.inspiration-shell {
  height: 100vh;
  overflow: hidden;
  color: #f4f4ee;
  background: #090a08;
  font-family: Inter, "Noto Sans SC", "Microsoft YaHei", sans-serif;
}
.inspiration-shell * { box-sizing: border-box; }
button, textarea { font: inherit; }
button { cursor: pointer; }
.studio-header {
  display: flex;
  height: 68px;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 0 24px;
  border-bottom: 1px solid #24251f;
  background: rgba(15,16,14,.98);
}
.studio-brand, .header-actions, .conversation-state, .active-muse { display: flex; align-items: center; }
.studio-brand { min-width: 0; gap: 11px; }
.icon-button {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  flex: 0 0 auto;
  border: 1px solid #2d2f29;
  border-radius: 10px;
  color: #999c93;
  background: #171815;
}
.icon-button:hover { color: #ffe500; border-color: #4c4921; }
.icon-button svg { width: 17px; height: 17px; }
.brand-mark {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 9px;
  color: #171700;
  background: #ffe500;
  font-size: 16px;
}
.brand-copy { min-width: 0; }
.brand-copy h1 { margin: 0; color: #f5f5ef; font-size: 16px; font-weight: 680; }
.brand-copy p { margin: 3px 0 0; color: #6d7067; font-size: 10px; }
.header-actions { gap: 9px; }
.save-state { display: flex; align-items: center; gap: 7px; color: #6f7269; font-size: 10px; white-space: nowrap; }
.save-state i { width: 6px; height: 6px; border-radius: 50%; background: #8a8518; }
.header-button {
  height: 36px;
  padding: 0 13px;
  border: 1px solid #2d2f29;
  border-radius: 10px;
  color: #aaada5;
  background: #171815;
  font-size: 11px;
}
.header-button:hover { color: #f1f1eb; }
.studio-flow {
  display: grid;
  height: 56px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
  padding: 10px 24px;
  border-bottom: 1px solid #1f201c;
  background: #0d0e0c;
}
.flow-step {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
  padding: 0 12px;
  border-radius: 9px;
  color: #5f625a;
}
.flow-step strong { font-size: 9px; font-weight: 700; letter-spacing: .08em; }
.flow-step span { overflow: hidden; font-size: 11px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.flow-step.active { color: #171700; background: #ffe500; box-shadow: 0 8px 24px rgba(255,229,0,.08); }
.flow-step.done { color: #b6b8b0; }
.studio-workspace {
  display: grid;
  height: calc(100vh - 124px);
  grid-template-columns: minmax(244px, 274px) minmax(440px, 1fr) minmax(250px, 292px);
  gap: 12px;
  padding: 14px;
  background-color: #090a08;
  background-image: linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px);
  background-size: 34px 34px;
}
.studio-panel {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid #252620;
  border-radius: 16px;
  background: rgba(16,17,14,.985);
  box-shadow: 0 22px 60px rgba(0,0,0,.18);
}
.material-rail, .idea-board { padding: 17px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #31332c transparent; }
.rail-heading { padding-bottom: 13px; border-bottom: 1px solid #252620; }
.rail-heading p, .conversation-header p, .hero-kicker {
  margin: 0 0 5px;
  color: #686b63;
  font-size: 8px;
  font-weight: 800;
  letter-spacing: .16em;
}
.rail-heading h2 { margin: 0; color: #efefe9; font-size: 16px; font-weight: 680; }
.rail-section { padding: 15px 0; border-bottom: 1px solid #252620; }
.rail-section:last-of-type { border-bottom: 0; }
.section-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
.section-title h3 { margin: 0; color: #bfc1b9; font-size: 11px; font-weight: 680; }
.section-title span { display: block; margin-top: 3px; color: #666960; font-size: 9px; }
.selection-note { margin: 9px 0 0; color: #b8ad16; font-size: 9px; line-height: 1.55; }
.bound-list { display: grid; gap: 6px; margin-top: 9px; }
.bound-list > span { display: flex; justify-content: space-between; gap: 8px; padding: 7px 8px; border: 1px solid #292b25; border-radius: 8px; background: #161713; }
.bound-list b { overflow: hidden; color: #b6b8b0; font-size: 9px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.bound-list small { color: #62655d; font-size: 8px; }
.reference-section :deep(.reference-novel-input) { margin: 0; }
.reference-section :deep(label), .reference-section :deep(.input-label) { color: #85887f !important; font-size: 9px !important; }
.reference-section :deep(input) { border-color: #30322b !important; border-radius: 9px !important; color: #dedfd8 !important; background: #171815 !important; }
.reference-section :deep(button) { border-radius: 8px !important; }
.section-toggle {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  border: 0;
  color: #bfc1b9;
  background: transparent;
  font-size: 11px;
  font-weight: 680;
}
.section-toggle > span { display: flex; align-items: center; gap: 8px; }
.section-toggle svg { width: 14px; height: 14px; color: #6a6d64; transition: transform .2s ease; }
.section-toggle svg.open { transform: rotate(90deg); }
.section-dot { width: 6px; height: 6px; border-radius: 50%; }
.boundary-dot { background: #966e9d; }
.boundary-editor { margin-top: 10px; }
.boundary-editor textarea {
  width: 100%;
  resize: vertical;
  padding: 10px;
  border: 1px solid #30322b;
  border-radius: 9px;
  outline: none;
  color: #dedfd8;
  background: #171815;
  font-size: 10px;
  line-height: 1.55;
}
.boundary-editor textarea:focus { border-color: #5a5522; }
.boundary-editor p { margin: 6px 0 0; color: #5e6159; font-size: 8px; line-height: 1.5; }
.tier-badge {
  margin: 0 !important;
  padding: 4px 7px;
  border: 1px solid #44451f;
  border-radius: 999px;
  color: #d3c700 !important;
  background: #1c1c0c;
  font-size: 8px !important;
}
.muse-list { display: grid; gap: 7px; }
.muse-card {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 9px;
  padding: 9px;
  border: 1px solid #2a2c26;
  border-radius: 10px;
  color: inherit;
  text-align: left;
  background: #151613;
}
.muse-card:hover:not(:disabled) { border-color: #484722; }
.muse-card.selected { border-color: #575224; background: #201f0e; }
.muse-card.locked { opacity: .52; cursor: not-allowed; }
.muse-avatar {
  display: grid;
  width: 31px;
  height: 31px;
  place-items: center;
  flex: 0 0 auto;
  border-radius: 9px;
  color: #171700;
  background: #dfd200;
  font-size: 10px;
  font-weight: 800;
}
.muse-copy { min-width: 0; flex: 1; }
.muse-copy strong, .active-muse strong { display: block; color: #d9dad4; font-size: 10px; font-weight: 650; }
.muse-copy small, .active-muse small { display: block; overflow: hidden; margin-top: 3px; color: #686b63; font-size: 8px; text-overflow: ellipsis; white-space: nowrap; }
.muse-card > svg { width: 13px; height: 13px; flex: 0 0 auto; color: #777a72; }
.muse-switches { display: grid; gap: 7px; margin-top: 10px; }
.muse-switches label { display: flex; align-items: center; gap: 8px; color: #aaada5; cursor: pointer; }
.muse-switches label.disabled { opacity: .5; cursor: not-allowed; }
.muse-switches input { accent-color: #ffe500; }
.muse-switches strong { display: block; font-size: 9px; font-weight: 650; }
.muse-switches small { display: block; margin-top: 2px; color: #60635b; font-size: 8px; }
.conversation-state { gap: 10px; }
.state-pulse { position: relative; display: grid; width: 31px; height: 31px; place-items: center; border-radius: 9px; background: #1f1f0d; }
.state-pulse::before { position: absolute; width: 13px; height: 13px; border: 1px solid #69631b; border-radius: 50%; content: ""; }
.state-pulse i { width: 5px; height: 5px; border-radius: 50%; background: #d0c300; }
.conversation-state strong { display: block; color: #d9dad4; font-size: 10px; font-weight: 650; }
.conversation-state small { display: block; margin-top: 3px; color: #696c64; font-size: 8px; }
.turn-progress { height: 3px; margin-top: 12px; overflow: hidden; border-radius: 2px; background: #272820; }
.turn-progress span { display: block; height: 100%; background: #d7ca00; transition: width .25s ease; }
.turn-hint { margin: 8px 0 0; color: #74776f; font-size: 8px; line-height: 1.5; }
.compact-chip-list { display: flex; flex-wrap: wrap; gap: 6px; }
.compact-chip-list span { padding: 6px 7px; border: 1px solid #30322b; border-radius: 7px; color: #9ea198; background: #171815; font-size: 8px; }
.boundary-summary { margin: 0; color: #969990; font-size: 9px; line-height: 1.65; white-space: pre-wrap; }
.active-muse { gap: 9px; }
.rail-bottom-actions { display: grid; gap: 7px; margin-top: 15px; }
.rail-bottom-actions button { min-height: 34px; border: 1px solid #2d2f29; border-radius: 9px; color: #8f9289; background: #171815; font-size: 9px; }
.rail-bottom-actions button:hover { color: #f1f1ea; }
.rail-fold-enter-active, .rail-fold-leave-active { transition: opacity .16s ease, transform .16s ease; }
.rail-fold-enter-from, .rail-fold-leave-to { opacity: 0; transform: translateY(-4px); }
.idea-stage { display: flex; flex-direction: column; }
.stage-loading { flex: 1; min-height: 0; }
.idea-hero { padding: 32px 34px 24px; border-bottom: 1px solid #252620; }
.hero-mark { display: grid; width: 38px; height: 38px; margin-bottom: 17px; place-items: center; border-radius: 11px; color: #171700; background: #ffe500; font-size: 18px; }
.idea-hero h2 { max-width: 640px; margin: 0; color: #f5f5ef; font-size: clamp(24px,2.2vw,34px); font-weight: 720; letter-spacing: -.035em; }
.idea-hero > p:last-child { max-width: 670px; margin: 11px 0 0; color: #8b8e85; font-size: 12px; line-height: 1.8; }
.starter-area { display: flex; min-height: 0; flex: 1; flex-direction: column; padding: 22px 28px 24px; }
.starter-grid { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: 9px; }
.starter-card {
  min-height: 105px;
  padding: 13px;
  border: 1px solid #2b2d27;
  border-radius: 11px;
  color: #aaada4;
  text-align: left;
  background: #151613;
}
.starter-card:hover, .starter-card.selected { border-color: #575224; color: #efefe8; background: #201f0e; transform: translateY(-1px); }
.starter-icon { display: block; width: 17px; height: 17px; margin-bottom: 13px; color: #c5ba00; }
.starter-icon :deep(svg) { width: 17px; height: 17px; }
.starter-card strong { display: block; font-size: 10px; font-weight: 680; }
.starter-card small { display: block; margin-top: 5px; color: #656860; font-size: 8px; line-height: 1.5; }
.idea-composer {
  margin-top: auto;
  overflow: hidden;
  border: 1px solid #37392f;
  border-radius: 13px;
  background: #131410;
  box-shadow: 0 16px 44px rgba(0,0,0,.2);
}
.idea-composer textarea {
  width: 100%;
  min-height: 96px;
  resize: none;
  padding: 15px 16px 10px;
  border: 0;
  outline: 0;
  color: #efefe9;
  background: transparent;
  font-size: 12px;
  line-height: 1.7;
}
.idea-composer textarea::placeholder { color: #5c5f57; }
.composer-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 8px; border-top: 1px solid #262820; }
.composer-footer > span { padding-left: 7px; color: #62655d; font-size: 8px; }
.composer-footer button {
  display: inline-flex;
  min-height: 36px;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  border: 0;
  border-radius: 9px;
  color: #171700;
  background: #ffe500;
  font-size: 10px;
  font-weight: 700;
}
.composer-footer button:disabled { opacity: .55; cursor: wait; }
.composer-footer button svg { width: 14px; height: 14px; }
.conversation-header { display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 17px 22px; border-bottom: 1px solid #252620; }
.conversation-header h2 { margin: 0; color: #efefe8; font-size: 17px; font-weight: 680; }
.conversation-header > span { padding: 6px 9px; border: 1px solid #36351e; border-radius: 8px; color: #c3b900; background: #1d1d0d; font-size: 9px; }
.chat-scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 20px 24px; scrollbar-width: thin; scrollbar-color: #34362f transparent; }
.chat-loading { min-height: 320px; }
.chat-scroll :deep(.chat-bubble) { max-width: 820px; }
.inline-blueprint-wrap { margin-top: 15px; }
.conversation-footer { padding: 11px 16px 15px; border-top: 1px solid #252620; background: #10110e; }
.conversation-footer :deep(.conversation-input) { margin: 0; }
.diverge-trigger { margin-bottom: 8px; padding: 7px 10px; border: 1px solid #4b4820; border-radius: 8px; color: #cec200; background: #1c1b0c; font-size: 9px; }
.diverge-trigger:disabled { opacity: .5; }
.diverge-results { max-height: 235px; overflow-y: auto; padding: 12px 16px; border-top: 1px solid #2a2b24; background: #11120f; }
.diverge-results-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 9px; }
.diverge-results-head strong { display: block; color: #d7d8d1; font-size: 10px; }
.diverge-results-head span { display: block; margin-top: 2px; color: #696c64; font-size: 8px; }
.diverge-results-head button { border: 0; color: #7b7e75; background: transparent; font-size: 8px; }
.diverge-cards { display: grid; grid-template-columns: repeat(3,minmax(180px,1fr)); gap: 7px; }
.diverge-card { position: relative; padding: 10px; border: 1px solid #2c2e27; border-radius: 9px; color: #aaada4; text-align: left; background: #171815; }
.diverge-card:hover, .diverge-card.picked { border-color: #565224; background: #201f0e; }
.diverge-card > div { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.diverge-card strong { color: #d4d5ce; font-size: 9px; }
.diverge-card div span { color: #9e9616; font-size: 8px; }
.diverge-card p { margin: 6px 0; color: #85887f; font-size: 8px; line-height: 1.5; }
.diverge-card small { display: block; margin-top: 3px; color: #696c64; font-size: 7px; }
.diverge-card > b { position: absolute; top: 7px; right: 7px; color: #d0c400; font-size: 7px; }
.idea-board { display: flex; flex-direction: column; }
.live-idea-card { margin-top: 14px; padding: 13px; border: 1px solid #2b2d27; border-radius: 11px; background: #161713; }
.live-idea-card.active { border-color: #3e3c1d; background: #1b1b0d; }
.live-idea-card > div { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.live-idea-card span { color: #73766d; font-size: 8px; }
.live-idea-card b { color: #bdb300; font-size: 8px; font-weight: 700; }
.live-idea-card h3 { margin: 10px 0 7px; color: #eeeee8; font-size: 13px; font-weight: 680; }
.live-idea-card p { margin: 0; color: #8e9188; font-size: 9px; line-height: 1.65; }
.board-section { padding: 15px 0; border-bottom: 1px solid #252620; }
.board-section > p { margin: 0 0 10px; color: #71746c; font-size: 8px; font-weight: 700; letter-spacing: .08em; }
.board-progress-list, .insight-list, .direction-list { display: grid; gap: 7px; }
.board-progress-list > div, .insight-list > div, .direction-list button {
  display: grid;
  grid-template-columns: 26px minmax(0,1fr);
  gap: 8px;
  align-items: start;
}
.board-progress-list > div { opacity: .44; }
.board-progress-list > div.active, .board-progress-list > div.done { opacity: 1; }
.board-progress-list > div > span, .direction-list button > span {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: 7px;
  color: #7f821e;
  background: #20200d;
  font-size: 8px;
  font-weight: 700;
}
.board-progress-list > div.active > span { color: #171700; background: #d7cb00; }
.board-progress-list strong, .insight-list strong, .direction-list strong { display: block; color: #aeb1a8; font-size: 9px; font-weight: 650; }
.board-progress-list small, .insight-list small, .direction-list small { display: block; margin-top: 3px; color: #5e6159; font-size: 8px; line-height: 1.45; }
.insight-icon { display: grid; width: 26px; height: 26px; place-items: center; color: #aaa217; font-size: 14px; }
.direction-list button { width: 100%; padding: 8px; border: 1px solid #2a2c26; border-radius: 9px; color: inherit; text-align: left; background: #151613; }
.direction-list button:hover { border-color: #4d4a21; }
.direction-list small { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.board-next { margin-top: auto; padding: 13px; border: 1px solid #30311f; border-radius: 10px; background: #18180d; }
.board-next span { color: #b7ad16; font-size: 8px; font-weight: 700; letter-spacing: .08em; }
.board-next p { margin: 5px 0 0; color: #a0a39a; font-size: 9px; line-height: 1.55; }
.fade-enter-active, .fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
@media (max-width: 1200px) {
  .studio-workspace { grid-template-columns: 238px minmax(420px,1fr) 248px; }
  .idea-hero { padding-inline: 26px; }
}
@media (max-width: 980px) {
  .studio-workspace { grid-template-columns: 230px minmax(0,1fr); }
  .idea-board { display: none; }
}
@media (max-width: 720px) {
  .inspiration-shell { height: auto; min-height: 100vh; overflow: auto; }
  .studio-header { height: 62px; padding: 0 13px; }
  .save-state, .header-button { display: none; }
  .studio-flow { height: auto; grid-template-columns: repeat(2,minmax(0,1fr)); padding: 8px 12px; }
  .flow-step { min-height: 34px; }
  .studio-workspace { height: auto; grid-template-columns: 1fr; padding: 10px; }
  .material-rail, .idea-board { max-height: none; overflow: visible; }
  .idea-stage { min-height: 660px; }
  .idea-board { display: flex; }
  .starter-grid { grid-template-columns: 1fr; }
  .starter-card { min-height: 82px; }
  .idea-hero { padding: 24px 19px 18px; }
  .starter-area { padding: 17px; }
  .composer-footer { align-items: flex-start; flex-direction: column; }
  .composer-footer button { width: 100%; justify-content: center; }
  .conversation-header { padding: 14px 16px; }
  .chat-scroll { min-height: 520px; padding: 16px; }
  .diverge-cards { grid-template-columns: 1fr; }
}
</style>

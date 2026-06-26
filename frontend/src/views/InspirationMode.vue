<!-- AIMETA P=灵感模式_AI对话创作|R=对话创作界面|NR=不含写作台功能|E=route:/inspiration#component:InspirationMode|X=ui|A=对话界面|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="inspiration-shell">

    <!-- ──────────── LEFT SIDEBAR ──────────── -->
    <aside class="sidebar">
      <!-- Brand header -->
      <div class="sidebar-brand">
        <div class="brand-logo">
          <span class="brand-accent">✦</span>
          <span class="brand-name">Octopus AI Novel</span>
        </div>
        <div class="brand-badge">💡 灵感模式</div>
      </div>

      <!-- ── PRE-START: config panel ── -->
      <div v-if="!conversationStarted" class="sidebar-config">
        <div class="config-section">
          <h2 class="config-headline">
            小说家的<br><span style="color: #FFE500;">新篇章</span>
          </h2>
          <p class="config-sub">让AI引导你，一步步构建出独一无二的故事世界。</p>
        </div>

        <div class="config-section">
          <ReferenceNovelInput
            v-model="referenceNovels"
            :search-status="referenceSearchStatus"
            :status-message="referenceSearchMessage"
            @library-selection-change="handleLibrarySelectionChange"
          />

          <div v-if="librarySelectionsWithNames.length" class="ref-selected-hint">
            已选：<strong style="color: #FFE500;">{{ librarySelectionsWithNames.join(' / ') }}</strong>
          </div>

          <div v-if="boundReferenceNovels.length" class="bound-novels">
            <p class="bound-label">项目已绑定参考小说：</p>
            <div class="bound-chips">
              <span v-for="novel in boundReferenceNovels" :key="novel.id" class="bound-chip">
                <span class="chip-title">{{ novel.title }}</span>
                <span class="chip-status">{{ novel.status }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="config-section">
          <button @click="showExclusions = !showExclusions" class="exclusion-toggle">
            <svg
              class="toggle-arrow"
              :style="{ transform: showExclusions ? 'rotate(90deg)' : 'rotate(0deg)' }"
              fill="currentColor" viewBox="0 0 20 20"
            >
              <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
            </svg>
            创作禁区（可选）
          </button>
          <div v-if="showExclusions" class="exclusion-body">
            <textarea
              v-model="exclusions"
              placeholder="例如：不要后宫、不要重生穿越..."
              rows="3"
              class="exclusion-textarea"
            />
            <p class="exclusion-hint">AI 将在整个对话和蓝图生成中遵守这些限制</p>
          </div>
        </div>

        <!-- ── 缪斯设定（分档特性）── -->
        <div class="muse-config">
          <div class="muse-config-head">
            <span class="muse-config-title">缪斯设定</span>
            <span class="tier-badge" :class="`tier-${userTier}`">
              {{ userTier === 'flagship' ? '旗舰' : userTier === 'creator' ? '创作者' : '免费' }}
            </span>
          </div>

          <!-- 缪斯人格选择（创作者档+）-->
          <label class="muse-field-label">
            缪斯人格
            <span v-if="!canUsePersona" class="lock-hint">🔒 创作者档</span>
          </label>
          <select v-model="selectedPersona" :disabled="!canUsePersona" class="muse-select">
            <option v-for="p in musePersonas" :key="p.key" :value="p.key">{{ p.label }}</option>
          </select>
          <p v-if="canUsePersona" class="muse-field-hint">
            {{ musePersonas.find((p) => p.key === selectedPersona)?.blurb || '' }}
          </p>

          <!-- 一键找素材（创作者档+）-->
          <label class="muse-toggle" :class="{ disabled: !canUseMuseSearch }">
            <input type="checkbox" :checked="canUseMuseSearch && !disableMuseSearch"
                   :disabled="!canUseMuseSearch"
                   @change="disableMuseSearch = !($event.target as HTMLInputElement).checked" />
            <span>开场跨界找素材（联网）<span v-if="!canUseMuseSearch" class="lock-hint">🔒 创作者档</span></span>
          </label>

          <!-- 灵感扰动（免费）-->
          <label class="muse-toggle">
            <input type="checkbox" :checked="!disableSpark"
                   @change="disableSpark = !($event.target as HTMLInputElement).checked" />
            <span>灵感扰动（每轮随机激发）</span>
          </label>
        </div>

        <div class="config-cta">
          <button
            @click="startConversation"
            :disabled="novelStore.isLoading || isPreparingConversation"
            class="start-btn"
            :class="{ disabled: novelStore.isLoading || isPreparingConversation }"
          >
            {{ isPreparingConversation || novelStore.isLoading ? '正在准备...' : '⚡ 开启灵感模式' }}
          </button>
          <button @click="goBack" class="back-link">返回首页</button>
        </div>
      </div>

      <!-- ── POST-START: status panel ── -->
      <div v-else class="sidebar-status">
        <div class="status-card">
          <div class="status-row">
            <span class="status-dot-wrap">
              <span class="status-ping"></span>
              <span class="status-dot"></span>
            </span>
            <span class="status-label">{{ showBlueprint ? '蓝图已生成' : showBlueprintConfirmation ? '信息收集完成' : '对话进行中' }}</span>
          </div>
          <div v-if="currentTurn > 0" class="status-turn">第 {{ currentTurn }} 轮对话</div>
        </div>

        <div v-if="normalizedReferenceNovels.length" class="sidebar-refs">
          <p class="refs-label">参考小说</p>
          <div class="refs-chips">
            <span v-for="r in normalizedReferenceNovels" :key="r" class="ref-chip">📚 {{ r }}</span>
          </div>
        </div>

        <div v-if="exclusions.trim()" class="sidebar-exclusion-summary">
          <p class="refs-label">创作禁区</p>
          <p class="exclusion-summary-text">{{ exclusions }}</p>
        </div>

        <div class="sidebar-actions">
          <button @click="handleRestart" class="action-btn">
            <svg class="action-icon" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
            </svg>
            重新开始
          </button>
          <button @click="exitConversation" class="action-btn action-exit">
            <svg class="action-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            退出
          </button>
        </div>
      </div>
    </aside>

    <!-- ──────────── RIGHT MAIN PANEL ──────────── -->
    <main class="chat-panel">

      <!-- Empty state before start -->
      <div v-if="!conversationStarted" class="chat-empty">
        <div class="empty-icon">✦</div>
        <p class="empty-title">准备好了吗？</p>
        <p class="empty-sub">在左侧配置好参考小说，点击「开启灵感模式」开始与文思对话。</p>
      </div>

      <!-- Chat area (always rendered once started) -->
      <template v-else>
        <div class="chat-scroll" ref="chatArea">
          <!-- Loading spinner for initial AI response -->
          <transition name="fade">
            <InspirationLoading v-if="isInitialLoading" class="chat-loading" />
          </transition>

          <!-- Chat bubbles -->
          <ChatBubble
            v-for="(message, index) in chatMessages"
            :key="index"
            :message="message.content"
            :type="message.type"
          />

          <!-- Blueprint confirmation flows inline after chat -->
          <div v-if="showBlueprintConfirmation" class="inline-blueprint-wrap">
            <BlueprintConfirmation
              :ai-message="confirmationMessage"
              @blueprint-generated="handleBlueprintGenerated"
              @back="backToConversation"
            />
          </div>

          <!-- Blueprint display flows inline after chat -->
          <div v-if="showBlueprint" class="inline-blueprint-wrap">
            <BlueprintDisplay
              :blueprint="completedBlueprint"
              :ai-message="blueprintMessage"
              @confirm="handleConfirmBlueprint"
              @regenerate="handleRegenerateBlueprint"
            />
          </div>
        </div>

        <!-- N 路发散结果卡片（旗舰档）-->
        <div v-if="divergeSeeds.length" class="diverge-results">
          <div class="diverge-results-head">缪斯给了你 {{ divergeSeeds.length }} 个迥异方向，挑一个继续（其余会保留，可继续对比 / 再挑）：</div>
          <div class="diverge-cards">
            <button
              v-for="seed in divergeSeeds"
              :key="seed.id"
              class="diverge-card"
              :class="{ 'is-picked': pickedSeedIds.includes(seed.id) }"
              @click="pickDivergeSeed(seed)"
            >
              <div class="diverge-card-title">
                <span class="diverge-card-name">
                  {{ seed.title || '未命名方向' }}
                  <span v-if="pickedSeedIds.includes(seed.id)" class="diverge-picked-badge">已投喂</span>
                </span>
                <span v-if="typeof seed.score === 'number'" class="diverge-score">{{ seed.score }}/30</span>
              </div>
              <div class="diverge-card-logline">{{ seed.logline }}</div>
              <div v-if="seed.hook" class="diverge-card-hook">🪝 {{ seed.hook }}</div>
              <div v-if="seed.twist" class="diverge-card-twist">🔄 {{ seed.twist }}</div>
              <div v-if="seed.verdict" class="diverge-card-verdict">{{ seed.verdict }}</div>
            </button>
          </div>
        </div>

        <!-- Input bar (hidden when blueprint confirmation/display is showing) -->
        <div
          v-if="!showBlueprintConfirmation && !showBlueprint"
          class="chat-input-bar"
        >
          <button
            v-if="canUseDivergence"
            class="diverge-trigger"
            :disabled="isDiverging || novelStore.isLoading"
            @click="handleDiverge"
            title="一次生成 5 个迥异世界观种子并智能评分（旗舰）"
          >
            {{ isDiverging ? '✨ 缪斯发散中…' : '✨ 给我 5 个狂点子' }}
          </button>
          <!-- 缪斯发散中：隐藏并禁用选项/输入/发送，改显发散进度状态 -->
          <InlineProgress
            v-if="isDiverging"
            label="缪斯正在发散 5 个迥异方向并打分…"
            hint="发散需两次模型调用（先生成、再评分），稍慢属正常，请勿离开页面。"
          />
          <ConversationInput
            v-else
            :ui-control="currentUIControl"
            :loading="novelStore.isLoading"
            @submit="handleUserInput"
          />
        </div>
      </template>
    </main>

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
const isInitialLoading = ref(false)
const showBlueprintConfirmation = ref(false)
const showBlueprint = ref(false)
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
      librarySelections.value = []
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

const bindReferencesIfNeeded = async () => {
  const projectId = novelStore.currentProject?.id
  if (!projectId) return
  const ids = selectedReferenceNovelIds.value
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

const resetInspirationMode = (options: { keepReferenceNovels?: boolean } = {}) => {
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
  exclusions.value = ''
  showExclusions.value = false

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

  resetInspirationMode({ keepReferenceNovels: true })
  isPreparingConversation.value = true

  try {
    await novelStore.createProject('未命名灵感', '开始灵感模式')

    if (selectedReferenceNovels.length > 0) {
      referenceSearchStatus.value = 'searching'
      referenceSearchMessage.value = `正在搜索 ${selectedReferenceNovels.length} 本参考小说...`
      try {
        const result = await novelStore.searchReferenceNovels(selectedReferenceNovels)
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
        referenceSearchMessage.value = '参考小说搜索失败，已自动降级为普通灵感模式'
        referenceContext.value = ''
      }
    }

    conversationStarted.value = true
    isInitialLoading.value = true

    await handleUserInput(null, {
      referenceNovels: selectedReferenceNovels,
      referenceContext: referenceContext.value
    })
  } catch (error) {
    console.error('启动灵感模式失败:', error)
    globalAlert.showError(`无法开始灵感模式: ${error instanceof Error ? error.message : '未知错误'}`, '启动失败')
    resetInspirationMode({ keepReferenceNovels: true })
  } finally {
    isPreparingConversation.value = false
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
    globalAlert.showError(`生成蓝图失败: ${error instanceof Error ? error.message : '未知错误'}`, '生成失败')
  }
}

const handleBlueprintGenerated = async (response: any) => {
  console.log('收到蓝图生成完成事件:', response)
  completedBlueprint.value = response.blueprint
  blueprintMessage.value = response.ai_message
  showBlueprintConfirmation.value = false
  showBlueprint.value = true
  await bindReferencesIfNeeded()
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
/* ──────────── Shell Layout ──────────── */
.inspiration-shell {
  display: flex;
  height: 100vh;
  background: #0A0A0A;
  overflow: hidden;
  font-family: 'Inter', sans-serif;
}

/* ──────────── Sidebar ──────────── */
.sidebar {
  width: 320px;
  flex-shrink: 0;
  background: #141414;
  border-right: 1px solid #2A2A2A;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-brand {
  padding: 20px 20px 16px;
  border-bottom: 1px solid #2A2A2A;
  flex-shrink: 0;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.brand-accent {
  color: #FFE500;
  font-size: 18px;
  font-weight: 700;
}

.brand-name {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 16px;
  font-weight: 700;
  color: #FFFFFF;
  letter-spacing: -0.01em;
}

.brand-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
  border-radius: 999px;
  font-size: 12px;
  color: #888;
}

/* ── Config Panel ── */
.sidebar-config {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.sidebar-config::-webkit-scrollbar { width: 4px; }
.sidebar-config::-webkit-scrollbar-track { background: transparent; }
.sidebar-config::-webkit-scrollbar-thumb { background: #2A2A2A; border-radius: 4px; }

.config-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.config-headline {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 24px;
  font-weight: 900;
  color: #FFFFFF;
  line-height: 1.2;
  margin: 0;
}

.config-sub {
  font-size: 13px;
  color: #888;
  line-height: 1.6;
  margin: 0;
}

.ref-selected-hint {
  font-size: 12px;
  color: #888;
  margin-top: 4px;
}

.bound-novels {
  margin-top: 8px;
  background: #1C1C1C;
  border: 1px dashed #2A2A2A;
  padding: 10px 12px;
  border-radius: 10px;
}

.bound-label {
  font-size: 11px;
  color: #888;
  margin: 0 0 6px;
}

.bound-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.bound-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 999px;
  background: #141414;
  border: 1px solid #2A2A2A;
  font-size: 12px;
  color: #FFFFFF;
}

.chip-title { font-weight: 600; }

.chip-status {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 999px;
  background: rgba(255,229,0,0.12);
  color: #FFE500;
}

.exclusion-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  cursor: pointer;
  color: #888;
  font-size: 13px;
  padding: 0;
  transition: color 0.15s;
}

.exclusion-toggle:hover { color: #CCC; }

.toggle-arrow {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
  transition: transform 0.2s;
}

.exclusion-body {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.exclusion-textarea {
  width: 100%;
  padding: 10px 12px;
  font-size: 12px;
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
  border-radius: 10px;
  color: #FFFFFF;
  outline: none;
  resize: none;
  box-sizing: border-box;
  font-family: 'Inter', sans-serif;
  transition: border-color 0.15s;
}

.exclusion-textarea:focus { border-color: #FFE500; }

.exclusion-hint {
  font-size: 11px;
  color: #555;
  margin: 0;
}

.config-cta {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding-top: 4px;
}

.start-btn {
  width: 100%;
  background: #FFE500;
  color: #000;
  font-weight: 700;
  font-size: 15px;
  padding: 13px 0;
  border-radius: 999px;
  border: none;
  cursor: pointer;
  font-family: 'Space Grotesk', sans-serif;
  transition: opacity 0.2s, transform 0.15s;
}

.start-btn:hover:not(.disabled) { opacity: 0.9; transform: translateY(-1px); }
.start-btn.disabled { opacity: 0.45; cursor: not-allowed; }

.back-link {
  background: none;
  border: none;
  cursor: pointer;
  color: #555;
  font-size: 13px;
  transition: color 0.15s;
}

.back-link:hover { color: #888; }

/* ── Status Panel ── */
.sidebar-status {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-card {
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-dot-wrap {
  position: relative;
  display: inline-flex;
  width: 10px;
  height: 10px;
  flex-shrink: 0;
}

.status-ping {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: #FFE500;
  opacity: 0.55;
  animation: ping 1.5s ease-in-out infinite;
}

.status-dot {
  position: relative;
  border-radius: 50%;
  width: 10px;
  height: 10px;
  background: #FFE500;
  display: block;
}

.status-label {
  font-size: 13px;
  font-weight: 600;
  color: #FFE500;
}

.status-turn {
  font-size: 12px;
  color: #888;
}

.sidebar-refs {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.refs-label {
  font-size: 11px;
  color: #555;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0;
}

.refs-chips {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ref-chip {
  font-size: 12px;
  color: #CCCCCC;
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
  padding: 4px 10px;
  border-radius: 8px;
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-exclusion-summary {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.exclusion-summary-text {
  font-size: 12px;
  color: #888;
  line-height: 1.5;
  margin: 0;
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
  padding: 8px 10px;
  border-radius: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.sidebar-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: auto;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
  border-radius: 10px;
  color: #888;
  font-size: 13px;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
  text-align: left;
}

.action-btn:hover { color: #CCCCCC; border-color: #444; background: #222; }
.action-exit:hover { color: #FF4757; border-color: #FF4757; }

.action-icon {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
}

/* ──────────── Chat Panel ──────────── */
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #0A0A0A;
}

/* Empty placeholder */
.chat-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  padding: 40px;
}

.empty-icon {
  font-size: 48px;
  color: #2A2A2A;
  line-height: 1;
  margin-bottom: 4px;
}

.empty-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: #444;
  margin: 0;
}

.empty-sub {
  font-size: 14px;
  color: #333;
  max-width: 320px;
  line-height: 1.6;
  margin: 0;
}

/* Chat scroll area */
.chat-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.chat-scroll::-webkit-scrollbar { width: 5px; }
.chat-scroll::-webkit-scrollbar-track { background: transparent; }
.chat-scroll::-webkit-scrollbar-thumb { background: #2A2A2A; border-radius: 5px; }

.chat-loading {
  align-self: center;
}

/* Inline blueprint panels */
.inline-blueprint-wrap {
  margin-top: 8px;
}

/* Input bar */
.chat-input-bar {
  padding: 16px 24px;
  border-top: 1px solid #1C1C1C;
  background: #0D0D0D;
  flex-shrink: 0;
}

/* ──────────── Animations ──────────── */
@keyframes ping {
  0%, 100% { transform: scale(1); opacity: 0.55; }
  50% { transform: scale(1.7); opacity: 0; }
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* ──────────── Mobile ──────────── */
@media (max-width: 768px) {
  .inspiration-shell {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    max-height: 50vh;
    border-right: none;
    border-bottom: 1px solid #2A2A2A;
  }

  .chat-panel {
    flex: 1;
    min-height: 0;
  }
}

/* ──────────── 缪斯设定 / N路发散 ──────────── */
.muse-config {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
}
.muse-config-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.muse-config-title { font-size: 13px; font-weight: 600; opacity: 0.9; }
.tier-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid currentColor;
}
.tier-free { color: #9aa0a6; }
.tier-creator { color: #6ad29a; }
.tier-flagship { color: #f5c451; }
.muse-field-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; opacity: 0.85; margin: 8px 0 4px;
}
.lock-hint { font-size: 11px; opacity: 0.7; }
.muse-select {
  width: 100%;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.25);
  color: inherit;
  border: 1px solid rgba(255, 255, 255, 0.12);
}
.muse-select:disabled { opacity: 0.5; cursor: not-allowed; }
.muse-field-hint { font-size: 11px; opacity: 0.6; margin: 4px 0 0; }
.muse-toggle {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; margin-top: 10px; cursor: pointer;
}
.muse-toggle.disabled { opacity: 0.55; cursor: not-allowed; }

.diverge-results { padding: 10px 16px; }
.diverge-results-head { font-size: 13px; opacity: 0.85; margin-bottom: 8px; }
.diverge-cards { display: flex; flex-direction: column; gap: 8px; }
.diverge-card {
  text-align: left;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.diverge-card:hover { border-color: #f5c451; background: rgba(245, 196, 81, 0.08); }
.diverge-card.is-picked { border-color: rgba(245, 196, 81, 0.5); background: rgba(245, 196, 81, 0.06); }
.diverge-card-title {
  display: flex; align-items: center; justify-content: space-between;
  font-weight: 600; font-size: 14px; margin-bottom: 4px;
}
.diverge-card-name { display: inline-flex; align-items: center; gap: 6px; }
.diverge-picked-badge {
  font-size: 11px; font-weight: 600;
  color: #0A0A0A; background: #f5c451;
  border-radius: 6px; padding: 1px 6px;
}
.diverge-score { font-size: 12px; color: #f5c451; }
.diverge-card-logline { font-size: 13px; opacity: 0.9; }
.diverge-card-hook,
.diverge-card-twist { font-size: 12px; opacity: 0.75; margin-top: 4px; }
.diverge-card-verdict { font-size: 11px; opacity: 0.6; margin-top: 6px; font-style: italic; }
.diverge-trigger {
  align-self: stretch;
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid #f5c451;
  background: rgba(245, 196, 81, 0.12);
  color: #f5c451;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.diverge-trigger:disabled { opacity: 0.6; cursor: not-allowed; }
</style>

<!-- AIMETA P=灵感模式_AI对话创作|R=对话创作界面|NR=不含写作台功能|E=route:/inspiration#component:InspirationMode|X=ui|A=对话界面|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="inspiration-shell">

    <!-- ──────────── LEFT SIDEBAR ──────────── -->
    <aside class="sidebar">
      <!-- Brand header -->
      <div class="sidebar-brand">
        <div class="brand-logo">
          <span class="brand-accent">✦</span>
          <span class="brand-name">Arboris Novel</span>
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

        <!-- Input bar (hidden when blueprint confirmation/display is showing) -->
        <div
          v-if="!showBlueprintConfirmation && !showBlueprint"
          class="chat-input-bar"
        >
          <ConversationInput
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
import { NovelAPI, type ReferenceNovelSummary, type UIControl, type Blueprint } from '@/api/novel'
import ChatBubble from '@/components/ChatBubble.vue'
import ConversationInput from '@/components/ConversationInput.vue'
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
  router.push('/')
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
    router.push('/')
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
      ...(exclusions.value.trim() ? { exclusions: exclusions.value.trim() } : {})
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

onMounted(() => {
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
</style>

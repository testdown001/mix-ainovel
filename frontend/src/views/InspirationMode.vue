<!-- AIMETA P=灵感模式_AI对话创作|R=对话创作界面|NR=不含写作台功能|E=route:/inspiration#component:InspirationMode|X=ui|A=对话界面|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="im-root">
    <div class="w-full max-w-6xl mx-auto">
      <!-- Landing / Entry -->
      <div v-if="!conversationStarted" class="im-landing im-fade-in">
        <h1 class="im-hero-title">小说家的新篇章</h1>
        <p class="im-hero-sub">
          准备好释放你的创造力了吗？让AI引导你，一步步构建出独一无二的故事世界。
        </p>
        <ReferenceNovelInput
          v-model="referenceNovels"
          :search-status="referenceSearchStatus"
          :status-message="referenceSearchMessage"
          @library-selection-change="handleLibrarySelectionChange"
        />
        <div v-if="librarySelectionsWithNames.length" class="im-ref-hint">
          已从库中选择参考小说：
          <strong>{{ librarySelectionsWithNames.join(' / ') }}</strong>
        </div>
        <div v-if="boundReferenceNovels.length" class="im-bound-panel">
          <p>当前项目已绑定的参考小说：</p>
          <div class="im-bound-list">
            <span v-for="novel in boundReferenceNovels" :key="novel.id" class="im-ref-chip">
              <span class="im-ref-chip-title">{{ novel.title }}</span>
              <span class="im-ref-chip-status">{{ novel.status }}</span>
            </span>
          </div>
        </div>
        <!-- Exclusions (collapsible) -->
        <div class="mt-4 mb-6 max-w-xl mx-auto text-left">
          <button
            @click="showExclusions = !showExclusions"
            class="im-exclusion-toggle"
          >
            <svg
              class="w-4 h-4 transition-transform duration-200"
              :class="{ 'rotate-90': showExclusions }"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
            </svg>
            创作禁区（可选）
          </button>
          <div v-if="showExclusions" class="mt-2">
            <textarea
              v-model="exclusions"
              placeholder="例如：不要后宫、不要重生穿越、禁止无脑打脸升级..."
              rows="3"
              class="im-textarea"
            />
            <p class="im-hint-text">AI 将在整个概念对话和蓝图生成中遵守这些限制</p>
          </div>
        </div>
        <button
          @click="startConversation"
          :disabled="novelStore.isLoading || isPreparingConversation"
          class="im-btn-start"
        >
          {{ isPreparingConversation || novelStore.isLoading ? '正在准备...' : '开启灵感模式' }}
        </button>
        <button
          @click="goBack"
          class="im-btn-back"
        >
          返回
        </button>
      </div>

      <!-- Conversation Interface -->
      <div
        v-else-if="!showBlueprintConfirmation && !showBlueprint"
        class="im-chat-shell im-fade-in"
      >
        <!-- Header -->
        <div class="im-chat-header">
          <div class="flex justify-between items-center">
            <div class="flex items-center gap-2">
              <span class="im-pulse-indicator">
                <span class="im-pulse-ring"></span>
                <span class="im-pulse-core"></span>
              </span>
              <span class="im-chat-status">与"文思"对话中...</span>
            </div>
            <div class="flex items-center gap-4">
              <span v-if="currentTurn > 0" class="im-turn-badge">
                第 {{ currentTurn }} 轮
              </span>
              <button
                @click="handleRestart"
                title="重新开始"
                class="im-header-btn"
              >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                </svg>
              </button>
              <button
                @click="exitConversation"
                title="返回首页"
                class="im-header-btn"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  class="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Chat Area -->
        <div class="im-chat-area" ref="chatArea">
          <transition name="fade">
            <InspirationLoading v-if="isInitialLoading" />
          </transition>
          <ChatBubble
            v-for="(message, index) in chatMessages"
            :key="index"
            :message="message.content"
            :type="message.type"
          />
        </div>

        <!-- Input Area -->
        <div class="im-chat-input">
          <ConversationInput
            :ui-control="currentUIControl"
            :loading="novelStore.isLoading"
            @submit="handleUserInput"
          />
        </div>
      </div>

      <!-- Blueprint Confirmation -->
      <BlueprintConfirmation
        v-if="showBlueprintConfirmation"
        :ai-message="confirmationMessage"
        @blueprint-generated="handleBlueprintGenerated"
        @back="backToConversation"
      />

      <!-- Blueprint Display -->
      <BlueprintDisplay
        v-if="showBlueprint"
        :blueprint="completedBlueprint"
        :ai-message="blueprintMessage"
        @confirm="handleConfirmBlueprint"
        @regenerate="handleRegenerateBlueprint"
      />
    </div>
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

// 清空所有状态，开始新的灵感对话
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

  // 清空 store 中的当前项目和对话状态
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

  // 重置所有状态，开始全新的对话
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

    // 发起第一次对话
    await handleUserInput(null, {
      referenceNovels: selectedReferenceNovels,
      referenceContext: referenceContext.value
    })
  } catch (error) {
    console.error('启动灵感模式失败:', error)
    globalAlert.showError(`无法开始灵感模式: ${error instanceof Error ? error.message : '未知错误'}`, '启动失败')
    resetInspirationMode({ keepReferenceNovels: true }) // 失败时保留参考小说输入
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
        } else { // assistant
          try {
            const assistantOutput = JSON.parse(item.content)
            return { content: assistantOutput.ai_message, type: 'ai' }
          } catch {
            return { content: item.content, type: 'ai' }
          }
        }
      }).filter((msg): msg is ChatMessage => msg !== null && msg.content !== null) // 过滤掉空的 user message

      const lastAssistantMsgStr = project.conversation_history.filter(m => m.role === 'assistant').pop()?.content
      if (lastAssistantMsgStr) {
        const lastAssistantMsg = JSON.parse(lastAssistantMsgStr)
        
        if (lastAssistantMsg.is_complete) {
          // 如果对话已完成，直接显示蓝图确认界面
          confirmationMessage.value = lastAssistantMsg.ai_message
          showBlueprintConfirmation.value = true
        } else {
          // 否则，恢复对话
          currentUIControl.value = lastAssistantMsg.ui_control
        }
      }
      // 计算当前轮次
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
    // 如果有用户输入，添加到聊天记录
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

    // 首次加载完成后，关闭加载动画
    if (isInitialLoading.value) {
      isInitialLoading.value = false
    }

    // 添加AI回复到聊天记录
    chatMessages.value.push({
      content: response.ai_message,
      type: 'ai'
    })
    currentTurn.value++

    await scrollToBottom()

    if (response.is_complete && response.ready_for_blueprint) {
      // 对话完成，显示蓝图确认界面
      confirmationMessage.value = response.ai_message
      showBlueprintConfirmation.value = true
    } else if (response.is_complete) {
      // 向后兼容：直接生成蓝图（如果后端还没更新）
      await handleGenerateBlueprint()
    } else {
      // 继续对话
      currentUIControl.value = response.ui_control
    }
  } catch (error) {
    console.error('对话失败:', error)
    // 确保在出错时也停止初始加载状态
    if (isInitialLoading.value) {
      isInitialLoading.value = false
    }
    globalAlert.showError(`抱歉，与AI连接时遇到问题: ${error instanceof Error ? error.message : '未知错误'}`, '通信失败')
    // 停止加载并返回初始界面
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
}

const handleRegenerateBlueprint = () => {
  showBlueprint.value = false
  showBlueprintConfirmation.value = true
}

const handleConfirmBlueprint = async () => {
  if (!completedBlueprint.value) {
    globalAlert.showError('蓝图数据缺失，请重新生成或稍后重试。', '保存失败')
    return
  }
  try {
    await novelStore.saveBlueprint(completedBlueprint.value)
    // 跳转到写作工作台
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
    // 每次进入灵感模式都重置状态，确保没有缓存
    resetInspirationMode()
  }
})
</script>

<style scoped>
/* Root */
.im-root {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 64px);
  padding: 1rem;
  font-family: var(--ar-font-ui);
}

/* Landing */
.im-landing {
  text-align: center;
  padding: 2rem;
  background-color: #0f1419;
  border-radius: 4px;
  border: 1px solid rgba(77, 70, 50, 0.15);
}

.im-hero-title {
  font-family: var(--ar-font-display);
  font-size: clamp(2rem, 5vw, 3rem);
  font-weight: 700;
  color: #dee3eb;
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.im-hero-sub {
  font-family: var(--ar-font-ui);
  font-size: 1.05rem;
  color: #8b929a;
  margin-top: 1rem;
  margin-bottom: 2rem;
  line-height: 1.6;
}

/* Reference hints */
.im-ref-hint {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #8b929a;
}

.im-ref-hint strong {
  color: #FACC15;
}

.im-bound-panel {
  margin-top: 0.75rem;
  background: #171c22;
  border: 1px dashed rgba(77, 70, 50, 0.25);
  padding: 0.75rem;
  border-radius: 4px;
}

.im-bound-panel p {
  margin: 0 0 0.25rem;
  font-size: 0.75rem;
  color: #8b929a;
}

.im-bound-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.im-ref-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  background: #252a30;
  border: 1px solid rgba(77, 70, 50, 0.15);
  font-size: 0.8rem;
  color: #dee3eb;
}

.im-ref-chip-title {
  font-weight: 600;
}

.im-ref-chip-status {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  background: rgba(74, 222, 128, 0.1);
  color: #4ADE80;
  text-transform: capitalize;
}

/* Exclusions */
.im-exclusion-toggle {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  color: #545d68;
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.2s;
}

.im-exclusion-toggle:hover {
  color: #8b929a;
}

.im-textarea {
  width: 100%;
  padding: 0.5rem 0.75rem;
  font-family: var(--ar-font-ui);
  font-size: 0.875rem;
  color: #dee3eb;
  background-color: #171c22;
  border: 1px solid rgba(77, 70, 50, 0.15);
  border-radius: 4px;
  resize: none;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.im-textarea::placeholder {
  color: #545d68;
}

.im-textarea:focus {
  border-color: rgba(250, 204, 21, 0.4);
  box-shadow: 0 0 0 2px rgba(250, 204, 21, 0.08);
}

.im-hint-text {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: #545d68;
}

/* CTA buttons */
.im-btn-start {
  font-family: var(--ar-font-display);
  font-size: 1rem;
  font-weight: 600;
  padding: 0.75rem 2rem;
  border-radius: 4px;
  border: 1px solid rgba(250, 204, 21, 0.5);
  background-color: rgba(250, 204, 21, 0.12);
  color: #FACC15;
  cursor: pointer;
  transition: background-color 0.2s, border-color 0.2s, box-shadow 0.3s, transform 0.15s;
  letter-spacing: 0.02em;
}

.im-btn-start:hover:not(:disabled) {
  background-color: rgba(250, 204, 21, 0.2);
  border-color: rgba(250, 204, 21, 0.7);
  box-shadow: 0 0 24px rgba(250, 204, 21, 0.12);
  transform: translateY(-1px);
}

.im-btn-start:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.im-btn-back {
  display: block;
  margin: 1rem auto 0;
  font-family: var(--ar-font-ui);
  font-size: 0.875rem;
  color: #545d68;
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.2s;
}

.im-btn-back:hover {
  color: #dee3eb;
}

/* Chat shell */
.im-chat-shell {
  height: 90vh;
  max-height: 950px;
  display: flex;
  flex-direction: column;
  background-color: #0f1419;
  border-radius: 4px;
  border: 1px solid rgba(77, 70, 50, 0.15);
  overflow: hidden;
}

.im-chat-header {
  padding: 1rem;
  border-bottom: 1px solid rgba(77, 70, 50, 0.15);
}

/* Pulse indicator */
.im-pulse-indicator {
  position: relative;
  display: inline-flex;
  width: 0.75rem;
  height: 0.75rem;
}

.im-pulse-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background-color: #4ADE80;
  animation: im-pulse-anim 2s ease-in-out infinite;
}

.im-pulse-core {
  position: relative;
  display: inline-flex;
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 50%;
  background-color: #4ADE80;
}

@keyframes im-pulse-anim {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 0; transform: scale(2); }
}

.im-chat-status {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 500;
  color: #4ADE80;
}

.im-turn-badge {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 500;
  color: #545d68;
  background-color: #171c22;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  border: 1px solid rgba(77, 70, 50, 0.15);
}

.im-header-btn {
  color: #545d68;
  background: none;
  border: none;
  cursor: pointer;
  transition: color 0.2s;
}

.im-header-btn:hover {
  color: #FACC15;
}

/* Chat area */
.im-chat-area {
  flex: 1;
  padding: 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  position: relative;
}

.im-chat-area::-webkit-scrollbar {
  width: 4px;
}

.im-chat-area::-webkit-scrollbar-track {
  background: transparent;
}

.im-chat-area::-webkit-scrollbar-thumb {
  background-color: rgba(77, 70, 50, 0.3);
  border-radius: 4px;
}

/* Input area */
.im-chat-input {
  padding: 1rem;
  border-top: 1px solid rgba(77, 70, 50, 0.15);
  background-color: #171c22;
}

/* Fade animation */
.im-fade-in {
  animation: im-fade 0.4s ease-out;
}

@keyframes im-fade {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

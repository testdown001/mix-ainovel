<!-- AIMETA P=灵感模式_AI对话创作|R=对话创作界面|NR=不含写作台功能|E=route:/inspiration#component:InspirationMode|X=ui|A=对话界面|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="flex items-center justify-center min-h-screen p-4" style="background: #0A0A0A;">
    <div class="w-full max-w-6xl mx-auto">
      <!-- 灵感模式入口界面 -->
      <div v-if="!conversationStarted" class="fade-in" style="background: #141414; border: 1px solid #2A2A2A; border-radius: 20px; padding: 48px 40px; max-width: 760px; margin: 0 auto;">
        <!-- Header -->
        <div class="text-center mb-10">
          <div style="display: inline-flex; align-items: center; gap: 10px; margin-bottom: 20px; padding: 8px 20px; background: #1C1C1C; border: 1px solid #2A2A2A; border-radius: 999px;">
            <span style="color: #FFE500; font-size: 16px;">💡</span>
            <span style="color: #888; font-size: 13px; font-weight: 500;">灵感模式</span>
          </div>
          <h1 style="font-family: 'Space Grotesk', sans-serif; font-size: 40px; font-weight: 900; color: #fff; line-height: 1.15; margin-bottom: 12px;">
            小说家的<span style="color: #FFE500;">新篇章</span>
          </h1>
          <p style="color: #888; font-size: 15px; line-height: 1.7; max-width: 480px; margin: 0 auto;">
            准备好释放你的创造力了吗？让AI引导你，一步步构建出独一无二的故事世界。
          </p>
        </div>

        <!-- Reference novel input -->
        <ReferenceNovelInput
          v-model="referenceNovels"
          :search-status="referenceSearchStatus"
          :status-message="referenceSearchMessage"
          @library-selection-change="handleLibrarySelectionChange"
        />

        <div v-if="librarySelectionsWithNames.length" style="margin-top: 8px; font-size: 13px; color: #888;">
          已从库中选择参考小说：
          <strong style="color: #FFE500;">{{ librarySelectionsWithNames.join(' / ') }}</strong>
        </div>

        <div v-if="boundReferenceNovels.length" style="margin-top: 12px; background: #1C1C1C; border: 1px dashed #2A2A2A; padding: 12px 14px; border-radius: 12px;">
          <p style="margin: 0 0 6px; font-size: 12px; color: #888;">当前项目已绑定的参考小说：</p>
          <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            <span v-for="novel in boundReferenceNovels" :key="novel.id" style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; background: #141414; border: 1px solid #2A2A2A; font-size: 13px; color: #fff;">
              <span style="font-weight: 600;">{{ novel.title }}</span>
              <span style="font-size: 11px; padding: 1px 6px; border-radius: 999px; background: #FFE50022; color: #FFE500;">{{ novel.status }}</span>
            </span>
          </div>
        </div>

        <!-- 创作禁区 (collapsible) -->
        <div style="margin-top: 20px; margin-bottom: 28px;">
          <button
            @click="showExclusions = !showExclusions"
            style="display: flex; align-items: center; gap: 6px; background: none; border: none; cursor: pointer; color: #888; font-size: 14px; padding: 0;"
          >
            <svg
              style="width: 14px; height: 14px; transition: transform 0.2s; flex-shrink: 0;"
              :style="{ transform: showExclusions ? 'rotate(90deg)' : 'rotate(0deg)' }"
              fill="currentColor" viewBox="0 0 20 20"
            >
              <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
            </svg>
            创作禁区（可选）
          </button>
          <div v-if="showExclusions" style="margin-top: 10px;">
            <textarea
              v-model="exclusions"
              placeholder="例如：不要后宫、不要重生穿越、禁止无脑打脸升级..."
              rows="3"
              style="width: 100%; padding: 12px 14px; font-size: 13px; background: #1C1C1C; border: 1px solid #2A2A2A; border-radius: 12px; color: #fff; outline: none; resize: none; box-sizing: border-box;"
            />
            <p style="margin-top: 6px; font-size: 12px; color: #888;">AI 将在整个概念对话和蓝图生成中遵守这些限制</p>
          </div>
        </div>

        <!-- CTA -->
        <div class="text-center">
          <button
            @click="startConversation"
            :disabled="novelStore.isLoading || isPreparingConversation"
            style="background: #FFE500; color: #000; font-weight: 700; font-size: 16px; padding: 14px 48px; border-radius: 999px; border: none; cursor: pointer; transition: opacity 0.2s; font-family: 'Space Grotesk', sans-serif;"
            :style="{ opacity: (novelStore.isLoading || isPreparingConversation) ? 0.5 : 1, cursor: (novelStore.isLoading || isPreparingConversation) ? 'not-allowed' : 'pointer' }"
          >
            {{ isPreparingConversation || novelStore.isLoading ? '正在准备...' : '⚡ 开启灵感模式' }}
          </button>
          <br>
          <button
            @click="goBack"
            style="margin-top: 16px; background: none; border: none; cursor: pointer; color: #888; font-size: 14px; display: inline-block;"
          >
            返回
          </button>
        </div>
      </div>

      <!-- 灵感模式交互界面 -->
      <div
        v-else-if="!showBlueprintConfirmation && !showBlueprint"
        class="fade-in"
        style="height: 90vh; max-height: 950px; display: flex; flex-direction: column; background: #141414; border: 1px solid #2A2A2A; border-radius: 20px; overflow: hidden;"
      >
        <!-- 头部 -->
        <div style="padding: 14px 20px; border-bottom: 1px solid #1C1C1C; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="position: relative; display: inline-flex; width: 10px; height: 10px;">
              <span style="position: absolute; inset: 0; border-radius: 50%; background: #FFE500; opacity: 0.6; animation: ping 1.5s ease-in-out infinite;"></span>
              <span style="position: relative; border-radius: 50%; width: 10px; height: 10px; background: #FFE500; display: block;"></span>
            </span>
            <span style="font-size: 14px; font-weight: 600; color: #FFE500;">与"文思"对话中...</span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <span v-if="currentTurn > 0" style="font-size: 13px; color: #888; background: #1C1C1C; padding: 4px 10px; border-radius: 8px;">
              第 {{ currentTurn }} 轮
            </span>
            <button
              @click="handleRestart"
              title="重新开始"
              style="background: none; border: none; cursor: pointer; color: #888; display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 8px;"
            >
              <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
            </button>
            <button
              @click="exitConversation"
              title="返回首页"
              style="background: none; border: none; cursor: pointer; color: #888; display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 8px;"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <!-- 聊天区域 -->
        <div style="flex: 1; padding: 24px; overflow-y: auto; display: flex; flex-direction: column; gap: 20px;" ref="chatArea">
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

        <!-- 输入区域 -->
        <div style="padding: 16px 20px; border-top: 1px solid #1C1C1C; background: #0D0D0D; flex-shrink: 0;">
          <ConversationInput
            :ui-control="currentUIControl"
            :loading="novelStore.isLoading"
            @submit="handleUserInput"
          />
        </div>
      </div>

      <!-- 蓝图确认界面 -->
      <BlueprintConfirmation
        v-if="showBlueprintConfirmation"
        :ai-message="confirmationMessage"
        @blueprint-generated="handleBlueprintGenerated"
        @back="backToConversation"
      />

      <!-- 大纲展示界面 -->
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
@keyframes ping {
  0%, 100% { transform: scale(1); opacity: 0.6; }
  50% { transform: scale(1.6); opacity: 0; }
}
</style>

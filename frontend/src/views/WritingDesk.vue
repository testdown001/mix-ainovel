<!-- AIMETA P=写作台_章节编辑主页面|R=写作界面_章节管理|NR=不含详情展示|E=route:/novel/:id#component:WritingDesk|X=ui|A=写作台|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="naiveThemeOverrides">
    <div class="m3-shell h-screen flex flex-col overflow-hidden">
      <WDHeader
        :project="project"
        :progress="progress"
        :completed-chapters="completedChapters"
        :total-chapters="totalChapters"
        @go-back="goBack"
        @view-project-detail="viewProjectDetail"
        @toggle-sidebar="toggleSidebar"
      />

      <!-- 主要内容区域 -->
      <div class="flex-1 w-full px-4 sm:px-6 lg:px-8 py-6 overflow-hidden">
        <!-- 加载状态 -->
        <div v-if="novelStore.isLoading" class="h-full flex justify-center items-center">
          <div class="text-center">
            <div
              class="w-10 h-10 mx-auto mb-4 rounded-full border-2 border-t-transparent animate-spin"
              style="border-color: #ffe500; border-top-color: transparent"
            ></div>
            <p class="text-sm" style="color: #888">正在加载项目数据...</p>
          </div>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="novelStore.error" class="text-center py-20">
          <div
            class="p-8 max-w-md mx-auto rounded-2xl"
            style="background: #141414; border: 1px solid #2a2a2a"
          >
            <div
              class="w-12 h-12 rounded-xl mx-auto mb-4 flex items-center justify-center"
              style="background: #3d0a0a"
            >
              <svg class="w-6 h-6" style="color: #ff4757" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fill-rule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                  clip-rule="evenodd"
                ></path>
              </svg>
            </div>
            <h3 class="text-lg font-bold mb-2 text-white">加载失败</h3>
            <p class="text-sm mb-5" style="color: #ff4757">{{ novelStore.error }}</p>
            <button
              @click="loadProject"
              class="px-5 py-2 rounded-xl text-sm font-semibold"
              style="background: #ffe500; color: #000; border: none; cursor: pointer"
            >
              重新加载
            </button>
          </div>
        </div>

        <!-- 主要内容 -->
        <div v-else-if="project" class="h-full flex gap-6">
          <WDSidebar
            :project="project"
            :sidebar-open="sidebarOpen"
            :selected-chapter-number="selectedChapterNumber"
            :generating-chapter="generatingChapter"
            :evaluating-chapter="evaluatingChapter"
            :is-generating-outline="isGeneratingOutline"
            :is-rebuilding-rag="isRebuildingRag"
            :batch-generating="batchGenerating"
            :batch-progress="batchProgress"
            :selected-preset="selectedPreset"
            :selected-skill-count="selectedGenerationSkills.length"
            :agent-enabled="useAgent"
            :professional-mode="professionalMode"
            @close-sidebar="closeSidebar"
            @select-chapter="selectChapter"
            @preview-prediction="handlePreviewPrediction"
            @generate-chapter="generateChapter"
            @edit-chapter="openEditChapterModal"
            @delete-chapter="deleteChapter"
            @generate-outline="generateOutline"
            @rebuild-rag="rebuildRag"
            @batch-generate="openBatchGenerateModal"
            @cancel-batch="cancelBatchGenerate"
            @open-preset-selector="openPresetSelector"
            @open-skill-selector="showSkillSelector = true"
            @open-middle-product-viewer="showMiddleProductViewer = true"
            @preview-context-plan="handlePreviewContextPlan"
            @open-diagnostic-panel="showDiagnosticPanel = true"
            @open-agent-visualizer="showAgentVisualizer = true"
            @update:professional-mode="setProfessionalMode"
          />

          <div class="flex-1 min-w-0">
            <WDModelPicker
              v-model:model-code="selectedModelCode"
              v-model:enable-polish="enablePolish"
            />
            <WDWorkspace
              :project="project"
              :selected-chapter-number="selectedChapterNumber"
              :open-prediction-tick="openPredictionTick"
              :generating-chapter="generatingChapter"
              :prediction-generating-chapter="predictionGeneratingChapter"
              :evaluating-chapter="evaluatingChapter"
              :show-version-selector="showVersionSelector"
              :chapter-generation-result="chapterGenerationResult"
              :selected-version-index="selectedVersionIndex"
              :available-versions="availableVersions"
              :is-selecting-version="isSelectingVersion"
              :streaming-draft-text="
                selectedChapterNumber === streamingChapterNumber ? streamingDraftText : ''
              "
              :streaming-stage="
                selectedChapterNumber === streamingChapterNumber ? streamingStage : null
              "
              @regenerate-chapter="regenerateChapter"
              @evaluate-chapter="evaluateChapter"
              @hide-version-selector="hideVersionSelector"
              @update:selected-version-index="selectedVersionIndex = $event"
              @show-version-detail="showVersionDetail"
              @open-version-compare="showVersionCompare = true"
              @confirm-version-selection="confirmVersionSelection"
              @generate-chapter="generateChapter"
              @show-evaluation-detail="showEvaluationDetailModal = true"
              @open-skill-apply="showSkillApplyModal = true"
              @request-prediction="openPredictionRequestModal"
              @fetch-chapter-status="fetchChapterStatus"
              @edit-chapter="editChapterContent"
              @toggle-codex="codexPanelOpen = !codexPanelOpen"
            />
          </div>
        </div>
      </div>
      <WDVersionDetailModal
        :show="showVersionDetailModal"
        :detail-version-index="detailVersionIndex"
        :version="availableVersions[detailVersionIndex] ?? null"
        :is-current="isCurrentVersion(detailVersionIndex)"
        @close="closeVersionDetail"
        @select-version="selectVersionFromDetail"
      />
      <WDVersionCompareView
        :show="showVersionCompare"
        :versions="availableVersions"
        :current-content="selectedChapter?.content ?? null"
        :selecting="isSelectingVersion"
        @close="showVersionCompare = false"
        @select="handleCompareSelect"
      />
      <WDEvaluationDetailModal
        :show="showEvaluationDetailModal"
        :evaluation="selectedChapter?.evaluation || null"
        @close="showEvaluationDetailModal = false"
      />
      <WDEditChapterModal
        :show="showEditChapterModal"
        :chapter="editingChapter"
        :project-id="project?.id || ''"
        @close="showEditChapterModal = false"
        @save="saveChapterChanges"
        @prediction-updated="onPredictionUpdated"
      />
      <WDGenerateOutlineModal
        :show="showGenerateOutlineModal"
        @close="showGenerateOutlineModal = false"
        @generate="handleGenerateOutline"
      />
      <WDBatchGenerateModal
        :show="showBatchGenerateModal"
        :start-chapter="batchStartChapter"
        :max-count="batchMaxCount"
        @close="showBatchGenerateModal = false"
        @start="batchGenerateChapters"
      />
      <UpgradePrompt
        :show="upgradePrompt.show"
        :kind="upgradePrompt.kind"
        :message="upgradePrompt.message"
        @close="upgradePrompt.show = false"
      />
      <WDCodexPanel
        :visible="codexPanelOpen"
        :blueprint="project?.blueprint"
        :selected-chapter-number="selectedChapterNumber"
        :outlines="project?.blueprint?.chapter_outline || []"
        @update:visible="codexPanelOpen = $event"
      />

      <!-- 预设选择器 -->
      <n-modal
        v-model:show="showPresetSelector"
        preset="card"
        title="选择生成模式"
        style="width: 600px; max-width: 90vw"
      >
        <PresetSelector v-model="selectedPreset" />
        <template #footer>
          <div class="flex justify-end gap-3">
            <n-button @click="showPresetSelector = false">取消</n-button>
            <n-button type="primary" @click="confirmPreset">确认</n-button>
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="showPredictionRequestModal"
        preset="card"
        title="剧情推演设置"
        style="width: 640px; max-width: 92vw"
      >
        <div class="space-y-4">
          <div class="text-sm" style="color: #888">
            <span class="font-medium text-white">目标章节：</span>
            第 {{ predictionTargetChapter || '-' }} 章
          </div>
          <div>
            <label class="mb-2 block text-sm font-medium text-white"
              >排除内容 / 创作禁区（可选）</label
            >
            <textarea
              v-model="predictionExclusions"
              rows="5"
              class="w-full resize-none rounded-xl px-4 py-3 text-sm outline-none transition-colors"
              style="background: #1c1c1c; border: 1px solid #2a2a2a; color: #fff"
              placeholder="例如：不要出现神秘老头、不要引入上一代宿主线索、不要提前揭示站台票来源"
            ></textarea>
            <p class="mt-2 text-xs" style="color: #888">
              这些内容会作为 exclusions 一起传给后端剧情推演接口。
            </p>
          </div>
        </div>
        <template #footer>
          <div class="flex justify-end gap-3">
            <n-button @click="showPredictionRequestModal = false">取消</n-button>
            <n-button
              type="primary"
              :loading="!!predictionGeneratingChapter"
              @click="confirmPredictionRequest"
            >
              重新推演
            </n-button>
          </div>
        </template>
      </n-modal>

      <n-modal
        v-model:show="showSkillSelector"
        preset="card"
        title="配置 Agent 技能"
        style="width: 720px; max-width: 92vw"
      >
        <SkillSelector
          selection-only
          :initial-selection="selectedGenerationSkills"
          :project-id="project?.id || ''"
          :chapter-number="selectedChapterNumber || 1"
          :chapter-content="selectedChapter?.content || ''"
          :chapter-info="
            selectedChapter
              ? { title: selectedChapter.title, summary: selectedChapter.summary }
              : {}
          "
          :character-profiles="project?.blueprint?.characters || []"
          :world-settings="project?.blueprint?.world_setting || {}"
          :previous-summary="selectedChapter?.summary || ''"
          :outline="selectedChapterOutline || {}"
          @cancel="showSkillSelector = false"
          @select="handleSkillSelection"
        />
      </n-modal>

      <n-modal
        v-model:show="showSkillApplyModal"
        preset="card"
        title="应用写作技能"
        style="width: 720px; max-width: 92vw"
      >
        <SkillSelector
          :initial-selection="selectedGenerationSkills"
          :project-id="project?.id || ''"
          :chapter-number="selectedChapterNumber || 1"
          :chapter-content="selectedChapter?.content || ''"
          :chapter-info="
            selectedChapter
              ? { title: selectedChapter.title, summary: selectedChapter.summary }
              : {}
          "
          :character-profiles="project?.blueprint?.characters || []"
          :world-settings="project?.blueprint?.world_setting || {}"
          :previous-summary="selectedChapter?.summary || ''"
          :outline="selectedChapterOutline || {}"
          @cancel="showSkillApplyModal = false"
          @error="handleSkillApplyError"
          @apply="handleSkillApplyResults"
        />
      </n-modal>

      <n-modal
        v-model:show="showSkillPreviewModal"
        preset="card"
        title="技能应用对比预览"
        style="width: 1100px; max-width: 96vw"
      >
        <div v-if="skillApplyPreview" class="space-y-4">
          <div class="flex flex-wrap items-center gap-2 text-sm" style="color: #888">
            <span class="font-medium text-white">已应用技能：</span>
            <span
              v-for="skillName in skillApplyPreview.skillNames"
              :key="skillName"
              class="inline-flex items-center rounded-full px-3 py-1 text-xs"
              style="background: #2a2a2a; color: #ffe500"
            >
              {{ skillName }}
            </span>
          </div>

          <div class="grid gap-3 md:grid-cols-3">
            <div
              class="rounded-lg border px-4 py-3"
              style="border-color: #2a2a2a; background: #1c1c1c"
            >
              <div class="text-xs" style="color: #888">原文字数</div>
              <div class="mt-1 text-lg font-semibold text-white">
                {{ skillPreviewStats.originalLength }}
              </div>
            </div>
            <div
              class="rounded-lg border px-4 py-3"
              style="border-color: #2a2a2a; background: #1c1c1c"
            >
              <div class="text-xs" style="color: #888">技能结果字数</div>
              <div class="mt-1 text-lg font-semibold text-white">
                {{ skillPreviewStats.transformedLength }}
              </div>
            </div>
            <div
              class="rounded-lg border px-4 py-3"
              style="border-color: #2a2a2a; background: #1c1c1c"
            >
              <div class="text-xs" style="color: #888">变化段落</div>
              <div class="mt-1 text-lg font-semibold text-white">
                {{ skillPreviewStats.changedParagraphs }}
              </div>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-2">
            <div class="rounded-xl border overflow-hidden" style="border-color: #2a2a2a">
              <div
                class="border-b px-4 py-3 text-sm font-medium text-white"
                style="border-color: #2a2a2a; background: #1c1c1c"
              >
                原文
              </div>
              <div
                class="max-h-[55vh] overflow-y-auto px-4 py-4 whitespace-pre-wrap text-sm leading-7 text-white"
                style="background: #141414"
              >
                {{ skillApplyPreview.originalContent }}
              </div>
            </div>

            <div class="rounded-xl border overflow-hidden" style="border-color: #2a2a2a">
              <div
                class="border-b px-4 py-3 text-sm font-medium"
                style="border-color: #2a2a2a; background: #2a2600; color: #ffe500"
              >
                技能结果
              </div>
              <div
                class="max-h-[55vh] overflow-y-auto px-4 py-4 whitespace-pre-wrap text-sm leading-7 text-white"
                style="background: #141414"
              >
                {{ skillApplyPreview.transformedContent }}
              </div>
            </div>
          </div>
        </div>

        <template #footer>
          <div class="flex justify-end gap-3">
            <n-button @click="closeSkillPreview">取消</n-button>
            <n-button type="primary" @click="confirmSkillApplyPreview">确认保存</n-button>
          </div>
        </template>
      </n-modal>

      <!-- 中间产物预览 -->
      <n-modal
        v-model:show="showMiddleProductViewer"
        preset="card"
        title="生成中间产物"
        style="width: 700px; max-width: 90vw"
      >
        <MiddleProductViewer
          :context-plan-data="currentContextPlanData"
          :evidence-summary-data="currentEvidenceSummaryData"
          :evidence-grade-data="currentEvidenceGradeData"
          :prompt-compile-summary-data="currentPromptCompileSummaryData"
          :verification-report-data="currentVerificationReportData"
          :mission-data="currentMissionData"
          :rag-data="currentRagData"
          :context-data="currentContextData"
          :foreshadowing-data="currentForeshadowingData"
        />
      </n-modal>

      <!-- 诊断面板 -->
      <n-modal
        v-model:show="showDiagnosticPanel"
        preset="card"
        title="生成诊断报告"
        style="width: 600px; max-width: 90vw"
      >
        <DiagnosticPanel
          :project-id="project?.id"
          :chapter-number="selectedChapterNumber || undefined"
          :professional-mode="professionalMode"
          @action="handleDiagnosticAction"
        />
      </n-modal>

      <!-- Agent 可视化 -->
      <n-modal
        v-model:show="showAgentVisualizer"
        preset="card"
        title="Agent 协作流程"
        style="width: 800px; max-width: 90vw"
      >
        <AgentFlowVisualizer
          :agents="agentNodes"
          :current-agent-id="currentAgentId"
          :is-running="isAgentRunning"
          :is-completed="isAgentCompleted"
          :total-time="agentTotalTime"
          :total-l-l-m-calls="agentLLMCalls"
          :total-tool-calls="agentToolCalls"
          @pause="handleAgentPause"
          @stop="handleAgentStop"
        />
      </n-modal>
    </div>
  </n-config-provider>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { NModal, NButton, NConfigProvider, darkTheme, type GlobalThemeOverrides } from 'naive-ui'
import { useNovelStore } from '@/stores/novel'
import { useAuthStore } from '@/stores/auth'
import { NovelAPI } from '@/api/novel'
import type {
  Chapter,
  ChapterOutline,
  ChapterGenerationResponse,
  ChapterVersion,
  AdvancedGenerateResponse,
  AdvancedGenerateFlowConfig,
} from '@/api/novel'
import { TaskAPI } from '@/api/task'
import { AdminAPI } from '@/api/admin'
import { globalAlert } from '@/composables/useAlert'
import { useWebSocket } from '@/composables/useWebSocket'
import { useAsyncGeneration } from '@/composables/useAsyncGeneration'
import WDHeader from '@/components/writing-desk/WDHeader.vue'
import WDSidebar from '@/components/writing-desk/WDSidebar.vue'
import WDWorkspace from '@/components/writing-desk/WDWorkspace.vue'
import WDModelPicker from '@/components/writing-desk/WDModelPicker.vue'
import WDVersionDetailModal from '@/components/writing-desk/WDVersionDetailModal.vue'
import WDVersionCompareView from '@/components/writing-desk/WDVersionCompareView.vue'
import WDEvaluationDetailModal from '@/components/writing-desk/WDEvaluationDetailModal.vue'
import WDEditChapterModal from '@/components/writing-desk/WDEditChapterModal.vue'
import WDGenerateOutlineModal from '@/components/writing-desk/WDGenerateOutlineModal.vue'
import WDBatchGenerateModal from '@/components/writing-desk/WDBatchGenerateModal.vue'
import WDCodexPanel from '@/components/writing-desk/WDCodexPanel.vue'
import UpgradePrompt from '@/components/UpgradePrompt.vue'
import { detectUpgradeHint } from '@/utils/upgradeHint'
import { isStreamInterruption } from '@/utils/streamInterruption'
import PresetSelector from '@/components/shared/PresetSelector.vue'
import MiddleProductViewer from '@/components/shared/MiddleProductViewer.vue'
import DiagnosticPanel from '@/components/shared/DiagnosticPanel.vue'
import AgentFlowVisualizer from '@/components/shared/AgentFlowVisualizer.vue'
import SkillSelector from '@/components/writing-desk/SkillSelector.vue'

interface Props {
  id: string
}

type WritingPreset = NonNullable<AdvancedGenerateFlowConfig['preset']>
type AgentNodeStatus = 'pending' | 'running' | 'completed' | 'failed'

interface AgentLog {
  time: string
  message: string
  type: 'info' | 'warning' | 'error' | 'success'
}

interface AgentNode {
  id: string
  name: string
  role: string
  icon: string
  status: AgentNodeStatus
  logs: AgentLog[]
}

// 现行三档（与 PresetSelector 选项、后端 fast/standard/premium 对齐）；
// 旧名（basic/enhanced/...）服务端已归一化弃用，localStorage 中的旧值经
// isWritingPreset 校验失败后回落 'fast'
const VALID_PRESETS: WritingPreset[] = ['fast', 'standard', 'premium']

function isWritingPreset(value: string | null): value is WritingPreset {
  return value !== null && VALID_PRESETS.includes(value as WritingPreset)
}

const naiveThemeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#FFE500',
    primaryColorHover: '#FFF176',
    primaryColorPressed: '#F9C800',
    primaryColorSuppl: '#FFE500',
    bodyColor: '#0A0A0A',
    baseColor: '#0A0A0A',
    cardColor: '#141414',
    modalColor: '#141414',
    popoverColor: '#1C1C1C',
    tableColor: '#141414',
    tableColorHover: '#1C1C1C',
    inputColor: '#1C1C1C',
    inputColorDisabled: '#111',
    borderColor: '#2A2A2A',
    dividerColor: '#2A2A2A',
    hoverColor: '#1C1C1C',
    textColorBase: '#FFFFFF',
    textColor1: '#FFFFFF',
    textColor2: '#CCCCCC',
    textColor3: '#888888',
    placeholderColor: '#555555',
    tagColor: '#1C1C1C',
    scrollbarColor: '#2A2A2A',
    scrollbarColorHover: '#444444',
  },
  Button: {
    textColorPrimary: '#000000',
    textColorHoverPrimary: '#000000',
    textColorPressedPrimary: '#000000',
    textColorFocusPrimary: '#000000',
  },
}

const props = defineProps<Props>()
const router = useRouter()
const novelStore = useNovelStore()
const authStore = useAuthStore()

// 状态管理
const selectedChapterNumber = ref<number | null>(null)
const chapterGenerationResult = ref<ChapterGenerationResponse | null>(null)
const selectedVersionIndex = ref<number>(0)
const generatingChapter = ref<number | null>(null)
const sidebarOpen = ref(false)
const showVersionDetailModal = ref(false)
const detailVersionIndex = ref<number>(0)
const showVersionCompare = ref(false)
const showEvaluationDetailModal = ref(false)
const showEditChapterModal = ref(false)
const editingChapter = ref<ChapterOutline | null>(null)
const isGeneratingOutline = ref(false)
const isRebuildingRag = ref(false)
const showGenerateOutlineModal = ref(false)
const codexPanelOpen = ref(false)
const showPresetSelector = ref(false)
const showPredictionRequestModal = ref(false)
const showSkillSelector = ref(false)
const showSkillApplyModal = ref(false)
const showSkillPreviewModal = ref(false)
const storedPreset = localStorage.getItem('octopus_preset')
const selectedPreset = ref<WritingPreset>(isWritingPreset(storedPreset) ? storedPreset : 'fast')
const storedWorkbenchMode = localStorage.getItem('octopus_workbench_mode')
const professionalMode = ref(storedWorkbenchMode === 'professional')
const predictionTargetChapter = ref<number | null>(null)
const predictionExclusions = ref('')
const predictionGeneratingChapter = ref<number | null>(null)
const selectedGenerationSkills = ref<NonNullable<AdvancedGenerateFlowConfig['selected_skills']>>([])
const skillApplyPreview = ref<{
  skillNames: string[]
  originalContent: string
  transformedContent: string
} | null>(null)
function confirmPreset() {
  localStorage.setItem('octopus_preset', selectedPreset.value)
  showPresetSelector.value = false
}

async function openPresetSelector() {
  await authStore.fetchUser()
  showPresetSelector.value = true
}

const setProfessionalMode = (enabled: boolean) => {
  professionalMode.value = enabled
  localStorage.setItem('octopus_workbench_mode', enabled ? 'professional' : 'guided')
}

type DiagnosticAction =
  | 'regenerate_chapter'
  | 'evaluate_chapter'
  | 'rebuild_rag'
  | 'preview_context_plan'
  | 'switch_professional'

// 自创先进多 Agent 架构开关
const useAgent = ref(false)
const fetchAgentSetting = async () => {
  try {
    const configs = await AdminAPI.listSystemConfigs()
    const agentConfig = configs.find((c) => c.key === 'enable_agent_system')
    useAgent.value = agentConfig?.value === 'true'
  } catch {
    // 非管理员或接口不可用时静默降级
    useAgent.value = false
  }
}
// 模型选择 + 润色（WDModelPicker v-model 回传；并入 flow_config 后随各 submit 透传到
// 生成入口做按档门控与积分计费）
const selectedModelCode = ref<string | null>(null)
const enablePolish = ref(false)

const agentFlowConfigOverrides = computed<Partial<AdvancedGenerateFlowConfig> | undefined>(() => {
  const overrides: Partial<AdvancedGenerateFlowConfig> = {}
  if (useAgent.value) {
    overrides.use_agent = true
    overrides.use_agentic_loop = true
  }
  if (selectedGenerationSkills.value.length > 0) {
    overrides.selected_skills = selectedGenerationSkills.value
  }
  if (selectedModelCode.value) {
    overrides.model_code = selectedModelCode.value
  }
  if (enablePolish.value) {
    overrides.enable_polish = true
  }
  return Object.keys(overrides).length > 0 ? overrides : undefined
})
const showMiddleProductViewer = ref(false)
const showDiagnosticPanel = ref(false)
const showAgentVisualizer = ref(false)

// 中间产物数据
const currentContextPlanData = ref(null)
const currentEvidenceSummaryData = ref(null)
const currentPromptCompileSummaryData = ref(null)
const currentVerificationReportData = ref(null)
const currentMissionData = ref(null)
const currentRagData = ref(null)
const currentContextData = ref(null)
const currentForeshadowingData = ref(null)
const currentEvidenceGradeData = ref(null)

// Agent 可视化数据
const currentAgentId = ref<string | null>(null)
const isAgentRunning = ref(false)
const isAgentCompleted = ref(false)
const agentTotalTime = ref(0)
const agentLLMCalls = ref(0)
const agentToolCalls = ref(0)
let _agentStartTime = 0
const agentNodes = ref<AgentNode[]>([
  { id: 'taizi', name: '需求智能体', role: '目标提取', icon: '👶', status: 'pending', logs: [] },
  { id: 'zhongshu', name: '规划智能体', role: '上下文规划', icon: '📜', status: 'pending', logs: [] },
  { id: 'shangshu', name: '协调智能体', role: '流程编排', icon: '🏛️', status: 'pending', logs: [] },
  { id: 'bingbu', name: '生成智能体', role: '章节生成', icon: '⚔️', status: 'pending', logs: [] },
  { id: 'libu', name: '一致性智能体', role: '角色一致性', icon: '📋', status: 'pending', logs: [] },
  { id: 'hubu', name: '技能智能体', role: '技能系统', icon: '🎯', status: 'pending', logs: [] },
  { id: 'menxia', name: '审核智能体', role: '质量审核', icon: '🔍', status: 'pending', logs: [] },
])

// Stage → Agent 状态映射：将后端推送的 stage 事件映射到 Agent 节点状态变更
function _setAgentStatus(id: string, status: AgentNodeStatus) {
  const node = agentNodes.value.find((a) => a.id === id)
  if (node) node.status = status
}

function _addAgentLog(
  id: string,
  message: string,
  type: 'info' | 'success' | 'warning' | 'error' = 'info',
) {
  const node = agentNodes.value.find((a) => a.id === id)
  if (!node) return
  if (!node.logs) node.logs = []
  const now = new Date()
  const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`
  node.logs.push({ time, message, type })
}

function updateAgentByStage(stage: string, message?: string) {
  // 处理 agent:xxx:yyy 格式的事件（先进多 Agent 架构）
  const agentMatch = stage.match(/^agent:(\w+):(\w+)$/)
  if (agentMatch) {
    const [, agentId, action] = agentMatch
    const msg = message || stage

    if (action === 'start') {
      _setAgentStatus(agentId, 'running')
      currentAgentId.value = agentId
      _addAgentLog(agentId, msg, 'info')
    } else if (action === 'done') {
      _setAgentStatus(agentId, 'completed')
      _addAgentLog(agentId, msg, 'success')
    } else {
      _addAgentLog(agentId, msg, 'info')
    }

    if (agentId === 'system' && action === 'done') {
      currentAgentId.value = null
      isAgentRunning.value = false
      isAgentCompleted.value = true
      agentTotalTime.value = _agentStartTime ? Date.now() - _agentStartTime : 0
    }
    return
  }

  // Agentic loop events (tool_call, tool_result, loop_iteration, context_compact)
  if (
    stage === 'tool_call' ||
    stage === 'tool_result' ||
    stage === 'loop_iteration' ||
    stage === 'context_compact'
  ) {
    const activeAgent = currentAgentId.value
    if (activeAgent) {
      if (stage === 'tool_call') {
        _addAgentLog(activeAgent, message || 'Calling tool...', 'info')
        agentToolCalls.value++
      } else if (stage === 'tool_result') {
        _addAgentLog(activeAgent, message || 'Tool completed', 'success')
      } else if (stage === 'loop_iteration') {
        _addAgentLog(activeAgent, message || 'New iteration', 'info')
        agentLLMCalls.value++
      } else if (stage === 'context_compact') {
        _addAgentLog(activeAgent, message || 'Context compacted', 'warning')
      }
    }
    return
  }

  // 传统流水线 stage 映射（兼容非 Agent 模式）
  switch (stage) {
    case 'starting':
      currentAgentId.value = 'taizi'
      _setAgentStatus('taizi', 'running')
      break
    case 'build_generation_prompt':
      _setAgentStatus('taizi', 'completed')
      _setAgentStatus('zhongshu', 'running')
      _setAgentStatus('libu', 'running')
      currentAgentId.value = 'zhongshu'
      break
    case 'generate_versions':
    case 'generate_fast_version':
    case 'generate_scene_by_scene':
      _setAgentStatus('zhongshu', 'completed')
      _setAgentStatus('libu', 'completed')
      _setAgentStatus('shangshu', 'completed')
      _setAgentStatus('bingbu', 'running')
      currentAgentId.value = 'bingbu'
      break
    case 'persist_versions':
      _setAgentStatus('bingbu', 'completed')
      _setAgentStatus('hubu', 'running')
      currentAgentId.value = 'hubu'
      break
    case 'completed':
      _setAgentStatus('hubu', 'completed')
      _setAgentStatus('menxia', 'completed')
      currentAgentId.value = null
      isAgentRunning.value = false
      isAgentCompleted.value = true
      agentTotalTime.value = _agentStartTime ? Date.now() - _agentStartTime : 0
      break
  }
}

function resetAgentState() {
  agentNodes.value.forEach((a) => {
    a.status = 'pending'
    a.logs = []
  })
  currentAgentId.value = null
  isAgentRunning.value = true
  isAgentCompleted.value = false
  agentTotalTime.value = 0
  agentLLMCalls.value = 0
  agentToolCalls.value = 0
  _agentStartTime = Date.now()
}

// Agent 控制函数
function handleAgentPause() {
  isAgentRunning.value = false
}

function handleAgentStop() {
  isAgentRunning.value = false
  isAgentCompleted.value = false
}

const openPredictionTick = ref(0)
const streamingChapterNumber = ref<number | null>(null)
// 断线待对账的章节：catch 里记下、finally 拉到后端最新状态后再决定提示什么
const interruptedChapter = ref<number | null>(null)
const streamingDraftText = ref('')
const streamingStage = ref<string | null>(null)
const activeGenerationToken = ref(0)

// 异步任务生成（Go Gateway 模式）
const asyncGen = useAsyncGeneration()
const useAsyncMode = ref(false) // 是否启用异步任务模式

// 检测 Go Gateway 是否可用
const detectAsyncMode = async () => {
  try {
    await TaskAPI.getStats()
    useAsyncMode.value = true
  } catch {
    useAsyncMode.value = false
  }
}

// 402 积分不足 / 403 档位不足 → 升级引导弹窗（替代裸报错的统一转化入口；
// 判定逻辑在 @/utils/upgradeHint，有 Vitest 回归）
const upgradePrompt = ref<{ show: boolean; kind: 'credits' | 'tier'; message: string }>({
  show: false,
  kind: 'credits',
  message: '',
})

// 连续生成相关状态
const showBatchGenerateModal = ref(false)
const batchGenerating = ref(false)
const batchProgress = ref<{ current: number; total: number } | null>(null)
const batchCancelled = ref(false)
const componentMounted = ref(true)

// 计算属性
const project = computed(() => novelStore.currentProject)

const selectedChapter = computed(() => {
  if (!project.value || selectedChapterNumber.value === null) return null
  return (
    project.value.chapters.find((ch) => ch.chapter_number === selectedChapterNumber.value) || null
  )
})

const showVersionSelector = computed(() => {
  if (!selectedChapter.value) return false
  const status = selectedChapter.value.generation_status
  return (
    status === 'waiting_for_confirm' ||
    status === 'evaluating' ||
    status === 'evaluation_failed' ||
    status === 'selecting'
  )
})

const evaluatingChapter = computed(() => {
  if (selectedChapter.value?.generation_status === 'evaluating') {
    return selectedChapter.value.chapter_number
  }
  return null
})

const isSelectingVersion = computed(() => {
  return selectedChapter.value?.generation_status === 'selecting'
})

const selectedChapterOutline = computed(() => {
  if (!project.value?.blueprint?.chapter_outline || selectedChapterNumber.value === null)
    return null
  return (
    project.value.blueprint.chapter_outline.find(
      (ch) => ch.chapter_number === selectedChapterNumber.value,
    ) || null
  )
})

const progress = computed(() => {
  if (!project.value?.blueprint?.chapter_outline) return 0
  const totalChapters = project.value.blueprint.chapter_outline.length
  const completedChapters = project.value.chapters.filter((ch) => ch.content).length
  return Math.round((completedChapters / totalChapters) * 100)
})

const totalChapters = computed(() => {
  return project.value?.blueprint?.chapter_outline?.length || 0
})

const completedChapters = computed(() => {
  return project.value?.chapters?.filter((ch) => ch.content)?.length || 0
})

const isCurrentVersion = (versionIndex: number) => {
  if (!selectedChapter.value?.content || !availableVersions.value?.[versionIndex]?.content)
    return false

  // 使用cleanVersionContent函数清理内容进行比较
  const cleanCurrentContent = cleanVersionContent(selectedChapter.value.content)
  const cleanVersionContentStr = cleanVersionContent(availableVersions.value[versionIndex].content)

  return cleanCurrentContent === cleanVersionContentStr
}

const cleanVersionContent = (content: string): string => {
  if (!content) return ''

  // 尝试解析JSON，看是否是完整的章节对象
  try {
    const parsed = JSON.parse(content)
    const extractContent = (value: any): string | null => {
      if (!value) return null
      if (typeof value === 'string') return value
      if (Array.isArray(value)) {
        for (const item of value) {
          const nested = extractContent(item)
          if (nested) return nested
        }
        return null
      }
      if (typeof value === 'object') {
        for (const key of ['content', 'chapter_content', 'chapter_text', 'text', 'body', 'story']) {
          if (value[key]) {
            const nested = extractContent(value[key])
            if (nested) return nested
          }
        }
      }
      return null
    }
    const extracted = extractContent(parsed)
    if (extracted) {
      // 如果是章节对象/数组，提取正文
      content = extracted
    }
  } catch (error) {
    // 如果不是JSON，继续处理字符串
  }

  // 去掉开头和结尾的引号
  let cleaned = content.replace(/^"|"$/g, '')

  // 处理转义字符
  cleaned = cleaned.replace(/\\n/g, '\n') // 换行符
  cleaned = cleaned.replace(/\\"/g, '"') // 引号
  cleaned = cleaned.replace(/\\t/g, '\t') // 制表符
  cleaned = cleaned.replace(/\\\\/g, '\\') // 反斜杠

  return cleaned
}

const canGenerateChapter = (chapterNumber: number) => {
  if (!project.value?.blueprint?.chapter_outline) return false

  // 检查前面所有章节是否都已成功生成
  const outlines = [...project.value.blueprint.chapter_outline].sort(
    (a, b) => a.chapter_number - b.chapter_number,
  )

  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break

    const chapter = project.value?.chapters.find(
      (ch) => ch.chapter_number === outline.chapter_number,
    )
    if (!chapter || chapter.generation_status !== 'successful') {
      return false // 前面有章节未完成
    }
  }

  // 检查当前章节是否已经完成
  const currentChapter = project.value?.chapters.find((ch) => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true // 已完成的章节可以重新生成
  }

  return true // 前面章节都完成了，可以生成当前章节
}

const isChapterFailed = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const hasChapterInProgress = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
  // waiting_for_confirm状态表示等待选择版本 = 进行中状态
  return chapter && chapter.generation_status === 'waiting_for_confirm'
}

// 可用版本列表 (合并生成结果和已有版本)
const availableVersions = computed(() => {
  // 优先使用新生成的版本（对象数组格式）
  if (chapterGenerationResult.value?.versions) {
    return chapterGenerationResult.value.versions
  }

  // 使用章节已有的版本（字符串数组格式，需要转换为对象数组）
  if (selectedChapter.value?.versions && Array.isArray(selectedChapter.value.versions)) {
    const metadataList = Array.isArray(selectedChapter.value.version_metadata)
      ? selectedChapter.value.version_metadata
      : []
    const convertedVersions = selectedChapter.value.versions
      .filter((v) => v && typeof v === 'string')
      .map((versionString, index) => ({
        content: versionString,
        style: metadataList[index]?.version_label || `版本 ${index + 1}`,
        metadata: metadataList[index],
      }))

    return convertedVersions
  }

  return []
})

// 方法
const goBack = () => {
  router.push('/workspace')
}

const viewProjectDetail = () => {
  if (project.value) {
    router.push(`/detail/${project.value.id}`)
  }
}

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

const closeSidebar = () => {
  sidebarOpen.value = false
}

const loadProject = async () => {
  try {
    await novelStore.loadProject(props.id)
    autoSelectNextChapter()
    noticeBackgroundGeneration()
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

/**
 * 刷新或重进页面后，后端可能还有章节在生成（异步任务路径不随页面关闭而停）。
 * 此前这种情况只是画着一个转圈的章节、没有任何说明，用户无从判断是「还在跑」
 * 还是「卡死了」。选中它同时让 WDWorkspace 的 10 秒轮询接管，完成即自动出现。
 */
const noticeBackgroundGeneration = () => {
  const inFlight = project.value?.chapters?.find(
    (ch) => ch.generation_status === 'generating',
  )
  if (!inFlight) return
  selectChapter(inFlight.chapter_number)
  globalAlert.showAlert(
    `第 ${inFlight.chapter_number} 章正在服务端生成，完成后会自动出现，无需重新点击生成`,
    'info',
    '后台仍在生成',
  )
}

const autoSelectNextChapter = () => {
  if (selectedChapterNumber.value !== null) return
  const p = project.value
  if (!p?.blueprint?.chapter_outline?.length) return

  const outlines = [...p.blueprint.chapter_outline].sort(
    (a, b) => a.chapter_number - b.chapter_number,
  )
  const chaptersMap = new Map(p.chapters.map((ch) => [ch.chapter_number, ch]))

  const next = outlines.find((o) => {
    const ch = chaptersMap.get(o.chapter_number)
    return !ch || ch.generation_status !== 'successful'
  })

  selectChapter(next ? next.chapter_number : outlines[outlines.length - 1].chapter_number)
}

const fetchChapterStatus = async () => {
  if (selectedChapterNumber.value === null) {
    return
  }
  try {
    await novelStore.loadChapter(selectedChapterNumber.value)
    console.log('Chapter status polled and updated.')
  } catch (error) {
    console.error('轮询章节状态失败:', error)
    // 在这里可以决定是否要通知用户轮询失败
  }
}

// 显示版本详情
const showVersionDetail = (versionIndex: number) => {
  detailVersionIndex.value = versionIndex
  showVersionDetailModal.value = true
}

// 关闭版本详情弹窗
const closeVersionDetail = () => {
  showVersionDetailModal.value = false
}

// 隐藏版本选择器，返回内容视图
const hideVersionSelector = () => {
  // Now controlled by computed property, but we can clear the generation result
  chapterGenerationResult.value = null
  selectedVersionIndex.value = 0
}

const selectChapter = (chapterNumber: number) => {
  const isSameChapter = selectedChapterNumber.value === chapterNumber
  selectedChapterNumber.value = chapterNumber

  if (!isSameChapter) {
    chapterGenerationResult.value = null
    const chapter = project.value?.chapters?.find((ch) => ch.chapter_number === chapterNumber)
    if (typeof chapter?.recommended_version_index === 'number') {
      const maxIndex = Math.max(0, (chapter.versions?.length || 1) - 1)
      selectedVersionIndex.value = Math.min(
        maxIndex,
        Math.max(0, chapter.recommended_version_index),
      )
    } else {
      selectedVersionIndex.value = 0
    }
  }

  closeSidebar()
}

const predictionPreviewBlockedStatuses: Chapter['generation_status'][] = [
  'waiting_for_confirm',
  'evaluation_failed',
  'evaluating',
  'selecting',
]

const handlePreviewPrediction = (chapterNumber: number) => {
  selectChapter(chapterNumber)
  const chapterStatus = project.value?.chapters?.find(
    (chapter) => chapter.chapter_number === chapterNumber,
  )?.generation_status

  if (chapterStatus && predictionPreviewBlockedStatuses.includes(chapterStatus)) {
    return
  }

  openPredictionTick.value += 1
}

const handlePreviewContextPlan = async () => {
  if (!project.value?.id || !selectedChapterNumber.value) return
  try {
    const res = await NovelAPI.previewContextPlan(project.value.id, selectedChapterNumber.value, {
      writing_notes: '',
      preset: selectedPreset.value,
      selected_skills: selectedGenerationSkills.value,
    })
    currentContextPlanData.value = res
    showMiddleProductViewer.value = true
  } catch (err: any) {
    globalAlert.showError(err?.response?.data?.detail || '预览计划失败')
  }
}

const handleDiagnosticAction = async (action: DiagnosticAction) => {
  if (action === 'switch_professional') {
    setProfessionalMode(true)
    return
  }

  if (action === 'rebuild_rag') {
    await rebuildRag(false)
    return
  }

  if (!selectedChapterNumber.value) {
    globalAlert.showError('请先选择一个章节', '操作失败')
    return
  }

  if (action === 'preview_context_plan') {
    showDiagnosticPanel.value = false
    await handlePreviewContextPlan()
    return
  }

  if (action === 'evaluate_chapter') {
    await evaluateChapter()
    return
  }

  if (action === 'regenerate_chapter') {
    const chapterNumber = selectedChapterNumber.value
    const message = hasChapterInProgress(chapterNumber)
      ? '重新生成会替换当前待选择版本，确定继续吗？'
      : isChapterFailed(chapterNumber)
        ? '将重新尝试生成该章节，确定继续吗？'
        : '重新生成会覆盖当前章节的生成结果，确定继续吗？'
    const confirmed = await globalAlert.showConfirm(message, '生成确认')
    if (!confirmed) return
    showDiagnosticPanel.value = false
    await generateChapter(chapterNumber)
  }
}

const handleSkillSelection = (
  skills: NonNullable<AdvancedGenerateFlowConfig['selected_skills']>,
) => {
  selectedGenerationSkills.value = skills
  showSkillSelector.value = false
}

const openPredictionRequestModal = (chapterNumber: number) => {
  predictionTargetChapter.value = chapterNumber
  showPredictionRequestModal.value = true
}

const confirmPredictionRequest = async () => {
  if (
    !project.value?.id ||
    predictionTargetChapter.value === null ||
    predictionGeneratingChapter.value !== null
  ) {
    return
  }

  predictionGeneratingChapter.value = predictionTargetChapter.value
  try {
    const result = await NovelAPI.generatePrediction(
      project.value.id,
      predictionTargetChapter.value,
      predictionExclusions.value.trim() || undefined,
    )

    const targetOutline = project.value.blueprint?.chapter_outline?.find(
      (outline) => outline.chapter_number === predictionTargetChapter.value,
    )
    if (targetOutline) {
      targetOutline.metadata = { ...targetOutline.metadata, prediction: result }
    }

    if (selectedChapterNumber.value === predictionTargetChapter.value) {
      openPredictionTick.value += 1
    }

    showPredictionRequestModal.value = false
    globalAlert.showSuccess(`第 ${predictionTargetChapter.value} 章剧情推演已更新`, '推演完成')
  } catch (error) {
    console.error('剧情推演失败:', error)
    globalAlert.showError(
      `剧情推演失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '推演失败',
    )
  } finally {
    predictionGeneratingChapter.value = null
  }
}

const handleSkillApplyError = (message: string) => {
  globalAlert.showError(message, '技能执行失败')
}

const skillPreviewStats = computed(() => {
  const originalContent = skillApplyPreview.value?.originalContent || ''
  const transformedContent = skillApplyPreview.value?.transformedContent || ''
  const originalParagraphs = originalContent
    .split(/\n\s*\n/)
    .map((item) => item.trim())
    .filter(Boolean)
  const transformedParagraphs = transformedContent
    .split(/\n\s*\n/)
    .map((item) => item.trim())
    .filter(Boolean)
  const maxParagraphs = Math.max(originalParagraphs.length, transformedParagraphs.length)
  let changedParagraphs = 0

  for (let index = 0; index < maxParagraphs; index += 1) {
    if ((originalParagraphs[index] || '') !== (transformedParagraphs[index] || '')) {
      changedParagraphs += 1
    }
  }

  return {
    originalLength: originalContent.length,
    transformedLength: transformedContent.length,
    changedParagraphs,
  }
})

const closeSkillPreview = () => {
  showSkillPreviewModal.value = false
  skillApplyPreview.value = null
}

const confirmSkillApplyPreview = async () => {
  if (!skillApplyPreview.value || selectedChapterNumber.value === null) {
    return
  }

  const saved = await editChapterContent({
    chapterNumber: selectedChapterNumber.value,
    content: skillApplyPreview.value.transformedContent,
  })
  if (saved) {
    closeSkillPreview()
  }
}

const handleSkillApplyResults = async (
  results: Array<{
    skill_id: string
    transformed_content: string
    success: boolean
    changed: boolean
    error?: string
  }>,
) => {
  if (!project.value || selectedChapterNumber.value === null || !selectedChapter.value) {
    globalAlert.showError('当前没有可应用技能的章节', '操作失败')
    return
  }

  const successfulResults = results.filter((item) => item.success)
  if (successfulResults.length === 0) {
    globalAlert.showError('所有技能执行都失败了，请稍后重试', '技能执行失败')
    return
  }

  const finalResult = successfulResults[successfulResults.length - 1]
  const originalContent = selectedChapter.value.content || ''
  const finalContent = finalResult.transformed_content || originalContent
  if (!finalContent || finalContent === originalContent) {
    showSkillApplyModal.value = false
    globalAlert.showAlert('技能已执行，但内容没有发生变化', 'info', '无需保存')
    return
  }

  showSkillApplyModal.value = false
  skillApplyPreview.value = {
    skillNames: successfulResults.map((item) => item.skill_id),
    originalContent,
    transformedContent: finalContent,
  }
  showSkillPreviewModal.value = true
}

const generateChapter = async (chapterNumber: number, writingNotes?: string) => {
  // 检查是否可以生成该章节
  if (
    !canGenerateChapter(chapterNumber) &&
    !isChapterFailed(chapterNumber) &&
    !hasChapterInProgress(chapterNumber)
  ) {
    globalAlert.showError('请按顺序生成章节，先完成前面的章节', '生成受限')
    return
  }

  try {
    const generationToken = activeGenerationToken.value + 1
    activeGenerationToken.value = generationToken
    generatingChapter.value = chapterNumber
    selectedChapterNumber.value = chapterNumber
    streamingChapterNumber.value = chapterNumber
    streamingDraftText.value = ''
    streamingStage.value = '准备生成...'
    currentContextPlanData.value = null
    currentEvidenceSummaryData.value = null
    currentPromptCompileSummaryData.value = null
    currentVerificationReportData.value = null
    currentEvidenceGradeData.value = null
    currentMissionData.value = null
    currentRagData.value = null
    currentContextData.value = null
    currentForeshadowingData.value = null
    resetAgentState()

    // Agent 模式下自动打开可视化弹窗
    if (useAgent.value) {
      showAgentVisualizer.value = true
    }

    // 在本地更新章节状态为generating
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
      if (chapter) {
        chapter.generation_status = 'generating'
      } else {
        // If chapter does not exist, create a temporary one to show generating state
        const outline = project.value.blueprint?.chapter_outline?.find(
          (o) => o.chapter_number === chapterNumber,
        )
        project.value.chapters.push({
          chapter_number: chapterNumber,
          title: outline?.title || '加载中...',
          summary: outline?.summary || '',
          content: '',
          versions: [],
          evaluation: null,
          generation_status: 'generating',
        } as Chapter)
      }
    }

    if (!project.value?.id) {
      throw new Error('没有当前项目')
    }

    // 根据模式选择生成方式
    if (useAsyncMode.value) {
      // 异步任务模式（通过 Go Gateway Task Dispatcher）
      await asyncGen.submitGeneration(
        project.value.id,
        chapterNumber,
        {
          preset: selectedPreset.value,
          use_agent_system: useAgent.value,
          writing_notes: writingNotes,
          ...(agentFlowConfigOverrides.value || {}),
        },
        (state) => {
          if (activeGenerationToken.value !== generationToken) return
          // 优先用中文 message(如"多版本生成中")：阶段日志可读、且进度条按中文关键词映射；
          // state.stage 是机器名(generate_versions)，留给 agent 可视化用。
          streamingStage.value = state.message || state.stage || '处理中...'
          if (state.stage) {
            updateAgentByStage(state.stage, state.message)
          }
        },
      )
    } else {
      // SSE 流式模式（直连 FastAPI）
      await NovelAPI.generateChapterStream(
        project.value.id,
        chapterNumber,
        writingNotes,
        selectedPreset.value,
        {
          onStage: (payload) => {
            if (activeGenerationToken.value !== generationToken) {
              return
            }
            if (typeof payload?.message === 'string' && payload.message.trim()) {
              streamingStage.value = payload.message.trim()
            } else if (typeof payload?.stage === 'string' && payload.stage.trim()) {
              streamingStage.value = payload.stage.trim()
            }
            // 将 stage 事件映射到 Agent 节点状态更新
            if (payload?.stage) {
              updateAgentByStage(payload.stage, payload?.message)
            }
          },
          onTextDelta: (delta) => {
            if (activeGenerationToken.value !== generationToken) {
              return
            }
            if (!delta) {
              return
            }
            streamingDraftText.value += delta
          },
          onEvent: (event, payload) => {
            if (event === 'middle_product' && payload?.type) {
              if (payload.type === 'context_plan') {
                currentContextPlanData.value = payload.data || null
              } else if (payload.type === 'retrieval_evidence_summary') {
                currentEvidenceSummaryData.value = payload.data || null
              } else if (payload.type === 'prompt_compile_summary') {
                currentPromptCompileSummaryData.value = payload.data || null
              } else if (payload.type === 'verification_report') {
                currentVerificationReportData.value = payload.data || null
              } else if (payload.type === 'mission') {
                currentMissionData.value = payload.data || null
              } else if (payload.type === 'rag') {
                currentRagData.value = payload.data || null
              } else if (payload.type === 'foreshadowing') {
                currentForeshadowingData.value = payload.data || null
              } else if (payload.type === 'context') {
                currentContextData.value = payload.data || null
              } else if (payload.type === 'evidence_grade') {
                currentEvidenceGradeData.value = payload.data || null
              }
            }
          },
        },
        agentFlowConfigOverrides.value,
      )
    }

    // store 中的 project 已经被更新，所以我们不需要手动修改本地状态
    // chapterGenerationResult 也不再需要，因为 availableVersions 会从更新后的 project.chapters 中获取数据
    // showVersionSelector is now a computed property and will update automatically.
    chapterGenerationResult.value = null
    selectedVersionIndex.value = 0
  } catch (error) {
    console.error('生成章节失败:', error)

    // 将当前运行中的 Agent 标记为失败
    const runningNode = agentNodes.value.find((a) => a.status === 'running')
    if (runningNode) runningNode.status = 'failed'
    isAgentRunning.value = false

    const errMessage = error instanceof Error ? error.message : '未知错误'
    // 连接中断而非生成失败：中断后由 finally 里的对账决定说法，这里既不本地标失败
    // （否则会闪一下「生成失败」界面），也不弹红——含糊报失败会让用户以为积分白扣，
    // 于是刷新 + 再点一次生成，我们白烧一次上游调用。
    const interrupted = isStreamInterruption(error)
    if (interrupted) {
      interruptedChapter.value = chapterNumber
    } else if (project.value?.chapters) {
      // 错误状态的本地更新仍然是必要的，以立即反映UI
      const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
      if (chapter) {
        chapter.generation_status = 'failed'
      }
    }

    const upgradeKind = interrupted ? null : detectUpgradeHint(errMessage)
    if (upgradeKind) {
      // 402 积分不足 / 403 档位不足：给升级动线而不是裸报错（卷级规划同款模式）
      upgradePrompt.value = { show: true, kind: upgradeKind, message: errMessage }
    } else if (!interrupted) {
      globalAlert.showError(`生成章节失败: ${errMessage}`, '生成失败')
    }
  } finally {
    generatingChapter.value = null
    streamingStage.value = null
    streamingDraftText.value = ''
    streamingChapterNumber.value = null
    // 无论成功或失败，都重新加载项目以确保 UI 与后端同步
    // 防止轮询竞态条件：在生成期间的最后一次轮询可能返回过期数据并覆盖新状态
    try {
      await novelStore.loadProject(props.id, true)
    } catch {
      // 静默失败，不影响主流程
    }
    if (interruptedChapter.value === chapterNumber) {
      interruptedChapter.value = null
      reconcileInterruptedChapter(chapterNumber)
    }
  }
}

/**
 * 断线后与后端真实状态对账，再决定告诉用户什么。三种真相三种说法：
 * 已落库 → 交成果；仍在生成（异步任务路径断的是推送、任务还在跑）→ 说清楚并让既有
 * 轮询接管；已终止（SSE 路径会连带取消生产者任务并退款）→ 明说可以重新生成。
 */
const reconcileInterruptedChapter = (chapterNumber: number) => {
  const chapter = project.value?.chapters?.find((ch) => ch.chapter_number === chapterNumber)
  const status = chapter?.generation_status
  const hasVersions = (chapter?.versions?.length || 0) > 0

  if (status === 'waiting_for_confirm' || status === 'successful' || hasVersions) {
    selectChapter(chapterNumber)
    globalAlert.showSuccess('连接中断，但这一章在服务端已经写完，已为你载入', '已恢复')
    return
  }

  if (status === 'generating' || status === 'evaluating' || status === 'selecting') {
    // 选中该章可让 WDWorkspace 里既有的 10 秒轮询接管，无需另造一套轮询
    selectChapter(chapterNumber)
    globalAlert.showAlert('连接中断，服务端仍在生成，进度会自动刷新', 'info', '连接已中断')
    return
  }

  globalAlert.showAlert(
    '连接中断，本次生成已终止、积分已退回，可直接重新生成',
    'info',
    '连接已中断',
  )
}

const regenerateChapter = async () => {
  if (selectedChapterNumber.value !== null) {
    await generateChapter(selectedChapterNumber.value)
  }
}

const selectVersion = async (versionIndex: number) => {
  if (selectedChapterNumber.value === null || !availableVersions.value?.[versionIndex]?.content) {
    return
  }

  try {
    // 在本地立即更新状态以反映UI
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(
        (ch) => ch.chapter_number === selectedChapterNumber.value,
      )
      if (chapter) {
        chapter.generation_status = 'selecting'
      }
    }

    selectedVersionIndex.value = versionIndex
    await novelStore.selectChapterVersion(selectedChapterNumber.value, versionIndex)

    // 状态更新将由 store 自动触发，本地无需手动更新
    // 轮询机制会处理状态变更，成功后会自动隐藏选择器
    // showVersionSelector.value = false
    chapterGenerationResult.value = null
    globalAlert.showSuccess('版本已确认', '操作成功')
  } catch (error) {
    console.error('选择章节版本失败:', error)
    // 错误状态下恢复章节状态
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(
        (ch) => ch.chapter_number === selectedChapterNumber.value,
      )
      if (chapter) {
        chapter.generation_status = 'waiting_for_confirm' // Or the previous state
      }
    }
    globalAlert.showError(
      `选择章节版本失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '选择失败',
    )
  }
}

// 从详情弹窗中选择版本
const selectVersionFromDetail = async () => {
  selectedVersionIndex.value = detailVersionIndex.value
  await selectVersion(detailVersionIndex.value)
  closeVersionDetail()
}

// 从对比分屏中选用版本（选定即确认为本章正文）
const handleCompareSelect = async (index: number) => {
  showVersionCompare.value = false
  selectedVersionIndex.value = index
  await selectVersion(index)
}

const confirmVersionSelection = async () => {
  await selectVersion(selectedVersionIndex.value)
}

const openEditChapterModal = (chapter: ChapterOutline) => {
  editingChapter.value = chapter
  showEditChapterModal.value = true
}

const saveChapterChanges = async (updatedChapter: ChapterOutline) => {
  try {
    await novelStore.updateChapterOutline(updatedChapter)
    globalAlert.showSuccess('章节大纲已更新', '保存成功')
  } catch (error) {
    console.error('更新章节大纲失败:', error)
    globalAlert.showError(
      `更新章节大纲失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '保存失败',
    )
  } finally {
    showEditChapterModal.value = false
  }
}

const evaluateChapter = async () => {
  if (selectedChapterNumber.value !== null) {
    // 保存原始状态，用于失败时恢复
    let previousStatus:
      | 'not_generated'
      | 'generating'
      | 'evaluating'
      | 'selecting'
      | 'failed'
      | 'evaluation_failed'
      | 'waiting_for_confirm'
      | 'successful'
      | undefined

    try {
      // 在本地更新章节状态为evaluating以立即反映在UI上
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(
          (ch) => ch.chapter_number === selectedChapterNumber.value,
        )
        if (chapter) {
          previousStatus = chapter.generation_status // 保存原状态
          chapter.generation_status = 'evaluating'
        }
      }
      await novelStore.evaluateChapter(selectedChapterNumber.value)

      // 评审完成后，状态会通过store和轮询更新，这里不需要额外操作
      globalAlert.showSuccess('章节评审结果已生成', '评审成功')
    } catch (error) {
      console.error('评审章节失败:', error)

      // 错误状态下恢复章节状态为原始状态
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(
          (ch) => ch.chapter_number === selectedChapterNumber.value,
        )
        if (chapter && previousStatus) {
          chapter.generation_status = previousStatus // 恢复为原状态
        }
      }

      globalAlert.showError(
        `评审章节失败: ${error instanceof Error ? error.message : '未知错误'}`,
        '评审失败',
      )
    }
  }
}

const deleteChapter = async (chapterNumbers: number | number[]) => {
  const numbersToDelete = Array.isArray(chapterNumbers) ? chapterNumbers : [chapterNumbers]
  const confirmationMessage =
    numbersToDelete.length > 1
      ? `您确定要删除选中的 ${numbersToDelete.length} 个章节吗？这个操作无法撤销。`
      : `您确定要删除第 ${numbersToDelete[0]} 章吗？这个操作无法撤销。`

  if (window.confirm(confirmationMessage)) {
    try {
      await novelStore.deleteChapter(numbersToDelete)
      globalAlert.showSuccess('章节已删除', '操作成功')
      // If the currently selected chapter was deleted, unselect it
      if (selectedChapterNumber.value && numbersToDelete.includes(selectedChapterNumber.value)) {
        selectedChapterNumber.value = null
      }
    } catch (error) {
      console.error('删除章节失败:', error)
      globalAlert.showError(
        `删除章节失败: ${error instanceof Error ? error.message : '未知错误'}`,
        '删除失败',
      )
    }
  }
}

const generateOutline = async () => {
  showGenerateOutlineModal.value = true
}

const editChapterContent = async (data: { chapterNumber: number; content: string }) => {
  if (!project.value) return false

  try {
    await novelStore.editChapterContent(project.value.id, data.chapterNumber, data.content)
    globalAlert.showSuccess('章节内容已更新', '保存成功')
    return true
  } catch (error) {
    console.error('编辑章节内容失败:', error)
    globalAlert.showError(
      `编辑章节内容失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '保存失败',
    )
    return false
  }
}

const handleGenerateOutline = async (
  numChapters: number,
  estimatedTotalChapters?: number,
  userPrompt?: string,
) => {
  if (!project.value) return
  isGeneratingOutline.value = true
  try {
    const startChapter = (project.value.blueprint?.chapter_outline?.length || 0) + 1
    await novelStore.generateChapterOutline(
      startChapter,
      numChapters,
      estimatedTotalChapters,
      userPrompt,
    )
    globalAlert.showSuccess('新的章节大纲已生成', '操作成功')
  } catch (error) {
    console.error('生成大纲失败:', error)
    globalAlert.showError(
      `生成大纲失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '生成失败',
    )
  } finally {
    isGeneratingOutline.value = false
  }
}

const rebuildRag = async (forceFull: boolean = false) => {
  if (!project.value) return
  isRebuildingRag.value = true
  try {
    const result = await NovelAPI.rebuildRag(project.value.id, forceFull)
    if (result.indexed_chapters === 0 && result.skipped_chapters > 0) {
      globalAlert.showSuccess(
        `已检查 ${result.skipped_chapters} 个章节，内容未变化，无需重新索引。如需强制刷新，请右键点击"刷新知识库"按钮。`,
        '知识库无变化',
      )
    } else {
      globalAlert.showSuccess(
        `已重新索引 ${result.indexed_chapters} 个章节，跳过 ${result.skipped_chapters} 个未变化章节${forceFull ? '（强制全量刷新）' : ''}`,
        '知识库已刷新',
      )
    }
  } catch (error) {
    console.error('刷新知识库失败:', error)
    globalAlert.showError(
      `刷新知识库失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '刷新失败',
    )
  } finally {
    isRebuildingRag.value = false
  }
}

const onPredictionUpdated = async () => {
  if (!project.value) return

  // 自动刷新知识库（RAG），将推演结果纳入后续生成的检索范围
  try {
    await NovelAPI.rebuildRag(project.value.id)
    globalAlert.showSuccess('知识库已自动更新', '推演同步')
  } catch {
    // 知识库刷新失败不阻塞主流程
  }
}

// ---- 连续生成相关 ----

/** 计算下一个未完成章节号 */
const batchStartChapter = computed(() => {
  if (!project.value?.blueprint?.chapter_outline) return 1
  const outlines = [...project.value.blueprint.chapter_outline].sort(
    (a, b) => a.chapter_number - b.chapter_number,
  )
  for (const outline of outlines) {
    const chapter = project.value.chapters.find(
      (ch) => ch.chapter_number === outline.chapter_number,
    )
    if (!chapter || chapter.generation_status !== 'successful') {
      return outline.chapter_number
    }
  }
  // 所有章节都已完成，返回最后章节号 + 1
  return outlines.length > 0 ? outlines[outlines.length - 1].chapter_number + 1 : 1
})

/** 计算从起始章节开始最多可生成多少章（有大纲的） */
const batchMaxCount = computed(() => {
  if (!project.value?.blueprint?.chapter_outline) return 0
  const outlines = [...project.value.blueprint.chapter_outline].sort(
    (a, b) => a.chapter_number - b.chapter_number,
  )
  let count = 0
  for (const outline of outlines) {
    if (outline.chapter_number >= batchStartChapter.value) {
      const chapter = project.value.chapters.find(
        (ch) => ch.chapter_number === outline.chapter_number,
      )
      if (!chapter || chapter.generation_status !== 'successful') {
        count++
      }
    }
  }
  return count
})

const openBatchGenerateModal = () => {
  showBatchGenerateModal.value = true
}

const cancelBatchGenerate = () => {
  batchCancelled.value = true
}

const batchGenerateChapters = async (count: number, writingNotes?: string) => {
  if (!project.value) return

  const projectId = project.value.id
  const outlines = [...(project.value.blueprint?.chapter_outline || [])].sort(
    (a, b) => a.chapter_number - b.chapter_number,
  )

  // 收集目标章节列表：从起始章节开始，取未完成且有大纲的章节
  const targetChapters: number[] = []
  for (const outline of outlines) {
    if (targetChapters.length >= count) break
    if (outline.chapter_number < batchStartChapter.value) continue
    const chapter = project.value.chapters.find(
      (ch) => ch.chapter_number === outline.chapter_number,
    )
    if (!chapter || chapter.generation_status !== 'successful') {
      targetChapters.push(outline.chapter_number)
    }
  }

  if (targetChapters.length === 0) {
    globalAlert.showError('没有可生成的章节', '连续生成')
    return
  }

  batchGenerating.value = true
  batchCancelled.value = false
  batchProgress.value = { current: 0, total: targetChapters.length }

  let completedCount = 0
  let failedCount = 0

  // 异步任务模式：提交批量任务到 Go Gateway
  if (useAsyncMode.value) {
    try {
      batchProgress.value = { current: 1, total: targetChapters.length }
      streamingStage.value = '提交批量任务...'

      const result = await asyncGen.submitBatchGeneration(
        projectId,
        targetChapters,
        {
          preset: selectedPreset.value,
          use_agent_system: useAgent.value,
          ...(agentFlowConfigOverrides.value || {}),
        },
        (state) => {
          streamingStage.value = state.stage || state.message || '处理中...'
          // 根据进度更新 batchProgress
          const progressChapter = Math.ceil((state.progress / 100) * targetChapters.length)
          batchProgress.value = {
            current: Math.max(1, progressChapter),
            total: targetChapters.length,
          }
        },
      )

      if (result.status === 'completed') {
        completedCount = targetChapters.length
        globalAlert.showSuccess(`批量生成完成，共 ${completedCount} 章`, '连续生成')
      }
    } catch (error) {
      console.error('批量异步生成失败:', error)
      globalAlert.showError(
        `批量生成失败: ${error instanceof Error ? error.message : '未知错误'}`,
        '连续生成',
      )
    } finally {
      batchGenerating.value = false
      batchProgress.value = null
      generatingChapter.value = null
      streamingStage.value = null

      if (componentMounted.value) {
        try {
          await novelStore.loadProject(projectId, true)
        } catch {
          /* 静默 */
        }
      }
    }
    return
  }

  // SSE 模式：逐章生成
  try {
    for (const chapterNumber of targetChapters) {
      // 检查是否取消或组件已卸载
      if (batchCancelled.value || !componentMounted.value) break

      batchProgress.value = { current: completedCount + 1, total: targetChapters.length }

      // 更新 UI 状态
      generatingChapter.value = chapterNumber
      selectedChapterNumber.value = chapterNumber

      // 本地更新章节状态为 generating
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
        if (chapter) {
          chapter.generation_status = 'generating'
        } else {
          const outline = project.value.blueprint?.chapter_outline?.find(
            (o) => o.chapter_number === chapterNumber,
          )
          project.value.chapters.push({
            chapter_number: chapterNumber,
            title: outline?.title || '加载中...',
            summary: outline?.summary || '',
            content: '',
            versions: [],
            evaluation: null,
            generation_status: 'generating',
          } as Chapter)
        }
      }

      try {
        // 调用生成 API，获取含 best_version_index 的原始响应
        const result: AdvancedGenerateResponse = await NovelAPI.generateChapterRaw(
          projectId,
          chapterNumber,
          writingNotes,
          selectedPreset.value,
          agentFlowConfigOverrides.value,
        )

        // 再次检查是否取消或组件已卸载（生成过程中可能点了取消或离开页面）
        if (batchCancelled.value || !componentMounted.value) {
          // 已生成但取消了，仍然选版以免浪费
          try {
            await NovelAPI.selectChapterVersion(projectId, chapterNumber, result.best_version_index)
            completedCount++
          } catch (selectErr) {
            console.warn(`取消时选版失败（第 ${chapterNumber} 章）:`, selectErr)
          }
          if (componentMounted.value) {
            try {
              await novelStore.loadProject(projectId, true)
            } catch {
              /* 静默 */
            }
          }
          break
        }

        // 自动选版
        await NovelAPI.selectChapterVersion(projectId, chapterNumber, result.best_version_index)

        // 刷新项目状态
        await novelStore.loadProject(projectId, true)
        completedCount++
      } catch (error) {
        console.error(`连续生成：第 ${chapterNumber} 章失败:`, error)
        failedCount++

        // 更新本地失败状态
        if (componentMounted.value && project.value?.chapters) {
          const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
          if (chapter) {
            chapter.generation_status = 'failed'
          }
        }

        // 失败后停止连续生成
        break
      } finally {
        generatingChapter.value = null
      }
    }
  } finally {
    batchGenerating.value = false
    batchProgress.value = null
    generatingChapter.value = null

    // 最终刷新一次项目状态（仅组件仍挂载时）
    if (componentMounted.value) {
      try {
        await novelStore.loadProject(projectId, true)
      } catch {
        // 静默失败
      }

      // 显示结果提示
      if (batchCancelled.value) {
        globalAlert.showSuccess(`已取消连续生成，共完成 ${completedCount} 章`, '连续生成已取消')
      } else if (failedCount > 0) {
        globalAlert.showError(`连续生成中断：完成 ${completedCount} 章，失败 1 章`, '连续生成异常')
      } else {
        globalAlert.showSuccess(`连续生成完成，共 ${completedCount} 章`, '连续生成完成')
      }
    }

    batchCancelled.value = false
  }
}

onMounted(() => {
  document.body.classList.add('m3-novel')
  loadProject()
  fetchAgentSetting()

  // 连接 WebSocket（Go Gateway 实时推送）
  const { connect: wsConnect } = useWebSocket()
  wsConnect()

  // 检测 Go Gateway 可用性，决定使用异步任务模式还是 SSE 流式模式
  detectAsyncMode()
})

onUnmounted(() => {
  document.body.classList.remove('m3-novel')
  componentMounted.value = false
  if (batchGenerating.value) {
    batchCancelled.value = true
  }

  // 断开 WebSocket
  const { disconnect: wsDisconnect } = useWebSocket()
  wsDisconnect()
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap');

:global(body.m3-novel) {
  --md-font-family: 'Manrope', 'Noto Sans SC', 'Noto Sans', 'PingFang SC', sans-serif;
  --md-primary: #ffe500;
  --md-primary-light: #fff062;
  --md-primary-dark: #e6ce00;
  --md-on-primary: #000000;
  --md-primary-container: #2a2600;
  --md-on-primary-container: #ffe500;
  --md-secondary: #888888;
  --md-secondary-light: #aaaaaa;
  --md-secondary-dark: #666666;
  --md-on-secondary: #ffffff;
  --md-secondary-container: #1c1c1c;
  --md-on-secondary-container: #cccccc;
  --md-surface: #141414;
  --md-surface-dim: #0a0a0a;
  --md-surface-container-lowest: #0a0a0a;
  --md-surface-container-low: #141414;
  --md-surface-container: #1c1c1c;
  --md-surface-container-high: #242424;
  --md-surface-container-highest: #2a2a2a;
  --md-on-surface: #ffffff;
  --md-on-surface-variant: #888888;
  --md-outline: #2a2a2a;
  --md-outline-variant: #1c1c1c;
  --md-error: #ff4757;
  --md-error-container: #3d0a0a;
  --md-on-error: #ffffff;
  --md-on-error-container: #ff9eb8;
  --md-success: #2ed573;
  --md-success-container: #0a2a1a;
  --md-on-success: #000000;
  --md-on-success-container: #2ed573;
  --md-warning-container: #2a2600;
  --md-on-warning-container: #ffe500;
  --md-background: #0a0a0a;
  --md-on-background: #ffffff;
  color: var(--md-on-surface);
  font-family: var(--md-font-family);
}

.m3-shell {
  background: #0a0a0a;
  color: var(--md-on-surface);
  font-family: var(--md-font-family);
  animation: m3-fade 0.6s ease-out both;
}

@media (prefers-reduced-motion: reduce) {
  .m3-shell {
    animation: none;
  }
}

/* 自定义样式 */
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: #2a2a2a;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* 动画效果 */
@keyframes m3-fade {
  from {
    opacity: 0;
    transform: translateY(18px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>

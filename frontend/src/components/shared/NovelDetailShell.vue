<!-- AIMETA P=小说详情壳_详情页布局容器|R=详情页布局_导航|NR=不含具体内容|E=component:NovelDetailShell|X=internal|A=布局组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="min-h-screen" style="background: #0A0A0A; font-family: 'Inter', sans-serif;">

    <!-- ==================== Global Nav Bar (User Mode) ==================== -->
    <header v-if="!isAdmin" class="sticky top-0 z-40 border-b" style="background: rgba(10,10,10,0.85); backdrop-filter: blur(12px); border-color: #2A2A2A;">
      <div class="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <!-- Logo -->
        <router-link to="/home" class="flex items-center gap-2.5 flex-shrink-0">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background: #FFE500;">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color: #000;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
            </svg>
          </div>
          <span class="text-xl font-bold tracking-tight" style="font-family: 'Space Grotesk', sans-serif; color: #fff;">Octopus AI Novel</span>
        </router-link>

        <!-- Nav Links -->
        <nav class="hidden md:flex items-center gap-7">
          <router-link to="/inspiration" class="nav-link">灵感模式</router-link>
          <router-link to="/workspace" class="nav-link nav-link-active">我的小说</router-link>
          <button class="nav-link" @click="goToWritingDesk">写作台</button>
          <router-link to="/settings" class="nav-link">设置</router-link>
        </nav>

        <!-- User Menu -->
        <div class="flex items-center gap-3 flex-shrink-0">
          <div class="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold" style="background: #FFE500; color: #000;">创</div>
          <span class="text-sm hidden sm:inline" style="color: #fff;">{{ authStore.user?.username || '' }}</span>
        </div>
      </div>
    </header>

    <!-- ==================== Admin Header ==================== -->
    <header v-else class="sticky top-0 z-40 border-b" style="background: rgba(10,10,10,0.92); backdrop-filter: blur(12px); border-color: #2A2A2A;">
      <div class="max-w-7xl mx-auto px-6 h-14 flex items-center gap-4">
        <button class="text-sm transition-colors flex items-center gap-1.5" style="color: #888;" @click="goBack"
          @mouseenter="($event.target as HTMLElement).style.color='#fff'" @mouseleave="($event.target as HTMLElement).style.color='#888'">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          返回管理
        </button>
        <div class="h-4 w-px" style="background: #2A2A2A;"></div>
        <h1 class="text-base font-semibold text-white truncate">{{ formattedTitle }}</h1>
      </div>
    </header>

    <!-- ==================== Main Content ==================== -->
    <div class="max-w-7xl mx-auto px-6 pb-16">

      <!-- Breadcrumb (User Mode) -->
      <div v-if="!isAdmin" class="flex items-center gap-2 text-sm pt-8 mb-6">
        <router-link to="/workspace" class="transition-colors" style="color: #888;"
          @mouseenter="($event.target as HTMLElement).style.color='#FFE500'" @mouseleave="($event.target as HTMLElement).style.color='#888'">
          我的小说
        </router-link>
        <span style="color: #555;">/</span>
        <span style="color: #fff;">{{ novelTitle }}</span>
      </div>

      <!-- Novel Hero (User Mode) -->
      <section v-if="!isAdmin" class="novel-hero mb-8">
        <div class="novel-cover-wrap">
          <div class="novel-cover" :class="{ 'novel-cover--generated': coverObjectUrl }">
            <img v-if="coverObjectUrl" :src="coverObjectUrl" :alt="`${novelTitle} 小说封面`">
            <div v-else class="novel-cover__fallback" :style="{ background: genreAvatarBg }">
              <span>{{ genreEmoji }}</span>
              <strong>{{ novelTitle }}</strong>
              <small>{{ novelGenre || '原创小说' }}</small>
            </div>
            <div class="novel-cover__shine"></div>
            <span v-if="coverObjectUrl" class="novel-cover__ai">AI COVER</span>
          </div>
          <button type="button" class="novel-cover-action" @click="openCoverDialog">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 20h9M16.5 3.5a2.12 2.12 0 013 3L8 18l-4 1 1-4L16.5 3.5z" />
            </svg>
            {{ coverObjectUrl ? '重新设计封面' : 'AI 生成封面' }}
          </button>
        </div>

        <div class="novel-hero__content">
          <div class="novel-hero__eyebrow">
            <span>ORIGINAL STORY</span>
            <i></i>
            <span>{{ novelGenre || '待设定类型' }}</span>
          </div>
          <h1>{{ novelTitle }}</h1>
          <div class="novel-hero__meta">
            <span v-if="novelGenre" class="novel-genre">{{ novelGenre }}</span>
            <span v-if="sectionData.overview?.is_completed || novel?.is_completed" class="novel-completed">已完结</span>
            <span>作者 {{ authStore.user?.username || '—' }}</span>
            <span v-if="overviewMeta.updated_at">更新于 {{ formatDateTime(overviewMeta.updated_at) }}</span>
          </div>
          <p class="novel-hero__summary">{{ novelDescription || '还没有填写一句话梗概，可在下方概览中补充作品的核心卖点。' }}</p>

          <div class="novel-hero__stats">
            <div><strong>{{ progressTotal }}</strong><span>规划章节</span></div>
            <div><strong>{{ progressCompleted }}</strong><span>已完成</span></div>
            <div><strong>{{ progressPercent }}%</strong><span>创作进度</span></div>
          </div>

          <div class="novel-hero__actions">
            <button class="novel-primary-action" type="button" @click="goToWritingDesk">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
              进入写作台
            </button>
            <button class="novel-secondary-action" type="button" @click="openCoverDialog">
              {{ coverObjectUrl ? '更新封面' : '制作封面' }}
            </button>
          </div>
        </div>

        <div class="novel-progress-card">
          <span>创作进度</span>
          <div class="relative w-24 h-24">
            <svg class="w-full h-full" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="none" stroke="#30302A" stroke-width="5" />
              <circle cx="50" cy="50" r="42" fill="none" stroke="#FFE500" stroke-width="5"
                stroke-linecap="round"
                :stroke-dasharray="circumference"
                :stroke-dashoffset="circumference - (progressPercent / 100) * circumference"
                transform="rotate(-90 50 50)"
                style="transition: stroke-dashoffset 0.7s ease;" />
            </svg>
            <strong>{{ progressPercent }}%</strong>
          </div>
          <small>{{ progressCompleted }} / {{ progressTotal }} 章完成</small>
          <div class="novel-progress-card__line"><i :style="{ width: progressPercent + '%' }"></i></div>
        </div>
      </section>

      <!-- ==================== Tab Bar ====================
           标签条横向滚动，但主操作必须留在滚动容器外：此前「开始创作」用 ml-auto 挂在
           标签条末尾，390px 屏上它在 x=840 处，用户得把标签条一路划到底才能看见整个页面
           最主要的按钮。 -->
      <div class="flex items-end gap-3 border-b" style="border-color: #2A2A2A;" :class="isAdmin ? 'mt-6' : ''">
        <div class="flex items-end gap-1 overflow-x-auto scrollbar-hide flex-1 min-w-0">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            type="button"
            @click="switchSection(tab.key)"
            class="px-4 py-3 text-sm font-medium transition-colors whitespace-nowrap -mb-px flex-shrink-0"
            :class="activeSection === tab.key
              ? 'border-b-2'
              : 'hover:text-white'"
            :style="activeSection === tab.key
              ? 'color: #FFE500; border-color: #FFE500;'
              : 'color: #888;'"
          >
            {{ tab.label }}
          </button>
        </div>

        <div v-if="!isAdmin" class="flex-shrink-0 pb-2 flex items-center gap-2">
          <button class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all border hover:opacity-90"
            style="border-color: #2A2A2A; color: #fff; background: transparent;"
            :disabled="exportBusy"
            @click="exportBook('txt')">
            {{ exportBusy ? '导出中…' : '导出全书' }}
          </button>
          <button class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-all border hover:opacity-90"
            style="border-color: #2A2A2A; color: #fff; background: transparent;"
            :disabled="exportBusy"
            @click="exportBook('markdown')">
            MD
          </button>
          <button class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-semibold transition-all border hover:opacity-90"
            style="border-color: #2A2A2A; color: #fff; background: transparent;"
            :disabled="exportBusy"
            @click="exportBook('docx')">
            DOCX
          </button>
          <button class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all border hover:opacity-90"
            :style="shareEnabled
              ? 'border-color: #FFE500; color: #FFE500; background: rgba(255,229,0,0.08);'
              : 'border-color: #2A2A2A; color: #fff; background: transparent;'"
            :disabled="shareBusy"
            @click="handleShareClick">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
            </svg>
            {{ shareBusy ? '处理中...' : '分享' }}
          </button>
        </div>
      </div>

      <!-- ==================== Section Content ==================== -->
      <div class="mt-6" :class="contentContainerClass">
        <!-- Loading State -->
        <div v-if="isSectionLoading" class="flex flex-col items-center justify-center py-20">
          <div class="w-8 h-8 border-2 rounded-full animate-spin" style="border-color: #2A2A2A; border-top-color: #FFE500;"></div>
          <p class="mt-4 text-sm" style="color: #888;">加载中...</p>
        </div>

        <!-- Error State -->
        <div v-else-if="currentError" class="flex flex-col items-center justify-center py-20 space-y-4">
          <div class="w-14 h-14 rounded-full flex items-center justify-center" style="background: rgba(255, 71, 87, 0.15);">
            <svg class="w-7 h-7" style="color: #FF4757;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p class="text-sm text-center" style="color: #fff;">{{ currentError }}</p>
          <button class="px-5 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-90"
            style="background: #FFE500; color: #000;" @click="reloadSection(activeSection, true)">
            重试
          </button>
        </div>

        <!-- Content Component -->
        <component
          v-else
          ref="sectionRef"
          :is="currentComponent"
          v-bind="componentProps"
          :class="componentContainerClass"
          @edit="handleSectionEdit"
          @add="startAddChapter"
          @regenerate="handleRegenerate"
          @delete-outlines="handleDeleteOutlines"
          @batch-generate="handleBatchGenerate"
          @batch-predict="handleBatchPredict"
          @switch-section="switchSection"
          @toggle-completed="handleToggleCompleted"
        />
      </div>
    </div>

    <NovelCoverDialog
      v-if="!isAdmin"
      :show="coverDialogOpen"
      :title="novelTitle"
      :current-cover-url="coverObjectUrl"
      :generating="coverGenerating"
      :error="coverError"
      :options-loading="coverOptionsLoading"
      :can-generate="coverOptions.can_generate"
      :credit-price="coverOptions.credit_price"
      :required-tier="coverOptions.required_tier"
      @close="coverDialogOpen = false"
      @generate="handleGenerateCover"
    />

    <!-- ==================== Blueprint Edit Modal ==================== -->
    <BlueprintEditModal
      v-if="!isAdmin"
      :show="isModalOpen"
      :title="modalTitle"
      :content="modalContent"
      :field="modalField"
      :project-id="projectId"
      :power-systems="powerSystems"
      @close="isModalOpen = false"
      @save="handleSave"
    />

    <!-- ==================== Share Panel Modal ==================== -->
    <transition
      enter-active-class="transition-all duration-200"
      leave-active-class="transition-all duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div v-if="isSharePanelOpen && !isAdmin" class="fixed inset-0 z-50 flex items-center justify-center" style="background: rgba(0,0,0,0.6);">
        <div class="absolute inset-0" @click="isSharePanelOpen = false"></div>
        <div class="relative w-full max-w-lg mx-4 rounded-2xl border" style="background: #141414; border-color: #2A2A2A;" @click.stop>
          <div class="px-6 py-5 border-b" style="border-color: #2A2A2A;">
            <h3 class="text-lg font-semibold text-white">公开分享</h3>
            <p class="text-xs mt-1.5 leading-5" style="color: #888;">任何人凭此链接可免登录阅读已完稿章节；关闭分享后链接立刻失效。</p>
          </div>
          <div class="px-6 py-5 space-y-4">
            <div class="flex items-center gap-2">
              <input :value="shareUrl" type="text" readonly
                class="flex-1 min-w-0 px-4 py-2.5 rounded-xl text-sm outline-none"
                style="background: #1C1C1C; border: 1px solid #2A2A2A; color: #fff;"
                @focus="($event.target as HTMLInputElement).select()">
              <button type="button" class="flex-shrink-0 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all hover:opacity-90"
                style="background: #FFE500; color: #000;" @click="copyShareUrl">
                {{ shareCopied ? '已复制' : '复制链接' }}
              </button>
            </div>
          </div>
          <div class="flex items-center justify-between gap-3 px-6 py-4 border-t" style="border-color: #2A2A2A;">
            <button type="button" class="px-4 py-2 rounded-lg text-sm transition-colors"
              style="color: #FF4757; border: 1px solid rgba(255,71,87,0.4);"
              :disabled="shareBusy" @click="disableShare">
              关闭分享
            </button>
            <button type="button" class="px-4 py-2 rounded-lg text-sm transition-colors" style="color: #888; border: 1px solid #2A2A2A;"
              @click="isSharePanelOpen = false">完成</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ==================== Add Chapter Modal ==================== -->
    <transition
      enter-active-class="transition-all duration-200"
      leave-active-class="transition-all duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div v-if="isAddChapterModalOpen && !isAdmin" class="fixed inset-0 z-50 flex items-center justify-center" style="background: rgba(0,0,0,0.6);">
        <div class="absolute inset-0" @click="cancelNewChapter"></div>
        <div class="relative w-full max-w-lg mx-4 rounded-2xl border" style="background: #141414; border-color: #2A2A2A;" @click.stop>
          <div class="px-6 py-5 border-b" style="border-color: #2A2A2A;">
            <h3 class="text-lg font-semibold text-white">新增章节大纲</h3>
          </div>
          <div class="px-6 py-5 space-y-5">
            <div>
              <label for="new-chapter-title" class="block text-sm font-medium mb-2" style="color: #888;">章节标题</label>
              <input id="new-chapter-title" v-model="newChapterTitle" type="text"
                class="w-full px-4 py-2.5 rounded-xl text-sm outline-none transition-colors"
                style="background: #1C1C1C; border: 1px solid #2A2A2A; color: #fff;"
                placeholder="例如：意外的相遇">
            </div>
            <div>
              <label for="new-chapter-summary" class="block text-sm font-medium mb-2" style="color: #888;">章节摘要</label>
              <textarea id="new-chapter-summary" v-model="newChapterSummary" rows="4"
                class="w-full px-4 py-2.5 rounded-xl text-sm outline-none transition-colors resize-none"
                style="background: #1C1C1C; border: 1px solid #2A2A2A; color: #fff;"
                placeholder="简要描述本章发生的主要事件"></textarea>
            </div>
          </div>
          <div class="flex items-center justify-end gap-3 px-6 py-4 border-t" style="border-color: #2A2A2A;">
            <button type="button" class="px-4 py-2 rounded-lg text-sm transition-colors" style="color: #888; border: 1px solid #2A2A2A;"
              @click="cancelNewChapter">取消</button>
            <button type="button" class="px-5 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-90"
              style="background: #FFE500; color: #000;" @click="saveNewChapter">保存</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { useAuthStore } from '@/stores/auth'
import { NovelAPI } from '@/api/novel'
import { AdminAPI } from '@/api/admin'
import { shareApi } from '@/api/share'
import { getProjectAnalysis, type ProjectAnalysis } from '@/api/gatekeeperReview'
import type { CoverGenerationOptions, GenerateCoverPayload, NovelCoverInfo, NovelProject, NovelSectionResponse, NovelSectionType, AllSectionType } from '@/api/novel'
import { formatDateTime } from '@/utils/date'
import BlueprintEditModal from '@/components/BlueprintEditModal.vue'
import OverviewSection from '@/components/novel-detail/OverviewSection.vue'
import WorldSettingSection from '@/components/novel-detail/WorldSettingSection.vue'
import CharactersSection from '@/components/novel-detail/CharactersSection.vue'
import RelationshipsSection from '@/components/novel-detail/RelationshipsSection.vue'
import ChapterOutlineSection from '@/components/novel-detail/ChapterOutlineSection.vue'
import ChaptersSection from '@/components/novel-detail/ChaptersSection.vue'
import EmotionCurveSection from '@/components/novel-detail/EmotionCurveSection.vue'
import ForeshadowingSection from '@/components/novel-detail/ForeshadowingSection.vue'
import VolumesSection from '@/components/novel-detail/VolumesSection.vue'
import WriterPersonaPanel from '@/components/WriterPersonaPanel.vue'
import ConceptLibrarySection from '@/components/novel-detail/ConceptLibrarySection.vue'
import NovelCoverDialog from '@/components/novel-detail/NovelCoverDialog.vue'

const fetchPowerSystems = async () => {
  try {
    const authStore = useAuthStore()
    const url = '/api/power-systems'
    const headers = new Headers({ 'Content-Type': 'application/json' })
    if (authStore.isAuthenticated && authStore.token) {
      headers.set('Authorization', `Bearer ${authStore.token}`)
    }
    const response = await fetch(url, { headers })
    if (response.ok) return await response.json()
    return []
  } catch (err) {
    console.error('获取力量体系失败', err)
    return []
  }
}

interface Props {
  isAdmin?: boolean
}

type SectionKey = AllSectionType | 'writer_persona' | 'concept_library' | 'volumes'

const props = withDefaults(defineProps<Props>(), {
  isAdmin: false
})

const route = useRoute()
const router = useRouter()
const novelStore = useNovelStore()
const authStore = useAuthStore()

const projectId = route.params.id as string

const tabs: Array<{ key: SectionKey; label: string }> = [
  { key: 'overview', label: '概览' },
  { key: 'chapters', label: '章节列表' },
  { key: 'characters', label: '人物' },
  { key: 'world_setting', label: '世界观' },
  { key: 'chapter_outline', label: '大纲' },
  { key: 'volumes', label: '分卷规划' },
  { key: 'foreshadowing', label: '伏笔' },
  { key: 'emotion_curve', label: '情感曲线' },
  { key: 'concept_library', label: '设定库' },
]

const sectionComponents: Record<SectionKey, any> = {
  overview: OverviewSection,
  world_setting: WorldSettingSection,
  characters: CharactersSection,
  relationships: RelationshipsSection,
  chapter_outline: ChapterOutlineSection,
  chapters: ChaptersSection,
  emotion_curve: EmotionCurveSection,
  foreshadowing: ForeshadowingSection,
  volumes: VolumesSection,
  writer_persona: WriterPersonaPanel,
  concept_library: ConceptLibrarySection
}

const sectionData = reactive<Partial<Record<SectionKey, any>>>({})
const sectionLoading = reactive<Record<SectionKey, boolean>>({
  overview: false, world_setting: false, characters: false,
  relationships: false, chapter_outline: false, chapters: false,
  emotion_curve: false, foreshadowing: false, writer_persona: false,
  concept_library: false, volumes: false
})
const sectionError = reactive<Record<SectionKey, string | null>>({
  overview: null, world_setting: null, characters: null,
  relationships: null, chapter_outline: null, chapters: null,
  emotion_curve: null, foreshadowing: null, writer_persona: null,
  concept_library: null, volumes: null
})

const overviewMeta = reactive<{ title: string; updated_at: string | null }>({
  title: '加载中...',
  updated_at: null
})

const activeSection = ref<SectionKey>('overview')
const powerSystems = ref<Array<{ id: number, name: string, levels: Array<{ id: number, name: string }> }>>([])

const isModalOpen = ref(false)
const modalTitle = ref('')
const modalContent = ref<any>('')
const modalField = ref('')

const isAddChapterModalOpen = ref(false)
const newChapterTitle = ref('')
const newChapterSummary = ref('')

// ==================== 公开分享 ====================

const exportBusy = ref(false)

// ==================== AI 小说封面 ====================

const coverDialogOpen = ref(false)
const coverGenerating = ref(false)
const coverError = ref('')
const coverObjectUrl = ref('')
const coverOptionsLoading = ref(false)
const coverOptions = ref<CoverGenerationOptions>({
  tier: 'free',
  required_tier: 'creator',
  can_generate: false,
  credit_price: 0
})

const loadCoverOptions = async () => {
  if (props.isAdmin || !projectId || coverOptionsLoading.value) return
  coverOptionsLoading.value = true
  try {
    coverOptions.value = await NovelAPI.getCoverGenerationOptions(projectId)
  } catch (error) {
    coverOptions.value.can_generate = false
    coverError.value = error instanceof Error ? error.message : '暂时无法读取封面生成权限'
  } finally {
    coverOptionsLoading.value = false
  }
}

const openCoverDialog = async () => {
  coverError.value = ''
  coverDialogOpen.value = true
  await loadCoverOptions()
}

const releaseCoverObjectUrl = () => {
  if (!coverObjectUrl.value) return
  URL.revokeObjectURL(coverObjectUrl.value)
  coverObjectUrl.value = ''
}

const loadCover = async () => {
  const coverInfo = sectionData.overview?.cover_image || novel.value?.cover_image
  if (!coverInfo || !projectId) {
    releaseCoverObjectUrl()
    return
  }
  try {
    const blob = await NovelAPI.getCoverBlob(projectId)
    releaseCoverObjectUrl()
    coverObjectUrl.value = URL.createObjectURL(blob)
  } catch (error) {
    console.warn('封面加载失败:', error)
    releaseCoverObjectUrl()
  }
}

const handleGenerateCover = async (payload: GenerateCoverPayload) => {
  if (coverGenerating.value || !projectId) return
  coverGenerating.value = true
  coverError.value = ''
  try {
    const result = await NovelAPI.generateCover(projectId, payload)
    if (sectionData.overview) sectionData.overview.cover_image = result.cover_image
    if (novel.value) novel.value.cover_image = result.cover_image as NovelCoverInfo
    await loadCover()
    coverDialogOpen.value = false
  } catch (error) {
    coverError.value = error instanceof Error ? error.message : '封面生成失败，请稍后重试'
  } finally {
    coverGenerating.value = false
  }
}

const exportBook = async (format: 'txt' | 'markdown' | 'docx') => {
  if (!projectId || exportBusy.value) return
  exportBusy.value = true
  try {
    await NovelAPI.exportManuscript(projectId, format)
  } catch (err) {
    console.error(err)
  } finally {
    exportBusy.value = false
  }
}

const shareEnabled = ref(false)
const shareToken = ref<string | null>(null)
const shareBusy = ref(false)
const isSharePanelOpen = ref(false)
const shareCopied = ref(false)

const shareUrl = computed(() =>
  shareToken.value ? `${window.location.origin}/share/${shareToken.value}` : ''
)

const loadShareStatus = async () => {
  if (props.isAdmin || !projectId) return
  try {
    const status = await shareApi.getStatus(projectId)
    shareEnabled.value = status.enabled
    shareToken.value = status.share_token
  } catch {
    // 分享状态取不到不影响详情页主体，按钮保持「未开启」形态即可
  }
}

const copyShareUrl = async () => {
  if (!shareUrl.value) return
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    shareCopied.value = true
    setTimeout(() => (shareCopied.value = false), 2000)
  } catch {
    // 剪贴板不可用（如非 https）：面板里展示着链接，可手动全选复制
  }
}

const handleShareClick = async () => {
  if (shareBusy.value) return
  if (shareEnabled.value) {
    isSharePanelOpen.value = true
    return
  }
  shareBusy.value = true
  try {
    const result = await shareApi.enable(projectId)
    shareEnabled.value = true
    shareToken.value = result.share_token
    isSharePanelOpen.value = true
    await copyShareUrl()
  } catch (error) {
    console.error('开启分享失败:', error)
    alert(error instanceof Error ? error.message : '开启分享失败')
  } finally {
    shareBusy.value = false
  }
}

const disableShare = async () => {
  if (shareBusy.value) return
  shareBusy.value = true
  try {
    await shareApi.disable(projectId)
    shareEnabled.value = false
    shareToken.value = null
    isSharePanelOpen.value = false
  } catch (error) {
    console.error('关闭分享失败:', error)
    alert(error instanceof Error ? error.message : '关闭分享失败')
  } finally {
    shareBusy.value = false
  }
}

const novel = computed(() => !props.isAdmin ? novelStore.currentProject as NovelProject | null : null)
const sectionRef = ref<any>(null)
const projectAnalysis = ref<ProjectAnalysis | null>(null)

// ==================== Novel Header Computed ====================

const novelTitle = computed(() => {
  const raw = overviewMeta.title || '加载中...'
  return raw.startsWith('《') ? raw.slice(1, -1) : raw
})

const formattedTitle = computed(() => {
  const title = overviewMeta.title || '加载中...'
  return title.startsWith('《') && title.endsWith('》') ? title : `《${title}》`
})

const novelGenre = computed(() => sectionData.overview?.genre || '')
const novelDescription = computed(() => sectionData.overview?.one_sentence_summary || '')

const genreEmoji = computed(() => {
  const g = novelGenre.value.toLowerCase()
  if (g.includes('仙侠') || g.includes('武侠')) return '⚔️'
  if (g.includes('都市')) return '🏙️'
  if (g.includes('玄幻') || g.includes('奇幻')) return '🌟'
  if (g.includes('科幻')) return '🚀'
  if (g.includes('言情') || g.includes('恋爱')) return '❤️'
  if (g.includes('悬疑') || g.includes('推理')) return '🔍'
  if (g.includes('历史')) return '📜'
  return '📚'
})

const genreAvatarBg = computed(() => {
  const g = novelGenre.value.toLowerCase()
  if (g.includes('仙侠') || g.includes('武侠')) return 'rgba(168, 85, 247, 0.2)'
  if (g.includes('都市')) return 'rgba(99, 102, 241, 0.2)'
  if (g.includes('玄幻') || g.includes('奇幻')) return 'rgba(255, 229, 0, 0.2)'
  if (g.includes('科幻')) return 'rgba(0, 180, 216, 0.2)'
  if (g.includes('言情') || g.includes('恋爱')) return 'rgba(255, 105, 180, 0.2)'
  return 'rgba(136, 136, 136, 0.15)'
})

const circumference = 2 * Math.PI * 42

const progressCompleted = computed(() => {
  if (!sectionData.chapters?.chapters) return 0
  return sectionData.chapters.chapters.filter((c: any) => c.generation_status === 'successful').length
})

const progressTotal = computed(() => {
  return sectionData.chapter_outline?.chapter_outline?.length || progressCompleted.value || 0
})

const progressPercent = computed(() => {
  if (progressTotal.value === 0) return 0
  return Math.round((progressCompleted.value / progressTotal.value) * 100)
})

// ==================== Content Layout ====================

const contentContainerClass = computed(() => {
  if (activeSection.value === 'chapters') return 'h-[calc(100vh-200px)] flex flex-col overflow-hidden'
  return ''
})

const componentContainerClass = computed(() => {
  if (activeSection.value === 'chapters') return 'flex-1 min-h-0 h-full flex flex-col overflow-hidden'
  return 'overflow-y-auto'
})

// ==================== Section Loading ====================

const ensureProjectLoaded = async () => {
  if (props.isAdmin || !projectId) return
  if (novel.value) return
  await novelStore.loadProject(projectId)
}

const loadProjectAnalysis = async () => {
  if (!projectId || props.isAdmin) return
  try {
    const resp = await getProjectAnalysis(projectId)
    projectAnalysis.value = resp.analysis
  } catch {
    projectAnalysis.value = null
  }
}

const loadSection = async (section: SectionKey, force = false) => {
  if (!projectId) return

  // volumes 与 analysis 系列一样由组件自行取数（专用端点），不走通用 section 接口
  const analysisSections: SectionKey[] = ['emotion_curve', 'foreshadowing', 'writer_persona', 'concept_library', 'volumes']
  if (analysisSections.includes(section)) return

  if (!force && sectionData[section]) return

  sectionLoading[section] = true
  sectionError[section] = null
  try {
    const response: NovelSectionResponse = props.isAdmin
      ? await AdminAPI.getNovelSection(projectId, section as NovelSectionType)
      : await NovelAPI.getSection(projectId, section as NovelSectionType)
    sectionData[section] = response.data
    if (section === 'overview') {
      overviewMeta.title = response.data?.title || overviewMeta.title
      overviewMeta.updated_at = response.data?.updated_at || null
      await loadCover()
      loadProjectAnalysis()
    }
  } catch (error) {
    console.error('加载模块失败:', error)
    sectionError[section] = error instanceof Error ? error.message : '加载失败'
  } finally {
    sectionLoading[section] = false
  }
}

const reloadSection = (section: SectionKey, force = false) => {
  loadSection(section, force)
}

const switchSection = (section: SectionKey | string) => {
  activeSection.value = section as SectionKey
  loadSection(section as SectionKey)
  if (section === 'chapter_outline') loadSection('chapters')
  if (section === 'relationships') loadSection('characters')
}

const goBack = () => router.push(props.isAdmin ? '/admin' : '/workspace')

const goToWritingDesk = async () => {
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) {
    router.push(`/novel/${projectId}`)
    return
  }
  const path = project.title === '未命名灵感' ? `/inspiration?project_id=${project.id}` : `/novel/${project.id}`
  router.push(path)
}

// ==================== Component Props ====================

const currentComponent = computed(() => sectionComponents[activeSection.value])
const isSectionLoading = computed(() => sectionLoading[activeSection.value])
const currentError = computed(() => sectionError[activeSection.value])

const componentProps = computed(() => {
  const data = sectionData[activeSection.value]
  const editable = !props.isAdmin

  switch (activeSection.value) {
    case 'overview':
      return {
        data: data || null,
        editable,
        chapters: sectionData.chapters?.chapters || [],
        characters: sectionData.characters?.characters || [],
        totalOutlines: sectionData.chapter_outline?.chapter_outline?.length || 0,
        isLoading: sectionLoading.chapters || sectionLoading.characters,
        projectId,
        isCompleted: sectionData.overview?.is_completed ?? novel.value?.is_completed ?? false,
        analysisData: projectAnalysis.value
      }
    case 'world_setting':
      return { data: data || null, editable }
    case 'characters':
      return { data: data || null, editable, powerSystems: powerSystems.value }
    case 'relationships':
      return { data: { ...(data || {}), characters: sectionData.characters?.characters || [] }, editable }
    case 'chapter_outline':
      return { outline: data?.chapter_outline || [], chapters: sectionData.chapters?.chapters || [], editable }
    case 'chapters':
      return { chapters: data?.chapters || [], isAdmin: props.isAdmin }
    case 'writer_persona':
      return { projectId }
    case 'volumes':
      return { projectId }
    default:
      return {}
  }
})

// ==================== Event Handlers ====================

const handleSectionEdit = (payload: { field: string; title: string; value: any }) => {
  if (props.isAdmin) return
  modalField.value = payload.field
  modalTitle.value = payload.title
  modalContent.value = payload.value
  isModalOpen.value = true
}

const resolveSectionKey = (field: string): SectionKey => {
  if (field.startsWith('world_setting')) return 'world_setting'
  if (field.startsWith('characters')) return 'characters'
  if (field.startsWith('relationships')) return 'relationships'
  if (field.startsWith('chapter_outline')) return 'chapter_outline'
  return 'overview'
}

const handleSave = async (data: { field: string; content: any }) => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return

  const { field, content } = data
  const payload: Record<string, any> = {}

  if (field.includes('.')) {
    const [parentField, childField] = field.split('.')
    payload[parentField] = {
      ...(project.blueprint?.[parentField as keyof typeof project.blueprint] as Record<string, any> | undefined),
      [childField]: content
    }
  } else {
    payload[field] = content
  }

  try {
    const updatedProject = await NovelAPI.updateBlueprint(project.id, payload)
    novelStore.setCurrentProject(updatedProject)
    const sectionToReload = resolveSectionKey(field)
    await loadSection(sectionToReload, true)
    if (sectionToReload !== 'overview') await loadSection('overview', true)
    isModalOpen.value = false
  } catch (error) {
    console.error('保存变更失败:', error)
  }
}

const handleToggleCompleted = async (isCompleted: boolean) => {
  if (props.isAdmin) return
  try {
    await NovelAPI.setCompleted(projectId, isCompleted)
    if (sectionData.overview) {
      sectionData.overview = { ...sectionData.overview, is_completed: isCompleted }
    }
    if (novel.value) {
      novel.value.is_completed = isCompleted
    }
  } catch (error) {
    console.error('设置完结状态失败:', error)
  }
}

const handleRegenerate = async (payload: { chapterNumbers?: number[]; totalChapters?: number }) => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return

  sectionRef.value?.setRegenerating?.(true)
  try {
    const result = await NovelAPI.regenerateOutlines(project.id, payload.chapterNumbers, payload.totalChapters)
    if (sectionData.chapter_outline) {
      sectionData.chapter_outline = { ...sectionData.chapter_outline, chapter_outline: result.chapter_outline }
    } else {
      sectionData.chapter_outline = { chapter_outline: result.chapter_outline }
    }
    sectionRef.value?.markRegenerated?.(result.updated_chapters, result.total_target)
    sectionData.chapters = null
  } catch (error) {
    console.error('重新生成大纲失败:', error)
    alert(error instanceof Error ? error.message : '重新生成大纲失败')
  } finally {
    sectionRef.value?.setRegenerating?.(false)
  }
}

const handleDeleteOutlines = async (payload: { chapterNumbers: number[] }) => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return

  const deleteSet = new Set(payload.chapterNumbers)
  const existingOutline = project.blueprint?.chapter_outline || []
  const remainingOutline = existingOutline.filter(ch => !deleteSet.has(ch.chapter_number))

  sectionRef.value?.setDeleting?.(true)
  try {
    const updatedProject = await NovelAPI.updateBlueprint(project.id, { chapter_outline: remainingOutline })
    novelStore.setCurrentProject(updatedProject)
    await loadSection('chapter_outline', true)
    sectionData.chapters = null
  } catch (error) {
    console.error('删除大纲失败:', error)
    alert(error instanceof Error ? error.message : '删除大纲失败')
  } finally {
    sectionRef.value?.setDeleting?.(false)
  }
}

const handleBatchGenerate = async (payload: { chapterNumbers: number[] }) => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return

  sectionRef.value?.setBatchGenerating?.(true)
  try {
    const result = await NovelAPI.batchGenerateChapters(project.id, payload.chapterNumbers)
    sectionData.chapters = null
    const msg = `连续生成完成！成功 ${result.completed} 章` +
      (result.failed > 0 ? `，失败 ${result.failed} 章` : '')
    alert(msg)
  } catch (error) {
    console.error('批量生成失败:', error)
    alert(error instanceof Error ? error.message : '批量生成失败')
  } finally {
    sectionRef.value?.setBatchGenerating?.(false)
  }
}

const handleBatchPredict = async () => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return

  sectionRef.value?.setPredictGenerating?.(true)
  try {
    const result = await NovelAPI.batchGeneratePredictions(project.id)
    if (result.queued === 0) {
      sectionRef.value?.setPredictGenerating?.(false)
      alert(result.message)
      return
    }
    sectionRef.value?.setPredictProgress?.({ total: result.queued, completed: 0, failed: 0 })
    pollPredictionProgress(project.id)
  } catch (error) {
    console.error('批量推演失败:', error)
    alert(error instanceof Error ? error.message : '批量推演失败')
    sectionRef.value?.setPredictGenerating?.(false)
  }
}

let predictionPollTimer: ReturnType<typeof setTimeout> | null = null

const pollPredictionProgress = async (projectId: string) => {
  if (predictionPollTimer) clearTimeout(predictionPollTimer)
  try {
    const progress = await NovelAPI.getPredictionProgress(projectId)
    sectionRef.value?.setPredictProgress?.(progress)
    if (progress.running) {
      predictionPollTimer = setTimeout(() => pollPredictionProgress(projectId), 3000)
    } else {
      sectionRef.value?.setPredictGenerating?.(false)
      reloadSection('chapter_outline', true)
    }
  } catch {
    predictionPollTimer = setTimeout(() => pollPredictionProgress(projectId), 5000)
  }
}

const startAddChapter = async () => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const outline = sectionData.chapter_outline?.chapter_outline || novel.value?.blueprint?.chapter_outline || []
  const nextNumber = outline.length > 0 ? Math.max(...outline.map((item: any) => item.chapter_number)) + 1 : 1
  newChapterTitle.value = `新章节 ${nextNumber}`
  newChapterSummary.value = ''
  isAddChapterModalOpen.value = true
}

const cancelNewChapter = () => {
  isAddChapterModalOpen.value = false
}

const saveNewChapter = async () => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return
  if (!newChapterTitle.value.trim()) {
    alert('章节标题不能为空')
    return
  }

  const existingOutline = project.blueprint?.chapter_outline || []
  const nextNumber = existingOutline.length > 0 ? Math.max(...existingOutline.map(ch => ch.chapter_number)) + 1 : 1
  const newOutline = [...existingOutline, {
    chapter_number: nextNumber,
    title: newChapterTitle.value,
    summary: newChapterSummary.value
  }]

  try {
    const updatedProject = await NovelAPI.updateBlueprint(project.id, { chapter_outline: newOutline })
    novelStore.setCurrentProject(updatedProject)
    await loadSection('chapter_outline', true)
    isAddChapterModalOpen.value = false
  } catch (error) {
    console.error('新增章节失败:', error)
  }
}

// ==================== Lifecycle ====================

onMounted(async () => {
  await loadSection('overview', true)
  loadSection('chapters')
  loadSection('characters')
  loadSection('chapter_outline')
  loadSection('world_setting')
  loadShareStatus()
  loadCoverOptions()
  powerSystems.value = await fetchPowerSystems()
})

onBeforeUnmount(() => {
  releaseCoverObjectUrl()
  if (predictionPollTimer) {
    clearTimeout(predictionPollTimer)
    predictionPollTimer = null
  }
})
</script>

<style scoped>
.nav-link {
  font-size: 14px;
  font-weight: 500;
  color: #888;
  transition: color 0.15s;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}
.nav-link:hover {
  color: #FFE500;
}
.nav-link-active {
  color: #FFE500 !important;
  font-weight: 700;
}

.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}

.novel-hero {
  position: relative;
  display: grid;
  grid-template-columns: 188px minmax(0, 1fr) 170px;
  gap: 30px;
  padding: 30px;
  overflow: hidden;
  background:
    radial-gradient(circle at 13% 25%, rgba(255, 229, 0, 0.09), transparent 30%),
    linear-gradient(125deg, #171713 0%, #111110 55%, #151510 100%);
  border: 1px solid #2c2c25;
  border-radius: 24px;
}
.novel-hero::after {
  content: '';
  position: absolute;
  right: -50px;
  bottom: -110px;
  width: 330px;
  height: 330px;
  border: 1px solid rgba(255, 229, 0, 0.07);
  border-radius: 50%;
  box-shadow: 0 0 0 50px rgba(255, 229, 0, 0.025), 0 0 0 100px rgba(255, 229, 0, 0.018);
  pointer-events: none;
}
.novel-cover-wrap { position: relative; z-index: 1; }
.novel-cover {
  position: relative;
  aspect-ratio: 2 / 3;
  overflow: hidden;
  background: #212119;
  border: 1px solid #3a392b;
  border-radius: 13px;
  box-shadow: 0 20px 44px rgba(0, 0, 0, 0.42), -9px 8px 0 #0b0b0a;
}
.novel-cover img { width: 100%; height: 100%; object-fit: cover; }
.novel-cover__fallback { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 22px; text-align: center; }
.novel-cover__fallback > span { font-size: 46px; filter: drop-shadow(0 7px 12px rgba(0, 0, 0, 0.38)); }
.novel-cover__fallback strong { color: #fff; font-size: 17px; line-height: 1.35; }
.novel-cover__fallback small { color: rgba(255, 255, 255, 0.5); font-size: 10px; letter-spacing: 0.15em; }
.novel-cover__shine { position: absolute; inset: 0; background: linear-gradient(115deg, rgba(255,255,255,0.1), transparent 22%, transparent 78%, rgba(255,229,0,0.07)); pointer-events: none; }
.novel-cover__ai { position: absolute; right: 9px; bottom: 9px; padding: 4px 6px; color: #111; font-size: 8px; font-weight: 900; letter-spacing: 0.12em; background: #ffe500; border-radius: 4px; }
.novel-cover-action { display: flex; align-items: center; justify-content: center; gap: 7px; width: 100%; margin-top: 14px; padding: 9px 10px; color: #b7b7ae; font-size: 12px; font-weight: 650; background: #1c1c18; border: 1px solid #34342c; border-radius: 9px; transition: 0.18s; }
.novel-cover-action:hover { color: #ffe500; border-color: #7c730f; }
.novel-cover-action svg { width: 14px; height: 14px; }
.novel-hero__content { position: relative; z-index: 1; min-width: 0; padding: 8px 0 2px; }
.novel-hero__eyebrow { display: flex; align-items: center; gap: 10px; color: #8b8b80; font-size: 9px; font-weight: 800; letter-spacing: 0.16em; }
.novel-hero__eyebrow span:first-child { color: #ffe500; }
.novel-hero__eyebrow i { width: 24px; height: 1px; background: #595847; }
.novel-hero__content h1 { margin: 13px 0 10px; color: #fff; font-size: clamp(27px, 3vw, 42px); font-weight: 800; line-height: 1.15; letter-spacing: -0.035em; }
.novel-hero__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 9px 14px; color: #777770; font-size: 11px; }
.novel-genre, .novel-completed { padding: 4px 8px; border-radius: 99px; }
.novel-genre { color: #ffe500; background: rgba(255, 229, 0, 0.07); border: 1px solid rgba(255, 229, 0, 0.35); }
.novel-completed { color: #37df87; background: rgba(46, 213, 115, 0.09); border: 1px solid rgba(46, 213, 115, 0.25); }
.novel-hero__summary { max-width: 720px; min-height: 52px; margin: 20px 0 18px; color: #aaa9a1; font-size: 13px; line-height: 1.8; }
.novel-hero__stats { display: flex; align-items: center; gap: 0; width: fit-content; padding: 12px 0; border-top: 1px solid #292921; border-bottom: 1px solid #292921; }
.novel-hero__stats > div { display: flex; flex-direction: column; min-width: 100px; padding: 0 22px; border-right: 1px solid #2e2e27; }
.novel-hero__stats > div:first-child { padding-left: 0; }
.novel-hero__stats > div:last-child { border-right: 0; }
.novel-hero__stats strong { color: #f5f5ee; font-size: 18px; }
.novel-hero__stats span { margin-top: 2px; color: #6f6f68; font-size: 10px; }
.novel-hero__actions { display: flex; gap: 10px; margin-top: 20px; }
.novel-primary-action, .novel-secondary-action { display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 40px; padding: 0 18px; font-size: 13px; font-weight: 750; border-radius: 10px; }
.novel-primary-action { color: #0b0b09; background: #ffe500; border: 1px solid #ffe500; box-shadow: 0 8px 24px rgba(255, 229, 0, 0.12); }
.novel-primary-action svg { width: 15px; height: 15px; }
.novel-secondary-action { color: #dddcd3; background: #1b1b18; border: 1px solid #393931; }
.novel-progress-card { position: relative; z-index: 1; align-self: center; display: flex; flex-direction: column; align-items: center; padding: 20px 16px; background: rgba(9, 9, 8, 0.48); border: 1px solid #2d2d27; border-radius: 16px; }
.novel-progress-card > span { margin-bottom: 10px; color: #808079; font-size: 10px; font-weight: 700; letter-spacing: 0.12em; }
.novel-progress-card .relative strong { position: absolute; inset: 0; display: grid; place-items: center; color: #ffe500; font-size: 20px; }
.novel-progress-card small { margin-top: 8px; color: #77776f; font-size: 10px; }
.novel-progress-card__line { width: 100%; height: 3px; margin-top: 14px; overflow: hidden; background: #2b2b25; border-radius: 99px; }
.novel-progress-card__line i { display: block; height: 100%; background: #ffe500; border-radius: inherit; transition: width 0.5s ease; }

@media (max-width: 980px) {
  .novel-hero { grid-template-columns: 160px minmax(0, 1fr); gap: 24px; }
  .novel-progress-card { display: none; }
}
@media (max-width: 640px) {
  .novel-hero { grid-template-columns: 112px minmax(0, 1fr); gap: 17px; padding: 20px; border-radius: 18px; }
  .novel-cover-action { font-size: 0; }
  .novel-cover-action::after { content: '制作封面'; font-size: 11px; }
  .novel-hero__content h1 { margin-top: 9px; font-size: 25px; }
  .novel-hero__summary { margin: 13px 0; font-size: 12px; line-height: 1.65; }
  .novel-hero__stats { display: none; }
  .novel-hero__actions { flex-direction: column; margin-top: 14px; }
  .novel-secondary-action { display: none; }
  .novel-hero__meta span:not(.novel-genre):not(.novel-completed) { display: none; }
}
</style>

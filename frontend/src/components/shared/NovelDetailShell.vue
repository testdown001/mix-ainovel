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

      <!-- Novel Header (User Mode) -->
      <div v-if="!isAdmin" class="flex items-start justify-between gap-6 mb-4">
        <!-- Left: Icon + Title + Meta -->
        <div class="flex items-start gap-5 min-w-0">
          <!-- Novel Avatar -->
          <div class="w-16 h-16 rounded-2xl flex items-center justify-center flex-shrink-0 text-2xl"
            :style="{ background: genreAvatarBg }">
            {{ genreEmoji }}
          </div>
          <div class="min-w-0">
            <h1 class="text-3xl font-bold text-white leading-tight truncate">{{ novelTitle }}</h1>
            <div class="flex items-center gap-3 mt-2 flex-wrap">
              <span v-if="novelGenre" class="px-2.5 py-0.5 rounded-full text-xs font-medium border" style="color: #FFE500; border-color: #FFE500;">
                {{ novelGenre }}
              </span>
              <span v-if="sectionData.overview?.is_completed || novel?.is_completed" class="px-2.5 py-0.5 rounded-full text-xs font-medium" style="background: rgba(46, 213, 115, 0.15); color: #2ED573;">
                已完结
              </span>
              <span class="text-sm" style="color: #888;">
                by {{ authStore.user?.username || '—' }}
              </span>
              <span v-if="overviewMeta.updated_at" class="text-sm" style="color: #666;">
                · 最近更新 {{ formatDateTime(overviewMeta.updated_at) }}
              </span>
            </div>
          </div>
        </div>

        <!-- Right: Progress Ring -->
        <div class="flex flex-col items-center flex-shrink-0">
          <div class="relative w-24 h-24">
            <svg class="w-full h-full" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="none" stroke="#2A2A2A" stroke-width="5" />
              <circle cx="50" cy="50" r="42" fill="none" stroke="#FFE500" stroke-width="5"
                stroke-linecap="round"
                :stroke-dasharray="circumference"
                :stroke-dashoffset="circumference - (progressPercent / 100) * circumference"
                transform="rotate(-90 50 50)"
                style="transition: stroke-dashoffset 0.7s ease;" />
            </svg>
            <div class="absolute inset-0 flex items-center justify-center">
              <span class="text-xl font-bold" style="color: #FFE500;">{{ progressPercent }}%</span>
            </div>
          </div>
          <span class="text-xs mt-1.5" style="color: #888;">{{ progressCompleted }}/{{ progressTotal }}章</span>
        </div>
      </div>

      <!-- Description (User Mode) -->
      <p v-if="!isAdmin && novelDescription" class="text-sm leading-6 mb-8" style="color: #888;">
        {{ novelDescription }}
      </p>
      <div v-else-if="!isAdmin" class="mb-6"></div>

      <!-- ==================== Tab Bar ==================== -->
      <div class="flex items-end gap-1 border-b overflow-x-auto scrollbar-hide" style="border-color: #2A2A2A;" :class="isAdmin ? 'mt-6' : ''">
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

        <!-- Spacer + Action Button -->
        <div v-if="!isAdmin" class="ml-auto flex-shrink-0 pb-2 pl-4">
          <button class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-90"
            style="background: #FFE500; color: #000;" @click="goToWritingDesk">
            <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
            </svg>
            开始创作
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
import { getProjectAnalysis, type ProjectAnalysis } from '@/api/gatekeeperReview'
import type { NovelProject, NovelSectionResponse, NovelSectionType, AllSectionType } from '@/api/novel'
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
import WriterPersonaPanel from '@/components/WriterPersonaPanel.vue'
import ConceptLibrarySection from '@/components/novel-detail/ConceptLibrarySection.vue'

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

type SectionKey = AllSectionType | 'writer_persona' | 'concept_library'

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
  writer_persona: WriterPersonaPanel,
  concept_library: ConceptLibrarySection
}

const sectionData = reactive<Partial<Record<SectionKey, any>>>({})
const sectionLoading = reactive<Record<SectionKey, boolean>>({
  overview: false, world_setting: false, characters: false,
  relationships: false, chapter_outline: false, chapters: false,
  emotion_curve: false, foreshadowing: false, writer_persona: false,
  concept_library: false
})
const sectionError = reactive<Record<SectionKey, string | null>>({
  overview: null, world_setting: null, characters: null,
  relationships: null, chapter_outline: null, chapters: null,
  emotion_curve: null, foreshadowing: null, writer_persona: null,
  concept_library: null
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

  const analysisSections: SectionKey[] = ['emotion_curve', 'foreshadowing', 'writer_persona', 'concept_library']
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
  powerSystems.value = await fetchPowerSystems()
})

onBeforeUnmount(() => {
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
</style>

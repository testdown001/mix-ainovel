<!-- AIMETA P=小说详情壳_详情页布局容器|R=详情页布局_导航|NR=不含具体内容|E=component:NovelDetailShell|X=internal|A=布局组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="nd-shell h-screen flex overflow-hidden" style="background-color: var(--ar-bg-base);">
    <!-- Sidebar -->
    <aside
      class="nd-sidebar fixed left-0 top-0 bottom-0 z-30 w-56 transform transition-transform duration-300 lg:translate-x-0"
      :class="isSidebarOpen ? 'translate-x-0' : '-translate-x-full'"
    >
      <!-- Project Info Header -->
      <div class="nd-sidebar-header">
        <div class="nd-project-title font-display">{{ overviewMeta.title || '加载中...' }}</div>
        <div class="nd-project-sub">{{ overviewMeta.genre || '小说项目' }}</div>
      </div>

      <!-- Primary Navigation -->
      <nav class="nd-sidebar-nav">
        <button
          v-for="section in primarySections"
          :key="section.key"
          type="button"
          @click="switchSection(section.key)"
          class="nd-nav-item w-full"
          :class="{ 'active': activeSection === section.key }"
        >
          <component :is="getSectionIcon(section.key)" class="nd-nav-icon w-[18px] h-[18px] flex-shrink-0" />
          <span class="nd-nav-label">{{ section.label }}</span>
        </button>

        <!-- Divider -->
        <div class="nd-nav-divider"></div>

        <!-- Analysis / Tools -->
        <button
          v-for="section in analysisSections"
          :key="section.key"
          type="button"
          @click="switchSection(section.key)"
          class="nd-nav-item w-full"
          :class="{ 'active': activeSection === section.key }"
        >
          <component :is="getSectionIcon(section.key)" class="nd-nav-icon w-[18px] h-[18px] flex-shrink-0" />
          <span class="nd-nav-label">{{ section.label }}</span>
        </button>
      </nav>

      <!-- Sidebar Footer -->
      <div class="nd-sidebar-footer">
        <button
          v-if="!isAdmin"
          class="nd-sidebar-cta w-full"
          @click="goToWritingDesk"
        >
          开始创作
        </button>
        <button class="nd-sidebar-link w-full" @click="goBack">
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
          返回列表
        </button>
      </div>
    </aside>

    <!-- Sidebar Overlay (Mobile) -->
    <transition
      enter-active-class="transition-opacity duration-300"
      leave-active-class="transition-opacity duration-300"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isSidebarOpen"
        class="fixed inset-0 z-20 lg:hidden"
        style="background-color: rgba(0, 0, 0, 0.5);"
        @click="toggleSidebar"
      ></div>
    </transition>

    <!-- Main Content Area -->
    <div class="nd-main flex-1 lg:ml-56 min-h-0 flex flex-col h-full overflow-hidden">
      <!-- Mobile menu button -->
      <div class="lg:hidden flex items-center px-4 h-12 flex-shrink-0" style="border-bottom: 1px solid rgba(250,204,21,0.06);">
        <button class="md-icon-btn" @click="toggleSidebar" aria-label="Toggle sidebar">
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" /></svg>
        </button>
        <span class="ml-2 text-sm truncate" style="color: var(--ar-text-muted);">{{ overviewMeta.title }}</span>
      </div>

      <!-- Scrollable content -->
      <div class="flex-1 min-h-0 overflow-y-auto" :class="contentScrollClass">
        <!-- Section Header -->
        <div class="nd-section-header">
          <div class="flex-1">
            <h1 class="nd-section-title font-display">{{ sectionTitle }}</h1>
            <p class="nd-section-sub">{{ sectionSubtitle }}</p>
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="isSectionLoading" class="flex flex-col items-center justify-center py-20 sm:py-28">
          <div class="md-spinner"></div>
          <p class="mt-4 ar-body" style="color: var(--ar-text-muted);">加载中...</p>
        </div>

        <!-- Error State -->
        <div v-else-if="currentError" class="flex flex-col items-center justify-center py-20 sm:py-28 space-y-4">
          <div class="w-16 h-16 rounded-[4px] flex items-center justify-center" style="background-color: var(--color-error-muted);">
            <svg class="w-8 h-8" style="color: var(--ar-error);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p class="ar-body-lg text-center" style="color: var(--ar-text-primary);">{{ currentError }}</p>
          <button class="md-btn md-btn-filled md-ripple" @click="reloadSection(activeSection, true)">重试</button>
        </div>

        <!-- Content -->
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
        />
      </div>
    </div>

    <!-- Blueprint Edit Modal -->
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

    <!-- Add Chapter Modal -->
    <transition
      enter-active-class="md-scale-enter-active"
      leave-active-class="md-scale-leave-active"
      enter-from-class="md-scale-enter-from"
      leave-to-class="md-scale-leave-to"
    >
      <div v-if="isAddChapterModalOpen && !isAdmin" class="md-dialog-overlay">
        <div class="absolute inset-0" @click="cancelNewChapter"></div>
        <div class="md-dialog relative w-full max-w-lg mx-4" @click.stop>
          <div class="md-dialog-header">
            <h3 class="md-dialog-title">新增章节大纲</h3>
          </div>
          <div class="md-dialog-content space-y-6">
            <div class="md-text-field">
              <label for="new-chapter-title" class="md-text-field-label">
                章节标题
              </label>
              <input
                id="new-chapter-title"
                v-model="newChapterTitle"
                type="text"
                class="md-text-field-input"
                placeholder="例如：意外的相遇"
              >
            </div>
            <div class="md-text-field">
              <label for="new-chapter-summary" class="md-text-field-label">
                章节摘要
              </label>
              <textarea
                id="new-chapter-summary"
                v-model="newChapterSummary"
                rows="4"
                class="md-textarea w-full"
                placeholder="简要描述本章发生的主要事件"
              ></textarea>
            </div>
          </div>
          <div class="md-dialog-actions">
            <button
              type="button"
              class="md-btn md-btn-text md-ripple"
              @click="cancelNewChapter"
            >
              取消
            </button>
            <button
              type="button"
              class="md-btn md-btn-filled md-ripple"
              @click="saveNewChapter"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { useAuthStore } from '@/stores/auth'
import { NovelAPI } from '@/api/novel'
import { AdminAPI } from '@/api/admin'
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

// Import PowerSystem related types and api
// Note: We need a generic api fetcher for /api/power-systems
const fetchPowerSystems = async () => {
  try {
    const authStore = useAuthStore()
    const url = '/api/power-systems'
    const headers = new Headers({ 'Content-Type': 'application/json' })
    if (authStore.isAuthenticated && authStore.token) {
      headers.set('Authorization', `Bearer ${authStore.token}`)
    }
    const response = await fetch(url, { headers })
    if (response.ok) {
      return await response.json()
    }
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

const projectId = route.params.id as string
const isSidebarOpen = ref(typeof window !== 'undefined' ? window.innerWidth >= 1024 : true)

const sections: Array<{ key: SectionKey; label: string; description: string }> = [
  { key: 'overview', label: '项目概览', description: '定位与整体梗概' },
  { key: 'world_setting', label: '世界设定', description: '规则、地点与阵营' },
  { key: 'characters', label: '主要角色', description: '人物性格与目标' },
  { key: 'relationships', label: '人物关系', description: '角色之间的联系' },
  { key: 'chapter_outline', label: '章节大纲', description: props.isAdmin ? '故事章节规划' : '故事结构规划' },
  { key: 'chapters', label: '章节内容', description: props.isAdmin ? '生成章节与正文' : '生成状态与摘要' },
  { key: 'emotion_curve', label: '情感曲线', description: '追踪章节情感变化' },
  { key: 'foreshadowing', label: '伏笔管理', description: '故事线索与回收' },
  { key: 'writer_persona', label: 'Writer 设定', description: '写作风格与对齐' },
  { key: 'concept_library', label: '设定百科', description: '世界观元素管理' }
]

const primarySections = computed(() => sections.slice(0, 6))
const analysisSections = computed(() => sections.slice(6))

const sectionTitleMap: Record<SectionKey, string> = {
  overview: '项目概览',
  world_setting: '世界观设定库',
  characters: '角色管理',
  relationships: '人物关系图谱',
  chapter_outline: '章节大纲',
  chapters: '章节内容',
  emotion_curve: '情感曲线分析',
  foreshadowing: '伏笔管理',
  writer_persona: 'Writer 风格设定',
  concept_library: '设定百科'
}

const sectionTitle = computed(() => sectionTitleMap[activeSection.value] || '')
const sectionSubtitle = computed(() => {
  const sec = sections.find(s => s.key === activeSection.value)
  return sec?.description || ''
})

const contentScrollClass = computed(() => {
  const fillSections: SectionKey[] = ['chapters']
  return fillSections.includes(activeSection.value) ? 'nd-content-fill' : 'nd-content-scroll'
})

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

// Section icons as functional components
const getSectionIcon = (key: SectionKey) => {
  const icons: Record<SectionKey, any> = {
    overview: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('rect', { x: 3, y: 3, width: 18, height: 18, rx: 2 }),
      h('line', { x1: 3, y1: 9, x2: 21, y2: 9 }),
      h('line', { x1: 9, y1: 21, x2: 9, y2: 9 })
    ]),
    world_setting: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('circle', { cx: 12, cy: 12, r: 10 }),
      h('path', { d: 'M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z' })
    ]),
    characters: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2' }),
      h('circle', { cx: 9, cy: 7, r: 4 }),
      h('path', { d: 'M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75' })
    ]),
    relationships: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2' }),
      h('circle', { cx: 9, cy: 7, r: 4 }),
      h('path', { d: 'M22 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75' })
    ]),
    chapter_outline: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('line', { x1: 8, y1: 6, x2: 21, y2: 6 }),
      h('line', { x1: 8, y1: 12, x2: 21, y2: 12 }),
      h('line', { x1: 8, y1: 18, x2: 21, y2: 18 }),
      h('line', { x1: 3, y1: 6, x2: 3.01, y2: 6 }),
      h('line', { x1: 3, y1: 12, x2: 3.01, y2: 12 }),
      h('line', { x1: 3, y1: 18, x2: 3.01, y2: 18 })
    ]),
    chapters: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M4 19.5A2.5 2.5 0 016.5 17H20' }),
      h('path', { d: 'M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z' })
    ]),
    emotion_curve: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z' })
    ]),
    foreshadowing: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M13 10V3L4 14h7v7l9-11h-7z' })
    ]),
    writer_persona: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z' })
    ]),
    concept_library: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
      h('path', { d: 'M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253' })
    ])
  }
  return icons[key]
}

const sectionData = reactive<Partial<Record<SectionKey, any>>>({})
const sectionLoading = reactive<Record<SectionKey, boolean>>({
  overview: false,
  world_setting: false,
  characters: false,
  relationships: false,
  chapter_outline: false,
  chapters: false,
  emotion_curve: false,
  foreshadowing: false,
  writer_persona: false,
  concept_library: false
})
const sectionError = reactive<Record<SectionKey, string | null>>({
  overview: null,
  world_setting: null,
  characters: null,
  relationships: null,
  chapter_outline: null,
  chapters: null,
  emotion_curve: null,
  foreshadowing: null,
  writer_persona: null,
  concept_library: null
})

const overviewMeta = reactive<{ title: string; updated_at: string | null; genre: string }>({
  title: '加载中...',
  updated_at: null,
  genre: ''
})

const activeSection = ref<SectionKey>('overview')

// System settings data
const powerSystems = ref<Array<{ id: number, name: string, levels: Array<{ id: number, name: string }> }>>([])

// Modal state (user mode only)
const isModalOpen = ref(false)
const modalTitle = ref('')
const modalContent = ref<any>('')
const modalField = ref('')

// Add chapter modal state (user mode only)
const isAddChapterModalOpen = ref(false)
const newChapterTitle = ref('')
const newChapterSummary = ref('')
const originalBodyOverflow = ref('')

const novel = computed(() => !props.isAdmin ? novelStore.currentProject as NovelProject | null : null)

const sectionRef = ref<any>(null)

const formattedTitle = computed(() => {
  const title = overviewMeta.title || '加载中...'
  return title.startsWith('《') && title.endsWith('》') ? title : `《${title}》`
})

const componentContainerClass = computed(() => {
  const fillSections: SectionKey[] = ['chapters']
  return fillSections.includes(activeSection.value)
    ? 'flex-1 min-h-0 h-full flex flex-col overflow-hidden'
    : 'overflow-y-auto'
})

const contentCardClass = computed(() => {
  const fillSections: SectionKey[] = ['chapters']
  return fillSections.includes(activeSection.value)
    ? 'overflow-hidden'
    : 'overflow-visible'
})

// 懒加载完整项目（仅在需要编辑时）
const ensureProjectLoaded = async () => {
  if (props.isAdmin || !projectId) return
  if (novel.value) return // 已加载
  await novelStore.loadProject(projectId)
}

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

const handleResize = () => {
  if (typeof window === 'undefined') return
  isSidebarOpen.value = window.innerWidth >= 1024
}

const loadSection = async (section: SectionKey, force = false) => {
  if (!projectId) return
  
  // 分析型Section使用独立的API，不需要在这里加载
  const analysisSections: SectionKey[] = ['emotion_curve', 'foreshadowing', 'writer_persona', 'concept_library']
  if (analysisSections.includes(section)) {
    return
  }
  
  if (!force && sectionData[section]) {
    return
  }

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
      overviewMeta.genre = response.data?.genre || response.data?.style || ''
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

const switchSection = (section: SectionKey) => {
  activeSection.value = section
  if (typeof window !== 'undefined' && window.innerWidth < 1024) {
    isSidebarOpen.value = false
  }
  loadSection(section)
  // 章节大纲需要 chapters 数据来判断完成状态
  if (section === 'chapter_outline') {
    loadSection('chapters')
  }
  // 关系图谱需要角色数据
  if (section === 'relationships') {
    loadSection('characters')
  }
}

const goBack = () => router.push(props.isAdmin ? '/admin' : '/workspace')

const goToWritingDesk = async () => {
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return
  const path = project.title === '未命名灵感' ? `/inspiration?project_id=${project.id}` : `/novel/${project.id}`
  router.push(path)
}

const currentComponent = computed(() => sectionComponents[activeSection.value])
const isSectionLoading = computed(() => sectionLoading[activeSection.value])
const currentError = computed(() => sectionError[activeSection.value])

const componentProps = computed(() => {
  const data = sectionData[activeSection.value]
  const editable = !props.isAdmin

  switch (activeSection.value) {
    case 'overview':
      return { data: data || null, editable }
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
    if (sectionToReload !== 'overview') {
      await loadSection('overview', true)
    }
    isModalOpen.value = false
  } catch (error) {
    console.error('保存变更失败:', error)
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
    // 用返回的最新大纲直接更新 sectionData，避免额外请求
    if (sectionData.chapter_outline) {
      sectionData.chapter_outline = { ...sectionData.chapter_outline, chapter_outline: result.chapter_outline }
    } else {
      sectionData.chapter_outline = { chapter_outline: result.chapter_outline }
    }
    // 标记哪些章节是新生成的
    sectionRef.value?.markRegenerated?.(result.updated_chapters, result.total_target)
    // 大纲变动后使章节内容缓存失效
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
    // 使章节内容列表缓存失效，切换时会重新加载
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
    const result = await NovelAPI.batchGenerateChapters(
      project.id,
      payload.chapterNumbers
    )
    // 使章节内容缓存失效，切换时重新加载
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

onMounted(async () => {
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', handleResize)
  }
  if (typeof document !== 'undefined') {
    originalBodyOverflow.value = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }

  // 只加载必要的 section 数据，不预加载完整项目
  await loadSection('overview', true)
  loadSection('world_setting')
  powerSystems.value = await fetchPowerSystems()
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', handleResize)
  }
  if (predictionPollTimer) {
    clearTimeout(predictionPollTimer)
    predictionPollTimer = null
  }
  if (typeof document !== 'undefined') {
    document.body.style.overflow = originalBodyOverflow.value || ''
  }
})
</script>

<style scoped>
/* ===== Sidebar ===== */
.nd-sidebar {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: var(--ar-bg-surface);
  border-right: 1px solid rgba(250, 204, 21, 0.08);
}

.nd-sidebar-header {
  flex-shrink: 0;
  padding: 20px 20px 12px;
}

.nd-project-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--ar-primary);
  font-style: italic;
  line-height: 1.3;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nd-project-sub {
  font-family: var(--ar-font-ui);
  font-size: 11px;
  color: var(--ar-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.nd-sidebar-nav {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nd-nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 38px;
  padding: 0 14px;
  border: none;
  border-radius: var(--ar-radius-sm);
  background-color: transparent;
  color: var(--ar-text-secondary);
  font-family: var(--ar-font-ui);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 150ms ease;
  text-decoration: none;
  text-align: left;
  position: relative;
  flex-shrink: 0;
}

.nd-nav-icon {
  opacity: 0.5;
  transition: opacity 150ms ease;
}

.nd-nav-item:hover {
  background-color: rgba(255, 255, 255, 0.04);
  color: var(--ar-text-primary);
}

.nd-nav-item:hover .nd-nav-icon {
  opacity: 0.8;
}

.nd-nav-item.active {
  background-color: rgba(74, 222, 128, 0.08);
  color: var(--ar-secondary);
}

.nd-nav-item.active .nd-nav-icon {
  opacity: 1;
  color: var(--ar-secondary);
}

.nd-nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 7px;
  bottom: 7px;
  width: 3px;
  background: var(--ar-secondary);
  border-radius: 0 2px 2px 0;
}

.nd-nav-divider {
  height: 1px;
  margin: 10px 14px;
  background: linear-gradient(90deg, rgba(250, 204, 21, 0.12) 0%, transparent 100%);
  flex-shrink: 0;
}

/* Sidebar Footer */
.nd-sidebar-footer {
  flex-shrink: 0;
  padding: 12px 10px 16px;
  border-top: 1px solid rgba(250, 204, 21, 0.06);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nd-sidebar-cta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  border: none;
  border-radius: var(--ar-radius-sm);
  background: var(--ar-primary);
  color: var(--ar-on-primary);
  font-family: var(--ar-font-ui);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms ease;
}

.nd-sidebar-cta:hover {
  filter: brightness(1.1);
  box-shadow: 0 0 12px rgba(250, 204, 21, 0.25);
}

.nd-sidebar-link {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 32px;
  border: none;
  border-radius: var(--ar-radius-sm);
  background: transparent;
  color: var(--ar-text-muted);
  font-family: var(--ar-font-ui);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 150ms ease;
}

.nd-sidebar-link:hover {
  color: var(--ar-text-secondary);
  background-color: rgba(255, 255, 255, 0.03);
}

/* ===== Content ===== */
.nd-main {
  background-color: var(--ar-bg-base);
}

.nd-content-scroll {
  padding: 24px 32px 40px;
}

.nd-content-fill {
  padding: 0;
  display: flex;
  flex-direction: column;
}

.nd-section-header {
  display: flex;
  align-items: flex-start;
  margin-bottom: 24px;
  padding: 24px 32px 0;
}

.nd-content-scroll .nd-section-header {
  padding: 0;
}

.nd-section-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--ar-text-primary);
  line-height: 1.2;
  margin: 0;
}

.nd-section-sub {
  font-family: var(--ar-font-ui);
  font-size: 13px;
  color: var(--ar-text-muted);
  margin-top: 4px;
}

/* Transitions */
.md-scale-enter-active,
.md-scale-leave-active {
  transition: all 250ms cubic-bezier(0.4, 0, 0.2, 1);
}

.md-scale-enter-from,
.md-scale-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

/* Scrollbar */
::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(250, 204, 21, 0.12);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(250, 204, 21, 0.25);
}

@media (max-width: 1023px) {
  .nd-sidebar {
    width: 240px;
  }
  .nd-content-scroll {
    padding: 16px 20px 32px;
  }
}
</style>

<!-- AIMETA P=小说工作区_小说列表管理|R=小说列表_创建|NR=不含章节编辑|E=route:/workspace#component:NovelWorkspace|X=ui|A=工作区|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="min-h-screen" style="background: #0A0A0A; font-family: 'Inter', sans-serif; padding: 0 0 48px;">
    <!-- Snackbar -->
    <transition
      enter-active-class="transition-all duration-300"
      leave-active-class="transition-all duration-300"
      enter-from-class="opacity-0 translate-y-4"
      leave-to-class="opacity-0 translate-y-4"
    >
      <div v-if="deleteMessage" class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-2xl" style="background: #1C1C1C; border: 1px solid #2A2A2A; min-width: 260px;">
        <svg v-if="deleteMessage.type === 'success'" class="w-5 h-5 flex-shrink-0" style="color: #2ED573;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <svg v-else class="w-5 h-5 flex-shrink-0" style="color: #FF4757;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span style="color: #fff; font-size: 14px;">{{ deleteMessage.text }}</span>
      </div>
    </transition>
    
    <div class="w-full max-w-7xl mx-auto px-6 pt-10">
      <!-- Page Header -->
      <div class="flex justify-between items-center mb-6">
        <div>
          <div class="flex items-center gap-4 mb-1.5">
            <router-link
              to="/home"
              class="flex items-center gap-1.5 text-sm transition-colors"
              style="color: #888;"
              @mouseenter="($event.target as HTMLElement).style.color='#fff'"
              @mouseleave="($event.target as HTMLElement).style.color='#888'"
            >
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              返回
            </router-link>
            <div class="h-4 w-px" style="background: #2A2A2A;"></div>
            <h1 style="font-family: 'Space Grotesk', sans-serif; font-weight: 900; font-size: 32px; color: #fff;">我的小说库</h1>
          </div>
          <p style="color: #888; font-size: 14px;">
            共 {{ novelStore.projects.length }} 部小说
          </p>
        </div>
        <button
          @click="goToInspiration"
          class="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold transition-all"
          style="background: #FFE500; color: #000; border: none; cursor: pointer;"
        >
          <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          新建小说
        </button>
      </div>

      <!-- Search + Filter Bar -->
      <div class="flex flex-col sm:flex-row gap-3 mb-8">
        <div class="relative flex-1">
          <svg class="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none" style="color: #555;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35m0 0A7 7 0 1116.65 16.65z"/>
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索小说标题..."
            class="w-full pl-10 pr-4 py-2.5 rounded-xl text-sm outline-none transition-colors"
            style="background: #141414; border: 1px solid #2A2A2A; color: #fff;"
            @focus="($event.target as HTMLElement).style.borderColor='#FFE500'"
            @blur="($event.target as HTMLElement).style.borderColor='#2A2A2A'"
          />
        </div>
        <div class="flex gap-2 flex-wrap">
          <button
            v-for="chip in filterChips"
            :key="chip.id"
            @click="activeFilter = chip.id"
            class="px-4 py-2 rounded-lg text-sm font-medium transition-all"
            :style="activeFilter === chip.id
              ? 'background: #2A2600; color: #FFE500; border: 1px solid #FFE50040;'
              : 'background: #141414; color: #888; border: 1px solid #2A2A2A;'"
          >{{ chip.label }}</button>
        </div>
      </div>

      <!-- 会员到期提醒（到期前 3 天，含试用转化） -->
      <RenewalBanner />

      <!-- Loading State -->
      <div v-if="novelStore.isLoading" class="flex flex-col items-center justify-center py-24">
        <div class="loader"></div>
        <p class="mt-4 text-sm" style="color: #888;">加载中...</p>
      </div>

      <!-- Error State -->
      <div v-else-if="novelStore.error" class="flex flex-col items-center justify-center py-24">
        <div class="w-16 h-16 rounded-2xl flex items-center justify-center mb-4" style="background: #3D0A0A;">
          <svg class="w-8 h-8" style="color: #FF4757;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <p class="mb-4 font-medium" style="color: #FF4757;">{{ novelStore.error }}</p>
        <button
          @click="loadProjects"
          class="px-6 py-2.5 rounded-xl font-semibold text-sm"
          style="background: #FFE500; color: #000; border: none; cursor: pointer;"
        >
          重试
        </button>
      </div>

      <!-- Project Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        <!-- Empty State -->
        <div v-if="filteredProjects.length === 0" class="col-span-full flex flex-col items-center justify-center py-24">
          <div class="text-6xl mb-5">📭</div>
          <p class="text-xl font-bold mb-2" style="color: #fff; font-family: 'Space Grotesk', sans-serif;">还没有项目</p>
          <p class="text-sm mb-8" style="color: #888;">快去开启灵感模式创建一个吧！</p>
          <button
            @click="goToInspiration"
            class="flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm"
            style="background: #FFE500; color: #000; border: none; cursor: pointer;"
          >
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            开始创作
          </button>
        </div>

        <!-- Project Cards -->
        <ProjectCard
          v-for="project in filteredProjects"
          :key="project.id"
          :project="project"
          @click="enterProject(project)"
          @detail="viewProjectDetail"
          @continue="enterProject"
          @delete="handleDeleteProject"
        />

        <!-- Create New Project Card -->
        <div
          @click="goToInspiration"
          class="flex items-center justify-center p-6 cursor-pointer min-h-[200px] rounded-2xl transition-all duration-200 group"
          style="background: #141414; border: 1px dashed #2A2A2A;"
        >
          <div class="text-center">
            <div class="w-12 h-12 mx-auto mb-3 rounded-xl flex items-center justify-center" style="background: #1C1C1C;">
              <svg class="w-6 h-6" style="color: #FFE500;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
              </svg>
            </div>
            <span class="font-semibold text-sm" style="color: #888;">创建新项目</span>
          </div>
        </div>

        <!-- Import Project Card -->
        <div
          @click="triggerImport"
          class="flex items-center justify-center p-6 cursor-pointer min-h-[200px] rounded-2xl transition-all duration-200 group"
          style="background: #141414; border: 1px dashed #2A2A2A;"
        >
          <div class="text-center">
            <div v-if="isImporting" class="flex flex-col items-center">
              <div class="loader w-8 h-8 mb-3"></div>
              <span class="font-semibold text-sm" style="color: #888;">正在导入并分析...</span>
            </div>
            <div v-else>
              <div class="w-12 h-12 mx-auto mb-3 rounded-xl flex items-center justify-center" style="background: #0A2A1A;">
                <svg class="w-6 h-6" style="color: #2ED573;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
              </div>
              <span class="font-semibold text-sm" style="color: #888;">导入小说文件</span>
            </div>
          </div>
        </div>
        <input
          type="file"
          ref="fileInput"
          accept=".txt"
          class="hidden"
          @change="handleFileImport"
        />
      </div>
    </div>

    <!-- Delete Confirmation Dialog -->
    <transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div v-if="showDeleteDialog" class="fixed inset-0 z-50 flex items-center justify-center" style="background: rgba(0,0,0,0.7); backdrop-filter: blur(4px);">
        <transition
          enter-active-class="transition-all duration-300"
          leave-active-class="transition-all duration-200"
          enter-from-class="opacity-0 scale-95"
          leave-to-class="opacity-0 scale-95"
        >
          <div class="max-w-md w-full mx-4 rounded-2xl p-8" style="background: #141414; border: 1px solid #2A2A2A;">
            <div class="flex items-center gap-4 mb-6">
              <div class="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0" style="background: #3D0A0A;">
                <svg class="w-6 h-6" style="color: #FF4757;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <div>
                <h3 class="font-bold text-lg" style="color: #fff; font-family: 'Space Grotesk', sans-serif;">确认删除</h3>
                <p class="text-xs" style="color: #888;">此操作无法撤销</p>
              </div>
            </div>
            
            <p class="mb-8 text-sm leading-relaxed" style="color: #aaa;">
              确定要删除项目 "<strong style="color: #fff;">{{ projectToDelete?.title }}</strong>" 吗？所有相关数据将被永久删除。
            </p>
            
            <div class="flex gap-3 justify-end">
              <button
                @click="cancelDelete"
                class="px-5 py-2.5 rounded-xl text-sm font-medium"
                style="background: #1C1C1C; border: 1px solid #2A2A2A; color: #888; cursor: pointer;"
              >
                取消
              </button>
              <button
                @click="confirmDelete"
                :disabled="isDeleting"
                class="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold"
                style="background: #FF4757; color: #fff; border: none; cursor: pointer;"
              >
                <svg v-if="isDeleting" class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {{ isDeleting ? '删除中...' : '确认删除' }}
              </button>
            </div>
          </div>
        </transition>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { useAuthStore } from '@/stores/auth'
import ProjectCard from '@/components/ProjectCard.vue'
import RenewalBanner from '@/components/RenewalBanner.vue'
import type { NovelProject, NovelProjectSummary } from '@/api/novel'
import { NovelAPI } from '@/api/novel'

const router = useRouter()
const novelStore = useNovelStore()
const authStore = useAuthStore()

const fileInput = ref<HTMLInputElement | null>(null)
const isImporting = ref(false)
const searchQuery = ref('')
const activeFilter = ref('all')

const filterChips = [
  { id: 'all', label: '全部' },
  { id: 'ongoing', label: '进行中' },
  { id: 'completed', label: '已完成' },
  { id: 'draft', label: '草稿' },
]

const filteredProjects = computed(() => {
  let list = novelStore.projects
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter(p => p.title.toLowerCase().includes(q))
  }
  if (activeFilter.value === 'completed') {
    list = list.filter(p => p.is_completed)
  } else if (activeFilter.value === 'ongoing') {
    list = list.filter(p => !p.is_completed && p.completed_chapters > 0)
  } else if (activeFilter.value === 'draft') {
    list = list.filter(p => !p.is_completed && p.completed_chapters === 0)
  }
  return list
})

const showDeleteDialog = ref(false)
const projectToDelete = ref<NovelProjectSummary | null>(null)
const isDeleting = ref(false)
const deleteMessage = ref<{type: 'success' | 'error', text: string} | null>(null)

const goToInspiration = () => {
  router.push('/inspiration')
}

const viewProjectDetail = (projectId: string) => {
  router.push(`/detail/${projectId}`)
}

const enterProject = (project: NovelProjectSummary) => {
  if (project.title === '未命名灵感') {
    router.push(`/inspiration?project_id=${project.id}`)
  } else {
    router.push(`/novel/${project.id}`)
  }
}

const loadProjects = async () => {
  await novelStore.loadProjects()
}

const triggerImport = () => {
  if (isImporting.value) return
  fileInput.value?.click()
}

const handleFileImport = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return

  const file = target.files[0]
  if (!file.name.endsWith('.txt')) {
    alert('请上传 .txt 格式的文件')
    return
  }

  isImporting.value = true
  try {
    const response = await NovelAPI.importNovel(file)
    await loadProjects()
    router.push(`/novel/${response.id}`)
  } catch (error: any) {
    console.error('导入失败:', error)
    alert(error.message || '导入失败，请重试')
  } finally {
    isImporting.value = false
    target.value = ''
  }
}

const handleDeleteProject = (projectId: string) => {
  const project = novelStore.projects.find(p => p.id === projectId)
  if (project) {
    projectToDelete.value = project
    showDeleteDialog.value = true
  }
}

const cancelDelete = () => {
  showDeleteDialog.value = false
  projectToDelete.value = null
}

const confirmDelete = async () => {
  if (!projectToDelete.value) return
  
  isDeleting.value = true
  try {
    await novelStore.deleteProjects([projectToDelete.value.id])
    deleteMessage.value = { type: 'success', text: `项目 "${projectToDelete.value.title}" 已成功删除` }
    showDeleteDialog.value = false
    projectToDelete.value = null
    
    setTimeout(() => {
      deleteMessage.value = null
    }, 3000)
  } catch (error) {
    console.error('删除项目失败:', error)
    deleteMessage.value = { type: 'error', text: '删除项目失败，请重试' }
    
    setTimeout(() => {
      deleteMessage.value = null
    }, 3000)
  } finally {
    isDeleting.value = false
  }
}

onMounted(() => {
  loadProjects()
})
</script>

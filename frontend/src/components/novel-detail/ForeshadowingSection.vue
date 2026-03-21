<!-- AIMETA P=伏笔区_伏笔管理展示|R=伏笔列表_回收状态|NR=不含分析逻辑|E=component:ForeshadowingSection|X=ui|A=伏笔组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="space-y-5">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-full flex items-center justify-center bg-[rgba(255,229,0,0.1)]">
          <svg class="w-5 h-5 text-[#FFE500]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div>
          <h3 class="text-base font-semibold text-white">伏笔管理</h3>
          <p class="text-xs text-[#666]">追踪故事线索与回收</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="generateForeshadowings"
          class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-[#FFE500] bg-[rgba(255,229,0,0.08)] hover:bg-[rgba(255,229,0,0.14)] border border-[rgba(255,229,0,0.2)] rounded-lg transition-colors"
          :disabled="isGenerating || isLoading"
        >
          <svg v-if="isGenerating" class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <svg v-else class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          {{ isGenerating ? 'AI 生成中...' : '同步伏笔' }}
        </button>
        <button
          @click="refreshData"
          class="w-8 h-8 flex items-center justify-center rounded-lg text-[#555] hover:text-[#888] hover:bg-[#1C1C1C] transition-colors"
          :disabled="isLoading"
        >
          <svg
            class="w-5 h-5 transition-transform"
            :class="{ 'animate-spin': isLoading }"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Statistics Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="bg-[#1C1C1C] border border-[#2A2A2A] rounded-xl p-4 text-center">
        <p class="text-xs text-[#666] mb-1">总伏笔</p>
        <p class="text-2xl font-bold text-white">{{ totalForeshadowings }}</p>
      </div>
      <div class="bg-[#1C1C1C] border border-[#2A2A2A] rounded-xl p-4 text-center">
        <p class="text-xs text-[#666] mb-1">已埋设</p>
        <p class="text-2xl font-bold text-[#FFE500]">{{ plantedCount }}</p>
      </div>
      <div class="bg-[#1C1C1C] border border-[#2A2A2A] rounded-xl p-4 text-center">
        <p class="text-xs text-[#666] mb-1">已回收</p>
        <p class="text-2xl font-bold text-[#2ED573]">{{ paidOffCount }}</p>
      </div>
      <div class="bg-[#1C1C1C] border border-[#2A2A2A] rounded-xl p-4 text-center">
        <p class="text-xs text-[#666] mb-1">待回收</p>
        <p class="text-2xl font-bold text-[#FF4757]">{{ overdueCount }}</p>
      </div>
    </div>

    <!-- Status Filter Tabs -->
    <div class="flex gap-1 border-b border-[#2A2A2A]">
      <button
        v-for="tab in statusTabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px"
        :class="activeTab === tab.key
          ? 'border-[#FFE500] text-[#FFE500]'
          : 'border-transparent text-[#555] hover:text-[#888]'"
      >
        {{ tab.label }}
        <span
          v-if="getCountByStatus(tab.key) > 0"
          class="ml-1.5 px-1.5 py-0.5 rounded-full text-xs"
          :style="{ backgroundColor: tab.color + '22', color: tab.color }"
        >
          {{ getCountByStatus(tab.key) }}
        </span>
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex flex-col items-center justify-center py-12">
      <div class="w-8 h-8 border-2 border-[#FFE500] border-t-transparent rounded-full animate-spin"></div>
      <p class="mt-4 text-sm text-[#666]">加载伏笔数据中...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="flex flex-col items-center justify-center py-12">
      <div class="w-12 h-12 rounded-full flex items-center justify-center mb-4 bg-[rgba(255,71,87,0.1)]">
        <svg class="w-6 h-6 text-[#FF4757]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <p class="text-sm text-[#FF4757]">{{ error }}</p>
      <button @click="refreshData" class="mt-4 text-sm text-[#FFE500] hover:text-[#FFC300] transition-colors">重试</button>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredForeshadowing.length === 0" class="flex flex-col items-center justify-center py-12">
      <div class="w-16 h-16 rounded-full flex items-center justify-center mb-4 bg-[#1C1C1C]">
        <svg class="w-8 h-8 text-[#444]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <p class="text-sm text-[#666]">
        {{ activeTab === 'all' ? '暂无伏笔记录' : `暂无${statusTabs.find(t => t.key === activeTab)?.label}的伏笔` }}
      </p>
      <p class="text-xs text-[#444] mt-1">系统会基于蓝图与章节数据自动维护伏笔</p>
    </div>

    <!-- Foreshadowing List -->
    <div v-else class="space-y-3">
      <div
        v-for="item in filteredForeshadowing"
        :key="item.id"
        class="bg-[#141414] border border-[#2A2A2A] rounded-xl p-4 transition-all duration-200 hover:border-[#3A3A3A]"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex-1">
            <!-- Status & Importance -->
            <div class="flex items-center gap-2 mb-2">
              <span
                class="px-2 py-0.5 rounded-full text-xs font-medium"
                :style="{ backgroundColor: getStatusColor(item.status) + '22', color: getStatusColor(item.status) }"
              >
                {{ getStatusLabel(item.status) }}
              </span>
              <span class="px-2 py-0.5 rounded-full text-xs font-medium bg-[#1C1C1C] text-[#888] border border-[#2A2A2A]">
                {{ getImportanceLabel(item.importance) }}
              </span>
            </div>

            <!-- Description -->
            <p class="text-sm text-[#bbb] mb-3">{{ item.description }}</p>

            <!-- Metadata -->
            <div class="flex flex-wrap gap-4">
              <div class="flex items-center gap-1">
                <svg class="w-4 h-4 text-[#444]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
                <span class="text-xs text-[#555]">
                  埋设于第{{ item.planted_chapter }}章《{{ item.planted_chapter_title }}》
                </span>
              </div>
              <div v-if="item.expected_payoff_chapter" class="flex items-center gap-1">
                <svg class="w-4 h-4 text-[#444]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="text-xs text-[#555]">
                  预期回收于第{{ item.expected_payoff_chapter }}章
                </span>
              </div>
              <div v-if="item.actual_payoff_chapter" class="flex items-center gap-1">
                <svg class="w-4 h-4 text-[#2ED573]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                <span class="text-xs text-[#2ED573]">
                  实际回收于第{{ item.actual_payoff_chapter }}章
                </span>
              </div>
            </div>
            <p
              v-if="item.author_note"
              class="text-xs text-[#444] mt-2"
            >
              备注：{{ item.author_note }}
            </p>
          </div>

          <div class="flex items-center gap-1.5 flex-shrink-0">
            <button
              @click="startEdit(item)"
              class="px-2.5 py-1 text-xs font-medium text-[#888] hover:text-white hover:bg-[#1C1C1C] rounded-lg transition-colors"
              :disabled="isSubmitting"
            >
              编辑
            </button>
            <button
              @click="deleteForeshadowing(item)"
              class="px-2.5 py-1 text-xs font-medium text-[#FF4757] bg-[rgba(255,71,87,0.08)] hover:bg-[rgba(255,71,87,0.15)] rounded-lg transition-colors"
              :disabled="isSubmitting"
            >
              删除
            </button>
          </div>
        </div>

        <!-- Edit Form -->
        <div
          v-if="editingId === item.id"
          class="mt-4 pt-4 border-t border-[#2A2A2A] space-y-3"
        >
          <div>
            <label class="block text-xs font-medium text-[#666] mb-1">伏笔描述</label>
            <textarea
              v-model="editForm.description"
              rows="3"
              class="w-full px-3 py-2 border border-[#2A2A2A] rounded-lg text-sm bg-[#0A0A0A] text-white placeholder-[#444] focus:border-[#FFE500] focus:outline-none transition-colors resize-none"
            ></textarea>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-[#666] mb-1">预期回收章节</label>
              <input
                v-model.number="editForm.expected_payoff_chapter"
                type="number"
                min="1"
                class="w-full px-3 py-2 border border-[#2A2A2A] rounded-lg text-sm bg-[#0A0A0A] text-white placeholder-[#444] focus:border-[#FFE500] focus:outline-none transition-colors"
                placeholder="留空表示不限制"
              />
            </div>
            <div>
              <label class="block text-xs font-medium text-[#666] mb-1">重要性</label>
              <select
                v-model="editForm.importance"
                class="w-full px-3 py-2 border border-[#2A2A2A] rounded-lg text-sm bg-[#0A0A0A] text-white focus:border-[#FFE500] focus:outline-none transition-colors"
              >
                <option value="short">短期伏笔</option>
                <option value="medium">中期伏笔</option>
                <option value="long">长期伏笔</option>
              </select>
            </div>
          </div>
          <div>
            <label class="block text-xs font-medium text-[#666] mb-1">备注</label>
            <textarea
              v-model="editForm.author_note"
              rows="2"
              class="w-full px-3 py-2 border border-[#2A2A2A] rounded-lg text-sm bg-[#0A0A0A] text-white placeholder-[#444] focus:border-[#FFE500] focus:outline-none transition-colors resize-none"
              placeholder="可选"
            ></textarea>
          </div>
          <div class="flex items-center justify-end gap-2">
            <button
              @click="cancelEdit"
              class="px-3 py-1.5 text-sm text-[#666] hover:text-[#888] transition-colors"
              :disabled="isSubmitting"
            >
              取消
            </button>
            <button
              @click="updateForeshadowing(item.id)"
              class="px-4 py-1.5 text-sm font-semibold bg-[#FFE500] text-black rounded-lg hover:bg-[#FFC300] transition-colors disabled:opacity-50"
              :disabled="isSubmitting"
            >
              {{ isSubmitting ? '保存中...' : '保存修改' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

interface Foreshadowing {
  id: string
  description: string
  planted_chapter: number
  planted_chapter_title: string
  expected_payoff_chapter?: number
  actual_payoff_chapter?: number
  status: 'planted' | 'paid_off' | 'overdue'
  importance: 'short' | 'medium' | 'long'
  author_note?: string
}

interface ForeshadowingResponse {
  project_id: string
  project_title: string
  total_foreshadowings: number
  planted_count: number
  paid_off_count: number
  overdue_count: number
  foreshadowings: Foreshadowing[]
}

const route = useRoute()
const authStore = useAuthStore()
const projectId = route.params.id as string

const isLoading = ref(false)
const isGenerating = ref(false)
const error = ref<string | null>(null)
const foreshadowingList = ref<Foreshadowing[]>([])
const totalForeshadowings = ref(0)
const plantedCount = ref(0)
const paidOffCount = ref(0)
const overdueCount = ref(0)
const activeTab = ref('all')
const editingId = ref<string | null>(null)
const isSubmitting = ref(false)
const editForm = ref({
  description: '',
  expected_payoff_chapter: null as number | null,
  importance: 'medium' as 'short' | 'medium' | 'long',
  author_note: ''
})

const statusTabs = [
  { key: 'all', label: '全部', color: '#888888' },
  { key: 'planted', label: '已埋设', color: '#FFE500' },
  { key: 'paid_off', label: '已回收', color: '#2ED573' },
  { key: 'overdue', label: '待回收', color: '#FF4757' }
]

const filteredForeshadowing = computed(() => {
  if (activeTab.value === 'all') {
    return foreshadowingList.value
  }
  return foreshadowingList.value.filter(item => item.status === activeTab.value)
})

const getCountByStatus = (status: string) => {
  if (status === 'all') return totalForeshadowings.value
  if (status === 'planted') return plantedCount.value
  if (status === 'paid_off') return paidOffCount.value
  if (status === 'overdue') return overdueCount.value
  return 0
}

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    'planted': '#FFE500',
    'paid_off': '#2ED573',
    'overdue': '#FF4757'
  }
  return colors[status] || '#888888'
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    'planted': '已埋设',
    'paid_off': '已回收',
    'overdue': '待回收'
  }
  return labels[status] || status
}

const getImportanceLabel = (importance: string) => {
  const labels: Record<string, string> = {
    'short': '短期伏笔',
    'medium': '中期伏笔',
    'long': '长期伏笔'
  }
  return labels[importance] || importance
}

const toBackendImportance = (importance: 'short' | 'medium' | 'long') => {
  if (importance === 'long') return 'major'
  if (importance === 'short') return 'subtle'
  return 'minor'
}

const parseErrorMessage = async (response: Response, fallback: string) => {
  try {
    const errorData = await response.json()
    return errorData.detail || errorData.message || fallback
  } catch {
    return `HTTP ${response.status}: ${response.statusText}`
  }
}

const fetchData = async () => {
  isLoading.value = true
  error.value = null

  try {
    const response = await fetch(`/api/novels/${projectId}/foreshadowings/summary`, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      let errorMessage = '获取伏笔数据失败'
      try {
        const errorData = await response.json()
        if (response.status === 422 && errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            const errors = errorData.detail.map((err: any) =>
              `${err.loc?.join('.')} - ${err.msg}`
            ).join('; ')
            errorMessage = `参数校验失败: ${errors}`
          } else if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail
          }
        } else {
          errorMessage = errorData.detail || errorData.message || JSON.stringify(errorData)
        }
      } catch (e) {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`
      }
      throw new Error(errorMessage)
    }

    const data: ForeshadowingResponse = await response.json()
    foreshadowingList.value = data.foreshadowings || []
    totalForeshadowings.value = data.total_foreshadowings
    plantedCount.value = data.planted_count
    paidOffCount.value = data.paid_off_count
    overdueCount.value = data.overdue_count
  } catch (e: any) {
    console.error('伏笔管理加载错误:', e)
    if (e instanceof Error) {
      error.value = e.message
    } else if (typeof e === 'string') {
      error.value = e
    } else {
      error.value = '加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}

const refreshData = () => {
  fetchData()
}

const generateForeshadowings = async () => {
  isGenerating.value = true
  error.value = null

  try {
    const response = await fetch(`/api/novels/${projectId}/foreshadowings/generate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      let errorMessage = '生成伏笔失败'
      try {
        const errorData = await response.json()
        errorMessage = errorData.detail || errorMessage
      } catch {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`
      }
      throw new Error(errorMessage)
    }

    await fetchData()
  } catch (e: any) {
    console.error('伏笔生成错误:', e)
    error.value = e instanceof Error ? e.message : '生成失败，请稍后重试'
  } finally {
    isGenerating.value = false
  }
}

const startEdit = (item: Foreshadowing) => {
  editingId.value = item.id
  editForm.value = {
    description: item.description || '',
    expected_payoff_chapter: item.expected_payoff_chapter ?? null,
    importance: item.importance || 'medium',
    author_note: item.author_note || ''
  }
}

const cancelEdit = () => {
  editingId.value = null
}

const updateForeshadowing = async (itemId: string) => {
  const description = editForm.value.description.trim()
  if (!description) {
    error.value = '伏笔描述不能为空'
    return
  }

  isSubmitting.value = true
  error.value = null

  try {
    const rawTarget = editForm.value.expected_payoff_chapter as unknown
    const targetRevealChapter = typeof rawTarget === 'number' && Number.isFinite(rawTarget) && rawTarget > 0
      ? rawTarget
      : null

    const response = await fetch(`/api/novels/${projectId}/foreshadowings/${itemId}`, {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${authStore.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        content: description,
        target_reveal_chapter: targetRevealChapter,
        importance: toBackendImportance(editForm.value.importance),
        author_note: editForm.value.author_note?.trim() || null
      })
    })

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, '更新伏笔失败'))
    }

    editingId.value = null
    await fetchData()
  } catch (e: any) {
    console.error('伏笔更新错误:', e)
    error.value = e instanceof Error ? e.message : '更新失败，请稍后重试'
  } finally {
    isSubmitting.value = false
  }
}

const deleteForeshadowing = async (item: Foreshadowing) => {
  if (!window.confirm('确认删除这条伏笔吗？该操作不可恢复。')) return

  isSubmitting.value = true
  error.value = null

  try {
    const response = await fetch(`/api/novels/${projectId}/foreshadowings/${item.id}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${authStore.token}`,
        'Content-Type': 'application/json'
      }
    })

    if (!response.ok) {
      throw new Error(await parseErrorMessage(response, '删除伏笔失败'))
    }

    if (editingId.value === item.id) {
      editingId.value = null
    }
    await fetchData()
  } catch (e: any) {
    console.error('伏笔删除错误:', e)
    error.value = e instanceof Error ? e.message : '删除失败，请稍后重试'
  } finally {
    isSubmitting.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

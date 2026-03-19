<!-- AIMETA P=伏笔区_伏笔管理展示|R=伏笔列表_回收状态|NR=不含分析逻辑|E=component:ForeshadowingSection|X=ui|A=伏笔组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="foreshadowing-section">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-full flex items-center justify-center" style="background-color: var(--md-warning-container);">
          <svg class="w-5 h-5" style="color: var(--md-on-warning-container);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div>
          <h3 class="md-title-medium" style="color: var(--md-on-surface);">伏笔管理</h3>
          <p class="md-body-small" style="color: var(--md-on-surface-variant);">追踪故事线索与回收</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="generateForeshadowings"
          class="md-btn md-btn-tonal md-ripple px-3 py-1.5 md-label-medium"
          :disabled="isGenerating || isLoading"
        >
          <svg v-if="isGenerating" class="w-4 h-4 mr-1.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <svg v-else class="w-4 h-4 mr-1.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          {{ isGenerating ? 'AI 生成中...' : '同步伏笔' }}
        </button>
        <button
          @click="refreshData"
          class="md-icon-btn md-ripple"
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
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="md-card md-card-outlined p-4 text-center" style="border-radius: var(--md-radius-md);">
        <p class="md-label-medium" style="color: var(--md-on-surface-variant);">总伏笔</p>
        <p class="md-headline-small" style="color: var(--md-primary);">{{ totalForeshadowings }}</p>
      </div>
      <div class="md-card md-card-outlined p-4 text-center" style="border-radius: var(--md-radius-md);">
        <p class="md-label-medium" style="color: var(--md-on-surface-variant);">已埋设</p>
        <p class="md-headline-small" style="color: var(--md-google-yellow);">{{ plantedCount }}</p>
      </div>
      <div class="md-card md-card-outlined p-4 text-center" style="border-radius: var(--md-radius-md);">
        <p class="md-label-medium" style="color: var(--md-on-surface-variant);">已回收</p>
        <p class="md-headline-small" style="color: var(--md-google-green);">{{ paidOffCount }}</p>
      </div>
      <div class="md-card md-card-outlined p-4 text-center" style="border-radius: var(--md-radius-md);">
        <p class="md-label-medium" style="color: var(--md-on-surface-variant);">待回收</p>
        <p class="md-headline-small" style="color: var(--md-google-red);">{{ overdueCount }}</p>
      </div>
    </div>

    <!-- Status Filter Tabs -->
    <div class="md-tabs mb-6">
      <button 
        v-for="tab in statusTabs" 
        :key="tab.key"
        @click="activeTab = tab.key"
        class="md-tab"
        :class="{ 'active': activeTab === tab.key }"
      >
        {{ tab.label }}
        <span 
          v-if="getCountByStatus(tab.key) > 0"
          class="ml-2 px-2 py-0.5 rounded-full md-label-small"
          :style="{ backgroundColor: tab.color + '20', color: tab.color }"
        >
          {{ getCountByStatus(tab.key) }}
        </span>
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex flex-col items-center justify-center py-12">
      <div class="md-spinner"></div>
      <p class="mt-4 md-body-medium" style="color: var(--md-on-surface-variant);">加载伏笔数据中...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="flex flex-col items-center justify-center py-12">
      <div class="w-12 h-12 rounded-full flex items-center justify-center mb-4" style="background-color: var(--md-error-container);">
        <svg class="w-6 h-6" style="color: var(--md-error);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <p class="md-body-medium" style="color: var(--md-error);">{{ error }}</p>
      <button @click="refreshData" class="md-btn md-btn-text md-ripple mt-4">重试</button>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredForeshadowing.length === 0" class="flex flex-col items-center justify-center py-12">
      <div class="w-16 h-16 rounded-full flex items-center justify-center mb-4" style="background-color: var(--md-surface-container);">
        <svg class="w-8 h-8" style="color: var(--md-on-surface-variant);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <p class="md-body-large" style="color: var(--md-on-surface);">
        {{ activeTab === 'all' ? '暂无伏笔记录' : `暂无${statusTabs.find(t => t.key === activeTab)?.label}的伏笔` }}
      </p>
      <p class="md-body-medium" style="color: var(--md-on-surface-variant);">系统会基于蓝图与章节数据自动维护伏笔</p>
    </div>

    <!-- Foreshadowing List -->
    <div v-else class="space-y-4">
      <div 
        v-for="item in filteredForeshadowing" 
        :key="item.id"
        class="md-card md-card-outlined p-4 transition-all duration-200"
        style="border-radius: var(--md-radius-md);"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex-1">
            <!-- Status & Importance -->
            <div class="flex items-center gap-2 mb-2">
              <span
                class="md-chip md-chip-filter selected px-2 py-1"
                :style="{ backgroundColor: getStatusColor(item.status) + '20', color: getStatusColor(item.status) }"
              >
                {{ getStatusLabel(item.status) }}
              </span>
              <span class="md-chip md-chip-assist px-2 py-1">
                {{ getImportanceLabel(item.importance) }}
              </span>
            </div>

            <!-- Description -->
            <p class="md-body-medium mb-3" style="color: var(--md-on-surface);">{{ item.description }}</p>

            <!-- Metadata -->
            <div class="flex flex-wrap gap-4">
              <div class="flex items-center gap-1">
                <svg class="w-4 h-4" style="color: var(--md-on-surface-variant);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
                <span class="md-body-small" style="color: var(--md-on-surface-variant);">
                  埋设于第{{ item.planted_chapter }}章《{{ item.planted_chapter_title }}》
                </span>
              </div>
              <div v-if="item.expected_payoff_chapter" class="flex items-center gap-1">
                <svg class="w-4 h-4" style="color: var(--md-on-surface-variant);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="md-body-small" style="color: var(--md-on-surface-variant);">
                  预期回收于第{{ item.expected_payoff_chapter }}章
                </span>
              </div>
              <div v-if="item.actual_payoff_chapter" class="flex items-center gap-1">
                <svg class="w-4 h-4" style="color: var(--md-success);" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                <span class="md-body-small" style="color: var(--md-success);">
                  实际回收于第{{ item.actual_payoff_chapter }}章
                </span>
              </div>
            </div>
            <p
              v-if="item.author_note"
              class="md-body-small mt-2"
              style="color: var(--md-on-surface-variant);"
            >
              备注：{{ item.author_note }}
            </p>
          </div>

          <div class="flex items-center gap-2">
            <button
              @click="startEdit(item)"
              class="md-btn md-btn-text md-ripple px-3 py-1 md-label-medium"
              :disabled="isSubmitting"
            >
              编辑
            </button>
            <button
              @click="deleteForeshadowing(item)"
              class="md-btn md-ripple px-3 py-1 md-label-medium"
              style="background-color: var(--md-error-container); color: var(--md-error);"
              :disabled="isSubmitting"
            >
              删除
            </button>
          </div>
        </div>

        <div
          v-if="editingId === item.id"
          class="mt-4 pt-4 border-t space-y-3"
          style="border-color: var(--md-outline-variant);"
        >
          <div>
            <label class="md-label-medium block mb-1" style="color: var(--md-on-surface-variant);">伏笔描述</label>
            <textarea
              v-model="editForm.description"
              rows="3"
              class="w-full px-3 py-2 border rounded-md md-body-medium"
              style="border-color: var(--md-outline-variant); background-color: var(--md-surface); color: var(--md-on-surface);"
            ></textarea>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label class="md-label-medium block mb-1" style="color: var(--md-on-surface-variant);">预期回收章节</label>
              <input
                v-model.number="editForm.expected_payoff_chapter"
                type="number"
                min="1"
                class="w-full px-3 py-2 border rounded-md md-body-medium"
                style="border-color: var(--md-outline-variant); background-color: var(--md-surface); color: var(--md-on-surface);"
                placeholder="留空表示不限制"
              />
            </div>
            <div>
              <label class="md-label-medium block mb-1" style="color: var(--md-on-surface-variant);">重要性</label>
              <select
                v-model="editForm.importance"
                class="w-full px-3 py-2 border rounded-md md-body-medium"
                style="border-color: var(--md-outline-variant); background-color: var(--md-surface); color: var(--md-on-surface);"
              >
                <option value="short">短期伏笔</option>
                <option value="medium">中期伏笔</option>
                <option value="long">长期伏笔</option>
              </select>
            </div>
          </div>
          <div>
            <label class="md-label-medium block mb-1" style="color: var(--md-on-surface-variant);">备注</label>
            <textarea
              v-model="editForm.author_note"
              rows="2"
              class="w-full px-3 py-2 border rounded-md md-body-medium"
              style="border-color: var(--md-outline-variant); background-color: var(--md-surface); color: var(--md-on-surface);"
              placeholder="可选"
            ></textarea>
          </div>
          <div class="flex items-center justify-end gap-2">
            <button
              @click="cancelEdit"
              class="md-btn md-btn-text md-ripple px-3 py-1.5 md-label-medium"
              :disabled="isSubmitting"
            >
              取消
            </button>
            <button
              @click="updateForeshadowing(item.id)"
              class="md-btn md-btn-filled md-ripple px-3 py-1.5 md-label-medium"
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
  { key: 'all', label: '全部', color: '#5F6368' },
  { key: 'planted', label: '已埋设', color: '#FBBC04' },
  { key: 'paid_off', label: '已回收', color: '#34A853' },
  { key: 'overdue', label: '待回收', color: '#EA4335' }
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
    'planted': '#FBBC04',
    'paid_off': '#34A853',
    'overdue': '#EA4335'
  }
  return colors[status] || '#5F6368'
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
        // 处理 422 错误（参数校验失败）
        if (response.status === 422 && errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            // FastAPI验证错误格式
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

    // 生成成功后刷新列表
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

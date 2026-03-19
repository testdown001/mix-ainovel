<!-- AIMETA P=伏笔区_伏笔管理展示|R=伏笔列表_回收状态|NR=不含分析逻辑|E=component:ForeshadowingSection|X=ui|A=伏笔组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="foreshadowing-section">
    <!-- Header -->
    <div class="fs-header">
      <div class="flex items-center gap-3">
        <div class="fs-icon-box">
          <svg class="w-5 h-5" style="color: #FACC15;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div>
          <h3 class="fs-title" style="font-family: var(--ar-font-display); color: #dee3eb;">伏笔管理</h3>
          <p class="fs-subtitle" style="color: #8b929a;">追踪故事线索与回收</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="generateForeshadowings"
          class="fs-btn-generate"
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
          class="fs-btn-icon"
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
      <div class="fs-stat-card">
        <p class="fs-stat-label">总伏笔</p>
        <p class="fs-stat-value" style="color: #FACC15;">{{ totalForeshadowings }}</p>
      </div>
      <div class="fs-stat-card">
        <p class="fs-stat-label">已埋设</p>
        <p class="fs-stat-value" style="color: #FACC15;">{{ plantedCount }}</p>
      </div>
      <div class="fs-stat-card">
        <p class="fs-stat-label">已回收</p>
        <p class="fs-stat-value" style="color: #4ADE80;">{{ paidOffCount }}</p>
      </div>
      <div class="fs-stat-card">
        <p class="fs-stat-label">待回收</p>
        <p class="fs-stat-value" style="color: #EF4444;">{{ overdueCount }}</p>
      </div>
    </div>

    <!-- Status Filter Tabs -->
    <div class="fs-tabs">
      <button 
        v-for="tab in statusTabs" 
        :key="tab.key"
        @click="activeTab = tab.key"
        class="fs-tab"
        :class="{ 'fs-tab--active': activeTab === tab.key }"
      >
        {{ tab.label }}
        <span 
          v-if="getCountByStatus(tab.key) > 0"
          class="fs-tab-badge"
          :style="{ backgroundColor: tab.color + '18', color: tab.color }"
        >
          {{ getCountByStatus(tab.key) }}
        </span>
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex flex-col items-center justify-center py-12">
      <div class="fs-spinner"></div>
      <p class="mt-4" style="color: #8b929a; font-family: var(--ar-font-ui); font-size: 0.875rem;">加载伏笔数据中...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="flex flex-col items-center justify-center py-12">
      <div class="fs-error-icon">
        <svg class="w-6 h-6" style="color: #EF4444;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <p style="color: #EF4444; font-size: 0.875rem;">{{ error }}</p>
      <button @click="refreshData" class="fs-btn-retry">重试</button>
    </div>

    <!-- Empty State -->
    <div v-else-if="filteredForeshadowing.length === 0" class="flex flex-col items-center justify-center py-12">
      <div class="fs-empty-icon">
        <svg class="w-8 h-8" style="color: #545d68;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <p style="color: #dee3eb; font-size: 1rem; margin-top: 0.5rem;">
        {{ activeTab === 'all' ? '暂无伏笔记录' : `暂无${statusTabs.find(t => t.key === activeTab)?.label}的伏笔` }}
      </p>
      <p style="color: #8b929a; font-size: 0.875rem; margin-top: 0.25rem;">系统会基于蓝图与章节数据自动维护伏笔</p>
    </div>

    <!-- Foreshadowing List -->
    <div v-else class="space-y-4">
      <div 
        v-for="item in filteredForeshadowing" 
        :key="item.id"
        class="fs-card"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex-1">
            <!-- Status & Importance -->
            <div class="flex items-center gap-2 mb-2">
              <!-- Green pulse dot for active (planted) foreshadowing -->
              <span v-if="item.status === 'planted'" class="fs-pulse-dot"></span>
              <span
                class="fs-status-chip"
                :style="{ backgroundColor: getStatusColor(item.status) + '18', color: getStatusColor(item.status), borderColor: getStatusColor(item.status) + '30' }"
              >
                {{ getStatusLabel(item.status) }}
              </span>
              <span class="fs-importance-chip">
                {{ getImportanceLabel(item.importance) }}
              </span>
            </div>

            <!-- Description -->
            <p class="fs-description">{{ item.description }}</p>

            <!-- Metadata -->
            <div class="flex flex-wrap gap-4">
              <div class="flex items-center gap-1">
                <svg class="w-4 h-4" style="color: #545d68;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
                <span class="fs-meta-text">
                  埋设于第{{ item.planted_chapter }}章《{{ item.planted_chapter_title }}》
                </span>
              </div>
              <div v-if="item.expected_payoff_chapter" class="flex items-center gap-1">
                <svg class="w-4 h-4" style="color: #545d68;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span class="fs-meta-text">
                  预期回收于第{{ item.expected_payoff_chapter }}章
                </span>
              </div>
              <div v-if="item.actual_payoff_chapter" class="flex items-center gap-1">
                <svg class="w-4 h-4" style="color: #4ADE80;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                <span style="color: #4ADE80; font-size: 0.8rem;">
                  实际回收于第{{ item.actual_payoff_chapter }}章
                </span>
              </div>
            </div>
            <p
              v-if="item.author_note"
              class="fs-author-note"
            >
              备注：{{ item.author_note }}
            </p>
          </div>

          <div class="flex items-center gap-2">
            <button
              @click="startEdit(item)"
              class="fs-btn-edit"
              :disabled="isSubmitting"
            >
              编辑
            </button>
            <button
              @click="deleteForeshadowing(item)"
              class="fs-btn-delete"
              :disabled="isSubmitting"
            >
              删除
            </button>
          </div>
        </div>

        <div
          v-if="editingId === item.id"
          class="fs-edit-form"
        >
          <div>
            <label class="fs-form-label">伏笔描述</label>
            <textarea
              v-model="editForm.description"
              rows="3"
              class="fs-input"
            ></textarea>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label class="fs-form-label">预期回收章节</label>
              <input
                v-model.number="editForm.expected_payoff_chapter"
                type="number"
                min="1"
                class="fs-input"
                placeholder="留空表示不限制"
              />
            </div>
            <div>
              <label class="fs-form-label">重要性</label>
              <select
                v-model="editForm.importance"
                class="fs-input"
              >
                <option value="short">短期伏笔</option>
                <option value="medium">中期伏笔</option>
                <option value="long">长期伏笔</option>
              </select>
            </div>
          </div>
          <div>
            <label class="fs-form-label">备注</label>
            <textarea
              v-model="editForm.author_note"
              rows="2"
              class="fs-input"
              placeholder="可选"
            ></textarea>
          </div>
          <div class="flex items-center justify-end gap-2">
            <button
              @click="cancelEdit"
              class="fs-btn-cancel"
              :disabled="isSubmitting"
            >
              取消
            </button>
            <button
              @click="updateForeshadowing(item.id)"
              class="fs-btn-save"
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
  { key: 'all', label: '全部', color: '#8b929a' },
  { key: 'planted', label: '已埋设', color: '#FACC15' },
  { key: 'paid_off', label: '已回收', color: '#4ADE80' },
  { key: 'overdue', label: '待回收', color: '#EF4444' }
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
    'planted': '#FACC15',
    'paid_off': '#4ADE80',
    'overdue': '#EF4444'
  }
  return colors[status] || '#8b929a'
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

<style scoped>
.foreshadowing-section {
  font-family: var(--ar-font-ui);
}

.fs-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}

.fs-icon-box {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(250, 204, 21, 0.08);
  border: 1px solid rgba(250, 204, 21, 0.15);
}

.fs-title {
  font-size: 1.125rem;
  font-weight: 600;
  line-height: 1.4;
  letter-spacing: 0.01em;
}

.fs-subtitle {
  font-size: 0.8rem;
  line-height: 1.4;
}

/* Stat cards */
.fs-stat-card {
  background-color: #0f1419;
  border: 1px solid rgba(77, 70, 50, 0.15);
  border-radius: 4px;
  padding: 1rem;
  text-align: center;
  transition: border-color 0.2s;
}

.fs-stat-card:hover {
  border-color: rgba(250, 204, 21, 0.25);
}

.fs-stat-label {
  font-family: var(--ar-font-ui);
  font-size: 0.75rem;
  font-weight: 500;
  color: #8b929a;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.fs-stat-value {
  font-family: var(--ar-font-display);
  font-size: 1.5rem;
  font-weight: 700;
  margin-top: 0.25rem;
}

/* Tabs */
.fs-tabs {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid rgba(77, 70, 50, 0.15);
  padding-bottom: 0;
}

.fs-tab {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 500;
  color: #545d68;
  padding: 0.5rem 0.75rem;
  border: none;
  background: none;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.fs-tab:hover {
  color: #8b929a;
}

.fs-tab--active {
  color: #FACC15;
  border-bottom-color: #FACC15;
}

.fs-tab-badge {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-weight: 600;
}

/* Foreshadowing cards */
.fs-card {
  background-color: #0f1419;
  border: 1px solid rgba(77, 70, 50, 0.15);
  border-radius: 4px;
  padding: 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.fs-card:hover {
  border-color: rgba(250, 204, 21, 0.2);
  box-shadow: 0 0 20px rgba(250, 204, 21, 0.04);
}

/* Green pulse dot for active foreshadowing */
.fs-pulse-dot {
  position: relative;
  display: inline-flex;
  width: 8px;
  height: 8px;
}

.fs-pulse-dot::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background-color: #4ADE80;
  animation: fs-pulse 2s ease-in-out infinite;
}

.fs-pulse-dot::after {
  content: '';
  position: relative;
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #4ADE80;
}

@keyframes fs-pulse {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 0; transform: scale(2.2); }
}

.fs-status-chip {
  font-family: var(--ar-font-ui);
  font-size: 0.7rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  border: 1px solid;
  letter-spacing: 0.02em;
}

.fs-importance-chip {
  font-family: var(--ar-font-ui);
  font-size: 0.7rem;
  font-weight: 500;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  background-color: #171c22;
  color: #8b929a;
  border: 1px solid rgba(77, 70, 50, 0.15);
}

.fs-description {
  font-family: var(--ar-font-ui);
  font-size: 0.875rem;
  color: #dee3eb;
  line-height: 1.6;
  margin-bottom: 0.75rem;
}

.fs-meta-text {
  font-size: 0.8rem;
  color: #545d68;
}

.fs-author-note {
  font-size: 0.8rem;
  color: #8b929a;
  margin-top: 0.5rem;
  font-style: italic;
}

/* Buttons */
.fs-btn-generate {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  padding: 0.375rem 0.75rem;
  border-radius: 4px;
  border: 1px solid rgba(250, 204, 21, 0.3);
  background-color: rgba(250, 204, 21, 0.08);
  color: #FACC15;
  cursor: pointer;
  transition: background-color 0.2s, border-color 0.2s;
}

.fs-btn-generate:hover:not(:disabled) {
  background-color: rgba(250, 204, 21, 0.15);
  border-color: rgba(250, 204, 21, 0.5);
}

.fs-btn-generate:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.fs-btn-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 4px;
  border: 1px solid rgba(77, 70, 50, 0.15);
  background: transparent;
  color: #8b929a;
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s;
}

.fs-btn-icon:hover:not(:disabled) {
  color: #FACC15;
  border-color: rgba(250, 204, 21, 0.3);
}

.fs-btn-icon:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.fs-btn-edit {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  border: 1px solid rgba(77, 70, 50, 0.15);
  background: transparent;
  color: #8b929a;
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s;
}

.fs-btn-edit:hover:not(:disabled) {
  color: #FACC15;
  border-color: rgba(250, 204, 21, 0.3);
}

.fs-btn-edit:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.fs-btn-delete {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  border: 1px solid rgba(239, 68, 68, 0.2);
  background-color: rgba(239, 68, 68, 0.08);
  color: #EF4444;
  cursor: pointer;
  transition: background-color 0.2s, border-color 0.2s;
}

.fs-btn-delete:hover:not(:disabled) {
  background-color: rgba(239, 68, 68, 0.15);
  border-color: rgba(239, 68, 68, 0.4);
}

.fs-btn-delete:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.fs-btn-retry {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 500;
  margin-top: 1rem;
  padding: 0.375rem 1rem;
  border-radius: 4px;
  border: 1px solid rgba(77, 70, 50, 0.15);
  background: transparent;
  color: #8b929a;
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s;
}

.fs-btn-retry:hover {
  color: #FACC15;
  border-color: rgba(250, 204, 21, 0.3);
}

/* Edit form */
.fs-edit-form {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(77, 70, 50, 0.15);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.fs-form-label {
  display: block;
  font-family: var(--ar-font-ui);
  font-size: 0.75rem;
  font-weight: 500;
  color: #8b929a;
  margin-bottom: 0.25rem;
  letter-spacing: 0.02em;
}

.fs-input {
  width: 100%;
  padding: 0.5rem 0.75rem;
  font-family: var(--ar-font-ui);
  font-size: 0.875rem;
  color: #dee3eb;
  background-color: #171c22;
  border: 1px solid rgba(77, 70, 50, 0.15);
  border-radius: 4px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  resize: vertical;
}

.fs-input::placeholder {
  color: #545d68;
}

.fs-input:focus {
  border-color: rgba(250, 204, 21, 0.4);
  box-shadow: 0 0 0 2px rgba(250, 204, 21, 0.08);
}

.fs-input option {
  background-color: #171c22;
  color: #dee3eb;
}

.fs-btn-cancel {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 500;
  padding: 0.375rem 0.75rem;
  border-radius: 4px;
  border: 1px solid rgba(77, 70, 50, 0.15);
  background: transparent;
  color: #8b929a;
  cursor: pointer;
  transition: color 0.2s;
}

.fs-btn-cancel:hover:not(:disabled) {
  color: #dee3eb;
}

.fs-btn-cancel:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.fs-btn-save {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.375rem 0.75rem;
  border-radius: 4px;
  border: 1px solid rgba(250, 204, 21, 0.4);
  background-color: rgba(250, 204, 21, 0.12);
  color: #FACC15;
  cursor: pointer;
  transition: background-color 0.2s, border-color 0.2s;
}

.fs-btn-save:hover:not(:disabled) {
  background-color: rgba(250, 204, 21, 0.2);
  border-color: rgba(250, 204, 21, 0.6);
}

.fs-btn-save:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Error & empty state icons */
.fs-error-icon {
  width: 3rem;
  height: 3rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.15);
  margin-bottom: 1rem;
}

.fs-empty-icon {
  width: 4rem;
  height: 4rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #171c22;
  border: 1px solid rgba(77, 70, 50, 0.15);
}

/* Spinner */
.fs-spinner {
  width: 2rem;
  height: 2rem;
  border: 2px solid rgba(77, 70, 50, 0.15);
  border-top-color: #FACC15;
  border-radius: 50%;
  animation: fs-spin 0.8s linear infinite;
}

@keyframes fs-spin {
  to { transform: rotate(360deg); }
}
</style>

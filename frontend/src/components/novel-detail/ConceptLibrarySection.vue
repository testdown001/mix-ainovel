<!-- 概念库 / 设定百科 Section -->
<template>
  <div class="space-y-4">
    <!-- 头部：标题 + AI提取 + 新增按钮 -->
    <div class="flex items-center justify-between">
      <h3 class="md-title-large" style="color: var(--md-on-surface);">设定百科</h3>
      <div class="flex gap-2">
        <button
          class="md-btn md-btn-outlined md-ripple text-sm"
          :disabled="isGenerating"
          @click="generateConcepts"
        >
          <span v-if="isGenerating">提取中...</span>
          <span v-else>🤖 AI提取概念</span>
        </button>
        <button class="md-btn md-btn-filled md-ripple text-sm" @click="openCreate">
          + 新增概念
        </button>
      </div>
    </div>

    <!-- 状态消息 -->
    <div v-if="message" class="p-3 rounded-lg text-sm" :class="messageType === 'success' ? 'bg-success-muted text-success' : messageType === 'error' ? 'bg-error-muted text-error' : 'bg-primary-muted text-primary'">
      {{ message }}
    </div>

    <!-- 类型过滤标签 -->
    <div class="flex flex-wrap gap-2">
      <button
        v-for="t in typeFilters"
        :key="t.value"
        class="px-3 py-1.5 rounded-full text-sm font-medium transition-all"
        :class="activeType === t.value
          ? 'text-white'
          : 'bg-bg-elevated text-text-secondary hover:bg-[rgba(255,255,255,0.05)]'"
        :style="activeType === t.value ? `background-color: ${t.color}` : ''"
        @click="activeType = activeType === t.value ? '' : t.value"
      >
        {{ t.icon }} {{ t.label }}
        <span class="ml-1 opacity-70">({{ countByType(t.value) }})</span>
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="md-spinner"></div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="filteredConcepts.length === 0" class="text-center py-12">
      <p class="md-body-large" style="color: var(--md-on-surface-variant);">
        {{ activeType ? '该分类暂无概念' : '暂无设定概念，点击"AI提取概念"自动识别' }}
      </p>
    </div>

    <!-- 概念卡片列表 -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      <div
        v-for="concept in filteredConcepts"
        :key="concept.id"
        class="p-4 rounded-xl border cursor-pointer transition-shadow"
        :style="`border-left: 4px solid ${getTypeColor(concept.entity_type)}`"
        @click="openEdit(concept)"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-lg">{{ getTypeIcon(concept.entity_type) }}</span>
              <h4 class="font-semibold truncate" style="color: var(--md-on-surface);">{{ concept.canonical_name }}</h4>
            </div>
            <p class="text-sm mt-1 line-clamp-2" style="color: var(--md-on-surface-variant);">
              {{ concept.description || '暂无描述' }}
            </p>
            <div v-if="concept.aliases.length" class="flex flex-wrap gap-1 mt-2">
              <span
                v-for="alias in concept.aliases"
                :key="alias"
                class="px-2 py-0.5 rounded-full text-xs bg-bg-elevated"
                style="color: var(--md-on-surface-variant);"
              >
                {{ alias }}
              </span>
            </div>
          </div>
          <button
            class="ml-2 flex-shrink-0 text-red-400 hover:text-red-600 transition-colors p-1"
            @click.stop="deleteConcept(concept)"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- 编辑/新增弹窗 -->
    <teleport to="body">
      <transition name="fade">
        <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30" @click.self="showModal = false">
          <div class="bg-bg-surface rounded-2xl w-full max-w-lg mx-4 p-6 space-y-4">
            <h3 class="md-title-large" style="color: var(--md-on-surface);">{{ editingId ? '编辑概念' : '新增概念' }}</h3>

            <div class="space-y-3">
              <div>
                <label class="block text-sm font-medium mb-1">名称 *</label>
                <input v-model="form.canonical_name" class="w-full px-3 py-2 border rounded-lg text-sm" placeholder="概念名称" />
              </div>
              <div>
                <label class="block text-sm font-medium mb-1">类型</label>
                <select v-model="form.entity_type" class="w-full px-3 py-2 border rounded-lg text-sm">
                  <option v-for="t in typeFilters" :key="t.value" :value="t.value">{{ t.icon }} {{ t.label }}</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium mb-1">描述</label>
                <textarea v-model="form.description" rows="3" class="w-full px-3 py-2 border rounded-lg text-sm" placeholder="详细描述..."></textarea>
              </div>
              <div>
                <label class="block text-sm font-medium mb-1">别名（逗号分隔）</label>
                <input v-model="aliasesInput" class="w-full px-3 py-2 border rounded-lg text-sm" placeholder="别名1, 别名2" />
              </div>
            </div>

            <div class="flex justify-end gap-2 pt-2">
              <button class="md-btn md-btn-text md-ripple" @click="showModal = false">取消</button>
              <button class="md-btn md-btn-filled md-ripple" :disabled="!form.canonical_name" @click="saveConcept">保存</button>
            </div>
          </div>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ConceptAPI, type Concept } from '@/api/novel'

const route = useRoute()
const projectId = route.params.id as string

const concepts = ref<Concept[]>([])
const loading = ref(false)
const activeType = ref('')
const message = ref('')
const messageType = ref<'success' | 'error' | 'info'>('info')
const isGenerating = ref(false)
const showModal = ref(false)
const editingId = ref<number | null>(null)
const aliasesInput = ref('')

const form = ref({
  canonical_name: '',
  entity_type: 'character',
  description: '',
})

const typeFilters = [
  { value: 'character', label: '角色', icon: '👤', color: '#6366f1' },
  { value: 'location', label: '地点', icon: '📍', color: '#10b981' },
  { value: 'organization', label: '组织', icon: '🏛️', color: '#f59e0b' },
  { value: 'item', label: '物品', icon: '🗡️', color: '#ef4444' },
  { value: 'ability', label: '能力', icon: '⚡', color: '#8b5cf6' },
]

const getTypeColor = (type: string) => typeFilters.find(t => t.value === type)?.color || '#6b7280'
const getTypeIcon = (type: string) => typeFilters.find(t => t.value === type)?.icon || '📋'
const countByType = (type: string) => concepts.value.filter(c => c.entity_type === type).length

const filteredConcepts = computed(() => {
  if (!activeType.value) return concepts.value
  return concepts.value.filter(c => c.entity_type === activeType.value)
})

const showMsg = (msg: string, type: 'success' | 'error' | 'info' = 'info') => {
  message.value = msg
  messageType.value = type
  setTimeout(() => { message.value = '' }, 4000)
}

const loadConcepts = async () => {
  loading.value = true
  try {
    concepts.value = await ConceptAPI.list(projectId)
  } catch (e: any) {
    showMsg(e.message || '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingId.value = null
  form.value = { canonical_name: '', entity_type: 'character', description: '' }
  aliasesInput.value = ''
  showModal.value = true
}

const openEdit = (concept: Concept) => {
  editingId.value = concept.id
  form.value = {
    canonical_name: concept.canonical_name,
    entity_type: concept.entity_type,
    description: concept.description || '',
  }
  aliasesInput.value = concept.aliases.join(', ')
  showModal.value = true
}

const saveConcept = async () => {
  const aliases = aliasesInput.value.split(',').map(s => s.trim()).filter(Boolean)
  try {
    if (editingId.value) {
      await ConceptAPI.update(projectId, editingId.value, { ...form.value, aliases })
      showMsg('概念更新成功', 'success')
    } else {
      await ConceptAPI.create(projectId, { ...form.value, aliases })
      showMsg('概念创建成功', 'success')
    }
    showModal.value = false
    await loadConcepts()
  } catch (e: any) {
    showMsg(e.message || '保存失败', 'error')
  }
}

const deleteConcept = async (concept: Concept) => {
  if (!confirm(`确定删除「${concept.canonical_name}」？`)) return
  try {
    await ConceptAPI.delete(projectId, concept.id)
    showMsg('已删除', 'success')
    await loadConcepts()
  } catch (e: any) {
    showMsg(e.message || '删除失败', 'error')
  }
}

const generateConcepts = async () => {
  isGenerating.value = true
  try {
    const result = await ConceptAPI.generate(projectId)
    showMsg(result.message, 'success')
    await loadConcepts()
  } catch (e: any) {
    showMsg(e.message || '提取失败', 'error')
  } finally {
    isGenerating.value = false
  }
}

onMounted(loadConcepts)
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.line-clamp-2 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
</style>

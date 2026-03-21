<!-- 概念库 / 设定百科 Section -->
<template>
  <div class="space-y-4">
    <!-- 头部：标题 + AI提取 + 新增按钮 -->
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-base font-semibold text-white">设定百科</h3>
        <p class="text-xs text-[#666] mt-0.5">概念、地点、组织与物品的统一管理</p>
      </div>
      <div class="flex gap-2">
        <button
          class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-[#888] border border-[#2A2A2A] bg-[#141414] hover:border-[#3A3A3A] hover:text-white rounded-lg transition-colors"
          :disabled="isGenerating"
          @click="generateConcepts"
        >
          <span v-if="isGenerating">提取中...</span>
          <span v-else>🤖 AI提取概念</span>
        </button>
        <button
          class="flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold bg-[#FFE500] text-black rounded-lg hover:bg-[#FFC300] transition-colors"
          @click="openCreate"
        >
          + 新增概念
        </button>
      </div>
    </div>

    <!-- 状态消息 -->
    <div
      v-if="message"
      class="p-3 rounded-lg text-sm"
      :class="messageType === 'success'
        ? 'bg-[rgba(46,213,115,0.08)] text-[#2ED573] border border-[rgba(46,213,115,0.2)]'
        : messageType === 'error'
          ? 'bg-[rgba(255,71,87,0.08)] text-[#FF4757] border border-[rgba(255,71,87,0.2)]'
          : 'bg-[rgba(6,182,212,0.08)] text-[#06B6D4] border border-[rgba(6,182,212,0.2)]'"
    >
      {{ message }}
    </div>

    <!-- 类型过滤标签 -->
    <div class="flex flex-wrap gap-2">
      <button
        v-for="t in typeFilters"
        :key="t.value"
        class="px-3 py-1.5 rounded-full text-sm font-medium transition-all"
        :class="activeType === t.value
          ? 'text-black'
          : 'bg-[#1C1C1C] text-[#666] hover:bg-[#222] hover:text-[#888] border border-[#2A2A2A]'"
        :style="activeType === t.value ? `background-color: ${t.color}` : ''"
        @click="activeType = activeType === t.value ? '' : t.value"
      >
        {{ t.icon }} {{ t.label }}
        <span class="ml-1 opacity-70">({{ countByType(t.value) }})</span>
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center py-12">
      <div class="w-8 h-8 border-2 border-[#FFE500] border-t-transparent rounded-full animate-spin"></div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="filteredConcepts.length === 0" class="text-center py-12">
      <p class="text-sm text-[#555]">
        {{ activeType ? '该分类暂无概念' : '暂无设定概念，点击"AI提取概念"自动识别' }}
      </p>
    </div>

    <!-- 概念卡片列表 -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      <div
        v-for="concept in filteredConcepts"
        :key="concept.id"
        class="p-4 rounded-xl border border-[#2A2A2A] bg-[#141414] cursor-pointer hover:border-[#3A3A3A] transition-all"
        :style="`border-left: 3px solid ${getTypeColor(concept.entity_type)}`"
        @click="openEdit(concept)"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-lg">{{ getTypeIcon(concept.entity_type) }}</span>
              <h4 class="font-semibold truncate text-white text-sm">{{ concept.canonical_name }}</h4>
            </div>
            <p class="text-xs text-[#666] mt-1 line-clamp-2">
              {{ concept.description || '暂无描述' }}
            </p>
            <div v-if="concept.aliases.length" class="flex flex-wrap gap-1 mt-2">
              <span
                v-for="alias in concept.aliases"
                :key="alias"
                class="px-2 py-0.5 rounded-full text-xs bg-[#1C1C1C] text-[#555] border border-[#2A2A2A]"
              >
                {{ alias }}
              </span>
            </div>
          </div>
          <button
            class="ml-2 flex-shrink-0 text-[#444] hover:text-[#FF4757] transition-colors p-1"
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
        <div v-if="showModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="showModal = false">
          <div class="bg-[#141414] border border-[#2A2A2A] rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6 space-y-4">
            <h3 class="text-base font-semibold text-white">{{ editingId ? '编辑概念' : '新增概念' }}</h3>

            <div class="space-y-3">
              <div>
                <label class="block text-xs font-medium text-[#666] mb-1">名称 *</label>
                <input
                  v-model="form.canonical_name"
                  class="w-full px-3 py-2 border border-[#2A2A2A] rounded-lg text-sm bg-[#0A0A0A] text-white placeholder-[#444] focus:border-[#FFE500] focus:outline-none transition-colors"
                  placeholder="概念名称"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-[#666] mb-1">类型</label>
                <select
                  v-model="form.entity_type"
                  class="w-full px-3 py-2 border border-[#2A2A2A] rounded-lg text-sm bg-[#0A0A0A] text-white focus:border-[#FFE500] focus:outline-none transition-colors"
                >
                  <option v-for="t in typeFilters" :key="t.value" :value="t.value">{{ t.icon }} {{ t.label }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs font-medium text-[#666] mb-1">描述</label>
                <textarea
                  v-model="form.description"
                  rows="3"
                  class="w-full px-3 py-2 border border-[#2A2A2A] rounded-lg text-sm bg-[#0A0A0A] text-white placeholder-[#444] focus:border-[#FFE500] focus:outline-none transition-colors resize-none"
                  placeholder="详细描述..."
                ></textarea>
              </div>
              <div>
                <label class="block text-xs font-medium text-[#666] mb-1">别名（逗号分隔）</label>
                <input
                  v-model="aliasesInput"
                  class="w-full px-3 py-2 border border-[#2A2A2A] rounded-lg text-sm bg-[#0A0A0A] text-white placeholder-[#444] focus:border-[#FFE500] focus:outline-none transition-colors"
                  placeholder="别名1, 别名2"
                />
              </div>
            </div>

            <div class="flex justify-end gap-2 pt-2">
              <button
                class="px-4 py-2 text-sm text-[#666] hover:text-[#888] transition-colors"
                @click="showModal = false"
              >
                取消
              </button>
              <button
                class="px-4 py-2 text-sm font-semibold bg-[#FFE500] text-black rounded-lg hover:bg-[#FFC300] transition-colors disabled:opacity-40"
                :disabled="!form.canonical_name"
                @click="saveConcept"
              >
                保存
              </button>
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
  { value: 'character', label: '角色', icon: '👤', color: '#FFE500' },
  { value: 'location', label: '地点', icon: '📍', color: '#2ED573' },
  { value: 'organization', label: '组织', icon: '🏛️', color: '#06B6D4' },
  { value: 'item', label: '物品', icon: '🗡️', color: '#FF4757' },
  { value: 'ability', label: '能力', icon: '⚡', color: '#A855F7' },
]

const getTypeColor = (type: string) => typeFilters.find(t => t.value === type)?.color || '#444'
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

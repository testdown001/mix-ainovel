<!-- AIMETA P=技能选择器组件|R=技能列表_选择_配置面板|NR=|E=SkillSelector|X=ui|A=技能系统|D=vue|S=dom -->
<template>
  <div class="skill-selector">
    <!-- 顶部标题区 -->
    <header class="selector-header">
      <h2 class="selector-title">写作技能</h2>
      <p class="selector-subtitle">选择技能优化章节内容</p>
    </header>

    <!-- 分类标签 -->
    <div class="category-tabs">
      <button
        class="category-tab"
        :class="{ active: selectedCategory === null }"
        @click="selectedCategory = null"
      >
        全部
      </button>
      <button
        v-for="cat in categories"
        :key="cat"
        class="category-tab"
        :class="{ active: selectedCategory === cat }"
        @click="selectedCategory = cat"
      >
        {{ getCategoryIcon(cat) }} {{ getCategoryLabel(cat) }}
      </button>
    </div>

    <!-- 搜索框 -->
    <div class="search-box">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索技能..."
        class="search-input"
      />
    </div>

    <!-- 技能列表 -->
    <div class="skill-grid">
      <div
        v-for="skill in filteredSkills"
        :key="skill.id"
        class="skill-card"
        :class="{ selected: selectedSkills.includes(skill.id) }"
        @click="toggleSkill(skill.id)"
      >
        <div class="skill-icon">{{ skill.icon }}</div>
        <div class="skill-info">
          <div class="skill-name">{{ skill.name }}</div>
          <div class="skill-desc">{{ skill.description }}</div>
          <div class="skill-meta">
            <span class="skill-category">{{ skill.category }}</span>
          </div>
        </div>
        <div class="skill-toggle">
          <input
            type="checkbox"
            :checked="selectedSkills.includes(skill.id)"
            @click.stop
            @change="toggleSkill(skill.id)"
          />
        </div>
      </div>

      <!-- 无技能提示 -->
      <div v-if="filteredSkills.length === 0" class="empty-state">
        <span>暂无技能</span>
      </div>
    </div>

    <!-- 技能配置 -->
    <div v-if="selectedSkills.length" class="skill-config">
      <h4 class="config-title">技能配置</h4>

      <div v-for="skillId in selectedSkills" :key="skillId" class="config-item">
        <div class="config-header">
          <span class="config-icon">{{ getSkillIcon(skillId) }}</span>
          <span class="config-name">{{ getSkillName(skillId) }}</span>
        </div>

        <div class="config-form">
          <div class="config-field">
            <label>强度</label>
            <select v-model="skillParams[skillId].intensity">
              <option value="subtle">轻微</option>
              <option value="moderate">中等</option>
              <option value="strong">强烈</option>
            </select>
          </div>

          <div class="config-field">
            <label>
              <input type="checkbox" v-model="skillParams[skillId].preserve_original" />
              保留原文
            </label>
          </div>
        </div>
      </div>
    </div>

    <!-- 执行按钮 -->
    <div v-if="selectedSkills.length" class="skill-actions">
      <button class="btn-cancel" @click="emit('cancel')">取消</button>
      <button class="btn-apply" @click="handleApply" :disabled="!canApply">
        应用技能
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { listSkills, getSkillCategories, executeSkill, type SkillInfo, type SkillExecuteResponse } from '@/api/skill'

interface Props {
  projectId: string
  chapterNumber: number
  chapterContent: string
  chapterInfo?: Record<string, unknown>
  characterProfiles?: Record<string, unknown>[]
  worldSettings?: Record<string, unknown>
  previousSummary?: string
  outline?: Record<string, unknown>
  userId?: number
}

const props = withDefaults(defineProps<Props>(), {
  chapterInfo: () => ({}),
  characterProfiles: () => [],
  worldSettings: () => ({}),
  previousSummary: '',
  outline: () => ({}),
  userId: 0
})

const emit = defineEmits<{
  (e: 'apply', results: SkillExecuteResponse[]): void
  (e: 'cancel'): void
  (e: 'error', error: string): void
}>()

// 状态
const skills = ref<SkillInfo[]>([])
const categories = ref<string[]>([])
const selectedCategory = ref<string | null>(null)
const searchQuery = ref('')
const selectedSkills = ref<string[]>([])
const skillParams = ref<Record<string, { intensity: string; preserve_original: boolean }>>({})

// 分类映射
const categoryLabels: Record<string, string> = {
  polish: '润色',
  dialogue: '对话',
  rhythm: '节奏',
  emotion: '情绪',
  consistency: '一致性',
  foreshadowing: '伏笔',
  structure: '结构',
  style: '风格'
}

const categoryIcons: Record<string, string> = {
  polish: '✍️',
  dialogue: '💬',
  rhythm: '🎵',
  emotion: '💖',
  consistency: '🔍',
  foreshadowing: '🎯',
  structure: '📐',
  style: '🎨'
}

function getCategoryLabel(cat: string): string {
  return categoryLabels[cat] || cat
}

function getCategoryIcon(cat: string): string {
  return categoryIcons[cat] || '✨'
}

function getSkillIcon(skillId: string): string {
  const skill = skills.value.find(s => s.id === skillId)
  return skill?.icon || '✨'
}

function getSkillName(skillId: string): string {
  const skill = skills.value.find(s => s.id === skillId)
  return skill?.name || skillId
}

// 加载技能列表
onMounted(async () => {
  try {
    const [skillsData, categoriesData] = await Promise.all([
      listSkills(),
      getSkillCategories()
    ])
    skills.value = skillsData
    categories.value = categoriesData
  } catch (e) {
    console.error('Failed to load skills:', e)
  }
})

// 过滤技能
const filteredSkills = computed(() => {
  let result = skills.value

  if (selectedCategory.value) {
    result = result.filter(s => s.category === selectedCategory.value)
  }

  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(s =>
      s.name.toLowerCase().includes(query) ||
      s.description.toLowerCase().includes(query)
    )
  }

  return result
})

// 切换技能选择
function toggleSkill(skillId: string) {
  const index = selectedSkills.value.indexOf(skillId)

  if (index > -1) {
    selectedSkills.value.splice(index, 1)
    delete skillParams.value[skillId]
  } else {
    selectedSkills.value.push(skillId)
    const skill = skills.value.find(s => s.id === skillId)
    skillParams.value[skillId] = {
      intensity: skill?.config?.default || 'moderate',
      preserve_original: skill?.config?.preserve_original ?? true
    }
  }
}

// 能否应用
const canApply = computed(() => {
  return selectedSkills.value.length > 0
})

// 应用技能
async function handleApply() {
  if (!canApply.value) return

  const results: SkillExecuteResponse[] = []

  for (const skillId of selectedSkills.value) {
    try {
      const response = await executeSkill(skillId, {
        project_id: props.projectId,
        chapter_number: props.chapterNumber,
        content: props.chapterContent,
        chapter_info: props.chapterInfo,
        character_profiles: props.characterProfiles,
        world_settings: props.worldSettings,
        previous_summary: props.previousSummary,
        outline: props.outline,
        params: {
          intensity: skillParams.value[skillId].intensity,
          preserve_original: skillParams.value[skillId].preserve_original
        },
        user_id: props.userId
      })
      results.push(response)
    } catch (e) {
      console.error(`Failed to execute skill ${skillId}:`, e)
      emit('error', `技能执行失败: ${getSkillName(skillId)}`)
    }
  }

  emit('apply', results)
}
</script>

<style scoped>
.skill-selector {
  max-width: 800px;
  margin: 0 auto;
  overflow-x: hidden;
  position: relative;
}

.selector-header {
  padding: 20px 0 16px;
  margin-bottom: 4px;
  border-bottom: 1px solid var(--md-outline-variant, #e8e8e8);
}

.selector-title {
  margin: 0 0 4px 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--md-on-surface, #1a1a1a);
  letter-spacing: 0.02em;
}

.selector-subtitle {
  margin: 0;
  font-size: 0.8125rem;
  color: var(--md-on-surface-variant, #666);
  line-height: 1.4;
}

.category-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  padding: 4px 0 0;
  align-items: center;
}

.category-tab {
  padding: 8px 14px;
  border: 1px solid var(--md-outline-variant, #e0e0e0);
  border-radius: 20px;
  background: var(--md-surface-container-lowest, #fafafa);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
  line-height: 1.25;
}

.category-tab:hover {
  border-color: var(--md-primary, #1976d2);
}

.category-tab.active {
  background: var(--md-primary, #1976d2);
  color: white;
  border-color: var(--md-primary, #1976d2);
}

.search-box {
  margin-bottom: 20px;
}

.search-input {
  width: 100%;
  padding: 10px 16px;
  border: 1px solid var(--md-outline-variant, #e0e0e0);
  border-radius: 8px;
  font-size: 14px;
}

.search-input:focus {
  outline: none;
  border-color: var(--md-primary, #1976d2);
}

.skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.skill-card {
  padding: 16px;
  background: white;
  border: 2px solid var(--md-outline-variant, #e0e0e0);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.skill-card:hover {
  border-color: var(--md-primary, #1976d2);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.skill-card.selected {
  border-color: var(--md-primary, #1976d2);
  background: var(--md-primary-container, #e3f2fd);
}

.skill-icon {
  font-size: 28px;
  flex-shrink: 0;
}

.skill-info {
  flex: 1;
  min-width: 0;
}

.skill-name {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
}

.skill-desc {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
  margin-bottom: 8px;
  line-height: 1.4;
}

.skill-meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
}

.skill-category {
  background: var(--md-surface-container-high, #f5f5f5);
  padding: 2px 8px;
  border-radius: 4px;
}

.skill-toggle {
  flex-shrink: 0;
  padding-top: 4px;
}

.skill-toggle input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px;
  color: var(--md-on-surface-variant, #666);
}

.skill-config {
  background: var(--md-surface-container-lowest, #fafafa);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
}

.config-title {
  margin: 0 0 16px 0;
  font-size: 1rem;
  font-weight: 600;
}

.config-item {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--md-outline-variant, #e8e8e8);
}

.config-item:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.config-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.config-icon {
  font-size: 20px;
}

.config-name {
  font-weight: 500;
}

.config-form {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.config-field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.config-field label {
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.config-field select {
  padding: 6px 10px;
  border: 1px solid var(--md-outline-variant, #e0e0e0);
  border-radius: 6px;
  font-size: 13px;
  background: white;
}

.skill-actions {
  display: flex;
  gap: 12px;
}

.btn-cancel,
.btn-apply {
  flex: 1;
  padding: 12px 20px;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}

.btn-cancel {
  background: white;
  border: 1px solid var(--md-outline-variant, #e0e0e0);
}

.btn-apply {
  background: var(--md-primary, #1976d2);
  color: white;
  border: none;
}

.btn-apply:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-apply:hover:not(:disabled) {
  opacity: 0.9;
}
</style>

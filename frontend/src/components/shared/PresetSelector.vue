<!-- AIMETA P=预设选择器_写作预设选择|R=预设选择_可视化说明|NR=|E=PresetSelector|X=ui|A=预设组件|D=vue|S=dom -->
<template>
  <div class="preset-selector">
    <!-- 预设级别标签 -->
    <div class="level-tabs">
      <button 
        v-for="level in levels" 
        :key="level.id"
        :class="['level-tab', { active: currentLevel === level.id }]"
        @click="currentLevel = level.id"
      >
        <span class="level-icon">{{ level.icon }}</span>
        <span class="level-name">{{ level.name }}</span>
      </button>
    </div>

    <!-- 预设卡片列表 -->
    <div class="preset-cards">
      <div 
        v-for="preset in currentPresets" 
        :key="preset.name"
        :class="['preset-card', { selected: modelValue === preset.name }]"
        @click="selectPreset(preset.name)"
      >
        <div class="preset-header">
          <span class="preset-name">{{ preset.name }}</span>
          <span class="preset-time">{{ preset.estimated_time }}</span>
        </div>
        <p class="preset-description">{{ preset.description }}</p>
        
        <!-- 特点标签 -->
        <div class="preset-features">
          <span 
            v-for="feature in preset.features" 
            :key="feature"
            class="feature-tag"
          >
            {{ feature }}
          </span>
        </div>
        
        <!-- 适用场景 -->
        <div class="preset-suitable">
          <span class="suitable-label">适用：</span>
          <span 
            v-for="scene in preset.suitable_for.slice(0, 2)" 
            :key="scene"
            class="scene-tag"
          >
            {{ scene }}
          </span>
        </div>
      </div>
    </div>

    <!-- 当前选择显示 -->
    <div class="selected-preset" v-if="modelValue">
      <span class="selected-label">当前选择：</span>
      <span class="selected-name">{{ selectedPresetInfo?.name }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface PresetInfo {
  name: string
  level: string
  name_cn: string
  description: string
  features: string[]
  suitable_for: string[]
  estimated_time: string
}

interface Props {
  modelValue?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

// 预设级别
const levels = [
  { id: 'beginner', name: '新手', icon: '🌱' },
  { id: 'intermediate', name: '进阶', icon: '🚀' },
  { id: 'advanced', name: '高阶', icon: '⚡' },
]

const currentLevel = ref('beginner')

// 预设数据
const allPresets: PresetInfo[] = [
  // 初级
  { name: 'quick', level: 'beginner', name_cn: '快速生成', description: '快速生成初稿，适合灵感记录', features: ['生成速度快', '基础质量', '适合初稿'], suitable_for: ['快速记录灵感', '大纲扩展'], estimated_time: '30秒' },
  { name: 'quality', level: 'beginner', name_cn: '质量优先', description: '注重生成质量，适合正式写作', features: ['质量优先', '多维评审', '自动修订'], suitable_for: ['正式写作', '重要章节'], estimated_time: '2-3分钟' },
  { name: 'fast', level: 'beginner', name_cn: '极速模式', description: '最快速度生成，适合快速迭代', features: ['极速生成', '轻量处理'], suitable_for: ['快速迭代', '大纲测试'], estimated_time: '10秒' },
  
  // 中级
  { name: 'style', level: 'intermediate', name_cn: '文笔打磨', description: '强化文笔和风格，适合进阶作者', features: ['文笔优化', '风格强化', '人味增强'], suitable_for: ['追求文笔', '风格化写作'], estimated_time: '3-4分钟' },
  { name: '爽点', level: 'intermediate', name_cn: '爽点强化', description: '强化爽点和情感共鸣', features: ['爽点增强', '情感共鸣', '节奏把控'], suitable_for: ['高潮章节', '打脸情节'], estimated_time: '2-3分钟' },
  
  // 高级
  { name: 'platinum', level: 'advanced', name_cn: '铂金模式', description: '完整功能，适合高要求写作', features: ['六维评审', '自动修订', '伏笔追踪'], suitable_for: ['精品创作', '长篇连载'], estimated_time: '5-10分钟' },
]

// 当前级别的预设
const currentPresets = computed(() => {
  return allPresets.filter(p => p.level === currentLevel.value)
})

// 选中的预设信息
const selectedPresetInfo = computed(() => {
  return allPresets.find(p => p.name === props.modelValue)
})

function selectPreset(name: string) {
  emit('update:modelValue', name)
}
</script>

<style scoped>
.preset-selector {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.level-tabs {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--md-outline-variant, #e0e0e0);
  padding-bottom: 8px;
}

.level-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 20px;
  transition: all 0.2s;
  color: var(--md-on-surface-variant, #666);
}

.level-tab.active {
  background: var(--md-primary-container, #e3f2fd);
  color: var(--md-primary, #1976d2);
}

.level-icon {
  font-size: 16px;
}

.preset-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.preset-card {
  padding: 12px;
  border: 1px solid var(--md-outline-variant, #e0e0e0);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--md-surface, #fff);
}

.preset-card:hover {
  border-color: var(--md-primary, #1976d2);
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.preset-card.selected {
  border-color: var(--md-primary, #1976d2);
  background: var(--md-primary-container, #e3f2fd);
}

.preset-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.preset-name {
  font-weight: 600;
  font-size: 14px;
}

.preset-time {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
  background: var(--md-surface-container, #f5f5f5);
  padding: 2px 8px;
  border-radius: 10px;
}

.preset-description {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
  margin-bottom: 8px;
  line-height: 1.4;
}

.preset-features {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

.feature-tag {
  font-size: 10px;
  padding: 2px 6px;
  background: var(--md-secondary-container, #f3e5f5);
  color: var(--md-secondary, #7b1fa2);
  border-radius: 4px;
}

.preset-suitable {
  font-size: 11px;
  color: var(--md-on-surface-variant, #666);
}

.suitable-label {
  font-weight: 500;
}

.scene-tag {
  margin-right: 4px;
  color: var(--md-tertiary, #00897b);
}

.selected-preset {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--md-surface-container-low, #fafafa);
  border-radius: 8px;
  font-size: 14px;
}

.selected-label {
  color: var(--md-on-surface-variant, #666);
}

.selected-name {
  font-weight: 600;
  color: var(--md-primary, #1976d2);
}
</style>

<!-- AIMETA P=生成模式选择器|R=模式选择_档位门控|NR=|E=PresetSelector|X=ui|A=模式组件|D=vue|S=dom -->
<template>
  <div class="preset-selector">
    <div class="preset-header">
      <h3 class="preset-title">选择生成模式</h3>
      <p class="preset-subtitle">不同模式适合不同创作需求</p>
    </div>

    <!-- 模式卡片列表 -->
    <div class="preset-cards">
      <div
        v-for="preset in presets"
        :key="preset.value"
        :class="['preset-card', {
          selected: modelValue === preset.value,
          locked: preset.requiresTier && !canUsePreset(preset.requiresTier)
        }]"
        @click="selectPreset(preset)"
      >
        <!-- 档位徽章 -->
        <div v-if="preset.requiresTier" class="tier-badge" :class="getTierClass(preset.requiresTier)">
          {{ getTierLabel(preset.requiresTier) }}
        </div>

        <!-- 锁定遮罩 -->
        <div v-if="preset.requiresTier && !canUsePreset(preset.requiresTier)" class="lock-overlay">
          <svg class="lock-icon" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
          </svg>
          <span class="lock-text">需要{{ getTierLabel(preset.requiresTier) }}</span>
        </div>

        <div class="preset-icon">{{ preset.icon }}</div>

        <div class="preset-info">
          <div class="preset-name-row">
            <span class="preset-name">{{ preset.name }}</span>
            <span class="preset-time">{{ preset.time }}</span>
          </div>
          <p class="preset-description">{{ preset.description }}</p>
        </div>

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
      </div>
    </div>

    <!-- 当前选择显示 -->
    <div class="selected-info" v-if="modelValue">
      <span class="info-label">当前模式：</span>
      <span class="info-value">{{ selectedPreset?.name }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useMessage } from 'naive-ui'

interface PresetInfo {
  value: string
  name: string
  icon: string
  description: string
  features: string[]
  time: string
  requiresTier?: 'creator' | 'flagship'  // 需要的最低档位
}

interface Props {
  modelValue?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const authStore = useAuthStore()
const message = useMessage()

// 用户当前档位。后台分配订阅后，重新打开/点击模式时会刷新 /users/me。
const userTier = computed(() => authStore.user?.effective_tier || 'free')

onMounted(() => {
  void authStore.fetchUser()
})

// 三种生成模式（与后端 pipeline_config_service.py 对应）
const presets: PresetInfo[] = [
  {
    value: 'fast',
    name: '快速模式',
    icon: '🌱',
    description: '极速生成，轻量处理，适合快速迭代和大纲测试',
    features: ['极速路径', '轻量处理', '30-60秒'],
    time: '30-60秒',
    // free 用户可用，不设置 requiresTier
  },
  {
    value: 'standard',
    name: '标准模式',
    icon: '🚀',
    description: '六维评审 + 世界观注入 + 文笔打磨，适合日常创作',
    features: ['六维评审', '世界观', '打磨', '3-5分钟'],
    time: '3-5分钟',
    requiresTier: 'creator',  // 创作者会员+
  },
  {
    value: 'premium',
    name: '精品模式',
    icon: '⚡',
    description: '完整流程 + 自我批判 + 读者模拟，适合精品创作',
    features: ['自我批判', '读者模拟', '优化器', '5-10分钟'],
    time: '5-10分钟',
    requiresTier: 'flagship',  // 旗舰会员+
  },
]

// 选中的预设信息
const selectedPreset = computed(() => {
  return presets.find(p => p.value === props.modelValue)
})

// 检查用户是否可以使用某个档位的功能
function canUsePreset(requiredTier: 'creator' | 'flagship'): boolean {
  const tierLevels = { free: 0, creator: 1, flagship: 2 }
  const userLevel = tierLevels[userTier.value as keyof typeof tierLevels] || 0
  const requiredLevel = tierLevels[requiredTier]
  return userLevel >= requiredLevel
}

// 获取档位标签
function getTierLabel(tier: 'creator' | 'flagship'): string {
  return tier === 'creator' ? '创作者会员' : '旗舰会员'
}

// 获取档位样式类
function getTierClass(tier: 'creator' | 'flagship'): string {
  return tier === 'creator' ? 'tier-creator' : 'tier-flagship'
}

async function selectPreset(preset: PresetInfo) {
  // 检查档位权限
  if (preset.requiresTier && !canUsePreset(preset.requiresTier)) {
    await authStore.fetchUser()
  }

  if (preset.requiresTier && !canUsePreset(preset.requiresTier)) {
    message.warning(`${preset.name}需要${getTierLabel(preset.requiresTier)}，请升级后使用`)
    return
  }

  emit('update:modelValue', preset.value)
}
</script>

<style scoped>
.preset-selector {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.preset-header {
  text-align: center;
}

.preset-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--md-on-surface, #FFFFFF);
  margin-bottom: 8px;
}

.preset-subtitle {
  font-size: 13px;
  color: var(--md-on-surface-variant, #888);
}

.preset-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.preset-card {
  position: relative;
  padding: 20px;
  border: 2px solid var(--md-outline-variant, #2A2A2A);
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--md-surface-container-low, #141414);
  overflow: hidden;
}

.preset-card:hover:not(.locked) {
  border-color: var(--md-primary, #FFE500);
  box-shadow: 0 4px 16px rgba(255, 229, 0, 0.12);
  transform: translateY(-2px);
}

.preset-card.selected {
  border-color: var(--md-primary, #FFE500);
  background: var(--md-primary-container, #2A2600);
}

.preset-card.locked {
  opacity: 0.6;
  cursor: not-allowed;
}

.tier-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  font-size: 10px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tier-badge.tier-creator {
  background: rgba(255, 229, 0, 0.15);
  color: #FFE500;
  border: 1px solid rgba(255, 229, 0, 0.3);
}

.tier-badge.tier-flagship {
  background: rgba(192, 132, 252, 0.15);
  color: #C084FC;
  border: 1px solid rgba(192, 132, 252, 0.3);
}

.lock-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: rgba(10, 10, 10, 0.85);
  backdrop-filter: blur(4px);
  z-index: 10;
}

.lock-icon {
  width: 32px;
  height: 32px;
  color: var(--md-on-surface-variant, #888);
}

.lock-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--md-on-surface-variant, #888);
}

.preset-icon {
  font-size: 32px;
  margin-bottom: 12px;
}

.preset-info {
  margin-bottom: 12px;
}

.preset-name-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.preset-name {
  font-weight: 600;
  font-size: 16px;
  color: var(--md-on-surface, #FFFFFF);
}

.preset-time {
  font-size: 11px;
  color: var(--md-on-surface-variant, #888);
  background: var(--md-surface-container-high, #242424);
  padding: 3px 8px;
  border-radius: 10px;
}

.preset-description {
  font-size: 13px;
  color: var(--md-on-surface-variant, #AAAAAA);
  line-height: 1.5;
}

.preset-features {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.feature-tag {
  font-size: 11px;
  padding: 4px 8px;
  background: var(--md-secondary-container, #1C1C1C);
  color: var(--md-on-secondary-container, #CCCCCC);
  border-radius: 6px;
  border: 1px solid var(--md-outline-variant, #2A2A2A);
}

.selected-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  background: var(--md-surface-container, #1C1C1C);
  border-radius: 12px;
  font-size: 14px;
}

.info-label {
  color: var(--md-on-surface-variant, #888);
}

.info-value {
  font-weight: 600;
  color: var(--md-primary, #FFE500);
}
</style>

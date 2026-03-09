<!-- AIMETA P=用户友好错误提示组件|R=错误展示_操作建议|NR=|E=UserErrorTip|X=ui|A=错误组件|D=vue|S=dom -->
<template>
  <div v-if="error" class="user-error-tip" :class="[`severity-${severity}`]">
    <!-- 错误图标 -->
    <div class="error-icon">
      <span v-if="severity === 'error'">❌</span>
      <span v-else-if="severity === 'warning'">⚠️</span>
      <span v-else>ℹ️</span>
    </div>
    
    <!-- 错误内容 -->
    <div class="error-content">
      <h4 class="error-title">{{ error.title || '出现问题' }}</h4>
      <p class="error-message">{{ error.message }}</p>
      <p v-if="error.suggestion" class="error-suggestion">
        💡 {{ error.suggestion }}
      </p>
    </div>
    
    <!-- 操作按钮 -->
    <div class="error-actions" v-if="error.actions && error.actions.length">
      <button 
        v-for="action in error.actions" 
        :key="action.type"
        class="action-btn"
        :class="getActionBtnClass(action.type)"
        @click="handleAction(action)"
      >
        {{ action.label }}
      </button>
    </div>
    
    <!-- 关闭按钮 -->
    <button v-if="showClose" class="close-btn" @click="$emit('close')">×</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface ErrorAction {
  type: string
  label: string
}

interface UserError {
  title?: string
  message: string
  suggestion?: string
  category?: string
  recoverable?: boolean
  actions?: ErrorAction[]
}

interface Props {
  error: UserError | null
  showClose?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showClose: true
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'action', action: ErrorAction): void
}>()

const severity = computed(() => {
  if (!props.error) return 'info'
  const category = props.error.category
  if (category === 'llm_api' || category === 'network') return 'error'
  if (category === 'parsing' || category === 'config') return 'warning'
  return 'info'
})

function getActionBtnClass(type: string): string {
  const classMap: Record<string, string> = {
    'retry': 'btn-primary',
    'open_settings': 'btn-secondary',
    'change_model': 'btn-secondary',
    'open_blueprint': 'btn-secondary',
    'contact_support': 'btn-outline',
  }
  return classMap[type] || 'btn-primary'
}

function handleAction(action: ErrorAction) {
  emit('action', action)
}
</script>

<style scoped>
.user-error-tip {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: var(--md-surface-container-low, #fafafa);
  border: 1px solid var(--md-outline-variant, #e0e0e0);
}

.user-error-tip.severity-error {
  background: var(--md-error-container, #ffebee);
  border-color: var(--md-error, #f44336);
}

.user-error-tip.severity-warning {
  background: var(--md-tertiary-container, #fff8e1);
  border-color: var(--md-tertiary, #ff9800);
}

.user-error-tip.severity-info {
  background: var(--md-primary-container, #e3f2fd);
  border-color: var(--md-primary, #2196f3);
}

.error-icon {
  font-size: 24px;
  line-height: 1;
}

.error-content {
  flex: 1;
}

.error-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 4px 0;
  color: var(--md-on-surface, #333);
}

.error-message {
  font-size: 13px;
  margin: 0 0 8px 0;
  color: var(--md-on-surface-variant, #666);
  line-height: 1.4;
}

.error-suggestion {
  font-size: 12px;
  margin: 0;
  color: var(--md-on-surface, #444);
  background: rgba(255,255,255,0.5);
  padding: 8px;
  border-radius: 6px;
}

.error-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-btn {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.btn-primary {
  background: var(--md-primary, #1976d2);
  color: white;
  border: none;
}

.btn-primary:hover {
  background: var(--md-primary, #1565c0);
}

.btn-secondary {
  background: var(--md-secondary-container, #f3e5f5);
  color: var(--md-secondary, #7b1fa2);
  border: none;
}

.btn-secondary:hover {
  background: var(--md-secondary, #7b1fa2);
  color: white;
}

.btn-outline {
  background: transparent;
  border: 1px solid var(--md-outline, #999);
  color: var(--md-on-surface, #666);
}

.btn-outline:hover {
  background: var(--md-surface-container, #f5f5f5);
}

.close-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
  color: var(--md-on-surface-variant, #999);
  border-radius: 50%;
}

.close-btn:hover {
  background: rgba(0,0,0,0.05);
}
</style>

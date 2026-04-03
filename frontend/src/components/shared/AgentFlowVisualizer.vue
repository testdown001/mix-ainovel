<!-- AIMETA P=Agent协作可视化组件|R=Agent流程展示_实时状态|NR=|E=AgentFlowVisualizer|X=ui|A=Agent可视化|D=vue|S=dom -->
<template>
  <div class="agent-flow-visualizer">
    <!-- Agent 流程图 -->
    <div class="agent-flow">
      <div 
        v-for="(agent, index) in agents" 
        :key="agent.id"
        class="agent-node"
        :class="[agent.status, { active: isAgentActive(agent.id) }]"
      >
        <!-- 连接线 -->
        <div v-if="index > 0" class="connector-line" :class="{ active: isConnectorActive(index) }"></div>
        
        <!-- Agent 节点 -->
        <div class="node-content">
          <div class="agent-icon">{{ agent.icon }}</div>
          <div class="agent-info">
            <span class="agent-name">{{ agent.name }}</span>
            <span class="agent-role">{{ agent.role }}</span>
          </div>
          <div class="agent-status">
            <span v-if="agent.status === 'completed'" class="status-badge completed">✅</span>
            <span v-else-if="agent.status === 'running'" class="status-badge running">🔄</span>
            <span v-else-if="agent.status === 'failed'" class="status-badge failed">❌</span>
            <span v-else class="status-badge pending">⏳</span>
          </div>
        </div>
        
        <!-- Agent 日志/输出 -->
        <div v-if="agent.logs?.length" :ref="(el) => setLogRef(agent.id, el)" class="agent-logs">
          <div
            v-for="(log, logIdx) in agent.logs"
            :key="logIdx"
            class="log-item"
            :class="log.type"
          >
            <span class="log-time">{{ log.time }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 控制面板 -->
    <div class="control-panel" v-if="isRunning">
      <button class="btn-control" @click="$emit('pause')">
        ⏸ 暂停
      </button>
      <button class="btn-control" @click="$emit('stop')">
        ⏹ 终止
      </button>
    </div>
    
    <!-- 完成面板 -->
    <div v-if="isCompleted" class="completion-panel">
      <div class="completion-summary">
        <span class="completion-icon">🎉</span>
        <span class="completion-text">Agent 协作完成</span>
      </div>
      <div class="completion-stats">
        <div class="stat">
          <span class="stat-label">总耗时</span>
          <span class="stat-value">{{ formatTime(totalTime) }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">调用 LLM</span>
          <span class="stat-value">{{ totalLLMCalls }} 次</span>
        </div>
        <div v-if="totalToolCalls > 0" class="stat">
          <span class="stat-label">工具调用</span>
          <span class="stat-value">{{ totalToolCalls }} 次</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

interface AgentLog {
  time: string
  message: string
  type: 'info' | 'warning' | 'error' | 'success'
}

interface AgentNode {
  id: string
  name: string
  role: string
  icon: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  logs?: AgentLog[]
}

interface Props {
  agents?: AgentNode[]
  currentAgentId?: string | null
  isRunning?: boolean
  isCompleted?: boolean
  totalTime?: number
  totalLLMCalls?: number
  totalToolCalls?: number
}

const props = withDefaults(defineProps<Props>(), {
  agents: () => [
    { id: 'taizi', name: '太子省', role: '需求分拣', icon: '👶', status: 'pending' },
    { id: 'zhongshu', name: '中书省', role: '规划中枢', icon: '📜', status: 'pending' },
    { id: 'shangshu', name: '尚书省', role: '调度协调', icon: '🏛️', status: 'pending' },
    { id: 'bingbu', name: '兵部', role: '章节生成', icon: '⚔️', status: 'pending' },
    { id: 'libu', name: '吏部', role: '角色管理', icon: '📋', status: 'pending' },
    { id: 'hubu', name: '户部', role: '技能系统', icon: '🎯', status: 'pending' },
    { id: 'menxia', name: '门下省', role: '质量审核', icon: '🔍', status: 'pending' },
  ],
  currentAgentId: null,
  isRunning: false,
  isCompleted: false,
  totalTime: 0,
  totalLLMCalls: 0,
  totalToolCalls: 0,
})

defineEmits<{
  (e: 'pause'): void
  (e: 'stop'): void
}>()

const currentIndex = computed(() => {
  if (!props.currentAgentId) return -1
  return props.agents.findIndex(a => a.id === props.currentAgentId)
})

function isAgentActive(agentId: string): boolean {
  return props.currentAgentId === agentId
}

function isConnectorActive(index: number): boolean {
  return index <= currentIndex.value
}

// 日志容器 ref 管理 + 自动滚动
const logRefs: Record<string, HTMLElement | null> = {}
function setLogRef(agentId: string, el: any) {
  logRefs[agentId] = el as HTMLElement | null
}

watch(
  () => props.agents.map(a => a.logs?.length ?? 0),
  () => {
    nextTick(() => {
      for (const agent of props.agents) {
        const el = logRefs[agent.id]
        if (el) el.scrollTop = el.scrollHeight
      }
    })
  },
  { deep: true }
)

function formatTime(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}
</script>

<style scoped>
.agent-flow-visualizer {
  background: var(--md-surface, #fff);
  border: 1px solid var(--md-outline-variant, #e0e0e0);
  border-radius: 12px;
  overflow: hidden;
}

.agent-flow {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-node {
  position: relative;
  padding-left: 20px;
}

.connector-line {
  position: absolute;
  left: 24px;
  top: -12px;
  width: 2px;
  height: 12px;
  background: var(--md-outline-variant, #e0e0e0);
}

.connector-line.active {
  background: var(--md-primary, #1976d2);
}

.node-content {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 10px;
  background: var(--md-surface-container-low, #fafafa);
  transition: all 0.3s;
}

.agent-node.active .node-content {
  background: var(--md-primary-container, #e3f2fd);
  box-shadow: 0 0 0 2px var(--md-primary, #1976d2);
}

.agent-node.completed .node-content {
  background: var(--md-tertiary-container, #e8f5e9);
}

.agent-node.failed .node-content {
  background: var(--md-error-container, #ffebee);
}

.agent-icon {
  font-size: 24px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--md-surface, #fff);
  border-radius: 50%;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.agent-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.agent-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--md-on-surface, #333);
}

.agent-role {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
}

.agent-status {
  display: flex;
  align-items: center;
}

.status-badge {
  font-size: 18px;
}

.status-badge.running {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.agent-logs {
  margin-top: 8px;
  margin-left: 52px;
  padding: 8px;
  background: var(--md-surface-container, #f5f5f5);
  border-radius: 8px;
  max-height: 120px;
  overflow-y: auto;
}

.log-item {
  display: flex;
  gap: 8px;
  font-size: 11px;
  padding: 4px 0;
  border-bottom: 1px solid var(--md-outline-variant, #eee);
}

.log-item:last-child {
  border-bottom: none;
}

.log-time {
  color: var(--md-on-surface-variant, #999);
  white-space: nowrap;
}

.log-message {
  color: var(--md-on-surface, #666);
}

.log-item.success .log-message {
  color: var(--md-tertiary, #4caf50);
}

.log-item.error .log-message {
  color: var(--md-error, #f44336);
}

.log-item.warning .log-message {
  color: var(--md-tertiary, #ff9800);
}

.control-panel {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: var(--md-surface-container, #f5f5f5);
  border-top: 1px solid var(--md-outline-variant, #e0e0e0);
}

.btn-control {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--md-surface, #fff);
  border: 1px solid var(--md-outline-variant, #e0e0e0);
}

.btn-control:hover {
  background: var(--md-surface-container-high, #eee);
}

.completion-panel {
  padding: 20px;
  background: var(--md-tertiary-container, #e8f5e9);
  border-top: 1px solid var(--md-outline-variant, #e0e0e0);
}

.completion-summary {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 16px;
}

.completion-icon {
  font-size: 24px;
}

.completion-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--md-tertiary, #2e7d32);
}

.completion-stats {
  display: flex;
  justify-content: center;
  gap: 32px;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat-label {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--md-primary, #1976d2);
}
</style>

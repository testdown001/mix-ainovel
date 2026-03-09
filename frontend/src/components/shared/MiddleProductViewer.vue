<!-- AIMETA P=中间产物预览组件|R=Mission_RAG_上下文预览|NR=|E=MiddleProductViewer|X=ui|A=预览组件|D=vue|S=dom -->
<template>
  <div class="middle-product-viewer">
    <!-- Tab 切换 -->
    <div class="viewer-tabs">
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        :class="['tab-btn', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span class="tab-label">{{ tab.label }}</span>
        <span v-if="tab.badge" class="tab-badge">{{ tab.badge }}</span>
      </button>
    </div>

    <!-- 内容区域 -->
    <div class="viewer-content">
      <!-- Mission 预览 -->
      <div v-if="activeTab === 'mission'" class="content-panel">
        <div class="panel-header">
          <h4>📜 本章 Mission</h4>
          <span class="panel-hint">AI 理解到的写作目标</span>
        </div>
        <div v-if="missionData" class="panel-body">
          <div class="info-section">
            <span class="info-label">核心任务：</span>
            <span class="info-value">{{ missionData.core_task || '未设置' }}</span>
          </div>
          <div class="info-section">
            <span class="info-label"> POV 角色：</span>
            <span class="info-value">{{ missionData.pov_character || '未设置' }}</span>
          </div>
          <div class="info-section">
            <span class="info-label">章节类型：</span>
            <span class="info-value">{{ missionData.chapter_type || '普通章' }}</span>
          </div>
          <div v-if="missionData.forbidden" class="info-section">
            <span class="info-label">⚠️ 禁止出现：</span>
            <span class="info-value warning">{{ missionData.forbidden.join(', ') }}</span>
          </div>
          <div v-if="missionData.allowed_new_characters?.length" class="info-section">
            <span class="info-label">✅ 本章可新登场：</span>
            <span class="info-value success">{{ missionData.allowed_new_characters.join(', ') }}</span>
          </div>
        </div>
        <div v-else class="panel-empty">
          <p>暂无 Mission 数据</p>
        </div>
      </div>

      <!-- RAG 检索结果 -->
      <div v-if="activeTab === 'rag'" class="content-panel">
        <div class="panel-header">
          <h4>📚 RAG 检索结果</h4>
          <span class="panel-hint">从已写内容中检索的相关段落</span>
        </div>
        <div v-if="ragData && ragData.chunks?.length" class="panel-body">
          <div class="rag-stats">
            <span class="stat-item">
              <span class="stat-label">检索到</span>
              <span class="stat-value">{{ ragData.chunks.length }}</span>
              <span class="stat-label">个相关片段</span>
            </span>
            <span class="stat-item">
              <span class="stat-label">章节摘要</span>
              <span class="stat-value">{{ ragData.summaries?.length || 0 }}</span>
              <span class="stat-label">条</span>
            </span>
          </div>
          <div class="rag-chunks">
            <div
              v-for="(chunk, idx) in ragData.chunks.slice(0, 5)"
              :key="idx"
              class="rag-chunk"
            >
              <div class="chunk-header">
                <span class="chunk-title">片段 {{ idx + 1 }}</span>
                <span v-if="typeof chunk === 'object' && chunk.score" class="chunk-score">相似度: {{ (chunk.score * 100).toFixed(1) }}%</span>
              </div>
              <p class="chunk-content">{{ typeof chunk === 'string' ? chunk : chunk.content }}</p>
            </div>
          </div>
        </div>
        <div v-else class="panel-empty">
          <p>暂无检索结果</p>
          <p class="empty-hint">可能是因为尚未写入足够的内容，或检索关键词不匹配</p>
        </div>
      </div>

      <!-- 上下文预览 -->
      <div v-if="activeTab === 'context'" class="content-panel">
        <div class="panel-header">
          <h4>🎯 上下文</h4>
          <span class="panel-hint">生成时使用的上下文信息</span>
        </div>
        <div v-if="contextData" class="panel-body">
          <div class="info-section">
            <span class="info-label">世界观：</span>
            <span class="info-value">{{ contextData.world || '默认' }}</span>
          </div>
          <div class="info-section">
            <span class="info-label">修炼体系：</span>
            <span class="info-value">{{ contextData.cultivation_system || '无' }}</span>
          </div>
          <div class="info-section">
            <span class="info-label">当前修为：</span>
            <span class="info-value">{{ contextData.current_realm || '未设定' }}</span>
          </div>
          <div v-if="contextData.recent_events?.length" class="info-section">
            <span class="info-label">近期事件：</span>
            <ul class="event-list">
              <li v-for="(event, idx) in contextData.recent_events" :key="idx">
                {{ event }}
              </li>
            </ul>
          </div>
        </div>
        <div v-else class="panel-empty">
          <p>暂无上下文数据</p>
        </div>
      </div>

      <!-- 伏笔预览 -->
      <div v-if="activeTab === 'foreshadowing'" class="content-panel">
        <div class="panel-header">
          <h4>🎭 伏笔追踪</h4>
          <span class="panel-hint">需要关注和回收的伏笔</span>
        </div>
        <div v-if="foreshadowingData" class="panel-body">
          <!-- 结构化数据模式 -->
          <template v-if="foreshadowingData.should_resolve || foreshadowingData.should_plant">
            <div class="foreshadowing-stats">
              <span class="stat-item resolve">
                <span class="stat-value">{{ foreshadowingData.should_resolve?.length || 0 }}</span>
                <span class="stat-label">待回收</span>
              </span>
              <span class="stat-item plant">
                <span class="stat-value">{{ foreshadowingData.should_plant?.length || 0 }}</span>
                <span class="stat-label">待埋下</span>
              </span>
              <span class="stat-item total">
                <span class="stat-value">{{ foreshadowingData.total_unresolved || 0 }}</span>
                <span class="stat-label">总计未回收</span>
              </span>
            </div>
            <div v-if="foreshadowingData.should_resolve?.length" class="foreshadowing-list">
              <h5>⚡ 本章应回收</h5>
              <div
                v-for="fs in foreshadowingData.should_resolve"
                :key="fs.id"
                class="foreshadowing-item"
                :class="{ urgent: fs.urgency === 'high' }"
              >
                <span class="fs-content">{{ fs.content }}</span>
                <span class="fs-origin">源于第{{ fs.chapter_number }}章</span>
              </div>
            </div>
          </template>
          <!-- 文本摘要模式（后端推送 brief 字符串） -->
          <div v-else-if="foreshadowingData.brief" class="foreshadowing-brief">
            <pre class="brief-content">{{ foreshadowingData.brief }}</pre>
          </div>
        </div>
        <div v-else class="panel-empty">
          <p>暂无伏笔数据</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface MissionData {
  core_task?: string
  pov_character?: string
  chapter_type?: string
  forbidden?: string[]
  allowed_new_characters?: string[]
}

interface RagData {
  chunks: Array<string | { content: string; score: number }>
  summaries?: string[]
  stats?: Record<string, any>
}

interface ContextData {
  world?: string
  cultivation_system?: string
  current_realm?: string
  recent_events?: string[]
}

interface ForeshadowingData {
  brief?: string
  should_resolve?: Array<{
    id: number
    content: string
    chapter_number: number
    urgency: string
  }>
  should_plant?: any[]
  total_unresolved?: number
}

interface Props {
  missionData?: MissionData | null
  ragData?: RagData | null
  contextData?: ContextData | null
  foreshadowingData?: ForeshadowingData | null
}

const props = defineProps<Props>()

const activeTab = ref('mission')

const tabs = computed(() => [
  { 
    id: 'mission', 
    label: 'Mission', 
    icon: '📜',
    badge: props.missionData ? '' : null 
  },
  { 
    id: 'rag', 
    label: 'RAG检索', 
    icon: '📚',
    badge: props.ragData?.chunks?.length ? `${props.ragData.chunks.length}` : null 
  },
  { 
    id: 'context', 
    label: '上下文', 
    icon: '🎯' 
  },
  { 
    id: 'foreshadowing', 
    label: '伏笔', 
    icon: '🎭',
    badge: props.foreshadowingData?.total_unresolved ? `${props.foreshadowingData.total_unresolved}` : null 
  },
])
</script>

<style scoped>
.middle-product-viewer {
  border: 1px solid var(--md-outline-variant, #e0e0e0);
  border-radius: 12px;
  overflow: hidden;
  background: var(--md-surface, #fff);
}

.viewer-tabs {
  display: flex;
  background: var(--md-surface-container, #f5f5f5);
  border-bottom: 1px solid var(--md-outline-variant, #e0e0e0);
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  color: var(--md-on-surface-variant, #666);
  transition: all 0.2s;
  position: relative;
}

.tab-btn:hover {
  background: var(--md-surface-container-high, #eee);
}

.tab-btn.active {
  color: var(--md-primary, #1976d2);
  background: var(--md-surface, #fff);
}

.tab-btn.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--md-primary, #1976d2);
}

.tab-icon {
  font-size: 16px;
}

.tab-badge {
  font-size: 10px;
  padding: 2px 6px;
  background: var(--md-error-container, #ffebee);
  color: var(--md-error, #f44336);
  border-radius: 10px;
}

.viewer-content {
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--md-outline-variant, #e0e0e0);
}

.panel-header h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.panel-hint {
  font-size: 11px;
  color: var(--md-on-surface-variant, #999);
}

.panel-body {
  font-size: 13px;
}

.panel-empty {
  text-align: center;
  padding: 24px;
  color: var(--md-on-surface-variant, #999);
}

.empty-hint {
  font-size: 12px;
  margin-top: 8px;
}

.info-section {
  margin-bottom: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.info-label {
  font-weight: 500;
  color: var(--md-on-surface, #333);
}

.info-value {
  color: var(--md-on-surface-variant, #666);
}

.info-value.warning {
  color: var(--md-error, #f44336);
}

.info-value.success {
  color: var(--md-tertiary, #4caf50);
}

.rag-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  padding: 8px;
  background: var(--md-surface-container, #f5f5f5);
  border-radius: 8px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.stat-value {
  font-weight: 600;
  color: var(--md-primary, #1976d2);
}

.rag-chunks {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rag-chunk {
  padding: 8px;
  border: 1px solid var(--md-outline-variant, #e0e0e0);
  border-radius: 8px;
}

.chunk-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}

.chunk-title {
  font-weight: 500;
  font-size: 12px;
}

.chunk-score {
  font-size: 11px;
  color: var(--md-tertiary, #4caf50);
}

.chunk-content {
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.event-list {
  margin: 4px 0 0 0;
  padding-left: 20px;
  font-size: 12px;
  color: var(--md-on-surface-variant, #666);
}

.foreshadowing-stats {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.foreshadowing-stats .stat-item {
  flex-direction: column;
  align-items: center;
  padding: 8px 16px;
  border-radius: 8px;
}

.foreshadowing-stats .stat-item.resolve {
  background: var(--md-error-container, #ffebee);
}

.foreshadowing-stats .stat-item.plant {
  background: var(--md-tertiary-container, #e8f5e9);
}

.foreshadowing-stats .stat-item.total {
  background: var(--md-surface-container, #f5f5f5);
}

.foreshadowing-list h5 {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: var(--md-on-surface, #333);
}

.foreshadowing-item {
  padding: 8px;
  background: var(--md-surface-container-low, #fafafa);
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 12px;
}

.foreshadowing-item.urgent {
  border-left: 3px solid var(--md-error, #f44336);
}

.fs-content {
  display: block;
  margin-bottom: 4px;
}

.fs-origin {
  font-size: 11px;
  color: var(--md-on-surface-variant, #999);
}

.foreshadowing-brief {
  padding: 8px;
  background: var(--md-surface-container-low, #fafafa);
  border-radius: 8px;
}

.brief-content {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--md-on-surface-variant, #666);
  font-family: inherit;
}
</style>

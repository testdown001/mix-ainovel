<!-- AIMETA P=世界观区_世界设定展示|R=世界观信息|NR=不含编辑功能|E=component:WorldSettingSection|X=ui|A=世界观组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="ws-root">
    <!-- Tabs -->
    <div class="ws-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="ws-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >{{ tab.label }}</button>
    </div>

    <!-- Tab: 地理/地点 -->
    <div v-if="activeTab === 'locations'" class="ws-tab-content">
      <div class="ws-grid-main">
        <!-- Featured Location -->
        <div class="ws-featured" v-if="featuredLocation">
          <div class="ws-featured-tags">
            <span class="ws-tag ws-tag--active">ACTIVE REGION</span>
            <span class="ws-tag-icon">📍</span>
          </div>
          <h2 class="ws-featured-title font-display">{{ featuredLocation.title }}</h2>
          <p class="ws-featured-desc">{{ featuredLocation.description }}</p>
          <div class="ws-featured-footer">
            <button v-if="editable" class="ws-link" @click="emitEdit('world_setting.key_locations', '关键地点', worldSetting.key_locations)">
              编辑地点 →
            </button>
          </div>
        </div>
        <div v-else class="ws-featured ws-empty-featured">
          <p class="ws-empty-text">暂无地点设定</p>
          <button v-if="editable" class="ws-link" @click="emitEdit('world_setting.key_locations', '关键地点', worldSetting.key_locations)">+ 添加地点</button>
        </div>

        <!-- AI Panel -->
        <div class="ws-ai-panel">
          <div class="ws-ai-header">
            <span class="ws-ai-dot"></span>
            <span class="ws-ai-label">AI LORE EXPANDER</span>
          </div>
          <h3 class="ws-ai-title">智能世界观补全</h3>
          <p class="ws-ai-sub">基于当前设定，为您生成周边细节：</p>
          <div class="ws-ai-snippet" v-if="featuredLocation">
            "{{ featuredLocation.description?.slice(0, 60) || '探索这个地点的更多细节' }}..."
          </div>
          <button class="ws-ai-btn">生成更多细节</button>
        </div>
      </div>

      <!-- Location Cards Grid -->
      <div class="ws-cards-row" v-if="otherLocations.length > 0">
        <div class="ws-loc-card" v-for="(loc, idx) in otherLocations" :key="idx">
          <div class="ws-loc-card-header">
            <span class="ws-loc-icon">🏛️</span>
            <span class="ws-loc-id">ID: LOC_{{ String(idx + 2).padStart(3, '0') }}</span>
          </div>
          <h4 class="ws-loc-name font-display">{{ loc.title }}</h4>
          <p class="ws-loc-desc">{{ loc.description }}</p>
        </div>
      </div>
    </div>

    <!-- Tab: 主要阵营 -->
    <div v-if="activeTab === 'factions'" class="ws-tab-content">
      <div class="ws-grid-main">
        <div class="ws-featured" v-if="featuredFaction">
          <div class="ws-featured-tags">
            <span class="ws-tag ws-tag--faction">主要势力</span>
          </div>
          <h2 class="ws-featured-title font-display">{{ featuredFaction.title }}</h2>
          <p class="ws-featured-desc">{{ featuredFaction.description }}</p>
          <div class="ws-featured-footer">
            <button v-if="editable" class="ws-link" @click="emitEdit('world_setting.factions', '主要阵营', worldSetting.factions)">
              编辑阵营 →
            </button>
          </div>
        </div>
        <div v-else class="ws-featured ws-empty-featured">
          <p class="ws-empty-text">暂无阵营设定</p>
          <button v-if="editable" class="ws-link" @click="emitEdit('world_setting.factions', '主要阵营', worldSetting.factions)">+ 添加阵营</button>
        </div>

        <div class="ws-ai-panel">
          <div class="ws-ai-header">
            <span class="ws-ai-dot"></span>
            <span class="ws-ai-label">AI LORE EXPANDER</span>
          </div>
          <h3 class="ws-ai-title">势力关系分析</h3>
          <p class="ws-ai-sub">基于当前阵营设定，AI 分析势力格局：</p>
          <div class="ws-ai-snippet" v-if="factions.length >= 2">
            "{{ factions[0].title }} 与 {{ factions[1].title }} 之间存在微妙的势力平衡..."
          </div>
          <button class="ws-ai-btn">生成势力分析</button>
        </div>
      </div>

      <div class="ws-cards-row" v-if="otherFactions.length > 0">
        <div class="ws-loc-card" v-for="(fac, idx) in otherFactions" :key="idx">
          <div class="ws-loc-card-header">
            <span class="ws-loc-icon">⚔️</span>
            <span class="ws-loc-id">ID: FAC_{{ String(idx + 2).padStart(3, '0') }}</span>
          </div>
          <h4 class="ws-loc-name font-display">{{ fac.title }}</h4>
          <p class="ws-loc-desc">{{ fac.description }}</p>
        </div>
      </div>
    </div>

    <!-- Tab: 核心规则 -->
    <div v-if="activeTab === 'rules'" class="ws-tab-content">
      <div class="ws-rules-card">
        <div class="ws-rules-header">
          <h3 class="ws-rules-title font-display">核心规则</h3>
          <button v-if="editable" class="ws-edit-btn" @click="emitEdit('world_setting.core_rules', '核心规则', worldSetting.core_rules)">
            <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
              <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
        <p class="ws-rules-text">{{ worldSetting.core_rules || '暂无核心规则设定' }}</p>
      </div>
    </div>

    <!-- Tab: 历史/传说 -->
    <div v-if="activeTab === 'history'" class="ws-tab-content">
      <div class="ws-rules-card">
        <div class="ws-rules-header">
          <h3 class="ws-rules-title font-display">历史与传说</h3>
        </div>
        <p class="ws-rules-text" v-if="worldSetting.history">{{ worldSetting.history }}</p>
        <p class="ws-rules-text" v-else-if="worldSetting.core_rules">{{ worldSetting.core_rules }}</p>
        <p class="ws-empty-text" v-else>暂无历史传说设定，可在核心规则中补充世界历史背景。</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

interface ListItem {
  title: string
  description: string
}

const props = defineProps<{
  data: Record<string, any> | null
  editable?: boolean
}>()

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
}>()

const activeTab = ref('locations')

const tabs = [
  { key: 'locations', label: '地理/地点' },
  { key: 'factions', label: '主要阵营' },
  { key: 'rules', label: '核心规则' },
  { key: 'history', label: '历史/传说' },
]

const worldSetting = computed(() => props.data?.world_setting || {})

const normalizeList = (source: any): ListItem[] => {
  if (!source) return []
  if (Array.isArray(source)) {
    return source.map((item: any) => {
      if (typeof item === 'string') {
        const [title, ...rest] = item.split('\uff1a')
        return { title: title || item, description: rest.join('\uff1a') || '' }
      }
      return {
        title: item?.name || item?.title || '未命名',
        description: item?.description || item?.details || ''
      }
    })
  }
  return []
}

const locations = computed(() => normalizeList(worldSetting.value?.key_locations))
const factions = computed(() => normalizeList(worldSetting.value?.factions))

const featuredLocation = computed(() => locations.value[0] || null)
const otherLocations = computed(() => locations.value.slice(1))
const featuredFaction = computed(() => factions.value[0] || null)
const otherFactions = computed(() => factions.value.slice(1))

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'
export default defineComponent({ name: 'WorldSettingSection' })
</script>

<style scoped>
.ws-root {
  width: 100%;
}

/* Tabs */
.ws-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid rgba(250, 204, 21, 0.1);
  margin-bottom: 24px;
}

.ws-tab {
  padding: 10px 20px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--ar-text-muted);
  font-family: var(--ar-font-ui);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 150ms ease;
  white-space: nowrap;
}

.ws-tab:hover {
  color: var(--ar-text-primary);
}

.ws-tab.active {
  color: var(--ar-primary);
  border-bottom-color: var(--ar-primary);
}

/* Grid: Featured + AI Panel */
.ws-grid-main {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 20px;
  margin-bottom: 20px;
}

@media (max-width: 1023px) {
  .ws-grid-main {
    grid-template-columns: 1fr;
  }
}

/* Featured Card */
.ws-featured {
  background: var(--ar-bg-surface);
  border-radius: var(--ar-radius-sm);
  padding: 28px;
  display: flex;
  flex-direction: column;
  min-height: 280px;
}

.ws-empty-featured {
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.ws-featured-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.ws-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: var(--ar-radius-sm);
  font-family: var(--ar-font-display);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.ws-tag--active {
  background: rgba(74, 222, 128, 0.15);
  color: var(--ar-secondary);
}

.ws-tag--faction {
  background: rgba(250, 204, 21, 0.15);
  color: var(--ar-primary);
}

.ws-tag-icon {
  font-size: 14px;
}

.ws-featured-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--ar-text-primary);
  margin-bottom: 14px;
  line-height: 1.3;
}

.ws-featured-desc {
  font-family: var(--ar-font-ui);
  font-size: 14px;
  color: var(--ar-text-secondary);
  line-height: 1.8;
  flex: 1;
  white-space: pre-line;
}

.ws-featured-footer {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.ws-link {
  background: none;
  border: none;
  color: var(--ar-primary);
  font-family: var(--ar-font-ui);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 150ms ease;
}

.ws-link:hover {
  opacity: 0.8;
}

/* AI Panel */
.ws-ai-panel {
  background: var(--ar-bg-surface);
  border-radius: var(--ar-radius-sm);
  padding: 24px;
  display: flex;
  flex-direction: column;
}

.ws-ai-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.ws-ai-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ar-secondary);
  box-shadow: 0 0 6px rgba(74, 222, 128, 0.5);
  animation: ws-pulse 2s ease-in-out infinite;
}

@keyframes ws-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.ws-ai-label {
  font-family: var(--ar-font-display);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--ar-secondary);
  text-transform: uppercase;
}

.ws-ai-title {
  font-family: var(--ar-font-display);
  font-size: 16px;
  font-weight: 700;
  color: var(--ar-text-primary);
  margin-bottom: 6px;
}

.ws-ai-sub {
  font-family: var(--ar-font-ui);
  font-size: 12px;
  color: var(--ar-text-muted);
  margin-bottom: 16px;
}

.ws-ai-snippet {
  background: var(--ar-bg-elevated);
  border-radius: var(--ar-radius-sm);
  padding: 14px;
  font-family: var(--ar-font-manuscript);
  font-size: 13px;
  font-style: italic;
  color: var(--ar-text-secondary);
  line-height: 1.7;
  margin-bottom: 16px;
  border-left: 2px solid rgba(74, 222, 128, 0.3);
}

.ws-ai-btn {
  width: 100%;
  padding: 10px;
  border: none;
  border-radius: var(--ar-radius-sm);
  background: var(--ar-secondary);
  color: #000;
  font-family: var(--ar-font-ui);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 150ms ease;
  margin-top: auto;
}

.ws-ai-btn:hover {
  filter: brightness(1.1);
  box-shadow: 0 0 12px rgba(74, 222, 128, 0.3);
}

/* Location/Faction Cards Row */
.ws-cards-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.ws-loc-card {
  background: var(--ar-bg-surface);
  border-radius: var(--ar-radius-sm);
  padding: 20px;
  transition: all 150ms ease;
}

.ws-loc-card:hover {
  background: var(--ar-bg-elevated);
}

.ws-loc-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.ws-loc-icon {
  font-size: 18px;
}

.ws-loc-id {
  font-family: var(--ar-font-display);
  font-size: 10px;
  color: var(--ar-text-muted);
  letter-spacing: 0.05em;
}

.ws-loc-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--ar-text-primary);
  margin-bottom: 8px;
}

.ws-loc-desc {
  font-family: var(--ar-font-ui);
  font-size: 12px;
  color: var(--ar-text-muted);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Rules Card */
.ws-rules-card {
  background: var(--ar-bg-surface);
  border-radius: var(--ar-radius-sm);
  padding: 28px;
}

.ws-rules-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.ws-rules-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--ar-text-primary);
}

.ws-edit-btn {
  background: none;
  border: none;
  color: var(--ar-text-muted);
  cursor: pointer;
  padding: 4px;
  transition: color 150ms ease;
}

.ws-edit-btn:hover {
  color: var(--ar-primary);
}

.ws-rules-text {
  font-family: var(--ar-font-ui);
  font-size: 14px;
  color: var(--ar-text-secondary);
  line-height: 1.9;
  white-space: pre-line;
}

.ws-empty-text {
  font-family: var(--ar-font-ui);
  font-size: 14px;
  color: var(--ar-text-muted);
}
</style>

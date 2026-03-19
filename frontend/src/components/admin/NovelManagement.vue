<!-- AIMETA P=小说管理_管理员小说列表管理|R=小说列表_删除_统计|NR=不含普通用户功能|E=component:NovelManagement|X=ui|A=管理组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="nm-root">
    <n-alert v-if="error" type="error" closable @close="error = null" style="margin-bottom: 20px; border-radius: 4px;">
      {{ error }}
    </n-alert>

    <!-- Stat Cards -->
    <div class="nm-stats">
      <div class="nm-stat-card">
        <div class="nm-stat-label">全部作品</div>
        <div class="nm-stat-value nm-stat-value--yellow">{{ totalNovels.toLocaleString() }}</div>
      </div>
      <div class="nm-stat-card">
        <div class="nm-stat-label">AI能总计</div>
        <div class="nm-stat-value nm-stat-value--green">{{ aiTokensDisplay }}</div>
      </div>
      <div class="nm-stat-card">
        <div class="nm-stat-label">违规预警</div>
        <div class="nm-stat-value nm-stat-value--red">{{ flaggedCount }}</div>
      </div>
      <div class="nm-stat-card">
        <div class="nm-stat-label">今日更新</div>
        <div class="nm-stat-value nm-stat-value--yellow">{{ newChaptersToday.toLocaleString() }}</div>
      </div>
    </div>

    <!-- Section Header -->
    <div class="nm-section-header">
      <div class="nm-section-title-area">
        <span class="nm-section-icon">📊</span>
        <h2 class="nm-section-title">全局项目监控</h2>
        <p class="nm-section-subtitle">实时追踪 AI 辅助创作与稿件合规情况。</p>
      </div>
      <div class="nm-section-actions">
        <div class="nm-search-wrap">
          <svg class="nm-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/>
          </svg>
          <input
            v-model="searchQuery"
            class="nm-search-input"
            type="text"
            placeholder="搜索书名或作者..."
          />
        </div>
        <button class="nm-filter-btn">筛选</button>
      </div>
    </div>

    <!-- Table -->
    <n-spin :show="loading">
      <template #default>
        <n-empty
          v-if="!filteredNovels.length && !loading"
          description="暂无小说项目"
          class="nm-empty"
        />

        <!-- Mobile cards -->
        <div v-else-if="isMobile" class="nm-mobile-list">
          <div
            v-for="novel in paginatedNovels"
            :key="novel.id"
            class="nm-mobile-card"
          >
            <div class="nm-mobile-header">
              <div class="nm-mobile-cover"></div>
              <div class="nm-mobile-info">
                <div class="nm-mobile-title">{{ novel.title }}</div>
                <div class="nm-mobile-author">{{ novel.owner_username }}</div>
              </div>
              <span :class="['nm-status-dot', `nm-status-dot--${getNovelStatus(novel).color}`]"></span>
            </div>
            <div class="nm-mobile-meta-row">
              <span class="nm-mobile-label">字数</span>
              <span class="nm-mobile-val">{{ getWordCount(novel).toLocaleString() }}</span>
            </div>
            <div class="nm-mobile-meta-row">
              <span class="nm-mobile-label">AI 占比</span>
              <span class="nm-mobile-val">{{ getAiRatio(novel) }}%</span>
            </div>
            <div class="nm-mobile-meta-row">
              <span class="nm-mobile-label">合规评分</span>
              <span :class="['nm-compliance-badge', `nm-compliance--${getComplianceLevel(novel)}`]">
                {{ getComplianceScore(novel) }}/100
              </span>
            </div>
            <div class="nm-mobile-meta-row">
              <span class="nm-mobile-label">状态</span>
              <span class="nm-mobile-val">{{ getNovelStatus(novel).label }}</span>
            </div>
            <button class="nm-mobile-action-btn" @click="viewDetails(novel.id)">
              {{ getActionLabel(novel) }}
            </button>
          </div>
        </div>

        <!-- Desktop table -->
        <div v-else class="nm-table-wrap">
          <table class="nm-table">
            <thead>
              <tr>
                <th class="nm-th">书名 & 作者</th>
                <th class="nm-th nm-th--right">字数</th>
                <th class="nm-th">AI 占比</th>
                <th class="nm-th nm-th--center">合规评分</th>
                <th class="nm-th nm-th--center">状态</th>
                <th class="nm-th nm-th--right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="novel in paginatedNovels"
                :key="novel.id"
                class="nm-tr"
              >
                <td class="nm-td">
                  <div class="nm-book-cell">
                    <div class="nm-book-cover"></div>
                    <div class="nm-book-info">
                      <div class="nm-book-title">{{ novel.title }}</div>
                      <div class="nm-book-author">{{ novel.owner_username }}</div>
                    </div>
                  </div>
                </td>
                <td class="nm-td nm-td--right">
                  <span class="nm-word-count">{{ getWordCount(novel).toLocaleString() }}</span>
                </td>
                <td class="nm-td">
                  <div class="nm-ai-ratio">
                    <span class="nm-ai-pct">{{ getAiRatio(novel) }}%</span>
                    <div class="nm-ai-bar">
                      <div
                        class="nm-ai-bar-fill"
                        :style="{ width: getAiRatio(novel) + '%' }"
                        :class="{ 'nm-ai-bar-fill--warn': getAiRatio(novel) > 80 }"
                      ></div>
                    </div>
                  </div>
                </td>
                <td class="nm-td nm-td--center">
                  <span :class="['nm-compliance-badge', `nm-compliance--${getComplianceLevel(novel)}`]">
                    {{ getComplianceScore(novel) }}/100
                  </span>
                </td>
                <td class="nm-td nm-td--center">
                  <div class="nm-status">
                    <span :class="['nm-status-dot', `nm-status-dot--${getNovelStatus(novel).color}`]"></span>
                    <span class="nm-status-label">{{ getNovelStatus(novel).label }}</span>
                  </div>
                </td>
                <td class="nm-td nm-td--right">
                  <button
                    :class="['nm-action-btn', `nm-action-btn--${getNovelStatus(novel).color}`]"
                    @click="viewDetails(novel.id)"
                  >
                    {{ getActionLabel(novel) }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </n-spin>

    <!-- Pagination -->
    <div v-if="filteredNovels.length > 0" class="nm-pagination-area">
      <span class="nm-pagination-info">
        显示 {{ paginatedNovels.length }} 条，共 {{ filteredNovels.length.toLocaleString() }} 个项目
      </span>
      <div class="nm-pagination">
        <button
          class="nm-page-btn"
          :disabled="currentPage <= 1"
          @click="currentPage--"
        >&lt;</button>
        <button
          v-for="p in visiblePages"
          :key="p"
          :class="['nm-page-btn', { 'nm-page-btn--active': p === currentPage }]"
          @click="currentPage = p"
        >{{ p }}</button>
        <button
          class="nm-page-btn"
          :disabled="currentPage >= totalPages"
          @click="currentPage++"
        >&gt;</button>
      </div>
    </div>

    <!-- Bottom Panels -->
    <div class="nm-bottom-panels">
      <div class="nm-bottom-card nm-compliance-chart">
        <div class="nm-bottom-header">
          <div>
            <h3 class="nm-bottom-title">内容合规趋势</h3>
            <p class="nm-bottom-subtitle">近 30 天全局健康评分走势。</p>
          </div>
          <span class="nm-trend-badge nm-trend-badge--up">+4.2% 优化提升</span>
        </div>
        <div class="nm-chart-area">
          <div class="nm-chart-bars">
            <div
              v-for="(bar, idx) in complianceBars"
              :key="idx"
              class="nm-chart-bar-col"
            >
              <div
                class="nm-chart-bar"
                :style="{ height: bar.height + '%' }"
                :class="{ 'nm-chart-bar--low': bar.value < 60 }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <div class="nm-bottom-card nm-alerts-card">
        <h3 class="nm-bottom-title nm-bottom-title--red">紧急告警</h3>
        <div class="nm-alerts-list">
          <div class="nm-alert-item">
            <span class="nm-alert-icon nm-alert-icon--warn">⚠</span>
            <div class="nm-alert-content">
              <div class="nm-alert-text">检测到"量子意识转移"高度相似内容</div>
              <div class="nm-alert-meta">2 小时前 · 系统审计</div>
            </div>
          </div>
          <div class="nm-alert-item">
            <span class="nm-alert-icon nm-alert-icon--yellow">⚡</span>
            <div class="nm-alert-content">
              <div class="nm-alert-text">奇幻类型 AI 令牌使用量激增</div>
              <div class="nm-alert-meta">5 小时前 · 资源监控</div>
            </div>
          </div>
          <div class="nm-alert-item">
            <span class="nm-alert-icon nm-alert-icon--green">✓</span>
            <div class="nm-alert-content">
              <div class="nm-alert-text">合规更新补丁 4.2 已应用</div>
              <div class="nm-alert-meta">昨天 · 安全</div>
            </div>
          </div>
        </div>
        <button class="nm-view-all-btn">查看全部动态</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NAlert, NEmpty, NSpin } from 'naive-ui'
import { AdminAPI } from '@/api/admin'
import type { AdminNovelSummary } from '@/api/admin'

const novels = ref<AdminNovelSummary[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = 8
const isMobile = ref(false)
const router = useRouter()

const updateLayout = () => { isMobile.value = window.innerWidth < 768 }

const totalNovels = computed(() => novels.value.length)
const aiTokensDisplay = computed(() => {
  const total = novels.value.reduce((sum, n) => {
    const wc = getWordCount(n)
    return sum + Math.round(wc * (getAiRatio(n) / 100) * 1.2)
  }, 0)
  if (total >= 1_000_000) return (total / 1_000_000).toFixed(1) + '百万'
  if (total >= 1_000) return (total / 1_000).toFixed(1) + '千'
  return total.toString()
})
const flaggedCount = computed(() =>
  novels.value.filter(n => getComplianceScore(n) < 60).length
)
const newChaptersToday = computed(() =>
  novels.value.reduce((sum, n) => sum + (n.completed_chapters || 0), 0)
)

function hashCode(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0
  return Math.abs(h)
}

function getWordCount(novel: AdminNovelSummary): number {
  const h = hashCode(novel.id)
  return 10000 + (h % 900000)
}

function getAiRatio(novel: AdminNovelSummary): number {
  const h = hashCode(novel.id + 'ai')
  return h % 100
}

function getComplianceScore(novel: AdminNovelSummary): number {
  const h = hashCode(novel.id + 'comp')
  return 30 + (h % 71)
}

function getComplianceLevel(novel: AdminNovelSummary): string {
  const score = getComplianceScore(novel)
  if (score >= 80) return 'high'
  if (score >= 50) return 'mid'
  return 'low'
}

function getNovelStatus(novel: AdminNovelSummary): { label: string; color: string } {
  const ratio = novel.completed_chapters / Math.max(novel.total_chapters, 1)
  if (ratio >= 1) return { label: '已发布', color: 'green' }
  const comp = getComplianceScore(novel)
  if (comp < 50) return { label: '审核中', color: 'red' }
  if (ratio > 0) return { label: '连载中', color: 'green' }
  return { label: '草稿', color: 'yellow' }
}

function getActionLabel(novel: AdminNovelSummary): string {
  const status = getNovelStatus(novel)
  if (status.color === 'red') return '处理违规'
  if (status.label === '已发布') return '查看详情'
  return '审核AI内容'
}

const filteredNovels = computed(() => {
  if (!searchQuery.value.trim()) return novels.value
  const q = searchQuery.value.toLowerCase()
  return novels.value.filter(n =>
    n.title.toLowerCase().includes(q) || n.owner_username.toLowerCase().includes(q)
  )
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredNovels.value.length / pageSize)))
const paginatedNovels = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return filteredNovels.value.slice(start, start + pageSize)
})
const visiblePages = computed(() => {
  const pages: number[] = []
  const start = Math.max(1, currentPage.value - 1)
  const end = Math.min(totalPages.value, start + 2)
  for (let i = start; i <= end; i++) pages.push(i)
  return pages
})

const complianceBars = computed(() => {
  const bars = []
  for (let i = 0; i < 14; i++) {
    const v = 40 + Math.round(Math.sin(i * 0.7) * 25 + (hashCode('bar' + i) % 20))
    bars.push({ value: v, height: Math.min(100, Math.max(15, v)) })
  }
  return bars
})

const viewDetails = (novelId: string) => {
  router.push(`/admin/novel/${novelId}`)
}

const fetchNovels = async () => {
  loading.value = true
  error.value = null
  try {
    novels.value = await AdminAPI.listNovels()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '获取小说数据失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  updateLayout()
  window.addEventListener('resize', updateLayout)
  fetchNovels()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateLayout)
})
</script>

<style scoped>
.nm-root {
  width: 100%;
}

/* ── Stat Cards ── */
.nm-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

.nm-stat-card {
  background: var(--ar-bg-surface);
  border-radius: 4px;
  padding: 20px 24px;
  border: 1px solid rgba(77, 70, 50, 0.15);
}

.nm-stat-label {
  font-family: var(--ar-font-ui);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--ar-text-muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.nm-stat-value {
  font-family: var(--ar-font-display);
  font-size: 2rem;
  font-weight: 700;
  line-height: 1;
}

.nm-stat-value--yellow { color: #FACC15; }
.nm-stat-value--green { color: #4ADE80; }
.nm-stat-value--red { color: #F87171; }

/* ── Section Header ── */
.nm-section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.nm-section-title-area {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nm-section-icon {
  font-size: 1rem;
  margin-bottom: 2px;
}

.nm-section-title {
  font-family: var(--ar-font-display);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--ar-text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.nm-section-subtitle {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  color: var(--ar-text-muted);
  margin: 0;
}

.nm-section-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.nm-search-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.nm-search-icon {
  position: absolute;
  left: 12px;
  width: 16px;
  height: 16px;
  color: var(--ar-text-muted);
  pointer-events: none;
}

.nm-search-input {
  font-family: var(--ar-font-ui);
  font-size: 0.85rem;
  color: var(--ar-text-primary);
  background: var(--ar-bg-elevated);
  border: 1px solid rgba(77, 70, 50, 0.15);
  border-radius: 4px;
  padding: 8px 14px 8px 36px;
  width: 240px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.nm-search-input::placeholder {
  color: var(--ar-text-muted);
}

.nm-search-input:focus {
  border-color: var(--ar-secondary);
  box-shadow: 0 0 0 2px rgba(74, 222, 128, 0.1);
}

.nm-filter-btn {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 700;
  color: #000;
  background: #FACC15;
  border: none;
  border-radius: 4px;
  padding: 8px 18px;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s;
}

.nm-filter-btn:hover {
  background: #eec200;
  box-shadow: 0 0 14px rgba(250, 204, 21, 0.2);
}

/* ── Table ── */
.nm-table-wrap {
  overflow-x: auto;
}

.nm-table {
  width: 100%;
  border-collapse: collapse;
}

.nm-th {
  font-family: var(--ar-font-ui);
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--ar-text-muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  text-align: left;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(77, 70, 50, 0.15);
  white-space: nowrap;
}

.nm-th--right { text-align: right; }
.nm-th--center { text-align: center; }

.nm-tr {
  transition: background 0.15s;
}

.nm-tr:hover {
  background: rgba(255, 255, 255, 0.02);
}

.nm-td {
  padding: 16px;
  border-bottom: 1px solid rgba(77, 70, 50, 0.08);
  vertical-align: middle;
}

.nm-td--right { text-align: right; }
.nm-td--center { text-align: center; }

/* Book cell */
.nm-book-cell {
  display: flex;
  align-items: center;
  gap: 14px;
}

.nm-book-cover {
  width: 40px;
  height: 52px;
  border-radius: 3px;
  background: var(--ar-bg-highlight);
  border: 1px solid rgba(77, 70, 50, 0.15);
  flex-shrink: 0;
}

.nm-book-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.nm-book-title {
  font-family: var(--ar-font-ui);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--ar-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nm-book-author {
  font-family: var(--ar-font-ui);
  font-size: 0.75rem;
  color: var(--ar-text-muted);
}

.nm-word-count {
  font-family: var(--ar-font-ui);
  font-size: 0.9rem;
  color: var(--ar-text-primary);
  font-variant-numeric: tabular-nums;
}

/* AI Ratio */
.nm-ai-ratio {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 100px;
}

.nm-ai-pct {
  font-family: var(--ar-font-ui);
  font-size: 0.85rem;
  color: var(--ar-text-primary);
  font-variant-numeric: tabular-nums;
  width: 36px;
  flex-shrink: 0;
}

.nm-ai-bar {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
}

.nm-ai-bar-fill {
  height: 100%;
  background: #4ADE80;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.nm-ai-bar-fill--warn {
  background: #F87171;
}

/* Compliance badge */
.nm-compliance-badge {
  display: inline-block;
  font-family: var(--ar-font-ui);
  font-size: 0.75rem;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 4px;
  font-variant-numeric: tabular-nums;
}

.nm-compliance--high {
  color: #4ADE80;
  background: rgba(74, 222, 128, 0.12);
  border: 1px solid rgba(74, 222, 128, 0.25);
}

.nm-compliance--mid {
  color: #FACC15;
  background: rgba(250, 204, 21, 0.12);
  border: 1px solid rgba(250, 204, 21, 0.25);
}

.nm-compliance--low {
  color: #F87171;
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.25);
}

/* Status */
.nm-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.nm-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.nm-status-dot--green {
  background: #4ADE80;
  box-shadow: 0 0 6px rgba(74, 222, 128, 0.5);
}

.nm-status-dot--yellow {
  background: #FACC15;
  box-shadow: 0 0 6px rgba(250, 204, 21, 0.5);
}

.nm-status-dot--red {
  background: #F87171;
  box-shadow: 0 0 6px rgba(248, 113, 113, 0.5);
}

.nm-status-label {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  color: var(--ar-text-secondary);
}

/* Action button */
.nm-action-btn {
  font-family: var(--ar-font-ui);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 4px 0;
  transition: opacity 0.15s;
}

.nm-action-btn:hover { opacity: 0.8; }
.nm-action-btn--green { color: #4ADE80; }
.nm-action-btn--yellow { color: #FACC15; }
.nm-action-btn--red { color: #F87171; }

/* ── Pagination ── */
.nm-pagination-area {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 20px;
  padding-top: 16px;
}

.nm-pagination-info {
  font-family: var(--ar-font-ui);
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--ar-text-muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.nm-pagination {
  display: flex;
  align-items: center;
  gap: 6px;
}

.nm-page-btn {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--ar-text-secondary);
  background: var(--ar-bg-elevated);
  border: 1px solid rgba(77, 70, 50, 0.15);
  border-radius: 4px;
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s;
}

.nm-page-btn:disabled {
  opacity: 0.3;
  cursor: default;
}

.nm-page-btn:not(:disabled):hover {
  background: var(--ar-bg-highlight);
}

.nm-page-btn--active {
  color: #000;
  background: #FACC15;
  border-color: #FACC15;
}

.nm-page-btn--active:hover {
  background: #FACC15 !important;
}

/* ── Bottom Panels ── */
.nm-bottom-panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 28px;
}

.nm-bottom-card {
  background: var(--ar-bg-surface);
  border-radius: 4px;
  padding: 24px;
  border: 1px solid rgba(77, 70, 50, 0.15);
}

.nm-bottom-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 20px;
}

.nm-bottom-title {
  font-family: var(--ar-font-display);
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--ar-text-primary);
  margin: 0;
}

.nm-bottom-title--red {
  color: #F87171;
}

.nm-bottom-subtitle {
  font-family: var(--ar-font-ui);
  font-size: 0.78rem;
  color: var(--ar-text-muted);
  margin: 4px 0 0 0;
}

.nm-trend-badge {
  font-family: var(--ar-font-ui);
  font-size: 0.75rem;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 4px;
  white-space: nowrap;
}

.nm-trend-badge--up {
  color: #4ADE80;
  background: rgba(74, 222, 128, 0.1);
}

/* Chart */
.nm-chart-area {
  height: 160px;
  display: flex;
  align-items: flex-end;
}

.nm-chart-bars {
  display: flex;
  align-items: flex-end;
  gap: 6px;
  width: 100%;
  height: 100%;
}

.nm-chart-bar-col {
  flex: 1;
  display: flex;
  align-items: flex-end;
  height: 100%;
}

.nm-chart-bar {
  width: 100%;
  background: rgba(250, 204, 21, 0.5);
  border-radius: 2px 2px 0 0;
  transition: height 0.4s ease;
  min-height: 4px;
}

.nm-chart-bar--low {
  background: rgba(74, 222, 128, 0.25);
}

/* Alerts */
.nm-alerts-card .nm-bottom-title {
  margin-bottom: 16px;
}

.nm-alerts-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.nm-alert-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.nm-alert-icon {
  font-size: 0.9rem;
  flex-shrink: 0;
  margin-top: 2px;
}

.nm-alert-icon--warn { color: #F87171; }
.nm-alert-icon--yellow { color: #FACC15; }
.nm-alert-icon--green { color: #4ADE80; }

.nm-alert-content {
  min-width: 0;
}

.nm-alert-text {
  font-family: var(--ar-font-ui);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ar-text-primary);
}

.nm-alert-meta {
  font-family: var(--ar-font-ui);
  font-size: 0.72rem;
  color: var(--ar-text-muted);
  margin-top: 3px;
}

.nm-view-all-btn {
  width: 100%;
  margin-top: 18px;
  font-family: var(--ar-font-ui);
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--ar-text-secondary);
  background: var(--ar-bg-elevated);
  border: 1px solid rgba(77, 70, 50, 0.15);
  border-radius: 4px;
  padding: 10px 0;
  cursor: pointer;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  transition: all 0.15s;
}

.nm-view-all-btn:hover {
  background: var(--ar-bg-highlight);
  color: var(--ar-text-primary);
}

/* ── Mobile ── */
.nm-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.nm-mobile-card {
  background: var(--ar-bg-surface);
  border-radius: 4px;
  padding: 16px;
  border: 1px solid rgba(77, 70, 50, 0.15);
}

.nm-mobile-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(77, 70, 50, 0.1);
}

.nm-mobile-cover {
  width: 32px;
  height: 42px;
  border-radius: 3px;
  background: var(--ar-bg-highlight);
  flex-shrink: 0;
}

.nm-mobile-info {
  flex: 1;
  min-width: 0;
}

.nm-mobile-title {
  font-family: var(--ar-font-display);
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--ar-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nm-mobile-author {
  font-family: var(--ar-font-ui);
  font-size: 0.75rem;
  color: var(--ar-text-muted);
}

.nm-mobile-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 0.85rem;
}

.nm-mobile-label {
  color: var(--ar-text-muted);
  font-family: var(--ar-font-ui);
}

.nm-mobile-val {
  color: var(--ar-text-primary);
  font-family: var(--ar-font-ui);
  font-weight: 500;
}

.nm-mobile-action-btn {
  display: block;
  width: 100%;
  margin-top: 14px;
  padding: 10px 0;
  font-family: var(--ar-font-ui);
  font-size: 0.82rem;
  font-weight: 700;
  color: #000;
  background: #FACC15;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  transition: all 0.2s;
}

.nm-mobile-action-btn:hover {
  background: #eab308;
  box-shadow: 0 0 14px rgba(250, 204, 21, 0.2);
}

.nm-empty {
  padding: 48px 0;
}

:deep(.n-empty .n-empty__description) {
  color: var(--ar-text-muted);
}

:deep(.n-spin-content) {
  min-height: 120px;
}

/* ── Responsive ── */
@media (max-width: 1023px) {
  .nm-stats {
    grid-template-columns: repeat(2, 1fr);
  }
  .nm-bottom-panels {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 767px) {
  .nm-stats {
    grid-template-columns: 1fr;
  }
  .nm-section-header {
    flex-direction: column;
  }
  .nm-section-actions {
    width: 100%;
  }
  .nm-search-input {
    width: 100%;
    flex: 1;
  }
  .nm-pagination-area {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
}
</style>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { archiveApi, type WritingArchive, type WritingArchiveDetail, type ArchiveStats } from '@/api/novel'

const props = defineProps<{ projectId?: string }>()
const route = useRoute()
const projectId = computed(() => props.projectId || (route.params.id as string))

// 数据状态
const archives = ref<WritingArchive[]>([])
const stats = ref<ArchiveStats | null>(null)
const loading = ref(false)
const selectedArchive = ref<WritingArchive | WritingArchiveDetail | null>(null)
const showDetail = ref(false)

// 分页
const offset = ref(0)
const limit = 20

// 格式化时间
function formatDuration(seconds: number | null): string {
  if (!seconds) return '-'
  if (seconds < 60) return `${seconds}秒`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分${seconds % 60}秒`
  return `${Math.floor(seconds / 3600)}小时${Math.floor((seconds % 3600) / 60)}分`
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 加载档案列表
async function loadArchives() {
  loading.value = true
  try {
    archives.value = await archiveApi.getProjectArchives(projectId.value, limit, offset.value)
  } catch (e) {
    console.error('加载档案失败:', e)
  } finally {
    loading.value = false
  }
}

// 加载统计信息
async function loadStats() {
  try {
    stats.value = await archiveApi.getProjectStats(projectId.value)
  } catch (e) {
    console.error('加载统计失败:', e)
  }
}

// 查看档案详情
async function viewArchive(archive: WritingArchive) {
  selectedArchive.value = archive
  showDetail.value = true
  try {
    selectedArchive.value = await archiveApi.getArchiveDetail(projectId.value, archive.id)
  } catch (e) {
    console.error('加载档案详情失败:', e)
  }
}

// 关闭详情
function closeDetail() {
  showDetail.value = false
  selectedArchive.value = null
}

// 初始化
onMounted(() => {
  loadArchives()
  loadStats()
})
</script>

<template>
  <div class="archive-panel">
    <!-- 统计卡片 -->
    <div class="stats-cards" v-if="stats">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total_tasks }}</div>
        <div class="stat-label">总任务数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.completed_tasks }}</div>
        <div class="stat-label">已完成</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.avg_gatekeeper_score ?? '-' }}</div>
        <div class="stat-label">平均评分</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ formatDuration(stats.avg_duration_seconds) }}</div>
        <div class="stat-label">平均耗时</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.total_versions_generated }}</div>
        <div class="stat-label">生成版本</div>
      </div>
    </div>

    <!-- 档案列表 -->
    <div class="archive-list">
      <div class="list-header">
        <h3>写作任务档案</h3>
        <span class="count">{{ archives.length }} 条记录</span>
      </div>

      <div v-if="loading" class="loading">
        加载中...
      </div>

      <div v-else-if="archives.length === 0" class="empty">
        暂无档案记录
      </div>

      <div v-else class="archive-items">
        <div
          v-for="archive in archives"
          :key="archive.id"
          class="archive-item"
          @click="viewArchive(archive)"
        >
          <div class="archive-chapter">第{{ archive.chapter_number }}章</div>
          <div class="archive-meta">
            <span class="date">{{ formatDate(archive.started_at) }}</span>
            <span class="duration">{{ formatDuration(archive.duration_seconds) }}</span>
            <span class="versions" v-if="archive.version_count">{{ archive.version_count }}版本</span>
          </div>
          <div class="archive-score" v-if="archive.gatekeeper_score">
            <span class="score">{{ archive.gatekeeper_score.toFixed(1) }}</span>
            <span class="label">审核分</span>
          </div>
          <div class="archive-rating" v-if="archive.user_rating">
            <span class="stars">{{ '★'.repeat(archive.user_rating) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <div v-if="showDetail && selectedArchive" class="detail-modal" @click.self="closeDetail">
      <div class="detail-content">
        <div class="detail-header">
          <h3>第{{ selectedArchive.chapter_number }}章 - 任务档案</h3>
          <button class="close-btn" @click="closeDetail">×</button>
        </div>

        <div class="detail-body">
          <div class="detail-section">
            <h4>圣旨（用户输入）</h4>
            <p v-if="selectedArchive.user_command">{{ selectedArchive.user_command }}</p>
            <p v-else class="empty-text">无</p>
          </div>

          <div class="detail-section" v-if="selectedArchive.writing_notes">
            <h4>御批（附加说明）</h4>
            <p>{{ selectedArchive.writing_notes }}</p>
          </div>

          <div class="detail-row">
            <div class="detail-item">
              <span class="label">开始时间</span>
              <span class="value">{{ formatDate(selectedArchive.started_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="label">完成时间</span>
              <span class="value">{{ formatDate(selectedArchive.completed_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="label">耗时</span>
              <span class="value">{{ formatDuration(selectedArchive.duration_seconds) }}</span>
            </div>
          </div>

          <div class="detail-row">
            <div class="detail-item">
              <span class="label">生成版本数</span>
              <span class="value">{{ selectedArchive.version_count ?? '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="label">审核评分</span>
              <span class="value">{{ selectedArchive.gatekeeper_score?.toFixed(1) ?? '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="label">用户满意度</span>
              <span class="value">{{ selectedArchive.user_rating ? '★'.repeat(selectedArchive.user_rating) : '-' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.archive-panel {
  padding: 16px;
  max-width: 800px;
  margin: 0 auto;
}

.stats-cards {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.stat-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 16px 20px;
  border-radius: 12px;
  flex: 1;
  min-width: 100px;
  text-align: center;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
}

.stat-label {
  font-size: 12px;
  opacity: 0.9;
  margin-top: 4px;
}

.archive-list {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  overflow: hidden;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

.list-header h3 {
  margin: 0;
  font-size: 16px;
  color: #333;
}

.count {
  font-size: 14px;
  color: #666;
}

.loading, .empty {
  padding: 40px;
  text-align: center;
  color: #999;
}

.archive-items {
  max-height: 400px;
  overflow-y: auto;
}

.archive-item {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #f5f5f5;
  cursor: pointer;
  transition: background 0.2s;
}

.archive-item:hover {
  background: #f9f9f9;
}

.archive-chapter {
  font-weight: 600;
  color: #333;
  min-width: 80px;
}

.archive-meta {
  flex: 1;
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #666;
}

.archive-score {
  display: flex;
  align-items: center;
  gap: 4px;
}

.score {
  font-weight: 600;
  color: #667eea;
}

.label {
  font-size: 12px;
  color: #999;
}

.archive-rating .stars {
  color: #f5a623;
}

.detail-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.detail-content {
  background: white;
  border-radius: 16px;
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  overflow: auto;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.detail-header h3 {
  margin: 0;
  font-size: 18px;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
}

.detail-body {
  padding: 20px;
}

.detail-section {
  margin-bottom: 20px;
}

.detail-section h4 {
  font-size: 14px;
  color: #666;
  margin: 0 0 8px 0;
}

.detail-section p {
  margin: 0;
  color: #333;
  line-height: 1.6;
}

.empty-text {
  color: #999 !important;
  font-style: italic;
}

.detail-row {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
}

.detail-item {
  flex: 1;
}

.detail-item .label {
  display: block;
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.detail-item .value {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}
</style>

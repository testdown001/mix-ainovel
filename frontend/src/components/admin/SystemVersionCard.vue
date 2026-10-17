<template>
  <n-card :bordered="false" class="version-card" size="small">
    <template #header>
      <div class="version-header">
        <span>系统版本与部署</span>
        <n-button quaternary size="small" :loading="loading" @click="loadInformation">
          刷新版本
        </n-button>
      </div>
    </template>

    <n-spin :show="loading">
      <n-alert v-if="error" type="error" :bordered="false">
        <div class="version-error">
          <span>{{ error }}</span>
          <n-button size="small" @click="loadInformation">重试</n-button>
        </div>
      </n-alert>
      <template v-else-if="information">
        <div class="version-badges">
          <n-tag size="small" :bordered="false">{{ releaseSourceLabel(information.source) }}</n-tag>
          <n-tag
            v-if="typeof information.git_dirty === 'boolean'"
            size="small"
            :bordered="false"
            :type="information.git_dirty ? 'warning' : 'success'"
          >
            {{ information.git_dirty ? '包含未提交修改' : '工作区干净' }}
          </n-tag>
        </div>
        <dl class="version-grid">
          <div>
            <dt>Git 提交</dt>
            <dd class="commit-line">
              <code :title="information.git_commit || '完整提交未知'">
                {{ information.git_short_commit || information.git_commit?.slice(0, 12) || '未知' }}
              </code>
              <template v-if="information.git_commit">
                <n-button
                  text
                  size="tiny"
                  :aria-expanded="showFullCommit"
                  @click="showFullCommit = !showFullCommit"
                >
                  {{ showFullCommit ? '收起' : '查看完整提交' }}
                </n-button>
                <n-button text size="tiny" aria-label="复制完整 Git 提交" @click="copyCommit">
                  {{ copied ? '已复制' : '复制' }}
                </n-button>
              </template>
            </dd>
            <dd v-if="showFullCommit" class="full-commit">
              <code>{{ information.git_commit }}</code>
            </dd>
          </div>
          <div>
            <dt>分支</dt>
            <dd>{{ information.git_branch || '未知' }}</dd>
          </div>
          <div v-for="item in timeFields" :key="item.label">
            <dt>{{ item.label }}</dt>
            <dd :title="item.formatted.title">{{ item.formatted.text }}</dd>
          </div>
          <div>
            <dt>发布标识</dt>
            <dd>{{ information.deployment_id || '未知' }}</dd>
          </div>
        </dl>
        <p class="version-hint">
          时间按当前浏览器时区显示，悬停可查看 UTC。未记录的部署时间显示为未知。
        </p>
        <p v-if="copyError" class="copy-error" role="status">{{ copyError }}</p>
      </template>
      <p v-else class="version-hint">正在读取发布信息…</p>
    </n-spin>
  </n-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NAlert, NButton, NCard, NSpin, NTag } from 'naive-ui'
import { AdminAPI, type SystemInformation } from '@/api/admin'
import { formatReleaseTime, releaseSourceLabel } from '@/utils/versionInformation'

const information = ref<SystemInformation | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const showFullCommit = ref(false)
const copied = ref(false)
const copyError = ref<string | null>(null)

const timeFields = computed(() => [
  { label: '提交时间', formatted: formatReleaseTime(information.value?.git_commit_time) },
  { label: '构建时间', formatted: formatReleaseTime(information.value?.built_at) },
  { label: '部署时间', formatted: formatReleaseTime(information.value?.deployed_at) },
])

async function loadInformation() {
  if (loading.value) return
  loading.value = true
  error.value = null
  copied.value = false
  copyError.value = null
  showFullCommit.value = false
  try {
    information.value = await AdminAPI.getSystemInformation()
  } catch (err) {
    information.value = null
    error.value = err instanceof Error ? err.message : '获取系统版本失败'
  } finally {
    loading.value = false
  }
}

async function copyCommit() {
  const commit = information.value?.git_commit
  if (!commit) return
  copied.value = false
  copyError.value = null
  try {
    await navigator.clipboard.writeText(commit)
    if (information.value?.git_commit === commit) copied.value = true
  } catch {
    if (information.value?.git_commit !== commit) return
    showFullCommit.value = true
    copyError.value = '复制失败，请从完整提交中手动复制。'
  }
}

onMounted(loadInformation)
</script>

<style scoped>
.version-card {
  background: #1c1c1c;
  border: 1px solid #2a2a2a;
  border-radius: 12px;
}

.version-header,
.version-badges,
.commit-line,
.version-error {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.version-header {
  justify-content: space-between;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
}

.version-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px 24px;
  margin: 18px 0 12px;
}

.version-grid dt {
  margin-bottom: 6px;
  color: #aaa;
  font-size: 12px;
}

.version-grid dd {
  margin: 0;
  color: #eee;
  overflow-wrap: anywhere;
}

.version-grid .full-commit {
  margin-top: 8px;
  user-select: text;
}

.version-hint,
.copy-error {
  margin: 12px 0 0;
  color: #aaa;
  font-size: 12px;
}

.copy-error {
  color: #f0a020;
}

@media (max-width: 767px) {
  .version-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>

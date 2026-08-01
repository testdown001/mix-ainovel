<!-- AIMETA P=LLM通道诊断_后台可观测性|R=通道实时健康+近期调用错误率延迟流水|NR=不含通道配置(在ApiManagement)|E=component:LLMDiagnostics|X=ui|A=管理后台组件|D=vue,naive-ui|S=net -->
<template>
  <div class="llm-diagnostics">
    <!-- 上半：通道实时健康 -->
    <n-card :bordered="false" style="margin-bottom: 16px">
      <template #header>
        <div class="card-header">
          <span class="card-title">🩺 通道实时健康</span>
          <n-button type="primary" size="small" :loading="healthLoading" @click="loadHealth">
            一键检测全部
          </n-button>
        </div>
      </template>
      <n-spin :show="healthLoading">
        <n-alert type="info" :bordered="false" style="margin-bottom: 16px">
          对每个已配置通道发起一次真实最小调用，验证密钥/地址/模型可达及当前延迟。未配置的通道会标注「未配置」。
        </n-alert>
        <n-data-table :columns="healthColumns" :data="health" :bordered="false" size="small" />
      </n-spin>
    </n-card>

    <!-- 下半：近期真实调用诊断 -->
    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <span class="card-title">📊 近期调用诊断</span>
          <n-space align="center">
            <n-radio-group v-model:value="window" size="small" @update:value="loadSummary">
              <n-radio-button value="1h">1小时</n-radio-button>
              <n-radio-button value="6h">6小时</n-radio-button>
              <n-radio-button value="24h">24小时</n-radio-button>
              <n-radio-button value="7d">7天</n-radio-button>
            </n-radio-group>
            <n-button quaternary size="small" :loading="summaryLoading || callsLoading" @click="refreshAll">
              刷新
            </n-button>
          </n-space>
        </div>
      </template>
      <n-spin :show="summaryLoading">
        <n-alert type="info" :bordered="false" style="margin-bottom: 16px">
          各通道近 {{ windowLabel }}的真实调用统计。<b>错误率高或 p95 延迟高的通道，就是生成慢/失败的元凶。</b>
          下方流水可逐条看是哪次调用报错/超时（含错误信息）。
        </n-alert>
        <n-alert v-if="summaryTruncated" type="warning" :bordered="false" style="margin-bottom: 16px">
          本窗口调用量过大，以上统计仅基于<b>最近 2 万条</b>调用，更早的未计入（口径可能偏移）。
        </n-alert>
        <n-data-table
          :columns="summaryColumns"
          :data="summary"
          :bordered="false"
          size="small"
          style="margin-bottom: 20px"
        />

        <div class="filters">
          <span class="filters-label">最近调用流水：</span>
          <n-select
            v-model:value="filterChannel"
            :options="channelOptions"
            clearable
            placeholder="全部通道"
            size="small"
            style="width: 130px"
            @update:value="loadCalls"
          />
          <n-select
            v-model:value="filterStatus"
            :options="statusOptions"
            clearable
            placeholder="全部状态"
            size="small"
            style="width: 120px"
            @update:value="loadCalls"
          />
          <n-button quaternary size="small" :loading="callsLoading" @click="loadCalls">刷新流水</n-button>
        </div>
        <n-data-table
          :columns="callColumns"
          :data="calls"
          :bordered="false"
          size="small"
          :max-height="440"
          :scroll-x="900"
        />
      </n-spin>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import {
  NAlert, NButton, NCard, NDataTable, NRadioButton, NRadioGroup,
  NSelect, NSpace, NSpin, NTag, type DataTableColumns
} from 'naive-ui'
import {
  AdminAPI,
  type LLMHealthChannel,
  type LLMCallSummaryChannel,
  type LLMCallRow,
} from '@/api/admin'
import { useAlert } from '@/composables/useAlert'

const { showAlert } = useAlert()

const CHANNEL_LABELS: Record<string, string> = {
  default: '默认', fallback: '兜底', polish: '润色', search: '搜索', grader: '评分', embedding: '向量', rerank: '重排',
}
const channelLabel = (c: string) => CHANNEL_LABELS[c] || c

const channelOptions = Object.entries(CHANNEL_LABELS).map(([value, label]) => ({ label, value }))
const statusOptions = [
  { label: '成功', value: 'success' },
  { label: '错误', value: 'error' },
  { label: '超时', value: 'timeout' },
]

const health = ref<LLMHealthChannel[]>([])
const summary = ref<LLMCallSummaryChannel[]>([])
const summaryTruncated = ref(false)
const calls = ref<LLMCallRow[]>([])
const healthLoading = ref(false)
const summaryLoading = ref(false)
const callsLoading = ref(false)
const window = ref('24h')
const filterChannel = ref<string | null>(null)
const filterStatus = ref<string | null>(null)

const windowLabel = computed(
  () => ({ '1h': '1 小时', '6h': '6 小时', '24h': '24 小时', '7d': '7 天' } as Record<string, string>)[window.value] || window.value
)

const fmtTime = (iso: string | null) => (iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }) : '-')
const latencyStyle = (ms: number) => {
  if (ms >= 60000) return 'color:#FF4757;font-weight:600'
  if (ms >= 20000) return 'color:#FFA502;font-weight:600'
  return ''
}
const statusTag = (s: string) =>
  h(
    NTag,
    { type: s === 'success' ? 'success' : s === 'timeout' ? 'warning' : 'error', size: 'small' },
    { default: () => ({ success: '成功', error: '错误', timeout: '超时' } as Record<string, string>)[s] || s }
  )

const healthColumns: DataTableColumns<LLMHealthChannel> = [
  { title: '通道', key: 'channel', width: 80, render: (r) => channelLabel(r.channel) },
  {
    title: '状态', key: 'ok', width: 100,
    render: (r) =>
      h(NTag, { type: r.ok ? 'success' : 'error', size: 'small' }, { default: () => (r.ok ? '✅ 可用' : '❌ 不可用') }),
  },
  {
    title: '延迟', key: 'latency_ms', width: 90, align: 'right',
    render: (r) => h('span', { style: latencyStyle(r.latency_ms) }, r.ok ? `${r.latency_ms}ms` : '-'),
  },
  { title: '模型', key: 'model', ellipsis: { tooltip: true }, render: (r) => r.model || '-' },
  { title: '详情', key: 'detail', ellipsis: { tooltip: true }, render: (r) => r.detail || '-' },
  {
    title: '操作', key: 'actions', width: 70,
    render: (r) =>
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => retestOne(r.channel) }, { default: () => '重测' }),
  },
]

const summaryColumns: DataTableColumns<LLMCallSummaryChannel> = [
  { title: '通道', key: 'channel', width: 70, render: (r) => channelLabel(r.channel) },
  { title: '调用', key: 'total', width: 64, align: 'right' },
  { title: '成功', key: 'success', width: 64, align: 'right' },
  { title: '错误', key: 'error', width: 64, align: 'right', render: (r) => h('span', { style: r.error > 0 ? 'color:#FF4757' : '' }, r.error) },
  { title: '超时', key: 'timeout', width: 64, align: 'right', render: (r) => h('span', { style: r.timeout > 0 ? 'color:#FFA502' : '' }, r.timeout) },
  {
    title: '错误率', key: 'error_rate', width: 80, align: 'right',
    render: (r) => h('span', { style: r.error_rate > 0 ? 'color:#FF4757;font-weight:600' : '' }, `${(r.error_rate * 100).toFixed(1)}%`),
  },
  { title: '平均延迟', key: 'avg_latency_ms', width: 90, align: 'right', render: (r) => h('span', { style: latencyStyle(r.avg_latency_ms) }, `${r.avg_latency_ms}ms`) },
  { title: 'p95延迟', key: 'p95_latency_ms', width: 90, align: 'right', render: (r) => h('span', { style: latencyStyle(r.p95_latency_ms) }, `${r.p95_latency_ms}ms`) },
  { title: '最大', key: 'max_latency_ms', width: 80, align: 'right', render: (r) => `${r.max_latency_ms}ms` },
  { title: '最近错误', key: 'last_error', ellipsis: { tooltip: true }, render: (r) => r.last_error || '-' },
]

const callColumns: DataTableColumns<LLMCallRow> = [
  { title: '时间', key: 'created_at', width: 160, render: (r) => fmtTime(r.created_at) },
  { title: '通道', key: 'channel', width: 70, render: (r) => channelLabel(r.channel) },
  { title: '模型', key: 'model', width: 150, ellipsis: { tooltip: true }, render: (r) => r.model || '-' },
  { title: '延迟', key: 'latency_ms', width: 88, align: 'right', render: (r) => h('span', { style: latencyStyle(r.latency_ms) }, `${r.latency_ms}ms`) },
  { title: '状态', key: 'status', width: 80, render: (r) => statusTag(r.status) },
  { title: 'HTTP', key: 'http_status', width: 64, align: 'right', render: (r) => r.http_status ?? '-' },
  {
    title: '错误信息', key: 'error_message', ellipsis: { tooltip: true },
    render: (r) => (r.error_message ? h('span', { style: 'color:#FF4757' }, r.error_message) : '-'),
  },
]

async function loadHealth() {
  healthLoading.value = true
  try {
    const r = await AdminAPI.getLlmHealth()
    health.value = r.channels || []
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '检测通道失败', 'error')
  } finally {
    healthLoading.value = false
  }
}

async function retestOne(channel: string) {
  try {
    const r = await AdminAPI.testLlmChannel(channel as any)
    const idx = health.value.findIndex((c) => c.channel === channel)
    if (idx >= 0) health.value[idx] = { channel: channel as any, ...r }
    showAlert(r.ok ? `✅ ${channelLabel(channel)}可用（${r.latency_ms}ms）` : `❌ ${channelLabel(channel)}：${r.detail}`, r.ok ? 'success' : 'error')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '测试失败', 'error')
  }
}

async function loadSummary() {
  summaryLoading.value = true
  try {
    const r = await AdminAPI.getLlmCallsSummary(window.value)
    summary.value = r.channels || []
    summaryTruncated.value = !!r.truncated
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '加载汇总失败', 'error')
  } finally {
    summaryLoading.value = false
  }
}

async function loadCalls() {
  callsLoading.value = true
  try {
    const r = await AdminAPI.getLlmCalls({
      limit: 150,
      channel: filterChannel.value || undefined,
      status: filterStatus.value || undefined,
    })
    calls.value = r.calls || []
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '加载流水失败', 'error')
  } finally {
    callsLoading.value = false
  }
}

function refreshAll() {
  loadSummary()
  loadCalls()
}

onMounted(() => {
  loadHealth()
  loadSummary()
  loadCalls()
})
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #fff;
}
.filters {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.filters-label {
  font-size: 13px;
  color: #888;
}
</style>

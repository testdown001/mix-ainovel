<!-- AIMETA P=LLM通道诊断_后台可观测性|R=通道实时健康+配置体检(假冗余/静默失效)+近期调用错误率延迟流水|NR=不含通道配置(在ApiManagement)|E=component:LLMDiagnostics|X=ui|A=管理后台组件|D=vue,naive-ui|S=net -->
<template>
  <div class="llm-diagnostics">
    <!-- 上半：通道实时健康 -->
    <n-card :bordered="false" style="margin-bottom: 16px">
      <template #header>
        <div class="card-header">
          <span class="card-title">🩺 通道实时健康</span>
          <n-space align="center" :size="8">
            <span v-if="healthCheckedAt" class="cache-hint">{{ healthCacheHint }}</span>
            <n-button type="primary" size="small" :loading="healthLoading" @click="loadHealth(true)">
              一键检测全部
            </n-button>
          </n-space>
        </div>
      </template>
      <n-spin :show="healthLoading">
        <n-alert type="info" :bordered="false" style="margin-bottom: 16px">
          对每个<b>已配置</b>通道发起一次真实最小调用，验证密钥/地址/模型可达及当前延迟。
          标注「未配置」的通道运行时根本不会被使用（详情里写明少了什么能力），不会拿默认通道冒名顶替。
          检测结果缓存 <b>10 分钟</b>，再次打开本页不会自动实测；点「一键检测全部」或单通道「重测」才会重新打上游。
        </n-alert>
        <n-data-table :columns="healthColumns" :data="health" :bordered="false" size="small" />
      </n-spin>
    </n-card>

    <!-- 中段：配置体检（只读审计，不发请求；与实时健康互补） -->
    <n-card :bordered="false" style="margin-bottom: 16px">
      <template #header>
        <div class="card-header">
          <span class="card-title">🔍 配置体检</span>
          <n-button quaternary size="small" :loading="auditLoading" @click="loadAudit">刷新</n-button>
        </div>
      </template>
      <n-spin :show="auditLoading">
        <n-alert type="info" :bordered="false" style="margin-bottom: 16px">
          实时健康测的是「现在通不通」，体检查的是它测不出的隐患：<b>假冗余</b>（兜底与主通道同一上游，
          供应商整站故障时一起挂）与<b>静默失效</b>（嵌入/搜索未配置时相关能力无声跳过，界面看不出来）。
        </n-alert>
        <n-alert v-if="!auditLoading && findings.length === 0" type="success" :bordered="false">
          未发现配置隐患。
        </n-alert>
        <div v-else class="audit-list">
          <n-alert
            v-for="f in findings"
            :key="f.code"
            :type="auditAlertType(f.level)"
            :bordered="false"
          >
            <template #header>
              <span class="audit-title">{{ f.title }}</span>
              <n-tag
                v-for="c in f.channels"
                :key="c"
                size="tiny"
                :bordered="false"
                style="margin-left: 8px"
              >
                {{ channelLabel(c) }}
              </n-tag>
            </template>
            {{ f.detail }}
          </n-alert>
        </div>
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
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import {
  NAlert, NButton, NCard, NDataTable, NRadioButton, NRadioGroup,
  NSelect, NSpace, NSpin, NTag, type DataTableColumns
} from 'naive-ui'
import {
  AdminAPI,
  type LLMHealthChannel,
  type LLMCallSummaryChannel,
  type LLMCallRow,
  type LLMConfigFinding,
} from '@/api/admin'
import { useAlert } from '@/composables/useAlert'

const { showAlert } = useAlert()

const CHANNEL_LABELS: Record<string, string> = {
  default: '默认', fallback: '兜底', polish: '润色', search: '搜索', grader: '评分', embedding: '向量', rerank: '重排',
}
// 体检发现项还会标注非通道对象（如模型目录），它不是可筛选的调用通道，故不并入
// CHANNEL_LABELS——否则调用流水的通道筛选里会多出一个永远查不到结果的选项。
const AUDIT_ONLY_LABELS: Record<string, string> = { catalog: '模型目录' }
const channelLabel = (c: string) => CHANNEL_LABELS[c] || AUDIT_ONLY_LABELS[c] || c

const channelOptions = Object.entries(CHANNEL_LABELS).map(([value, label]) => ({ label, value }))
const statusOptions = [
  { label: '成功', value: 'success' },
  { label: '错误', value: 'error' },
  { label: '超时', value: 'timeout' },
]

const HEALTH_CACHE_KEY = 'arboris.admin.llm-health'
const HEALTH_CACHE_TTL_MS = 10 * 60 * 1000

type HealthCachePayload = { channels: LLMHealthChannel[]; checkedAt: number }

function readHealthCache(): HealthCachePayload | null {
  try {
    const raw = sessionStorage.getItem(HEALTH_CACHE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as HealthCachePayload
    if (!parsed?.checkedAt || !Array.isArray(parsed.channels)) return null
    if (Date.now() - parsed.checkedAt > HEALTH_CACHE_TTL_MS) return null
    return parsed
  } catch {
    return null
  }
}

function writeHealthCache(channels: LLMHealthChannel[], checkedAt = Date.now()) {
  try {
    sessionStorage.setItem(HEALTH_CACHE_KEY, JSON.stringify({ channels, checkedAt }))
  } catch {
    /* quota / private mode：缓存失败不影响检测本身 */
  }
}

const health = ref<LLMHealthChannel[]>([])
const healthCheckedAt = ref<number | null>(null)
const findings = ref<LLMConfigFinding[]>([])
const auditLoading = ref(false)
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

// Date.now() 不是响应式依赖，直接写进 computed 会让「N 分钟前」停在挂载那一刻；
// 用一个定时推进的 ref 当依赖驱动重算。注意本文件里 window 被 ref 遮蔽，只能用裸 setInterval。
const nowTick = ref(Date.now())
let hintTimer: ReturnType<typeof setInterval> | null = null

const healthCacheHint = computed(() => {
  if (!healthCheckedAt.value) return ''
  const ageMin = Math.max(0, Math.floor((nowTick.value - healthCheckedAt.value) / 60000))
  const time = new Date(healthCheckedAt.value).toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })
  if (ageMin <= 0) return `检测于 ${time}`
  return `检测于 ${time}（${ageMin} 分钟前，10 分钟内不再自动实测）`
})

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
    // 三态：未配置（运行时不会走这条通道，压根没发测试请求）/ 可用 / 不可用。
    // 把「未配置」画成灰色而非红叉，是因为可选通道不配是合法选择，但必须让管理员
    // 看见——否则他会以为这个能力在工作（详情里写了少的是什么能力）。
    title: '状态', key: 'ok', width: 100,
    render: (r) =>
      r.configured === false
        ? h(NTag, { size: 'small', bordered: false }, { default: () => '— 未配置' })
        : h(NTag, { type: r.ok ? 'success' : 'error', size: 'small' }, { default: () => (r.ok ? '✅ 可用' : '❌ 不可用') }),
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

const auditAlertType = (level: LLMConfigFinding['level']) =>
  level === 'error' ? 'error' : level === 'warn' ? 'warning' : 'info'

async function loadAudit() {
  auditLoading.value = true
  try {
    const r = await AdminAPI.getLlmConfigAudit()
    findings.value = r.findings || []
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '配置体检失败', 'error')
  } finally {
    auditLoading.value = false
  }
}

async function loadHealth(force = false) {
  if (!force) {
    const cached = readHealthCache()
    if (cached) {
      health.value = cached.channels
      healthCheckedAt.value = cached.checkedAt
      return
    }
  }
  healthLoading.value = true
  try {
    const r = await AdminAPI.getLlmHealth()
    health.value = r.channels || []
    const checkedAt = Date.now()
    healthCheckedAt.value = checkedAt
    writeHealthCache(health.value, checkedAt)
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
    const row = { channel: channel as any, ...r }
    if (idx >= 0) health.value[idx] = row
    else health.value = [...health.value, row]
    // 只重跑了这一条：批次时钟必须停在上次全量检测的时刻。刷成 now 会让另外几行
    // 陈旧数据冒充「刚检测」，还把 10 分钟自动实测窗口整体后推。
    if (healthCheckedAt.value) writeHealthCache(health.value, healthCheckedAt.value)
    if (r.configured === false) {
      showAlert(`${channelLabel(channel)}未配置：${r.detail}`, 'info')
    } else {
      showAlert(
        r.ok ? `✅ ${channelLabel(channel)}可用（${r.latency_ms}ms）` : `❌ ${channelLabel(channel)}：${r.detail}`,
        r.ok ? 'success' : 'error'
      )
    }
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
  loadHealth(false)
  loadAudit()
  loadSummary()
  loadCalls()
  hintTimer = setInterval(() => { nowTick.value = Date.now() }, 30000)
})

onUnmounted(() => {
  if (hintTimer !== null) clearInterval(hintTimer)
  hintTimer = null
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
.audit-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.audit-title {
  font-weight: 600;
}
.cache-hint {
  font-size: 12px;
  color: #888;
  font-weight: 400;
}
</style>

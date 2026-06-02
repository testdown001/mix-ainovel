<!-- AIMETA P=API管理_模型配置与用量统计|R=多通道LLM配置CRUD(SystemConfig)+可用性测试+用量统计|E=component:ApiManagement|X=ui|A=API管理组件|D=vue|S=dom,net -->
<template>
  <n-space vertical size="large">
    <n-tabs v-model:value="activeTab" type="line" animated>

      <!-- ===== Tab 1: API 配置 ===== -->
      <n-tab-pane name="config" tab="API 配置">
        <n-space vertical size="large" style="margin-top: 16px;">

          <!-- 默认 LLM -->
          <n-card :bordered="false">
            <template #header>
              <div class="card-header">
                <span class="card-title">🤖 默认 LLM 配置</span>
                <n-button quaternary size="small" @click="fetchAllConfigs" :loading="loading">刷新</n-button>
              </div>
            </template>
            <n-spin :show="loading">
              <n-alert type="info" :bordered="false" style="margin-bottom:16px">
                系统默认模型，所有未单独配置的功能均使用此 API。
              </n-alert>
              <n-form label-placement="top">
                <n-grid :cols="2" :x-gap="16">
                  <n-gi><n-form-item label="API Key" required>
                    <n-input v-model:value="defaultForm.api_key" type="password" show-password-on="click" placeholder="必填" />
                  </n-form-item></n-gi>
                  <n-gi><n-form-item label="模型名称">
                    <n-input v-model:value="defaultForm.model" placeholder="例：gpt-4o / claude-opus-4" />
                  </n-form-item></n-gi>
                  <n-gi :span="2"><n-form-item label="Base URL">
                    <n-input v-model:value="defaultForm.base_url" placeholder="例：https://api.openai.com/v1" />
                  </n-form-item></n-gi>
                  <n-gi><n-form-item label="API 格式">
                    <n-select v-model:value="defaultForm.api_format" :options="apiFormatOptions" placeholder="留空自动识别" clearable />
                  </n-form-item></n-gi>
                </n-grid>
                <n-space justify="end">
                  <n-button :loading="testing.default" @click="testChannel('default')">测试连接</n-button>
                  <n-button type="primary" :loading="defaultSaving" @click="saveConfig('default')">保存</n-button>
                </n-space>
              </n-form>
            </n-spin>
          </n-card>

          <!-- 兜底 API -->
          <n-card :bordered="false">
            <template #header>
              <div class="card-header">
                <span class="card-title">🛡️ 兜底 API 配置</span>
                <n-tag :type="fallbackForm.api_key ? 'success' : 'warning'" size="small">
                  {{ fallbackForm.api_key ? '已配置' : '未配置' }}
                </n-tag>
              </div>
            </template>
            <n-spin :show="loading">
              <n-alert type="warning" :bordered="false" style="margin-bottom:16px">
                当默认 API 调用失败（超时、余额不足、限速）时自动切换至此备用 API，保障生成连续性。
              </n-alert>
              <n-form label-placement="top">
                <n-grid :cols="2" :x-gap="16">
                  <n-gi><n-form-item label="API Key">
                    <n-input v-model:value="fallbackForm.api_key" type="password" show-password-on="click" placeholder="留空则不启用兜底" />
                  </n-form-item></n-gi>
                  <n-gi><n-form-item label="模型名称">
                    <n-input v-model:value="fallbackForm.model" placeholder="例：gpt-4o-mini" />
                  </n-form-item></n-gi>
                  <n-gi :span="2"><n-form-item label="Base URL">
                    <n-input v-model:value="fallbackForm.base_url" placeholder="例：https://api.openai.com/v1" />
                  </n-form-item></n-gi>
                  <n-gi><n-form-item label="API 格式">
                    <n-select v-model:value="fallbackForm.api_format" :options="apiFormatOptions" placeholder="留空自动识别" clearable />
                  </n-form-item></n-gi>
                </n-grid>
                <n-space justify="end">
                  <n-button :loading="testing.fallback" @click="testChannel('fallback')">测试连接</n-button>
                  <n-button type="primary" :loading="fallbackSaving" @click="saveConfig('fallback')">保存</n-button>
                </n-space>
              </n-form>
            </n-spin>
          </n-card>

          <!-- 润色优化模型 -->
          <n-card :bordered="false">
            <template #header>
              <div class="card-header">
                <span class="card-title">✨ 润色优化模型</span>
                <n-tag :type="polishForm.api_key ? 'success' : 'default'" size="small">
                  {{ polishForm.api_key ? '独立配置' : '使用默认' }}
                </n-tag>
              </div>
            </template>
            <n-spin :show="loading">
              <n-alert type="info" :bordered="false" style="margin-bottom:16px">
                配置独立的润色优化模型（推荐擅长角色扮演的微调模型）。留空则自动使用默认 LLM。
              </n-alert>
              <n-form label-placement="top">
                <n-grid :cols="2" :x-gap="16">
                  <n-gi><n-form-item label="API Key">
                    <n-input v-model:value="polishForm.api_key" type="password" show-password-on="click" placeholder="留空使用默认" />
                  </n-form-item></n-gi>
                  <n-gi><n-form-item label="模型名称">
                    <n-input v-model:value="polishForm.model" placeholder="留空使用默认" />
                  </n-form-item></n-gi>
                  <n-gi :span="2"><n-form-item label="Base URL">
                    <n-input v-model:value="polishForm.base_url" placeholder="留空使用默认" />
                  </n-form-item></n-gi>
                  <n-gi><n-form-item label="API 格式">
                    <n-select v-model:value="polishForm.api_format" :options="apiFormatOptions" placeholder="留空使用默认" clearable />
                  </n-form-item></n-gi>
                </n-grid>
                <n-space justify="end">
                  <n-button :loading="testing.polish" @click="testChannel('polish')">测试连接</n-button>
                  <n-button type="primary" :loading="polishSaving" @click="saveConfig('polish')">保存</n-button>
                </n-space>
              </n-form>
            </n-spin>
          </n-card>

          <!-- 参考小说搜索模型 -->
          <n-card :bordered="false">
            <template #header>
              <div class="card-header">
                <span class="card-title">🔍 参考小说搜索模型</span>
                <n-tag :type="searchForm.api_key ? 'success' : 'default'" size="small">
                  {{ searchForm.api_key ? '已启用' : '未启用' }}
                </n-tag>
              </div>
            </template>
            <n-spin :show="loading">
              <n-alert type="info" :bordered="false" style="margin-bottom:16px">
                配置灵感模式的联网搜索模型（推荐 Grok / Perplexity 等支持联网的模型）。全部留空则关闭联网搜索。
              </n-alert>
              <n-form label-placement="top">
                <n-grid :cols="2" :x-gap="16">
                  <n-gi><n-form-item label="API Key">
                    <n-input v-model:value="searchForm.api_key" type="password" show-password-on="click" placeholder="留空则关闭搜索" />
                  </n-form-item></n-gi>
                  <n-gi><n-form-item label="模型名称">
                    <n-input v-model:value="searchForm.model" placeholder="例：grok-3" />
                  </n-form-item></n-gi>
                  <n-gi :span="2"><n-form-item label="Base URL">
                    <n-input v-model:value="searchForm.base_url" placeholder="例：https://api.x.ai/v1" />
                  </n-form-item></n-gi>
                  <n-gi><n-form-item label="API 格式">
                    <n-select v-model:value="searchForm.api_format" :options="apiFormatOptions" placeholder="留空自动识别" clearable />
                  </n-form-item></n-gi>
                </n-grid>
                <n-space justify="end">
                  <n-button :loading="testing.search" @click="testChannel('search')">测试连接</n-button>
                  <n-button type="primary" :loading="searchSaving" @click="saveConfig('search')">保存</n-button>
                </n-space>
              </n-form>
            </n-spin>
          </n-card>

        </n-space>
      </n-tab-pane>

      <!-- ===== Tab 2: 用量统计 ===== -->
      <n-tab-pane name="usage" tab="用量统计">
        <n-space vertical size="large" style="margin-top: 16px;">

          <!-- 时间范围选择 -->
          <n-card :bordered="false">
            <n-space align="center" justify="space-between" :wrap="true">
              <n-space align="center" :size="12" :wrap="true">
                <span style="color:#888; font-size:13px;">统计周期</span>
                <n-radio-group v-model:value="period" @update:value="onPeriodChange">
                  <n-radio-button value="day">今天</n-radio-button>
                  <n-radio-button value="week">近 7 天</n-radio-button>
                  <n-radio-button value="month">近 30 天</n-radio-button>
                  <n-radio-button value="custom">自定义</n-radio-button>
                </n-radio-group>
                <n-date-picker
                  v-if="period === 'custom'"
                  v-model:value="customRange"
                  type="daterange"
                  clearable
                  style="width:260px"
                  @update:value="fetchStats"
                />
                <n-button quaternary size="small" @click="testChannel('embedding')" :loading="testing.embedding">
                  测试向量模型
                </n-button>
              </n-space>
              <n-button quaternary size="small" @click="fetchStats" :loading="statsLoading">刷新</n-button>
            </n-space>
          </n-card>

          <!-- 汇总卡片 -->
          <n-grid :cols="3" :x-gap="16" :y-gap="16">
            <n-gi>
              <n-card :bordered="false" class="stat-card">
                <div class="stat-icon">🔤</div>
                <n-statistic label="总 Token 消耗（估算）" :value="stats?.grand_total_tokens ?? 0" show-separator>
                  <template #suffix>tokens</template>
                </n-statistic>
              </n-card>
            </n-gi>
            <n-gi>
              <n-card :bordered="false" class="stat-card">
                <div class="stat-icon">⚡</div>
                <n-statistic label="总请求次数" :value="stats?.grand_total_requests ?? 0" show-separator>
                  <template #suffix>次</template>
                </n-statistic>
              </n-card>
            </n-gi>
            <n-gi>
              <n-card :bordered="false" class="stat-card">
                <div class="stat-icon">📅</div>
                <n-statistic label="模型 × 用途" :value="stats?.summary?.length ?? 0" show-separator>
                  <template #suffix>项</template>
                </n-statistic>
              </n-card>
            </n-gi>
          </n-grid>

          <n-alert type="default" :bordered="false" :show-icon="false" style="font-size:12px;color:#888">
            说明：请求次数为精确计数；Token 为中英混合估算值（流式响应无法稳定取得精确用量，向量模型按文本长度估算）。
          </n-alert>

          <!-- 各模型汇总 -->
          <n-card :bordered="false">
            <template #header><span class="card-title">各模型用量汇总</span></template>
            <n-spin :show="statsLoading">
              <n-empty v-if="!stats?.summary?.length && !statsLoading" description="暂无用量数据，发生 API 调用后将自动开始统计">
                <template #icon><span style="font-size:40px">📊</span></template>
              </n-empty>
              <n-data-table v-else :columns="summaryColumns" :data="stats?.summary ?? []" :bordered="false" size="small" />
            </n-spin>
          </n-card>

          <!-- 每日明细 -->
          <n-card :bordered="false">
            <template #header><span class="card-title">每日明细</span></template>
            <n-spin :show="statsLoading">
              <n-empty v-if="!stats?.rows?.length && !statsLoading" description="暂无明细数据">
                <template #icon><span style="font-size:40px">📋</span></template>
              </n-empty>
              <n-data-table v-else :columns="rowColumns" :data="stats?.rows ?? []" :bordered="false" size="small" :pagination="{ pageSize: 20 }" />
            </n-spin>
          </n-card>

        </n-space>
      </n-tab-pane>

    </n-tabs>
  </n-space>
</template>

<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NAlert, NButton, NCard, NDataTable, NDatePicker, NEmpty, NForm, NFormItem,
  NGi, NGrid, NInput, NRadioButton, NRadioGroup, NSelect, NSpace,
  NSpin, NStatistic, NTabPane, NTabs, NTag, type DataTableColumns
} from 'naive-ui'
import { AdminAPI, type ApiUsageStats, type ChannelType } from '@/api/admin'
import { useAlert } from '@/composables/useAlert'

const { showAlert } = useAlert()

// ---- shared ----
const loading = ref(false)
const activeTab = ref('config')

const apiFormatOptions = [
  { label: 'auto（自动识别）', value: 'auto' },
  { label: 'openai', value: 'openai' },
  { label: 'anthropic', value: 'anthropic' },
  { label: 'anyrouter', value: 'anyrouter' },
  { label: 'gemini', value: 'gemini' },
  { label: 'openai-responses', value: 'openai-responses' },
]

// ---- API forms ----
const defaultForm = reactive({ api_key: '', base_url: '', model: '', api_format: null as string | null })
const fallbackForm = reactive({ api_key: '', base_url: '', model: '', api_format: null as string | null })
const polishForm = reactive({ api_key: '', base_url: '', model: '', api_format: null as string | null })
const searchForm = reactive({ api_key: '', base_url: '', model: '', api_format: null as string | null })

const defaultSaving = ref(false)
const fallbackSaving = ref(false)
const polishSaving = ref(false)
const searchSaving = ref(false)

const testing = reactive<Record<ChannelType, boolean>>({
  default: false, fallback: false, polish: false, search: false, embedding: false,
})

const CONFIG_MAP = {
  default:  { prefix: 'llm',           label: '默认 LLM 配置' },
  fallback: { prefix: 'llm_fallback',  label: '兜底 API 配置' },
  polish:   { prefix: 'llm_optimize',  label: '润色优化模型配置' },
  search:   { prefix: 'llm_search',    label: '参考小说搜索模型配置' },
} as const
type ConfigKey = keyof typeof CONFIG_MAP

const getForm = (type: ConfigKey) => {
  return { default: defaultForm, fallback: fallbackForm, polish: polishForm, search: searchForm }[type]
}
const getSaving = (type: ConfigKey) => {
  return { default: defaultSaving, fallback: fallbackSaving, polish: polishSaving, search: searchSaving }[type]
}

const fetchAllConfigs = async () => {
  loading.value = true
  try {
    const allConfigs = await AdminAPI.listSystemConfigs()
    const map = new Map(allConfigs.map((c) => [c.key, c.value]))
    for (const [type, { prefix }] of Object.entries(CONFIG_MAP) as [ConfigKey, { prefix: string; label: string }][]) {
      const form = getForm(type)
      form.api_key = map.get(`${prefix}.api_key`) || ''
      form.base_url = map.get(`${prefix}.base_url`) || ''
      form.model = map.get(`${prefix}.model`) || ''
      form.api_format = map.get(`${prefix}.api_format`) || null
    }
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '加载配置失败', 'error')
  } finally {
    loading.value = false
  }
}

const saveConfig = async (type: ConfigKey) => {
  const { prefix, label } = CONFIG_MAP[type]
  const form = getForm(type)
  const saving = getSaving(type)
  saving.value = true
  try {
    const entries = [
      { key: `${prefix}.api_key`, value: form.api_key, description: `${label} API Key` },
      { key: `${prefix}.base_url`, value: form.base_url, description: `${label} Base URL` },
      { key: `${prefix}.model`, value: form.model, description: `${label} 模型名称` },
      { key: `${prefix}.api_format`, value: form.api_format || '', description: `${label} API 格式` },
    ]
    for (const entry of entries) {
      await AdminAPI.upsertSystemConfig(entry.key, { value: entry.value, description: entry.description })
    }
    showAlert(`${label}已保存`, 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

// ---- 真实可用性测试 ----
const testChannel = async (type: ChannelType) => {
  testing[type] = true
  try {
    const r = await AdminAPI.testLlmChannel(type)
    if (r.ok) {
      showAlert(`✅ 可用：${r.model || '模型'}（${r.latency_ms}ms）${r.detail}`, 'success')
    } else {
      showAlert(`❌ 不可用：${r.detail}`, 'error')
    }
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '测试请求失败', 'error')
  } finally {
    testing[type] = false
  }
}

// ---- Usage stats ----
const period = ref<'day' | 'week' | 'month' | 'custom'>('week')
const customRange = ref<[number, number] | null>(null)
const statsLoading = ref(false)
const stats = ref<ApiUsageStats | null>(null)

const API_TYPE_LABEL: Record<string, string> = {
  default: '默认', fallback: '兜底', polish: '润色', search: '搜索', embedding: '向量', grader: '评分',
}
const apiTypeLabel = (t: string) => API_TYPE_LABEL[t] || t
const formatNum = (n: number) => n.toLocaleString('zh-CN')
const toDateStr = (ms: number) => new Date(ms).toISOString().slice(0, 10)

const onPeriodChange = () => {
  if (period.value !== 'custom') fetchStats()
}

const fetchStats = async () => {
  if (period.value === 'custom' && !customRange.value) return
  statsLoading.value = true
  try {
    stats.value = await AdminAPI.getApiUsageStats({
      period: period.value,
      startDate: customRange.value ? toDateStr(customRange.value[0]) : undefined,
      endDate: customRange.value ? toDateStr(customRange.value[1]) : undefined,
    })
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '加载用量统计失败', 'error')
  } finally {
    statsLoading.value = false
  }
}

const summaryColumns: DataTableColumns = [
  { title: '模型', key: 'model', ellipsis: true, width: 200 },
  { title: '用途', key: 'api_type', width: 80, render: (row: any) => h('span', apiTypeLabel(row.api_type)) },
  { title: '输入 Tokens', key: 'prompt_tokens', align: 'right', render: (row: any) => formatNum(row.prompt_tokens) },
  { title: '输出 Tokens', key: 'completion_tokens', align: 'right', render: (row: any) => formatNum(row.completion_tokens) },
  { title: '总 Tokens', key: 'total_tokens', align: 'right', sorter: 'default',
    render: (row: any) => h('span', { style: 'color:#FFE500; font-weight:600' }, formatNum(row.total_tokens)) },
  { title: '请求次数', key: 'request_count', align: 'right', render: (row: any) => formatNum(row.request_count) },
]

const rowColumns: DataTableColumns = [
  { title: '日期', key: 'log_date', width: 110 },
  { title: '模型', key: 'model', ellipsis: true },
  { title: '用途', key: 'api_type', width: 80, render: (row: any) => h('span', apiTypeLabel(row.api_type)) },
  { title: '输入', key: 'prompt_tokens', align: 'right', render: (row: any) => h('span', { style: 'font-size:12px; color:#aaa' }, formatNum(row.prompt_tokens)) },
  { title: '输出', key: 'completion_tokens', align: 'right', render: (row: any) => h('span', { style: 'font-size:12px; color:#aaa' }, formatNum(row.completion_tokens)) },
  { title: '总 Tokens', key: 'total_tokens', align: 'right', render: (row: any) => h('span', { style: 'color:#FFE500' }, formatNum(row.total_tokens)) },
  { title: '请求次数', key: 'request_count', align: 'right', width: 90, render: (row: any) => formatNum(row.request_count) },
]

onMounted(() => {
  fetchAllConfigs()
  fetchStats()
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
.stat-card {
  text-align: center;
  padding: 8px 0;
}
.stat-icon {
  font-size: 28px;
  margin-bottom: 8px;
}
</style>

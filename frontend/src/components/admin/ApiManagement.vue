<!-- AIMETA P=API管理_模型配置|R=多通道LLM配置CRUD(写入SystemConfig)|E=component:ApiManagement|X=ui|A=API管理组件|D=vue|S=dom,net -->
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
                <n-space justify="end"><n-button type="primary" :loading="defaultSaving" @click="saveConfig('default')">保存</n-button></n-space>
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
                <n-space justify="end"><n-button type="primary" :loading="fallbackSaving" @click="saveConfig('fallback')">保存</n-button></n-space>
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
                <n-space justify="end"><n-button type="primary" :loading="polishSaving" @click="saveConfig('polish')">保存</n-button></n-space>
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
                <n-space justify="end"><n-button type="primary" :loading="searchSaving" @click="saveConfig('search')">保存</n-button></n-space>
              </n-form>
            </n-spin>
          </n-card>

        </n-space>
      </n-tab-pane>

    </n-tabs>
  </n-space>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  NAlert, NButton, NCard, NForm, NFormItem,
  NGi, NGrid, NInput, NSelect, NSpace,
  NSpin, NTabPane, NTabs, NTag
} from 'naive-ui'
import { AdminAPI } from '@/api/admin'
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

onMounted(() => {
  fetchAllConfigs()
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

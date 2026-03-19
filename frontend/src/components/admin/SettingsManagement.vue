<!-- AIMETA P=设置管理_系统设置界面|R=系统配置表单|NR=不含用户设置|E=component:SettingsManagement|X=ui|A=设置组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <n-space vertical size="large" class="admin-settings">
    <n-card :bordered="false" class="settings-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">每日请求额度</span>
          <n-button quaternary size="small" class="refresh-btn" @click="fetchDailyLimit" :loading="dailyLimitLoading">
            刷新
          </n-button>
        </div>
      </template>
      <n-spin :show="dailyLimitLoading">
        <n-alert v-if="dailyLimitError" type="error" closable @close="dailyLimitError = null">
          {{ dailyLimitError }}
        </n-alert>
        <n-form label-placement="top" class="limit-form">
          <n-form-item label="未配置 API Key 的用户每日可用请求次数">
            <n-input-number
              v-model:value="dailyLimit"
              :min="0"
              :step="10"
              placeholder="请输入每日请求上限"
            />
          </n-form-item>
          <n-space justify="end">
            <button class="save-btn" :disabled="dailyLimitSaving" @click="saveDailyLimit">
              {{ dailyLimitSaving ? '保存中...' : '保存设置' }}
            </button>
          </n-space>
        </n-form>
      </n-spin>
    </n-card>

    <n-card :bordered="false" class="settings-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">润色优化模型配置</span>
        </div>
      </template>
      <n-spin :show="polishLoading">
        <n-alert v-if="polishError" type="error" closable @close="polishError = null">
          {{ polishError }}
        </n-alert>
        <div class="info-banner">
          配置独立的润色优化模型（如擅长角色扮演的微调模型）。留空则自动使用默认 LLM 配置。
        </div>
        <n-form label-placement="top" class="polish-form">
          <n-form-item label="API Key">
            <n-input
              v-model:value="polishForm.api_key"
              type="password"
              show-password-on="click"
              placeholder="留空使用默认 API Key"
            />
          </n-form-item>
          <n-form-item label="Base URL">
            <n-input v-model:value="polishForm.base_url" placeholder="留空使用默认 Base URL" />
          </n-form-item>
          <n-form-item label="模型名称">
            <n-input v-model:value="polishForm.model" placeholder="留空使用默认模型" />
          </n-form-item>
          <n-form-item label="API 格式">
            <n-select
              v-model:value="polishForm.api_format"
              :options="apiFormatOptions"
              placeholder="留空使用默认格式"
              clearable
            />
          </n-form-item>
          <n-space justify="end">
            <button class="save-btn" :disabled="polishSaving" @click="savePolishConfig">
              {{ polishSaving ? '保存中...' : '保存设置' }}
            </button>
          </n-space>
        </n-form>
      </n-spin>
    </n-card>

    <n-card :bordered="false" class="settings-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">参考小说搜索模型配置</span>
        </div>
      </template>
      <n-spin :show="searchModelLoading">
        <n-alert v-if="searchModelError" type="error" closable @close="searchModelError = null">
          {{ searchModelError }}
        </n-alert>
        <div class="info-banner">
          配置灵感模式的联网搜索模型。全部留空表示关闭参考小说网络搜索。
        </div>
        <n-form label-placement="top" class="search-form">
          <n-form-item label="API Key">
            <n-input
              v-model:value="searchModelForm.api_key"
              type="password"
              show-password-on="click"
              placeholder="留空表示关闭搜索"
            />
          </n-form-item>
          <n-form-item label="Base URL">
            <n-input v-model:value="searchModelForm.base_url" placeholder="例如：https://api.x.ai/v1" />
          </n-form-item>
          <n-form-item label="模型名称">
            <n-input v-model:value="searchModelForm.model" placeholder="例如：grok-3" />
          </n-form-item>
          <n-form-item label="API 格式">
            <n-select
              v-model:value="searchModelForm.api_format"
              :options="apiFormatOptions"
              placeholder="留空自动识别"
              clearable
            />
          </n-form-item>
          <n-space justify="end">
            <button class="save-btn" :disabled="searchModelSaving" @click="saveSearchModelConfig">
              {{ searchModelSaving ? '保存中...' : '保存设置' }}
            </button>
          </n-space>
        </n-form>
      </n-spin>
    </n-card>

    <n-card :bordered="false" class="settings-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">三省六部 Agent 系统</span>
        </div>
      </template>
      <n-spin :show="agentLoading">
        <n-alert v-if="agentError" type="error" closable @close="agentError = null">
          {{ agentError }}
        </n-alert>
        <div class="info-banner">
          启用后，章节生成将使用三省六部多 Agent 协作系统（太子省 → 中书省 → 尚书省 → 兵部 → 门下省），替代传统单流水线生成。
        </div>
        <n-form label-placement="left" class="agent-form">
          <n-form-item label="启用 Agent 系统">
            <n-switch
              v-model:value="agentEnabled"
              :loading="agentSaving"
              @update:value="saveAgentSetting"
            />
          </n-form-item>
        </n-form>
      </n-spin>
    </n-card>

    <n-card :bordered="false" class="settings-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">系统配置</span>
          <button class="create-btn" @click="openCreateModal">
            新增配置
          </button>
        </div>
      </template>

      <n-spin :show="configLoading">
        <n-alert v-if="configError" type="error" closable @close="configError = null">
          {{ configError }}
        </n-alert>

        <n-data-table
          :columns="columns"
          :data="configs"
          :loading="configLoading"
          :bordered="false"
          :row-key="rowKey"
          class="config-table"
        />
      </n-spin>
    </n-card>
  </n-space>

  <n-modal
    v-model:show="configModalVisible"
    preset="card"
    :title="modalTitle"
    class="config-modal"
    :style="{ width: '520px', maxWidth: '92vw' }"
  >
    <n-form label-placement="top" :model="configForm">
      <n-form-item label="Key">
        <n-input
          v-model:value="configForm.key"
          :disabled="!isCreateMode"
          placeholder="请输入唯一 Key"
        />
      </n-form-item>
      <n-form-item label="值">
        <n-input v-model:value="configForm.value" placeholder="配置的具体值" />
      </n-form-item>
      <n-form-item label="描述">
        <n-input v-model:value="configForm.description" placeholder="配置项的用途说明，可选" />
      </n-form-item>
    </n-form>
    <template #footer>
      <n-space justify="end">
        <n-button quaternary @click="closeConfigModal">取消</n-button>
        <n-button type="primary" :loading="configSaving" @click="submitConfig">
          保存
        </n-button>
      </n-space>
    </template>
  </n-modal>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSelect,
  NSpace,
  NSpin,
  NSwitch,
  type DataTableColumns
} from 'naive-ui'

import {
  AdminAPI,
  type DailyRequestLimit,
  type SystemConfig,
  type SystemConfigUpdatePayload,
  type SystemConfigUpsertPayload
} from '@/api/admin'
import { useAlert } from '@/composables/useAlert'

const { showAlert } = useAlert()

const dailyLimit = ref<number | null>(null)
const dailyLimitLoading = ref(false)
const dailyLimitSaving = ref(false)
const dailyLimitError = ref<string | null>(null)

const configs = ref<SystemConfig[]>([])
const configLoading = ref(false)
const configSaving = ref(false)
const configError = ref<string | null>(null)

// ---- 润色优化模型配置 ----
const polishLoading = ref(false)
const polishSaving = ref(false)
const polishError = ref<string | null>(null)
const polishForm = reactive({
  api_key: '',
  base_url: '',
  model: '',
  api_format: null as string | null
})
const apiFormatOptions = [
  { label: 'auto（自动识别）', value: 'auto' },
  { label: 'openai', value: 'openai' },
  { label: 'anthropic', value: 'anthropic' },
  { label: 'anyrouter', value: 'anyrouter' },
  { label: 'gemini', value: 'gemini' },
  { label: 'openai-responses', value: 'openai-responses' }
]

const POLISH_CONFIG_KEYS = [
  'llm_optimize.api_key',
  'llm_optimize.base_url',
  'llm_optimize.model',
  'llm_optimize.api_format'
] as const

const fetchPolishConfig = async () => {
  polishLoading.value = true
  polishError.value = null
  try {
    const allConfigs = await AdminAPI.listSystemConfigs()
    const configMap = new Map(allConfigs.map((c) => [c.key, c.value]))
    polishForm.api_key = configMap.get('llm_optimize.api_key') || ''
    polishForm.base_url = configMap.get('llm_optimize.base_url') || ''
    polishForm.model = configMap.get('llm_optimize.model') || ''
    polishForm.api_format = configMap.get('llm_optimize.api_format') || null
  } catch (err) {
    polishError.value = err instanceof Error ? err.message : '加载润色模型配置失败'
  } finally {
    polishLoading.value = false
  }
}

// ---- 参考小说搜索模型配置 ----
const searchModelLoading = ref(false)
const searchModelSaving = ref(false)
const searchModelError = ref<string | null>(null)
const searchModelForm = reactive({
  api_key: '',
  base_url: '',
  model: '',
  api_format: null as string | null
})

const fetchSearchModelConfig = async () => {
  searchModelLoading.value = true
  searchModelError.value = null
  try {
    const allConfigs = await AdminAPI.listSystemConfigs()
    const configMap = new Map(allConfigs.map((c) => [c.key, c.value]))
    searchModelForm.api_key = configMap.get('llm_search.api_key') || ''
    searchModelForm.base_url = configMap.get('llm_search.base_url') || ''
    searchModelForm.model = configMap.get('llm_search.model') || ''
    searchModelForm.api_format = configMap.get('llm_search.api_format') || null
  } catch (err) {
    searchModelError.value = err instanceof Error ? err.message : '加载搜索模型配置失败'
  } finally {
    searchModelLoading.value = false
  }
}

const saveSearchModelConfig = async () => {
  searchModelSaving.value = true
  try {
    const entries: Array<{ key: string; value: string; description: string }> = [
      { key: 'llm_search.api_key', value: searchModelForm.api_key, description: '参考小说搜索专用 API Key' },
      { key: 'llm_search.base_url', value: searchModelForm.base_url, description: '参考小说搜索专用 Base URL' },
      { key: 'llm_search.model', value: searchModelForm.model, description: '参考小说搜索专用模型名称' },
      { key: 'llm_search.api_format', value: searchModelForm.api_format || '', description: '参考小说搜索专用 API 格式' }
    ]
    for (const entry of entries) {
      await AdminAPI.upsertSystemConfig(entry.key, {
        value: entry.value,
        description: entry.description
      })
    }
    showAlert('参考小说搜索模型配置已保存', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    searchModelSaving.value = false
  }
}

const savePolishConfig = async () => {
  polishSaving.value = true
  try {
    const entries: Array<{ key: string; value: string; description: string }> = [
      { key: 'llm_optimize.api_key', value: polishForm.api_key, description: '润色优化专用 API Key' },
      { key: 'llm_optimize.base_url', value: polishForm.base_url, description: '润色优化专用 Base URL' },
      { key: 'llm_optimize.model', value: polishForm.model, description: '润色优化专用模型名称' },
      { key: 'llm_optimize.api_format', value: polishForm.api_format || '', description: '润色优化专用 API 格式' }
    ]
    for (const entry of entries) {
      await AdminAPI.upsertSystemConfig(entry.key, {
        value: entry.value,
        description: entry.description
      })
    }
    showAlert('润色模型配置已保存', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    polishSaving.value = false
  }
}

// ---- 三省六部 Agent 系统开关 ----
const agentLoading = ref(false)
const agentSaving = ref(false)
const agentError = ref<string | null>(null)
const agentEnabled = ref(false)

const AGENT_CONFIG_KEY = 'enable_agent_system'

const fetchAgentSetting = async () => {
  agentLoading.value = true
  agentError.value = null
  try {
    const allConfigs = await AdminAPI.listSystemConfigs()
    const cfg = allConfigs.find(c => c.key === AGENT_CONFIG_KEY)
    agentEnabled.value = cfg?.value === 'true'
  } catch (err) {
    agentError.value = err instanceof Error ? err.message : '加载 Agent 配置失败'
  } finally {
    agentLoading.value = false
  }
}

const saveAgentSetting = async (val: boolean) => {
  agentSaving.value = true
  try {
    await AdminAPI.upsertSystemConfig(AGENT_CONFIG_KEY, {
      value: val ? 'true' : 'false',
      description: '是否启用三省六部多 Agent 系统生成章节'
    })
    showAlert(val ? '已启用三省六部 Agent 系统' : '已关闭三省六部 Agent 系统', 'success')
  } catch (err) {
    agentEnabled.value = !val
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    agentSaving.value = false
  }
}

const configModalVisible = ref(false)
const isCreateMode = ref(true)
const configForm = reactive<SystemConfig>({
  key: '',
  value: '',
  description: ''
})

const rowKey = (row: SystemConfig) => row.key

const modalTitle = computed(() => (isCreateMode.value ? '新增配置项' : '编辑配置项'))

const fetchDailyLimit = async () => {
  dailyLimitLoading.value = true
  dailyLimitError.value = null
  try {
    const result = await AdminAPI.getDailyRequestLimit()
    dailyLimit.value = result.limit
  } catch (err) {
    dailyLimitError.value = err instanceof Error ? err.message : '加载每日限制失败'
  } finally {
    dailyLimitLoading.value = false
  }
}

const saveDailyLimit = async () => {
  if (dailyLimit.value === null || dailyLimit.value < 0) {
    showAlert('请设置有效的每日额度', 'error')
    return
  }
  dailyLimitSaving.value = true
  try {
    await AdminAPI.setDailyRequestLimit(dailyLimit.value)
    showAlert('每日额度已更新', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    dailyLimitSaving.value = false
  }
}

const fetchConfigs = async () => {
  configLoading.value = true
  configError.value = null
  try {
    configs.value = await AdminAPI.listSystemConfigs()
  } catch (err) {
    configError.value = err instanceof Error ? err.message : '加载配置失败'
  } finally {
    configLoading.value = false
  }
}

const openCreateModal = () => {
  isCreateMode.value = true
  configForm.key = ''
  configForm.value = ''
  configForm.description = ''
  configModalVisible.value = true
}

const openEditModal = (config: SystemConfig) => {
  isCreateMode.value = false
  configForm.key = config.key
  configForm.value = config.value
  configForm.description = config.description || ''
  configModalVisible.value = true
}

const closeConfigModal = () => {
  configModalVisible.value = false
  configSaving.value = false
}

const submitConfig = async () => {
  if (!configForm.key.trim() || !configForm.value.trim()) {
    showAlert('Key 与 Value 均为必填项', 'error')
    return
  }
  configSaving.value = true
  try {
    let updated: SystemConfig
    if (isCreateMode.value) {
      updated = await AdminAPI.upsertSystemConfig(configForm.key.trim(), {
        value: configForm.value,
        description: configForm.description || undefined
      })
      configs.value.unshift(updated)
    } else {
      updated = await AdminAPI.patchSystemConfig(configForm.key, {
        value: configForm.value,
        description: configForm.description || undefined
      } as SystemConfigUpdatePayload)
      const index = configs.value.findIndex((item) => item.key === updated.key)
      if (index !== -1) {
        configs.value.splice(index, 1, updated)
      }
    }
    showAlert('配置已保存', 'success')
    closeConfigModal()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    configSaving.value = false
  }
}

const deleteConfig = async (key: string) => {
  try {
    await AdminAPI.deleteSystemConfig(key)
    configs.value = configs.value.filter((item) => item.key !== key)
    showAlert('配置已删除', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '删除失败', 'error')
  }
}

const columns: DataTableColumns<SystemConfig> = [
  {
    title: 'Key',
    key: 'key',
    width: 220,
    ellipsis: { tooltip: true }
  },
  {
    title: '值',
    key: 'value',
    ellipsis: { tooltip: true }
  },
  {
    title: '描述',
    key: 'description',
    ellipsis: { tooltip: true },
    render(row) {
      return row.description || '—'
    }
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    width: 160,
    render(row) {
      return h(
        NSpace,
        { justify: 'center', size: 'small' },
        {
          default: () => [
            h(
              NButton,
              {
                size: 'small',
                type: 'primary',
                tertiary: true,
                onClick: () => openEditModal(row)
              },
              { default: () => '编辑' }
            ),
            h(
              NPopconfirm,
              {
                'positive-text': '删除',
                'negative-text': '取消',
                type: 'error',
                placement: 'left',
                onPositiveClick: () => deleteConfig(row.key)
              },
              {
                default: () => '确认删除该配置项？',
                trigger: () =>
                  h(
                    NButton,
                    { size: 'small', type: 'error', quaternary: true },
                    { default: () => '删除' }
                  )
              }
            )
          ]
        }
      )
    }
  }
]

onMounted(() => {
  fetchDailyLimit()
  fetchPolishConfig()
  fetchSearchModelConfig()
  fetchAgentSetting()
  fetchConfigs()
})
</script>

<style scoped>
.admin-settings {
  width: 100%;
}

.settings-card {
  background: #0f1419;
  border-radius: 4px;
  border: 1px solid rgba(77, 70, 50, 0.15);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.card-title {
  font-family: var(--ar-font-display);
  font-size: 1.25rem;
  font-weight: 600;
  color: #FACC15;
}

.refresh-btn {
  color: #8b929a !important;
}

.refresh-btn:hover {
  color: #FACC15 !important;
}

.create-btn {
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 600;
  color: #000;
  background: #FACC15;
  border: none;
  border-radius: 4px;
  padding: 6px 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.create-btn:hover {
  background: #eab308;
  box-shadow: 0 0 14px rgba(250, 204, 21, 0.2);
}

.save-btn {
  font-family: var(--ar-font-ui);
  font-size: 0.85rem;
  font-weight: 600;
  color: #000;
  background: #FACC15;
  border: none;
  border-radius: 4px;
  padding: 8px 20px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.save-btn:hover:not(:disabled) {
  background: #eab308;
  box-shadow: 0 0 14px rgba(250, 204, 21, 0.2);
}

.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.info-banner {
  font-family: var(--ar-font-ui);
  font-size: 0.85rem;
  color: #8b929a;
  background: #171c22;
  border: 1px solid rgba(77, 70, 50, 0.15);
  border-left: 2px solid #4ADE80;
  border-radius: 4px;
  padding: 12px 16px;
  margin-bottom: 20px;
  line-height: 1.6;
}

.limit-form {
  max-width: 360px;
}

.polish-form {
  max-width: 480px;
}

.search-form {
  max-width: 480px;
}

.agent-form {
  max-width: 360px;
}

.config-modal {
  max-width: min(640px, 92vw);
}

:deep(.n-card > .n-card-header) {
  border-bottom: 1px solid rgba(77, 70, 50, 0.15);
}

:deep(.n-card) {
  --n-color: #0f1419;
  --n-color-embedded: #171c22;
  --n-text-color: #dee3eb;
  --n-title-text-color: #dee3eb;
  border-radius: 4px;
}

:deep(.n-form-item .n-form-item-label) {
  color: #8b929a;
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

:deep(.n-input) {
  --n-color: #252a30;
  --n-color-focus: #252a30;
  --n-color-disabled: #171c22;
  --n-border: 1px solid rgba(77, 70, 50, 0.15);
  --n-border-focus: 1px solid rgba(250, 204, 21, 0.4);
  --n-border-disabled: 1px solid rgba(77, 70, 50, 0.1);
  --n-text-color: #dee3eb;
  --n-text-color-disabled: #545d68;
  --n-placeholder-color: #545d68;
  --n-caret-color: #FACC15;
  border-radius: 4px;
}

:deep(.n-input-number) {
  --n-color: #252a30;
  --n-color-focus: #252a30;
  --n-border: 1px solid rgba(77, 70, 50, 0.15);
  --n-border-focus: 1px solid rgba(250, 204, 21, 0.4);
  --n-text-color: #dee3eb;
  --n-placeholder-color: #545d68;
  border-radius: 4px;
}

:deep(.n-select) {
  --n-border: 1px solid rgba(77, 70, 50, 0.15);
  --n-border-focus: 1px solid rgba(250, 204, 21, 0.4);
  --n-border-active: 1px solid rgba(250, 204, 21, 0.4);
  --n-color: #252a30;
  --n-color-active: #252a30;
  --n-text-color: #dee3eb;
  --n-placeholder-color: #545d68;
  border-radius: 4px;
}

:deep(.n-switch.n-switch--active) {
  --n-rail-color-active: #FACC15;
}

:deep(.n-button--primary-type) {
  --n-color: #FACC15;
  --n-text-color: #000;
  --n-color-hover: #eab308;
  --n-text-color-hover: #000;
  --n-border: 1px solid #FACC15;
  --n-border-hover: 1px solid #eab308;
}

:deep(.n-data-table .n-data-table-thead) {
  background: #171c22;
}

:deep(.n-data-table .n-data-table-th) {
  color: #8b929a;
  font-family: var(--ar-font-ui);
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid rgba(77, 70, 50, 0.15) !important;
  background: transparent;
}

:deep(.n-data-table .n-data-table-td) {
  color: #dee3eb;
  border-bottom: 1px solid rgba(77, 70, 50, 0.1) !important;
  background: transparent;
}

:deep(.n-data-table .n-data-table-tr:hover .n-data-table-td) {
  background: #171c22 !important;
}

:deep(.n-data-table) {
  --n-td-color: transparent;
  --n-th-color: transparent;
  --n-border-color: rgba(77, 70, 50, 0.15);
  --n-td-color-hover: #171c22;
}

:deep(.n-alert) {
  border-radius: 4px;
}

:deep(.n-modal .n-card) {
  background: #171c22;
  border: 1px solid rgba(77, 70, 50, 0.25);
  border-radius: 4px;
}

:deep(.n-modal .n-card-header__main) {
  font-family: var(--ar-font-display);
  color: #FACC15;
}

@media (max-width: 767px) {
  .card-title {
    font-size: 1.125rem;
  }
}
</style>

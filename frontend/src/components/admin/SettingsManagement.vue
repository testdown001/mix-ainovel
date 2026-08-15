<!-- AIMETA P=设置管理_系统设置界面|R=系统配置表单|NR=不含用户设置|E=component:SettingsManagement|X=ui|A=设置组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <n-space vertical size="large" class="admin-settings">
    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <span class="card-title">每日请求额度</span>
          <n-button quaternary size="small" @click="fetchDailyLimit" :loading="dailyLimitLoading">
            刷新
          </n-button>
        </div>
      </template>
      <n-spin :show="dailyLimitLoading">
        <n-alert v-if="dailyLimitError" type="error" closable @close="dailyLimitError = null">
          {{ dailyLimitError }}
        </n-alert>
        <n-form label-placement="top" class="limit-form">
          <n-form-item label="每位用户每日可用请求次数">
            <n-input-number
              v-model:value="dailyLimit"
              :min="0"
              :step="10"
              placeholder="请输入每日请求上限"
            />
          </n-form-item>
          <n-space justify="end">
            <n-button type="primary" :loading="dailyLimitSaving" @click="saveDailyLimit">
              保存设置
            </n-button>
          </n-space>
        </n-form>
      </n-spin>
    </n-card>

    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <span class="card-title">每日创建小说上限</span>
          <n-button quaternary size="small" @click="fetchNovelLimit" :loading="novelLimitLoading">
            刷新
          </n-button>
        </div>
      </template>
      <n-spin :show="novelLimitLoading">
        <n-alert v-if="novelLimitError" type="error" closable @close="novelLimitError = null">
          {{ novelLimitError }}
        </n-alert>
        <n-alert type="info" :bordered="false" style="margin-bottom: 16px">
          限制每个用户每天最多创建的小说数量，防止滥用。设置为 0 表示不限制。
        </n-alert>
        <n-form label-placement="top" class="limit-form">
          <n-form-item label="每用户每日创建上限">
            <n-input-number
              v-model:value="novelDailyLimit"
              :min="0"
              :step="1"
              placeholder="默认 5"
            />
          </n-form-item>
          <n-space justify="end">
            <n-button type="primary" :loading="novelLimitSaving" @click="saveNovelLimit">
              保存设置
            </n-button>
          </n-space>
        </n-form>
      </n-spin>
    </n-card>

    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <span class="card-title">自创先进多 Agent 架构</span>
        </div>
      </template>
      <n-spin :show="agentLoading">
        <n-alert v-if="agentError" type="error" closable @close="agentError = null">
          {{ agentError }}
        </n-alert>
        <n-alert type="info" :bordered="false" style="margin-bottom: 16px">
          启用后，章节生成将使用自创先进多 Agent 架构，联动规划、技能、上下文、生成与审核模块，替代传统单流水线生成。
        </n-alert>
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

    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <span class="card-title">注册人机验证 (Turnstile)</span>
        </div>
      </template>
      <n-spin :show="captchaLoading">
        <n-alert v-if="captchaError" type="error" closable @close="captchaError = null">
          {{ captchaError }}
        </n-alert>
        <n-alert type="info" :bordered="false" style="margin-bottom: 16px">
          启用后，用户注册时需完成 Cloudflare Turnstile 人机验证。请前往
          <a href="https://dash.cloudflare.com/sign-up?to=/:account/turnstile" target="_blank" rel="noopener" style="color: #63e2b7;">Cloudflare Dashboard</a>
          获取 Site Key 和 Secret Key。
        </n-alert>
        <n-form label-placement="top" class="captcha-form">
          <n-form-item label="启用人机验证">
            <n-switch v-model:value="captchaEnabled" />
          </n-form-item>
          <n-form-item label="Site Key（前端）">
            <n-input v-model:value="captchaForm.site_key" placeholder="Turnstile Site Key" />
          </n-form-item>
          <n-form-item label="Secret Key（后端）">
            <n-input
              v-model:value="captchaForm.secret_key"
              type="password"
              show-password-on="click"
              placeholder="Turnstile Secret Key"
            />
          </n-form-item>
          <n-space justify="end">
            <n-button type="primary" :loading="captchaSaving" @click="saveCaptchaConfig">
              保存设置
            </n-button>
          </n-space>
        </n-form>
      </n-spin>
    </n-card>

    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <span class="card-title">积分单价</span>
          <n-button quaternary size="small" :loading="creditPriceLoading" @click="fetchCreditPrices">
            刷新
          </n-button>
        </div>
      </template>
      <n-spin :show="creditPriceLoading">
        <n-alert v-if="creditPriceError" type="error" closable @close="creditPriceError = null">
          {{ creditPriceError }}
        </n-alert>
        <n-alert type="info" :bordered="false" style="margin-bottom: 16px">
          润色与蓝图深度打磨的积分单价，对应 SystemConfig
          <code>credits.price.polish</code> /
          <code>credits.price.blueprint_deep</code>。快速成书不扣费。
        </n-alert>
        <n-form label-placement="top" class="polish-form">
          <n-form-item label="润色附加（每章）">
            <n-input-number v-model:value="polishPrice" :min="0" :step="1" />
          </n-form-item>
          <n-form-item label="蓝图深度打磨">
            <n-input-number v-model:value="blueprintDeepPrice" :min="0" :step="1" />
          </n-form-item>
          <n-space justify="end">
            <n-button type="primary" :loading="creditPriceSaving" @click="saveCreditPrices">
              保存单价
            </n-button>
          </n-space>
        </n-form>
      </n-spin>
    </n-card>

    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <span class="card-title">系统配置</span>
          <n-button type="primary" size="small" @click="openCreateModal">
            新增配置
          </n-button>
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

const novelDailyLimit = ref<number | null>(5)
const novelLimitLoading = ref(false)
const novelLimitSaving = ref(false)
const novelLimitError = ref<string | null>(null)

const configs = ref<SystemConfig[]>([])
const configLoading = ref(false)
const configSaving = ref(false)
const configError = ref<string | null>(null)

const creditPriceLoading = ref(false)
const creditPriceSaving = ref(false)
const creditPriceError = ref<string | null>(null)
const polishPrice = ref<number>(5)
const blueprintDeepPrice = ref<number>(20)

const CREDIT_PRICE_KEYS = {
  polish: 'credits.price.polish',
  blueprintDeep: 'credits.price.blueprint_deep',
}

const fetchCreditPrices = async () => {
  creditPriceLoading.value = true
  creditPriceError.value = null
  try {
    const allConfigs = await AdminAPI.listSystemConfigs()
    const map = new Map(allConfigs.map((c) => [c.key, c.value]))
    const polish = Number(map.get(CREDIT_PRICE_KEYS.polish))
    const deep = Number(map.get(CREDIT_PRICE_KEYS.blueprintDeep))
    polishPrice.value = Number.isFinite(polish) ? polish : 5
    blueprintDeepPrice.value = Number.isFinite(deep) ? deep : 20
  } catch (err) {
    creditPriceError.value = err instanceof Error ? err.message : '加载积分单价失败'
  } finally {
    creditPriceLoading.value = false
  }
}

const saveCreditPrices = async () => {
  creditPriceSaving.value = true
  try {
    await AdminAPI.upsertSystemConfig(CREDIT_PRICE_KEYS.polish, {
      value: String(Math.max(0, Math.floor(polishPrice.value ?? 0))),
      description: '润色(humanize/polish)附加积分单价，默认不勾选；勾选时每章额外扣此积分。',
    })
    await AdminAPI.upsertSystemConfig(CREDIT_PRICE_KEYS.blueprintDeep, {
      value: String(Math.max(0, Math.floor(blueprintDeepPrice.value ?? 0))),
      description: '蓝图深度打磨积分单价。仅实际跑审稿/修订时扣费；快速成书免费。',
    })
    showAlert('积分单价已保存', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    creditPriceSaving.value = false
  }
}

// ---- 注册人机验证 (Turnstile) ----
const captchaLoading = ref(false)
const captchaSaving = ref(false)
const captchaError = ref<string | null>(null)
const captchaEnabled = ref(false)
const captchaForm = reactive({
  site_key: '',
  secret_key: ''
})

const CAPTCHA_CONFIG_KEYS = {
  enabled: 'captcha.enabled',
  site_key: 'captcha.site_key',
  secret_key: 'captcha.secret_key'
}

const fetchCaptchaConfig = async () => {
  captchaLoading.value = true
  captchaError.value = null
  try {
    const allConfigs = await AdminAPI.listSystemConfigs()
    const configMap = new Map(allConfigs.map((c) => [c.key, c.value]))
    captchaEnabled.value = configMap.get(CAPTCHA_CONFIG_KEYS.enabled) === 'true'
    captchaForm.site_key = configMap.get(CAPTCHA_CONFIG_KEYS.site_key) || ''
    captchaForm.secret_key = configMap.get(CAPTCHA_CONFIG_KEYS.secret_key) || ''
  } catch (err) {
    captchaError.value = err instanceof Error ? err.message : '加载人机验证配置失败'
  } finally {
    captchaLoading.value = false
  }
}

const saveCaptchaConfig = async () => {
  captchaSaving.value = true
  try {
    const entries: Array<{ key: string; value: string; description: string }> = [
      { key: CAPTCHA_CONFIG_KEYS.enabled, value: captchaEnabled.value ? 'true' : 'false', description: '是否启用注册人机验证' },
      { key: CAPTCHA_CONFIG_KEYS.site_key, value: captchaForm.site_key, description: 'Cloudflare Turnstile Site Key' },
      { key: CAPTCHA_CONFIG_KEYS.secret_key, value: captchaForm.secret_key, description: 'Cloudflare Turnstile Secret Key' }
    ]
    for (const entry of entries) {
      await AdminAPI.upsertSystemConfig(entry.key, {
        value: entry.value,
        description: entry.description
      })
    }
    showAlert('人机验证配置已保存', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    captchaSaving.value = false
  }
}

// ---- 自创先进多 Agent 架构开关 ----
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
      description: '是否启用自创先进多 Agent 架构生成章节'
    })
    showAlert(val ? '已启用自创先进多 Agent 架构' : '已关闭自创先进多 Agent 架构', 'success')
  } catch (err) {
    // 保存失败时回滚开关状态
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

const NOVEL_LIMIT_KEY = 'novel.daily_create_limit'

const fetchNovelLimit = async () => {
  novelLimitLoading.value = true
  novelLimitError.value = null
  try {
    const allConfigs = await AdminAPI.listSystemConfigs()
    const cfg = allConfigs.find(c => c.key === NOVEL_LIMIT_KEY)
    novelDailyLimit.value = cfg ? parseInt(cfg.value, 10) : 5
  } catch (err) {
    novelLimitError.value = err instanceof Error ? err.message : '加载每日创建上限失败'
  } finally {
    novelLimitLoading.value = false
  }
}

const saveNovelLimit = async () => {
  if (novelDailyLimit.value === null || novelDailyLimit.value < 0) {
    showAlert('请设置有效的每日创建上限', 'error')
    return
  }
  novelLimitSaving.value = true
  try {
    await AdminAPI.upsertSystemConfig(NOVEL_LIMIT_KEY, {
      value: String(novelDailyLimit.value),
      description: '每用户每日最多创建小说数量'
    })
    showAlert('每日创建上限已更新', 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    novelLimitSaving.value = false
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
  fetchNovelLimit()
  fetchAgentSetting()
  fetchCaptchaConfig()
  fetchCreditPrices()
  fetchConfigs()
})
</script>

<style scoped>
.admin-settings {
  width: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #FFFFFF;
  font-family: 'Space Grotesk', sans-serif;
}

.limit-form {
  max-width: 360px;
}

.llm-form {
  max-width: 480px;
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

.captcha-form {
  max-width: 480px;
}

.config-modal {
  max-width: min(640px, 92vw);
}

@media (max-width: 767px) {
  .card-title {
    font-size: 1.125rem;
  }
}
</style>

<template>
  <n-space vertical size="large" class="payment-channels">
    <!-- Stripe -->
    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <div class="channel-header-left">
            <div class="channel-logo stripe-logo">S</div>
            <div>
              <div class="card-title">Stripe</div>
              <div class="card-subtitle">国际信用卡 / 借记卡支付</div>
            </div>
          </div>
          <n-space align="center" :size="12">
            <n-tag :type="savedEnabled.stripe ? 'success' : 'default'" size="small" round>
              {{ savedEnabled.stripe ? '已启用' : '未启用' }}
            </n-tag>
            <n-switch :value="stripeForm.enabled" :loading="toggling.stripe" :disabled="!loaded" @update:value="(v: boolean) => onToggleEnabled('stripe', v)" />
          </n-space>
        </div>
      </template>
      <n-spin :show="stripeLoading">
        <n-alert v-if="stripeError" type="error" closable @close="stripeError = null" style="margin-bottom:16px">
          <n-space align="center" :size="12">
            <span>{{ stripeError }}</span>
            <n-button v-if="!loaded" size="small" :loading="stripeLoading" @click="loadChannels">重试</n-button>
          </n-space>
        </n-alert>
        <n-form label-placement="top" :model="stripeForm">
          <n-grid :cols="2" :x-gap="16">
            <n-gi>
              <n-form-item label="Publishable Key（公钥）">
                <n-input
                  v-model:value="stripeForm.publishable_key"
                  placeholder="pk_live_..."
                  :input-props="{ autocomplete: 'off' }"
                />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="Secret Key（私钥）" feedback="留空保持已存值不变">
                <n-input
                  v-model:value="stripeForm.secret_key"
                  type="password"
                  show-password-on="click"
                  placeholder="sk_live_..."
                  :input-props="{ autocomplete: 'off' }"
                />
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-grid :cols="2" :x-gap="16">
            <n-gi>
              <n-form-item label="Webhook Secret" feedback="留空保持已存值不变">
                <n-input
                  v-model:value="stripeForm.webhook_secret"
                  type="password"
                  show-password-on="click"
                  placeholder="whsec_..."
                  :input-props="{ autocomplete: 'off' }"
                />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="运行模式">
                <n-radio-group v-model:value="stripeForm.mode">
                  <n-radio value="test">测试模式</n-radio>
                  <n-radio value="live">生产模式</n-radio>
                </n-radio-group>
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-grid :cols="3" :x-gap="16">
            <n-gi>
              <n-form-item label="结算货币">
                <n-input v-model:value="stripeForm.currency" placeholder="usd / eur / hkd ..." />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="支付成功跳转">
                <n-input v-model:value="stripeForm.success_url" placeholder="https://你的域名/pay/success" />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="支付取消跳转">
                <n-input v-model:value="stripeForm.cancel_url" placeholder="https://你的域名/pay/cancel" />
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-alert type="info" :show-icon="false" style="margin-bottom:12px">
            Webhook 地址（在 Stripe 后台配置）：<code>https://你的域名/api/payment/stripe/webhook</code>，事件选 checkout.session.completed。
          </n-alert>
          <n-space justify="end">
            <n-button type="primary" :disabled="!loaded" :loading="stripeSaving" @click="saveChannel('stripe')">
              保存配置
            </n-button>
          </n-space>
        </n-form>
      </n-spin>
    </n-card>

    <!-- Alipay -->
    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <div class="channel-header-left">
            <div class="channel-logo alipay-logo">支</div>
            <div>
              <div class="card-title">支付宝</div>
              <div class="card-subtitle">Alipay · 国内支付首选</div>
            </div>
          </div>
          <n-space align="center" :size="12">
            <n-tag :type="savedEnabled.alipay ? 'success' : 'default'" size="small" round>
              {{ savedEnabled.alipay ? '已启用' : '未启用' }}
            </n-tag>
            <n-switch :value="alipayForm.enabled" :loading="toggling.alipay" :disabled="!loaded" @update:value="(v: boolean) => onToggleEnabled('alipay', v)" />
          </n-space>
        </div>
      </template>
      <n-spin :show="alipayLoading">
        <n-alert v-if="alipayError" type="error" closable @close="alipayError = null" style="margin-bottom:16px">
          <n-space align="center" :size="12">
            <span>{{ alipayError }}</span>
            <n-button v-if="!loaded" size="small" :loading="alipayLoading" @click="loadChannels">重试</n-button>
          </n-space>
        </n-alert>
        <n-form label-placement="top" :model="alipayForm">
          <n-grid :cols="2" :x-gap="16">
            <n-gi>
              <n-form-item label="App ID">
                <n-input
                  v-model:value="alipayForm.app_id"
                  placeholder="请输入支付宝 App ID"
                  :input-props="{ autocomplete: 'off' }"
                />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="应用私钥（RSA2）" feedback="留空保持已存值不变">
                <n-button v-if="!secretVisible.alipay_private_key" secondary size="small" @click="revealSecret('alipay_private_key')">
                  已配置 · 点击编辑
                </n-button>
                <n-input
                  v-else
                  v-model:value="alipayForm.private_key"
                  type="textarea"
                  :rows="3"
                  placeholder="-----BEGIN RSA PRIVATE KEY-----..."
                  :input-props="{ autocomplete: 'off' }"
                />
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-grid :cols="2" :x-gap="16">
            <n-gi>
              <n-form-item label="支付宝公钥（RSA2）" feedback="留空保持已存值不变">
                <n-button v-if="!secretVisible.alipay_alipay_public_key" secondary size="small" @click="revealSecret('alipay_alipay_public_key')">
                  已配置 · 点击编辑
                </n-button>
                <n-input
                  v-else
                  v-model:value="alipayForm.alipay_public_key"
                  type="textarea"
                  :rows="3"
                  placeholder="填入支付宝平台提供的公钥"
                  :input-props="{ autocomplete: 'off' }"
                />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="异步回调地址（Notify URL）">
                <n-input
                  v-model:value="alipayForm.notify_url"
                  placeholder="https://yourdomain.com/api/payment/alipay/notify"
                />
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-form-item label="运行模式">
            <n-radio-group v-model:value="alipayForm.mode">
              <n-radio value="sandbox">沙箱模式</n-radio>
              <n-radio value="production">生产模式</n-radio>
            </n-radio-group>
          </n-form-item>
          <n-space justify="end">
            <n-button type="primary" :disabled="!loaded" :loading="alipaySaving" @click="saveChannel('alipay')">
              保存配置
            </n-button>
          </n-space>
        </n-form>
      </n-spin>
    </n-card>

    <!-- WeChat Pay -->
    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <div class="channel-header-left">
            <div class="channel-logo wechat-logo">微</div>
            <div>
              <div class="card-title">微信支付</div>
              <div class="card-subtitle">WeChat Pay · 扫码 / JSAPI 支付</div>
            </div>
          </div>
          <n-space align="center" :size="12">
            <n-tag :type="savedEnabled.wechat ? 'success' : 'default'" size="small" round>
              {{ savedEnabled.wechat ? '已启用' : '未启用' }}
            </n-tag>
            <n-switch :value="wechatForm.enabled" :loading="toggling.wechat" :disabled="!loaded" @update:value="(v: boolean) => onToggleEnabled('wechat', v)" />
          </n-space>
        </div>
      </template>
      <n-spin :show="wechatLoading">
        <n-alert v-if="wechatError" type="error" closable @close="wechatError = null" style="margin-bottom:16px">
          <n-space align="center" :size="12">
            <span>{{ wechatError }}</span>
            <n-button v-if="!loaded" size="small" :loading="wechatLoading" @click="loadChannels">重试</n-button>
          </n-space>
        </n-alert>
        <n-form label-placement="top" :model="wechatForm">
          <n-grid :cols="2" :x-gap="16">
            <n-gi>
              <n-form-item label="商户号（Mch ID）">
                <n-input
                  v-model:value="wechatForm.mch_id"
                  placeholder="请输入微信支付商户号"
                  :input-props="{ autocomplete: 'off' }"
                />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="AppID">
                <n-input
                  v-model:value="wechatForm.app_id"
                  placeholder="微信公众号 / 小程序 AppID"
                  :input-props="{ autocomplete: 'off' }"
                />
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-grid :cols="2" :x-gap="16">
            <n-gi>
              <n-form-item label="API v3 密钥" feedback="留空保持已存值不变">
                <n-input
                  v-model:value="wechatForm.api_v3_key"
                  type="password"
                  show-password-on="click"
                  placeholder="32位 API v3 密钥"
                  :input-props="{ autocomplete: 'off' }"
                />
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="证书序列号">
                <n-input
                  v-model:value="wechatForm.serial_no"
                  placeholder="商户证书序列号"
                  :input-props="{ autocomplete: 'off' }"
                />
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-form-item label="商户私钥（PEM）" feedback="留空保持已存值不变">
            <n-button v-if="!secretVisible.wechat_private_key" secondary size="small" @click="revealSecret('wechat_private_key')">
              已配置 · 点击编辑
            </n-button>
            <n-input
              v-else
              v-model:value="wechatForm.private_key"
              type="textarea"
              :rows="3"
              placeholder="-----BEGIN PRIVATE KEY-----..."
              :input-props="{ autocomplete: 'off' }"
            />
          </n-form-item>
          <!-- 「支付方式」多选框已移除：后端只实现 NATIVE 扫码，pay.wechat.pay_methods 从不被读取，勾了也不生效 -->
          <n-grid :cols="2" :x-gap="16">
            <n-gi>
              <n-form-item label="支付方式">
                <n-tag size="small" :bordered="false">Native（扫码）</n-tag>
              </n-form-item>
            </n-gi>
            <n-gi>
              <n-form-item label="回调地址（Notify URL）">
                <n-input
                  v-model:value="wechatForm.notify_url"
                  placeholder="https://yourdomain.com/api/payment/wechat/notify"
                />
              </n-form-item>
            </n-gi>
          </n-grid>
          <n-space justify="end">
            <n-button type="primary" :disabled="!loaded" :loading="wechatSaving" @click="saveChannel('wechat')">
              保存配置
            </n-button>
          </n-space>
        </n-form>
      </n-spin>
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import {
  NSpace, NCard, NButton, NTag, NSwitch, NForm, NFormItem, NInput,
  NSelect, NGrid, NGi, NSpin, NAlert, NRadioGroup, NRadio,
  useMessage
} from 'naive-ui'
import { AdminAPI } from '@/api/admin'

const message = useMessage()

const currencyOptions = [
  { label: 'CNY 人民币', value: 'CNY' },
  { label: 'USD 美元', value: 'USD' },
  { label: 'EUR 欧元', value: 'EUR' },
  { label: 'HKD 港元', value: 'HKD' },
  { label: 'JPY 日元', value: 'JPY' }
]

const stripeForm = reactive({
  enabled: false,
  publishable_key: '',
  secret_key: '',
  webhook_secret: '',
  mode: 'test',
  currency: 'usd',
  success_url: '',
  cancel_url: '',
  currencies: ['CNY', 'USD']
})

const alipayForm = reactive({
  enabled: false,
  app_id: '',
  private_key: '',
  alipay_public_key: '',
  notify_url: '',
  mode: 'sandbox'
})

const wechatForm = reactive({
  enabled: false,
  mch_id: '',
  app_id: '',
  api_v3_key: '',
  serial_no: '',
  private_key: '',
  notify_url: ''
})

const stripeLoading = ref(false)
const stripeSaving = ref(false)
const stripeError = ref<string | null>(null)

const alipayLoading = ref(false)
const alipaySaving = ref(false)
const alipayError = ref<string | null>(null)

const wechatLoading = ref(false)
const wechatSaving = ref(false)
const wechatError = ref<string | null>(null)
// 成功加载过配置才允许保存：表单初始值是空串，加载失败就保存会把已存的私钥清空
const loaded = ref(false)
// 密钥/证书字段：留空 = 保持已存值（不发送该键）；只有填了内容才覆盖
const SECRET_FIELDS: Record<string, Set<string>> = {
  stripe: new Set(['secret_key', 'webhook_secret']),
  alipay: new Set(['private_key', 'alipay_public_key']),
  wechat: new Set(['api_v3_key', 'private_key']),
}

// 启用开关即点即存：原来开关只改表单、标签立刻变「已启用」，不点保存其实什么都没生效
const savedEnabled = reactive<Record<string, boolean>>({ stripe: false, alipay: false, wechat: false })
const toggling = reactive<Record<string, boolean>>({ stripe: false, alipay: false, wechat: false })
const channelName = (channel: string) => channel === 'stripe' ? 'Stripe' : channel === 'alipay' ? '支付宝' : '微信支付'

const onToggleEnabled = async (channel: string, val: boolean) => {
  if (!loaded.value) return
  const form = formOf(channel)
  if (val && channel === 'stripe' && !stripeForm.publishable_key) {
    message.warning('请先填写并保存 Stripe 密钥后再启用')
    return
  }
  form.enabled = val
  toggling[channel] = true
  try {
    await AdminAPI.upsertSystemConfig(`pay.${channel}.enabled`, { value: val ? 'true' : 'false' })
    savedEnabled[channel] = val
    message.success(`${channelName(channel)} 已${val ? '启用' : '停用'}`)
  } catch {
    form.enabled = savedEnabled[channel]
    message.error(`${channelName(channel)} 开关保存失败，已恢复为${savedEnabled[channel] ? '已启用' : '未启用'}`)
  } finally {
    toggling[channel] = false
  }
}

// 私钥/证书 PEM 是多行文本，没有 type=password 可用：已有值时折叠成「已配置 · 点击编辑」，
// 避免整段私钥明文摊在后台页面上；没有值时直接显示输入框
const secretVisible = reactive<Record<string, boolean>>({
  alipay_private_key: true, alipay_alipay_public_key: true, wechat_private_key: true,
})
const revealSecret = (key: string) => { secretVisible[key] = true }
const collapseFilledSecrets = () => {
  secretVisible.alipay_private_key = !alipayForm.private_key
  secretVisible.alipay_alipay_public_key = !alipayForm.alipay_public_key
  secretVisible.wechat_private_key = !wechatForm.private_key
}

// 各渠道表单字段 → 后端 SystemConfig 键（pay.{channel}.{field}）。
// 只持久化后端实际读取的字段（与 PaymentService._get_*_config 对齐）。
const channelKeyFields: Record<string, string[]> = {
  stripe: ['enabled', 'publishable_key', 'secret_key', 'webhook_secret', 'mode', 'currency', 'success_url', 'cancel_url'],
  alipay: ['enabled', 'app_id', 'private_key', 'alipay_public_key', 'notify_url', 'mode'],
  wechat: ['enabled', 'mch_id', 'app_id', 'api_v3_key', 'serial_no', 'private_key', 'notify_url'],
}
const formOf = (channel: string): Record<string, any> =>
  channel === 'stripe' ? stripeForm : channel === 'alipay' ? alipayForm : wechatForm

const loadChannels = async () => {
  stripeLoading.value = true; alipayLoading.value = true; wechatLoading.value = true
  try {
    const list = await AdminAPI.listSystemConfigs()
    const map: Record<string, string> = {}
    for (const c of list || []) map[c.key] = c.value
    for (const [channel, fields] of Object.entries(channelKeyFields)) {
      const form = formOf(channel)
      for (const f of fields) {
        const key = `pay.${channel}.${f}`
        if (key in map) {
          form[f] = f === 'enabled' ? ['1', 'true', 'yes', 'on'].includes((map[key] || '').toLowerCase()) : map[key]
        }
      }
    }
    for (const channel of Object.keys(channelKeyFields)) savedEnabled[channel] = !!formOf(channel).enabled
    collapseFilledSecrets()
    loaded.value = true
    stripeError.value = alipayError.value = wechatError.value = null
  } catch (err) {
    // 以前这里静默吞掉：表单空白但「保存」可点，一保存就把已存的私钥覆盖成空串
    loaded.value = false
    const reason = err instanceof Error ? err.message : '加载配置失败'
    const text = `配置加载失败：${reason}。为避免把已保存的密钥覆盖成空值，已禁用保存。`
    stripeError.value = alipayError.value = wechatError.value = text
  } finally {
    stripeLoading.value = false; alipayLoading.value = false; wechatLoading.value = false
  }
}

const saveChannel = async (channel: string) => {
  const savingRef = channel === 'stripe' ? stripeSaving : channel === 'alipay' ? alipaySaving : wechatSaving
  if (!loaded.value) return
  savingRef.value = true
  try {
    const form = formOf(channel)
    for (const f of channelKeyFields[channel]) {
      const raw = form[f]
      const value = f === 'enabled' ? (raw ? 'true' : 'false') : String(raw ?? '')
      if (SECRET_FIELDS[channel]?.has(f) && !value) continue  // 留空的密钥不发送，保持库内值
      await AdminAPI.upsertSystemConfig(`pay.${channel}.${f}`, { value })
    }
    savedEnabled[channel] = !!form.enabled
    collapseFilledSecrets()
    message.success(`${channelName(channel)} 配置已保存`)
  } catch {
    message.error('保存失败，请重试')
  } finally {
    savingRef.value = false
  }
}

onMounted(loadChannels)
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.channel-header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.card-title {
  font-size: 1rem;
  font-weight: 600;
  color: #fff;
}
.card-subtitle {
  font-size: 0.8rem;
  color: #888;
  margin-top: 2px;
}
.channel-logo {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
}
.stripe-logo {
  background: linear-gradient(135deg, #635BFF, #8B83FF);
}
.alipay-logo {
  background: linear-gradient(135deg, #1677FF, #36A3F7);
}
.wechat-logo {
  background: linear-gradient(135deg, #07C160, #2ED573);
  color: #fff;
}
</style>

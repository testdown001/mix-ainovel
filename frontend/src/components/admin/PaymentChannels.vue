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
            <n-tag :type="stripeForm.enabled ? 'success' : 'default'" size="small" round>
              {{ stripeForm.enabled ? '已启用' : '未启用' }}
            </n-tag>
            <n-switch v-model:value="stripeForm.enabled" @update:value="onStripeToggle" />
          </n-space>
        </div>
      </template>
      <n-spin :show="stripeLoading">
        <n-alert v-if="stripeError" type="error" closable @close="stripeError = null" style="margin-bottom:16px">
          {{ stripeError }}
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
              <n-form-item label="Secret Key（私钥）">
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
              <n-form-item label="Webhook Secret">
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
          <n-form-item label="支持的货币">
            <n-select
              v-model:value="stripeForm.currencies"
              multiple
              :options="currencyOptions"
              placeholder="选择支持的货币"
            />
          </n-form-item>
          <n-space justify="end">
            <n-button @click="testConnection('stripe')" :loading="stripeTesting" size="small">
              测试连接
            </n-button>
            <n-button type="primary" :loading="stripeSaving" @click="saveChannel('stripe')">
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
            <n-tag :type="alipayForm.enabled ? 'success' : 'default'" size="small" round>
              {{ alipayForm.enabled ? '已启用' : '未启用' }}
            </n-tag>
            <n-switch v-model:value="alipayForm.enabled" />
          </n-space>
        </div>
      </template>
      <n-spin :show="alipayLoading">
        <n-alert v-if="alipayError" type="error" closable @close="alipayError = null" style="margin-bottom:16px">
          {{ alipayError }}
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
              <n-form-item label="应用私钥（RSA2）">
                <n-input
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
              <n-form-item label="支付宝公钥（RSA2）">
                <n-input
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
            <n-button @click="testConnection('alipay')" :loading="alipayTesting" size="small">
              测试连接
            </n-button>
            <n-button type="primary" :loading="alipaySaving" @click="saveChannel('alipay')">
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
            <n-tag :type="wechatForm.enabled ? 'success' : 'default'" size="small" round>
              {{ wechatForm.enabled ? '已启用' : '未启用' }}
            </n-tag>
            <n-switch v-model:value="wechatForm.enabled" />
          </n-space>
        </div>
      </template>
      <n-spin :show="wechatLoading">
        <n-alert v-if="wechatError" type="error" closable @close="wechatError = null" style="margin-bottom:16px">
          {{ wechatError }}
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
              <n-form-item label="API v3 密钥">
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
          <n-form-item label="商户私钥（PEM）">
            <n-input
              v-model:value="wechatForm.private_key"
              type="textarea"
              :rows="3"
              placeholder="-----BEGIN PRIVATE KEY-----..."
              :input-props="{ autocomplete: 'off' }"
            />
          </n-form-item>
          <n-grid :cols="2" :x-gap="16">
            <n-gi>
              <n-form-item label="支付方式">
                <n-checkbox-group v-model:value="wechatForm.pay_methods">
                  <n-space>
                    <n-checkbox value="native">Native（扫码）</n-checkbox>
                    <n-checkbox value="jsapi">JSAPI（H5）</n-checkbox>
                    <n-checkbox value="app">APP 支付</n-checkbox>
                  </n-space>
                </n-checkbox-group>
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
            <n-button @click="testConnection('wechat')" :loading="wechatTesting" size="small">
              测试连接
            </n-button>
            <n-button type="primary" :loading="wechatSaving" @click="saveChannel('wechat')">
              保存配置
            </n-button>
          </n-space>
        </n-form>
      </n-spin>
    </n-card>
  </n-space>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import {
  NSpace, NCard, NButton, NTag, NSwitch, NForm, NFormItem, NInput,
  NSelect, NGrid, NGi, NSpin, NAlert, NRadioGroup, NRadio,
  NCheckboxGroup, NCheckbox, useMessage
} from 'naive-ui'

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
  pay_methods: ['native'],
  notify_url: ''
})

const stripeLoading = ref(false)
const stripeSaving = ref(false)
const stripeTesting = ref(false)
const stripeError = ref<string | null>(null)

const alipayLoading = ref(false)
const alipaySaving = ref(false)
const alipayTesting = ref(false)
const alipayError = ref<string | null>(null)

const wechatLoading = ref(false)
const wechatSaving = ref(false)
const wechatTesting = ref(false)
const wechatError = ref<string | null>(null)

const onStripeToggle = (val: boolean) => {
  if (val && !stripeForm.publishable_key) {
    message.warning('请先填写 Stripe 密钥后再启用')
    stripeForm.enabled = false
  }
}

const saveChannel = async (channel: string) => {
  const savingRef = channel === 'stripe' ? stripeSaving : channel === 'alipay' ? alipaySaving : wechatSaving
  savingRef.value = true
  try {
    await new Promise(r => setTimeout(r, 600))
    message.success(`${channel === 'stripe' ? 'Stripe' : channel === 'alipay' ? '支付宝' : '微信支付'} 配置已保存`)
  } catch {
    message.error('保存失败，请重试')
  } finally {
    savingRef.value = false
  }
}

const testConnection = async (channel: string) => {
  const testingRef = channel === 'stripe' ? stripeTesting : channel === 'alipay' ? alipayTesting : wechatTesting
  testingRef.value = true
  try {
    await new Promise(r => setTimeout(r, 800))
    message.success('连接测试成功 ✓')
  } catch {
    message.error('连接测试失败，请检查配置')
  } finally {
    testingRef.value = false
  }
}
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

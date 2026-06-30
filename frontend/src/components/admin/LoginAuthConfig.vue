<!-- AIMETA P=登录方式配置_后台|R=邮件SMTP/微信/谷歌/手机短信登录配置|NR=不含登录逻辑|E=component:LoginAuthConfig|X=ui|A=配置面板|D=vue,naive-ui|S=net|RD=./README.ai -->
<template>
  <div class="login-auth-config">
    <n-spin :show="loading">
      <n-space vertical :size="20">
        <!-- 邮件服务 —— 注册 / 找回密码验证码 -->
        <n-card title="邮件服务" size="small">
          <n-alert type="info" :show-icon="false" style="margin-bottom:12px">
            注册与找回密码的邮箱验证码依赖此配置。可选「自建 SMTP」或「Resend API」，所选通道的字段需全部填写后才会生效（缺项注册会提示「未配置邮件服务」）。
          </n-alert>
          <n-form label-placement="left" label-width="120">
            <n-form-item label="发送通道">
              <n-select v-model:value="form['email.provider']" :options="emailProviderOptions" style="max-width:280px" />
            </n-form-item>

            <template v-if="form['email.provider'] === 'resend'">
              <n-alert type="warning" :show-icon="false" style="margin-bottom:12px">
                发件人地址的域名必须已在 Resend 后台完成验证（配置 SPF/DKIM），否则会发送失败。沙箱地址 onboarding@resend.dev 只能发给你自己的 Resend 账户邮箱。
              </n-alert>
              <n-form-item label="Resend API Key">
                <n-input v-model:value="form['resend.api_key']" type="password" show-password-on="click" placeholder="re_ 开头的 API Key" />
              </n-form-item>
              <n-form-item label="发件人">
                <n-input v-model:value="form['resend.from']" placeholder="须为已验证域名下地址，如 验证码 <noreply@yourdomain.com>" />
              </n-form-item>
            </template>

            <template v-else>
              <n-form-item label="SMTP 服务器">
                <n-input v-model:value="form['smtp.server']" placeholder="如 smtp.qq.com / smtp.gmail.com / smtp.feishu.cn" />
              </n-form-item>
              <n-form-item label="端口">
                <n-input v-model:value="form['smtp.port']" placeholder="465（SSL）或 587（STARTTLS）" />
              </n-form-item>
              <n-form-item label="发信账号">
                <n-input v-model:value="form['smtp.username']" placeholder="发信邮箱完整账号" />
              </n-form-item>
              <n-form-item label="授权码 / 密码">
                <n-input v-model:value="form['smtp.password']" type="password" show-password-on="click" placeholder="邮箱 SMTP 授权码（多数邮箱非登录密码）" />
              </n-form-item>
              <n-form-item label="发件人">
                <n-input v-model:value="form['smtp.from']" placeholder="发件人地址，一般与发信账号相同" />
              </n-form-item>
            </template>

            <n-button type="primary" :loading="saving === 'email'" @click="saveGroup('email', emailKeys)">保存邮件配置</n-button>
          </n-form>
        </n-card>

        <!-- 微信登录 -->
        <n-card title="微信登录（网站应用扫码）" size="small">
          <template #header-extra>
            <n-switch v-model:value="form['auth.wechat_enabled']" />
          </template>
          <n-form label-placement="left" label-width="120">
            <n-form-item label="AppID">
              <n-input v-model:value="form['wechat.app_id']" placeholder="微信开放平台 网站应用 AppID" />
            </n-form-item>
            <n-form-item label="AppSecret">
              <n-input v-model:value="form['wechat.app_secret']" type="password" show-password-on="click" placeholder="AppSecret" />
            </n-form-item>
            <n-form-item label="回调地址">
              <n-input v-model:value="form['wechat.redirect_uri']" placeholder="https://你的域名/api/auth/wechat/callback" />
            </n-form-item>
            <n-button type="primary" :loading="saving === 'wechat'" @click="saveGroup('wechat', wechatKeys)">保存微信配置</n-button>
          </n-form>
        </n-card>

        <!-- 谷歌登录 -->
        <n-card title="谷歌登录（OAuth2）" size="small">
          <template #header-extra>
            <n-switch v-model:value="form['auth.google_enabled']" />
          </template>
          <n-form label-placement="left" label-width="120">
            <n-form-item label="Client ID">
              <n-input v-model:value="form['google.client_id']" placeholder="Google OAuth Client ID" />
            </n-form-item>
            <n-form-item label="Client Secret">
              <n-input v-model:value="form['google.client_secret']" type="password" show-password-on="click" placeholder="Client Secret" />
            </n-form-item>
            <n-form-item label="回调地址">
              <n-input v-model:value="form['google.redirect_uri']" placeholder="https://你的域名/api/auth/google/callback" />
            </n-form-item>
            <n-button type="primary" :loading="saving === 'google'" @click="saveGroup('google', googleKeys)">保存谷歌配置</n-button>
          </n-form>
        </n-card>

        <!-- 手机号登录 / 短信 -->
        <n-card title="手机号登录（验证码登录即注册）" size="small">
          <template #header-extra>
            <n-switch v-model:value="form['auth.phone_enabled']" />
          </template>
          <n-form label-placement="left" label-width="120">
            <n-form-item label="短信服务商">
              <n-select v-model:value="form['sms.provider']" :options="smsProviderOptions" style="width:200px" />
            </n-form-item>
            <template v-if="form['sms.provider'] === 'aliyun'">
              <n-form-item label="AccessKeyId">
                <n-input v-model:value="form['sms.access_key_id']" placeholder="阿里云 AccessKeyId" />
              </n-form-item>
              <n-form-item label="AccessKeySecret">
                <n-input v-model:value="form['sms.access_key_secret']" type="password" show-password-on="click" placeholder="AccessKeySecret" />
              </n-form-item>
              <n-form-item label="短信签名">
                <n-input v-model:value="form['sms.sign_name']" placeholder="如：阿尔博里斯" />
              </n-form-item>
              <n-form-item label="模板 CODE">
                <n-input v-model:value="form['sms.template_code']" placeholder="如：SMS_123456789" />
              </n-form-item>
              <n-form-item label="区域">
                <n-input v-model:value="form['sms.region']" placeholder="cn-hangzhou（默认）" />
              </n-form-item>
            </template>
            <n-alert v-else type="info" :show-icon="false" style="margin-bottom:12px">
              mock 模式仅记录日志、不真正发送验证码（验证码可在后端日志查看），用于开发联调；上线请选阿里云并填齐密钥。
            </n-alert>
            <n-button type="primary" :loading="saving === 'phone'" @click="saveGroup('phone', phoneKeys)">保存手机/短信配置</n-button>
          </n-form>
        </n-card>
      </n-space>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { NSpin, NSpace, NCard, NForm, NFormItem, NInput, NSwitch, NSelect, NButton, NAlert, useMessage } from 'naive-ui'
import { AdminAPI } from '@/api/admin'

const message = useMessage()
const loading = ref(false)
const saving = ref<string | null>(null)

const smsProviderOptions = [
  { label: '阿里云短信', value: 'aliyun' },
  { label: 'mock（仅日志，不真发）', value: 'mock' },
]

const emailProviderOptions = [
  { label: '自建 SMTP', value: 'smtp' },
  { label: 'Resend API', value: 'resend' },
]

const boolKeys = ['auth.wechat_enabled', 'auth.google_enabled', 'auth.phone_enabled']
const wechatKeys = ['auth.wechat_enabled', 'wechat.app_id', 'wechat.app_secret', 'wechat.redirect_uri']
const googleKeys = ['auth.google_enabled', 'google.client_id', 'google.client_secret', 'google.redirect_uri']
const phoneKeys = ['auth.phone_enabled', 'sms.provider', 'sms.access_key_id', 'sms.access_key_secret', 'sms.sign_name', 'sms.template_code', 'sms.region']
const smtpKeys = ['smtp.server', 'smtp.port', 'smtp.username', 'smtp.password', 'smtp.from']
const emailKeys = ['email.provider', ...smtpKeys, 'resend.api_key', 'resend.from']
const allKeys = [...new Set([...wechatKeys, ...googleKeys, ...phoneKeys, ...emailKeys])]

const form = reactive<Record<string, any>>({})
for (const k of allKeys) form[k] = boolKeys.includes(k) ? false : ''
form['sms.provider'] = 'mock'
form['email.provider'] = 'smtp'
form['smtp.port'] = '465'

const parseBool = (v: string) => ['1', 'true', 'yes', 'on'].includes((v || '').toLowerCase())

const loadConfigs = async () => {
  loading.value = true
  try {
    const list = await AdminAPI.listSystemConfigs()
    const map: Record<string, string> = {}
    for (const c of list || []) map[c.key] = c.value
    for (const k of allKeys) {
      if (k in map) form[k] = boolKeys.includes(k) ? parseBool(map[k]) : map[k]
    }
  } catch {
    message.error('加载登录配置失败')
  } finally {
    loading.value = false
  }
}

const saveGroup = async (group: string, keys: string[]) => {
  saving.value = group
  try {
    for (const k of keys) {
      const raw = form[k]
      const value = boolKeys.includes(k) ? (raw ? 'true' : 'false') : String(raw ?? '')
      await AdminAPI.upsertSystemConfig(k, { value })
    }
    message.success('已保存')
  } catch {
    message.error('保存失败')
  } finally {
    saving.value = null
  }
}

onMounted(loadConfigs)
</script>

<style scoped>
.login-auth-config { padding: 4px; }
</style>

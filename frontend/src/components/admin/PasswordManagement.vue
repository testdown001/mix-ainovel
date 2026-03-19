<!-- AIMETA P=密码管理_管理员密码修改|R=密码修改表单|NR=不含用户管理|E=component:PasswordManagement|X=ui|A=密码组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <n-space vertical size="large" class="password-container">
    <div class="password-card">
      <div class="card-header-block">
        <span class="card-title">管理员密码修改</span>
        <div class="title-accent"></div>
      </div>

      <n-alert v-if="mustReset" type="warning" class="alert-block">
        为保障安全，请先更新默认密码后再继续使用管理后台。
      </n-alert>

      <n-alert v-if="error" type="error" closable @close="error = null" class="alert-block">
        {{ error }}
      </n-alert>

      <n-spin :show="submitting">
        <n-form class="password-form" label-placement="top" @submit.prevent="handleSubmit">
          <n-form-item label="当前密码">
            <n-input
              v-model:value="form.oldPassword"
              type="password"
              show-password-on="click"
              placeholder="请输入当前管理员密码"
              autocomplete="current-password"
            />
          </n-form-item>

          <div class="form-divider"></div>

          <n-form-item label="新密码">
            <n-input
              v-model:value="form.newPassword"
              type="password"
              show-password-on="click"
              placeholder="请输入至少 8 位新密码"
              autocomplete="new-password"
            />
          </n-form-item>

          <n-form-item label="确认新密码">
            <n-input
              v-model:value="form.confirmPassword"
              type="password"
              show-password-on="click"
              placeholder="请再次输入新密码"
              autocomplete="new-password"
            />
          </n-form-item>

          <div class="form-submit">
            <button class="submit-btn" type="button" :disabled="submitting" @click="handleSubmit">
              {{ submitting ? '保存中...' : '保存新密码' }}
            </button>
          </div>
        </n-form>
      </n-spin>
    </div>
  </n-space>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { NAlert, NButton, NCard, NForm, NFormItem, NInput, NSpace, NSpin } from 'naive-ui'

import { AdminAPI } from '@/api/admin'
import { useAlert } from '@/composables/useAlert'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const { showAlert } = useAlert()

const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const submitting = ref(false)
const error = ref<string | null>(null)

const mustReset = computed(() => authStore.mustChangePassword && authStore.user?.is_admin)

const resetForm = () => {
  form.oldPassword = ''
  form.newPassword = ''
  form.confirmPassword = ''
}

const handleSubmit = async () => {
  error.value = null

  if (!form.oldPassword.trim() || !form.newPassword.trim()) {
    error.value = '请填写完整的密码信息'
    return
  }

  if (form.newPassword.length < 8) {
    error.value = '新密码长度需至少 8 位'
    return
  }

  if (form.newPassword === form.oldPassword) {
    error.value = '新密码不能与当前密码相同'
    return
  }

  if (form.newPassword !== form.confirmPassword) {
    error.value = '两次输入的新密码不一致'
    return
  }

  submitting.value = true
  try {
    await AdminAPI.changePassword(form.oldPassword, form.newPassword)
    await authStore.fetchUser()
    resetForm()
    await showAlert('密码已更新，请使用新密码继续操作', 'success')
  } catch (err) {
    error.value = err instanceof Error ? err.message : '密码更新失败'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.password-container {
  max-width: 520px;
  margin: 0 auto;
}

.password-card {
  background: #0f1419;
  border: 1px solid rgba(77, 70, 50, 0.15);
  border-radius: 4px;
  padding: 28px;
}

.card-header-block {
  margin-bottom: 24px;
}

.card-title {
  font-family: var(--ar-font-display);
  font-size: 1.25rem;
  font-weight: 600;
  color: #FACC15;
  display: block;
}

.title-accent {
  margin-top: 8px;
  width: 40px;
  height: 2px;
  background: linear-gradient(90deg, #FACC15, transparent);
  border-radius: 1px;
}

.alert-block {
  margin-bottom: 20px;
}

.password-form {
  max-width: 420px;
}

.form-divider {
  height: 1px;
  background: rgba(77, 70, 50, 0.15);
  margin: 4px 0 16px;
}

.form-submit {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.submit-btn {
  font-family: var(--ar-font-ui);
  font-size: 0.85rem;
  font-weight: 600;
  color: #000;
  background: #FACC15;
  border: none;
  border-radius: 4px;
  padding: 10px 28px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.submit-btn:hover:not(:disabled) {
  background: #eab308;
  box-shadow: 0 0 18px rgba(250, 204, 21, 0.2);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
  --n-border: 1px solid rgba(77, 70, 50, 0.15);
  --n-border-focus: 1px solid rgba(250, 204, 21, 0.4);
  --n-text-color: #dee3eb;
  --n-placeholder-color: #545d68;
  --n-caret-color: #FACC15;
  border-radius: 4px;
}

:deep(.n-input .n-input__eye) {
  color: #545d68;
}

:deep(.n-input .n-input__eye:hover) {
  color: #FACC15;
}

:deep(.n-alert) {
  border-radius: 4px;
}

:deep(.n-alert--warning-type) {
  background: rgba(250, 204, 21, 0.06);
  border: 1px solid rgba(250, 204, 21, 0.15);
}

:deep(.n-alert--error-type) {
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
}
</style>

<!-- AIMETA P=用户管理_用户列表管理|R=用户CRUD_权限|NR=不含认证功能|E=component:UserManagement|X=ui|A=用户组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="user-panel">
    <div class="panel-header">
      <span class="panel-title">用户管理</span>
      <div class="panel-actions">
        <n-input
          v-model:value="keyword"
          clearable
          placeholder="搜索用户名或邮箱"
          @update:value="handleSearch"
          class="search-input"
        />
        <n-button
          class="action-btn action-btn--primary"
          size="small"
          @click="handleAdd"
        >
          新建用户
        </n-button>
        <button class="refresh-btn" @click="fetchUsers" :disabled="loading">
          <span v-if="loading" class="spinner" />
          <span v-else>刷新</span>
        </button>
      </div>
    </div>

    <n-alert v-if="error" type="error" closable @close="error = null" class="user-alert">
      {{ error }}
    </n-alert>

    <n-spin :show="loading">
      <n-data-table
        :columns="columns"
        :data="filteredUsers"
        :bordered="false"
        :pagination="pagination"
        :row-key="rowKey"
        class="cyber-table"
      />
    </n-spin>

    <!-- Create/Edit User Modal -->
    <n-modal
      v-model:show="showModal"
      preset="card"
      :title="modalTitle"
      class="cyber-modal"
      style="width: 500px"
    >
      <n-form
        ref="formRef"
        :model="formModel"
        :rules="rules"
        label-placement="left"
        label-width="80"
        require-mark-placement="right-hanging"
      >
        <n-form-item label="用户名" path="username">
          <n-input
            v-model:value="formModel.username"
            placeholder="请输入用户名"
            :input-props="{ autocomplete: 'off' }"
          />
        </n-form-item>
        <n-form-item label="邮箱" path="email">
          <n-input
            v-model:value="formModel.email"
            placeholder="请输入邮箱（可选）"
            :input-props="{ autocomplete: 'off' }"
          />
        </n-form-item>
        <n-form-item
          label="密码"
          path="password"
          :rule="isEditMode ? [{ min: 6, message: '密码至少 6 个字符', trigger: 'blur' }] : passwordRules"
        >
          <n-input
            v-model:value="formModel.password"
            type="password"
            show-password-on="click"
            :placeholder="isEditMode ? '不修改请留空' : '请输入密码'"
            :input-props="{ autocomplete: 'new-password' }"
          />
        </n-form-item>
        <n-form-item label="权限" path="is_admin">
          <n-switch v-model:value="formModel.is_admin" :disabled="!isEditMode">
            <template #checked>管理员</template>
            <template #unchecked>普通用户</template>
          </n-switch>
        </n-form-item>
        <n-form-item label="状态" path="is_active">
          <n-switch v-model:value="formModel.is_active">
            <template #checked>激活</template>
            <template #unchecked>禁用</template>
          </n-switch>
        </n-form-item>
      </n-form>
      <template #footer>
        <div class="modal-footer">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="submitting" @click="handleSubmit">
            确认
          </n-button>
        </div>
      </template>
    </n-modal>
  </div>
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
  NModal,
  NPopconfirm,
  NSpin,
  NSwitch,
  NTag,
  NSpace,
  useMessage,
  type DataTableColumns,
  type FormInst,
  type FormRules,
  type FormItemRule
} from 'naive-ui'

import { AdminAPI, type AdminUser, type UserCreatePayload } from '@/api/admin'

const message = useMessage()
const users = ref<AdminUser[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const keyword = ref('')

const showModal = ref(false)
const submitting = ref(false)
const isEditMode = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInst | null>(null)

const formModel = reactive({
  username: '',
  email: '',
  password: '',
  is_admin: false,
  is_active: true
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, message: '用户名至少 2 个字符', trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ]
}

const passwordRules: FormItemRule[] = [
  { required: true, message: '请输入密码', trigger: 'blur' },
  { min: 6, message: '密码至少 6 个字符', trigger: 'blur' }
]

const pagination = reactive({
  page: 1,
  pageSize: 10,
  showSizePicker: true,
  pageSizes: [10, 20, 50]
})

const columns: DataTableColumns<AdminUser> = [
  {
    title: 'ID',
    key: 'id',
    sorter: (a, b) => a.id - b.id,
    width: 80
  },
  {
    title: '用户名',
    key: 'username',
    ellipsis: { tooltip: true }
  },
  {
    title: '邮箱',
    key: 'email',
    ellipsis: { tooltip: true },
    render(row) {
      return row.email || '—'
    }
  },
  {
    title: '权限',
    key: 'is_admin',
    align: 'center',
    render(row) {
      return h(
        NTag,
        {
          type: row.is_admin ? 'success' : 'default',
          bordered: false,
          size: 'small'
        },
        { default: () => (row.is_admin ? '管理员' : '普通用户') }
      )
    }
  },
  {
    title: '状态',
    key: 'is_active',
    align: 'center',
    render(row) {
      return h(
        NTag,
        {
          type: row.is_active ? 'success' : 'error',
          bordered: false,
          size: 'small'
        },
        { default: () => (row.is_active ? '激活' : '禁用') }
      )
    }
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    render(row) {
      return h(NSpace, { justify: 'center', size: 'small' }, {
        default: () => [
          h(
            NButton,
            {
              size: 'small',
              type: 'primary',
              secondary: true,
              onClick: () => handleEdit(row)
            },
            { default: () => '编辑' }
          ),
          h(
            NPopconfirm,
            {
              onPositiveClick: () => handleDelete(row.id)
            },
            {
              trigger: () => h(
                NButton,
                {
                  size: 'small',
                  type: 'error',
                  secondary: true,
                  disabled: row.is_admin
                },
                { default: () => '删除' }
              ),
              default: () => '确定要删除该用户吗？'
            }
          )
        ]
      })
    }
  }
]

const filteredUsers = computed(() => {
  if (!keyword.value.trim()) {
    return users.value
  }
  const q = keyword.value.trim().toLowerCase()
  return users.value.filter(
    (user) =>
      user.username.toLowerCase().includes(q) ||
      (user.email && user.email.toLowerCase().includes(q))
  )
})

const modalTitle = computed(() => isEditMode.value ? '编辑用户' : '新建用户')

const rowKey = (row: AdminUser) => row.id

const fetchUsers = async () => {
  loading.value = true
  error.value = null
  try {
    users.value = await AdminAPI.listUsers()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取用户数据失败'
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
}

const handleAdd = () => {
  isEditMode.value = false
  editingId.value = null
  // 清空表单数据
  formModel.username = ''
  formModel.email = ''
  formModel.password = ''
  formModel.is_admin = false
  formModel.is_active = true
  
  showModal.value = true
}

const handleEdit = (row: AdminUser) => {
  isEditMode.value = true
  editingId.value = row.id
  formModel.username = row.username
  formModel.email = row.email || ''
  formModel.password = '' // 密码留空表示不修改
  formModel.is_admin = row.is_admin
  formModel.is_active = row.is_active
  showModal.value = true
}

const handleDelete = async (id: number) => {
  try {
    await AdminAPI.deleteUser(id)
    message.success('删除成功')
    await fetchUsers()
  } catch (err) {
    message.error(err instanceof Error ? err.message : '删除失败')
  }
}

const handleSubmit = () => {
  formRef.value?.validate(async (errors) => {
    if (errors) return

    submitting.value = true
    try {
      if (isEditMode.value && editingId.value) {
        const payload: any = {
          username: formModel.username,
          is_admin: formModel.is_admin,
          is_active: formModel.is_active
        }
        if (formModel.email) payload.email = formModel.email
        if (formModel.password) payload.password = formModel.password
        
        await AdminAPI.updateUser(editingId.value, payload)
        message.success('更新成功')
      } else {
        const payload: UserCreatePayload = {
          username: formModel.username,
          password: formModel.password,
          is_admin: formModel.is_admin,
          is_active: formModel.is_active
        }
        if (formModel.email) payload.email = formModel.email
        
        await AdminAPI.createUser(payload)
        message.success('创建成功')
      }
      showModal.value = false
      await fetchUsers()
    } catch (err) {
      message.error(err instanceof Error ? err.message : '操作失败')
    } finally {
      submitting.value = false
    }
  })
}

onMounted(fetchUsers)
</script>

<style scoped>
.user-panel {
  width: 100%;
  box-sizing: border-box;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ar-spacing-4);
  flex-wrap: wrap;
  margin-bottom: var(--ar-spacing-6);
}

.panel-title {
  font-family: var(--ar-font-display);
  font-size: var(--ar-text-h2);
  font-weight: 700;
  color: var(--ar-text-primary);
  letter-spacing: -0.01em;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: var(--ar-spacing-3);
  flex-wrap: wrap;
}

.search-input {
  width: min(230px, 60vw);
}

/* Override Naive UI input to match cyberpunk design */
.search-input :deep(.n-input) {
  --n-border: 1px solid var(--ar-border) !important;
  --n-border-hover: 1px solid rgba(250, 204, 21, 0.3) !important;
  --n-border-focus: 1px solid var(--ar-secondary) !important;
  --n-color: var(--ar-bg-elevated) !important;
  --n-color-focus: var(--ar-bg-elevated) !important;
  --n-text-color: var(--ar-text-primary) !important;
  --n-placeholder-color: var(--ar-text-muted) !important;
  --n-caret-color: var(--ar-primary) !important;
  --n-border-radius: var(--ar-radius-sm) !important;
  font-family: var(--ar-font-ui);
}

.action-btn--primary {
  font-family: var(--ar-font-ui);
  font-weight: 600;
  border-radius: var(--ar-radius-sm) !important;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  padding: 0 14px;
  border: 1px solid var(--ar-border);
  border-radius: var(--ar-radius-sm);
  background: transparent;
  color: var(--ar-text-secondary);
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-body-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--ar-duration-short) var(--ar-easing-standard);
}

.refresh-btn:hover:not(:disabled) {
  color: var(--ar-primary);
  border-color: rgba(250, 204, 21, 0.3);
  background: var(--ar-primary-muted);
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid var(--ar-bg-highlight);
  border-top-color: var(--ar-primary);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.user-alert {
  margin-bottom: var(--ar-spacing-4);
}

/* Cyberpunk Data Table overrides */
.cyber-table :deep(.n-data-table) {
  --n-border-color: var(--ar-border) !important;
  --n-th-color: var(--ar-bg-surface) !important;
  --n-td-color: transparent !important;
  --n-th-text-color: var(--ar-text-secondary) !important;
  --n-td-text-color: var(--ar-text-primary) !important;
  --n-border-radius: var(--ar-radius-sm) !important;
}

.cyber-table :deep(.n-data-table-wrapper) {
  border-radius: var(--ar-radius-sm);
  border: 1px solid var(--ar-border);
  background: var(--ar-bg-surface);
}

.cyber-table :deep(.n-data-table-th) {
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-label);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--ar-text-secondary) !important;
  background: var(--ar-bg-surface) !important;
  border-bottom: 1px solid var(--ar-border) !important;
  border-color: var(--ar-border) !important;
}

.cyber-table :deep(.n-data-table-td) {
  font-family: var(--ar-font-ui);
  font-size: var(--ar-text-body);
  color: var(--ar-text-primary) !important;
  border-bottom: 1px solid var(--ar-border-subtle) !important;
  border-color: var(--ar-border-subtle) !important;
  background: transparent !important;
}

.cyber-table :deep(.n-data-table-tr:hover .n-data-table-td) {
  background: var(--ar-bg-elevated) !important;
}

.cyber-table :deep(.n-data-table-th__ellipsis),
.cyber-table :deep(.n-data-table-td__ellipsis) {
  color: inherit;
}

/* Pagination overrides */
.cyber-table :deep(.n-pagination) {
  --n-item-color: transparent !important;
  --n-item-color-hover: var(--ar-primary-muted) !important;
  --n-item-color-active: var(--ar-primary-muted) !important;
  --n-item-text-color: var(--ar-text-secondary) !important;
  --n-item-text-color-hover: var(--ar-primary) !important;
  --n-item-text-color-active: var(--ar-primary) !important;
  --n-item-border: 1px solid var(--ar-border) !important;
  --n-item-border-hover: 1px solid rgba(250, 204, 21, 0.3) !important;
  --n-item-border-active: 1px solid var(--ar-primary) !important;
  --n-item-border-radius: var(--ar-radius-sm) !important;
  --n-button-color-hover: var(--ar-primary-muted) !important;
  --n-button-border: 1px solid var(--ar-border) !important;
  --n-button-border-hover: 1px solid rgba(250, 204, 21, 0.3) !important;
  --n-button-icon-color: var(--ar-text-secondary) !important;
  --n-button-icon-color-hover: var(--ar-primary) !important;
  font-family: var(--ar-font-ui);
  margin-top: var(--ar-spacing-4);
}

/* Modal overrides */
.cyber-modal :deep(.n-card) {
  --n-color: var(--ar-bg-elevated) !important;
  --n-border-color: var(--ar-border) !important;
  --n-border-radius: var(--ar-radius-sm) !important;
  --n-title-text-color: var(--ar-text-primary) !important;
  --n-title-font-weight: 700 !important;
  box-shadow: var(--ar-elevation-glow) !important;
}

.cyber-modal :deep(.n-card-header__main) {
  font-family: var(--ar-font-display);
  font-size: var(--ar-text-h3);
}

.cyber-modal :deep(.n-card-header) {
  border-bottom: 1px solid var(--ar-border) !important;
}

.cyber-modal :deep(.n-card__footer) {
  border-top: 1px solid var(--ar-border) !important;
}

/* Form overrides within modal */
.cyber-modal :deep(.n-form-item-label__text) {
  font-family: var(--ar-font-ui) !important;
  color: var(--ar-text-secondary) !important;
  font-weight: 500;
}

.cyber-modal :deep(.n-input) {
  --n-border: 1px solid var(--ar-border) !important;
  --n-border-hover: 1px solid rgba(250, 204, 21, 0.3) !important;
  --n-border-focus: 1px solid var(--ar-secondary) !important;
  --n-color: var(--ar-bg-highlight) !important;
  --n-color-focus: var(--ar-bg-highlight) !important;
  --n-text-color: var(--ar-text-primary) !important;
  --n-placeholder-color: var(--ar-text-muted) !important;
  --n-caret-color: var(--ar-primary) !important;
  --n-border-radius: var(--ar-radius-sm) !important;
  font-family: var(--ar-font-ui);
}

.cyber-modal :deep(.n-switch.n-switch--active) {
  --n-rail-color-active: var(--ar-secondary) !important;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--ar-spacing-2);
}

@media (max-width: 767px) {
  .panel-header {
    flex-direction: column;
    align-items: stretch;
  }

  .panel-title {
    font-size: var(--ar-text-h3);
  }

  .panel-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input {
    width: 100%;
  }
}
</style>

<!-- AIMETA P=用户管理_用户列表管理|R=用户CRUD_权限|NR=不含认证功能|E=component:UserManagement|X=ui|A=用户组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <n-card :bordered="false" class="admin-card">
    <template #header>
      <div class="card-header">
        <span class="card-title">用户管理</span>
        <n-space :size="12">
          <n-input
            v-model:value="keyword"
            clearable
            round
            placeholder="搜索用户名或邮箱"
            @update:value="handleSearch"
            class="search-input"
          />
          <n-select
            v-if="showExpiring"
            v-model:value="expiringDays"
            size="small"
            class="days-select"
            :options="expiringDayOptions"
            @update:value="fetchExpiringUsers"
          />
          <n-button
            size="small"
            :type="showExpiring ? 'warning' : 'default'"
            :secondary="showExpiring"
            @click="toggleExpiring"
          >
            {{ showExpiring ? '返回全部用户' : '即将到期' }}
          </n-button>
          <n-button type="primary" size="small" @click="handleAdd">
            新建用户
          </n-button>
          <n-button quaternary size="small" @click="refreshCurrentView" :loading="loading || expiringLoading">
            刷新
          </n-button>
        </n-space>
      </div>
    </template>

    <n-space vertical size="large">
      <n-alert v-if="error" type="error" closable @close="error = null">
        {{ error }}
      </n-alert>

      <template v-if="showExpiring">
        <n-alert type="info" :bordered="false" :show-icon="false">
          到期即静默回落免费版，是订阅制唯一的自动流失点。「试用」一列区分未转化的注册赠期与已付费用户，
          两者该说的话不一样；「已提醒」是自动到期邮件的发送状态，避免人工重复打扰。
        </n-alert>
        <n-spin :show="expiringLoading">
          <n-empty v-if="!expiringUsers.length" :description="`未来 ${expiringDays} 天内没有会员到期`" />
          <n-data-table
            v-else
            :columns="expiringColumns"
            :data="expiringUsers"
            :bordered="false"
            :pagination="expiringPagination"
            :row-key="expiringRowKey"
            size="small"
            class="user-table"
          />
        </n-spin>
      </template>

      <n-spin v-if="!showExpiring" :show="loading">
        <n-data-table
          :columns="columns"
          :data="filteredUsers"
          :bordered="false"
          :pagination="pagination"
          :row-key="rowKey"
          class="user-table"
        />
      </n-spin>
    </n-space>

    <!-- Create/Edit User Modal -->
    <n-modal v-model:show="showModal" preset="card" :title="modalTitle" style="width: 500px">
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
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="submitting" @click="handleSubmit">
            确认
          </n-button>
        </n-space>
      </template>
    </n-modal>

    <n-drawer v-model:show="showDetailDrawer" :width="720">
      <n-drawer-content title="用户详情" closable>
        <n-spin :show="detailLoading">
          <n-space v-if="subscriptionDetail" vertical size="large">
            <n-descriptions label-placement="left" bordered :column="2" size="small">
              <n-descriptions-item label="用户 ID">
                {{ subscriptionDetail.user.id }}
              </n-descriptions-item>
              <n-descriptions-item label="用户名">
                {{ subscriptionDetail.user.username }}
              </n-descriptions-item>
              <n-descriptions-item label="邮箱">
                {{ subscriptionDetail.user.email || '—' }}
              </n-descriptions-item>
              <n-descriptions-item label="状态">
                {{ subscriptionDetail.user.is_active ? '激活' : '禁用' }}
              </n-descriptions-item>
              <n-descriptions-item label="当前套餐">
                {{ subscriptionDetail.current_plan?.name || tierLabel(subscriptionDetail.quota.effective_tier) }}
              </n-descriptions-item>
              <n-descriptions-item label="有效档位">
                <n-tag :type="subscriptionDetail.quota.is_premium ? 'success' : 'default'" size="small">
                  {{ tierLabel(subscriptionDetail.quota.effective_tier) }}
                </n-tag>
              </n-descriptions-item>
              <n-descriptions-item label="订阅有效期">
                {{ formatDate(subscriptionDetail.quota.premium_expires_at) }}
              </n-descriptions-item>
              <n-descriptions-item label="章节额度">
                {{ subscriptionDetail.quota.daily_chapter_used }} / {{ limitLabel(subscriptionDetail.quota.daily_chapter_limit) }}
              </n-descriptions-item>
            </n-descriptions>

            <section class="detail-section">
              <h3 class="detail-section-title">分配订阅套餐</h3>
              <n-form label-placement="left" label-width="90">
                <n-form-item label="套餐">
                  <n-select
                    v-model:value="assignForm.plan_id"
                    :options="assignPlanOptions"
                    placeholder="选择要分配的套餐"
                  />
                </n-form-item>
                <n-form-item label="周期">
                  <n-radio-group v-model:value="assignForm.period">
                    <n-radio-button value="monthly">月付 30 天</n-radio-button>
                    <n-radio-button value="yearly">年付 365 天</n-radio-button>
                  </n-radio-group>
                </n-form-item>
                <n-form-item label="备注">
                  <n-input
                    v-model:value="assignForm.remark"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 4 }"
                    placeholder="可选，记录后台分配原因"
                  />
                </n-form-item>
                <n-space justify="end">
                  <n-button
                    type="primary"
                    :loading="assignLoading"
                    :disabled="!assignForm.plan_id"
                    @click="handleAssignSubscription"
                  >
                    分配订阅
                  </n-button>
                </n-space>
              </n-form>
            </section>

            <section class="detail-section">
              <h3 class="detail-section-title">订阅历史</h3>
              <n-data-table
                :columns="historyColumns"
                :data="subscriptionDetail.history"
                :bordered="false"
                :pagination="{ pageSize: 8 }"
                size="small"
              />
            </section>
          </n-space>
          <n-empty v-else description="暂无详情" />
        </n-spin>
      </n-drawer-content>
    </n-drawer>
  </n-card>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NDescriptions,
  NDescriptionsItem,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NPopconfirm,
  NRadioButton,
  NRadioGroup,
  NSelect,
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

import {
  AdminAPI,
  type AdminExpiringUser,
  type AdminUser,
  type AdminUserSubscriptionDetail,
  type AdminUserSubscriptionHistoryItem,
  type UserCreatePayload
} from '@/api/admin'

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
const showDetailDrawer = ref(false)
const detailLoading = ref(false)
const assignLoading = ref(false)
const subscriptionDetail = ref<AdminUserSubscriptionDetail | null>(null)
const detailUserId = ref<number | null>(null)

const formModel = reactive({
  username: '',
  email: '',
  password: '',
  is_admin: false,
  is_active: true
})

const assignForm = reactive<{
  plan_id: number | null
  period: 'monthly' | 'yearly'
  remark: string
}>({
  plan_id: null,
  period: 'monthly',
  remark: ''
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

// 即将到期视图：整表翻页看不出谁快到期，运营需要一份可直接触达的名单
const showExpiring = ref(false)
const expiringLoading = ref(false)
const expiringUsers = ref<AdminExpiringUser[]>([])
const expiringDays = ref(7)
const expiringDayOptions = [
  { label: '7 天内', value: 7 },
  { label: '15 天内', value: 15 },
  { label: '30 天内', value: 30 }
]
const expiringPagination = reactive({ page: 1, pageSize: 10 })
const expiringRowKey = (row: AdminExpiringUser) => row.user_id

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
    title: '当前套餐',
    key: 'current_plan_name',
    width: 130,
    render(row) {
      const tier = row.effective_tier || 'free'
      return h(
        NTag,
        {
          type: tier === 'free' ? 'default' : 'success',
          bordered: false,
          size: 'small'
        },
        { default: () => row.current_plan_name || tierLabel(tier) }
      )
    }
  },
  {
    title: '有效期',
    key: 'premium_expires_at',
    width: 170,
    render(row) {
      return formatDate(row.premium_expires_at)
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
              secondary: true,
              onClick: () => handleViewDetail(row)
            },
            { default: () => '详情' }
          ),
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

const expiringColumns: DataTableColumns<AdminExpiringUser> = [
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
    title: '档位',
    key: 'effective_tier',
    width: 110,
    render(row) {
      return h(
        NTag,
        { type: 'success', bordered: false, size: 'small' },
        { default: () => tierLabel(row.effective_tier) }
      )
    }
  },
  {
    title: '到期时间',
    key: 'premium_expires_at',
    width: 170,
    render(row) {
      return formatDate(row.premium_expires_at)
    }
  },
  {
    title: '剩余',
    key: 'days_left',
    width: 90,
    align: 'center',
    sorter: (a, b) => a.days_left - b.days_left,
    render(row) {
      return h(
        NTag,
        {
          type: row.days_left <= 1 ? 'error' : row.days_left <= 3 ? 'warning' : 'default',
          bordered: false,
          size: 'small'
        },
        { default: () => (row.days_left <= 0 ? '今天' : `${row.days_left} 天`) }
      )
    }
  },
  {
    title: '来源',
    key: 'has_paid_order',
    width: 100,
    align: 'center',
    render(row) {
      return h(
        NTag,
        { type: row.has_paid_order ? 'info' : 'warning', bordered: false, size: 'small' },
        { default: () => (row.has_paid_order ? '已付费' : '试用') }
      )
    }
  },
  {
    title: '余额',
    key: 'credit_total',
    width: 100,
    align: 'right',
    render(row) {
      return `${row.credit_total} 分`
    }
  },
  {
    title: '已提醒',
    key: 'reminded',
    width: 90,
    align: 'center',
    render(row) {
      return row.reminded ? '是' : '否'
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    align: 'center',
    render(row) {
      return h(
        NButton,
        { size: 'small', secondary: true, onClick: () => openDetailById(row.user_id) },
        { default: () => '详情' }
      )
    }
  }
]

const historyColumns: DataTableColumns<AdminUserSubscriptionHistoryItem> = [
  {
    title: '时间',
    key: 'paid_at',
    width: 150,
    render(row) {
      return formatDate(row.paid_at || row.created_at)
    }
  },
  {
    title: '套餐',
    key: 'plan_name',
    ellipsis: { tooltip: true }
  },
  {
    title: '渠道',
    key: 'channel',
    width: 90,
    render(row) {
      return row.channel === 'admin' ? '后台分配' : row.channel
    }
  },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render(row) {
      return h(
        NTag,
        {
          type: row.status === 'paid' ? 'success' : row.status === 'pending' ? 'warning' : 'default',
          size: 'small',
          bordered: false
        },
        { default: () => statusLabel(row.status) }
      )
    }
  },
  {
    title: '金额',
    key: 'amount',
    width: 100,
    render(row) {
      return `${row.currency} ${Number(row.amount || 0).toFixed(2)}`
    }
  },
  {
    title: '备注',
    key: 'remark',
    ellipsis: { tooltip: true },
    render(row) {
      return row.remark || '—'
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

const assignPlanOptions = computed(() =>
  (subscriptionDetail.value?.plans || [])
    .filter((plan) => plan.is_active && plan.tier !== 'free')
    .map((plan) => ({
      label: `${plan.name} · ${tierLabel(plan.tier)} · ${limitLabel(plan.daily_chapter_limit)}章/日`,
      value: plan.id
    }))
)

const rowKey = (row: AdminUser) => row.id

const tierLabel = (tier?: string | null) => {
  switch (tier) {
    case 'creator':
      return '创作者版'
    case 'flagship':
      return '旗舰版'
    case 'free':
      return '免费版'
    default:
      return tier || '—'
  }
}

const statusLabel = (status: string) => {
  switch (status) {
    case 'paid':
      return '已支付'
    case 'pending':
      return '待支付'
    case 'cancelled':
      return '已取消'
    case 'refunded':
      return '已退款'
    default:
      return status || '—'
  }
}

const formatDate = (value?: string | null) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const limitLabel = (value: number) => (value <= 0 ? '无限' : String(value))

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

const loadUserSubscription = async (id: number) => {
  detailLoading.value = true
  try {
    subscriptionDetail.value = await AdminAPI.getUserSubscription(id)
    const firstAssignable = assignPlanOptions.value[0]
    assignForm.plan_id = firstAssignable ? Number(firstAssignable.value) : null
  } catch (err) {
    message.error(err instanceof Error ? err.message : '获取用户详情失败')
  } finally {
    detailLoading.value = false
  }
}

const openDetailById = async (userId: number) => {
  detailUserId.value = userId
  subscriptionDetail.value = null
  assignForm.plan_id = null
  assignForm.period = 'monthly'
  assignForm.remark = ''
  showDetailDrawer.value = true
  await loadUserSubscription(userId)
}

const handleViewDetail = async (row: AdminUser) => {
  await openDetailById(row.id)
}

const fetchExpiringUsers = async () => {
  expiringLoading.value = true
  error.value = null
  try {
    expiringUsers.value = await AdminAPI.listExpiringUsers(expiringDays.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '获取即将到期用户失败'
  } finally {
    expiringLoading.value = false
  }
}

const toggleExpiring = async () => {
  showExpiring.value = !showExpiring.value
  if (showExpiring.value && !expiringUsers.value.length) {
    await fetchExpiringUsers()
  }
}

const refreshCurrentView = async () => {
  await (showExpiring.value ? fetchExpiringUsers() : fetchUsers())
}

const handleAssignSubscription = async () => {
  if (!detailUserId.value || !assignForm.plan_id) return
  assignLoading.value = true
  try {
    subscriptionDetail.value = await AdminAPI.assignUserSubscription(detailUserId.value, {
      plan_id: assignForm.plan_id,
      period: assignForm.period,
      remark: assignForm.remark || null
    })
    assignForm.remark = ''
    await fetchUsers()
    message.success('订阅分配成功')
  } catch (err) {
    message.error(err instanceof Error ? err.message : '订阅分配失败')
  } finally {
    assignLoading.value = false
  }
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
.admin-card {
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

.search-input {
  width: min(230px, 60vw);
}

.days-select {
  width: 108px;
}

.detail-section {
  padding-top: 4px;
}

.detail-section-title {
  margin: 0 0 12px;
  font-size: 0.95rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
}

@media (max-width: 767px) {
  .card-header {
    flex-direction: column;
    align-items: stretch;
  }

  .card-title {
    font-size: 1.125rem;
  }

  .search-input {
    width: 100%;
  }
}
</style>

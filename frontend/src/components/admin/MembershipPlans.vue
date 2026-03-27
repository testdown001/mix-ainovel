<template>
  <n-space vertical size="large" class="membership-plans">
    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <span class="card-title">会员套餐管理</span>
          <n-space :size="10">
            <n-button type="primary" size="small" @click="handleAdd">
              + 新建套餐
            </n-button>
            <n-button quaternary size="small" @click="fetchPlans" :loading="loading">
              刷新
            </n-button>
          </n-space>
        </div>
      </template>

      <n-alert v-if="error" type="error" closable @close="error = null" style="margin-bottom:16px">
        {{ error }}
      </n-alert>

      <n-spin :show="loading">
        <div class="plans-grid">
          <div
            v-for="plan in plans"
            :key="plan.id"
            class="plan-card"
            :class="{ 'plan-recommended': plan.is_recommended }"
          >
            <div class="plan-card-top">
              <div class="plan-badge-row">
                <n-tag v-if="plan.is_recommended" type="warning" size="small" round>推荐</n-tag>
                <n-tag :type="plan.is_active ? 'success' : 'error'" size="small" round>
                  {{ plan.is_active ? '上架中' : '已下架' }}
                </n-tag>
              </div>
              <div class="plan-name">{{ plan.name }}</div>
              <div class="plan-price">
                <span class="price-currency">¥</span>
                <span class="price-amount">{{ plan.price }}</span>
                <span class="price-period">/{{ plan.period_label }}</span>
              </div>
              <div class="plan-desc">{{ plan.description }}</div>
            </div>
            <div class="plan-features">
              <div v-for="(feat, i) in plan.features" :key="i" class="feature-item">
                <span class="feature-check">✓</span>
                <span>{{ feat }}</span>
              </div>
            </div>
            <div class="plan-actions">
              <n-button size="small" @click="handleEdit(plan)">编辑</n-button>
              <n-button
                size="small"
                :type="plan.is_active ? 'warning' : 'success'"
                @click="toggleActive(plan)"
              >
                {{ plan.is_active ? '下架' : '上架' }}
              </n-button>
              <n-popconfirm @positive-click="handleDelete(plan.id)">
                <template #trigger>
                  <n-button size="small" type="error">删除</n-button>
                </template>
                确认删除该套餐？
              </n-popconfirm>
            </div>
          </div>

          <div v-if="plans.length === 0 && !loading" class="empty-state">
            <div class="empty-icon">💳</div>
            <div class="empty-text">暂无套餐，点击「新建套餐」创建第一个套餐</div>
          </div>
        </div>
      </n-spin>
    </n-card>

    <!-- Create/Edit Modal -->
    <n-modal v-model:show="showModal" preset="card" :title="isEdit ? '编辑套餐' : '新建套餐'" style="width:600px">
      <n-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-placement="left"
        label-width="90"
        require-mark-placement="right-hanging"
      >
        <n-form-item label="套餐名称" path="name">
          <n-input v-model:value="form.name" placeholder="如：基础版、专业版、旗舰版" />
        </n-form-item>
        <n-form-item label="套餐描述" path="description">
          <n-input v-model:value="form.description" type="textarea" :rows="2" placeholder="简短描述套餐定位" />
        </n-form-item>
        <n-grid :cols="2" :x-gap="16">
          <n-gi>
            <n-form-item label="价格（元）" path="price">
              <n-input-number v-model:value="form.price" :min="0" :precision="2" placeholder="0.00" style="width:100%" />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="周期" path="period">
              <n-select v-model:value="form.period" :options="periodOptions" />
            </n-form-item>
          </n-gi>
        </n-grid>
        <n-grid :cols="2" :x-gap="16">
          <n-gi>
            <n-form-item label="每日章节数" path="daily_chapter_limit">
              <n-input-number v-model:value="form.daily_chapter_limit" :min="0" placeholder="0=不限" style="width:100%" />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="最大项目数" path="max_novels">
              <n-input-number v-model:value="form.max_novels" :min="0" placeholder="0=不限" style="width:100%" />
            </n-form-item>
          </n-gi>
        </n-grid>
        <n-form-item label="权益列表" path="features">
          <n-space vertical style="width:100%">
            <n-space v-for="(feat, i) in form.features" :key="i" align="center">
              <n-input v-model:value="form.features[i]" placeholder="填写一条权益说明" style="width:380px" />
              <n-button quaternary circle size="small" @click="removeFeature(i)">✕</n-button>
            </n-space>
            <n-button dashed size="small" @click="addFeature">+ 添加权益</n-button>
          </n-space>
        </n-form-item>
        <n-grid :cols="2" :x-gap="16">
          <n-gi>
            <n-form-item label="推荐套餐">
              <n-switch v-model:value="form.is_recommended" />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="立即上架">
              <n-switch v-model:value="form.is_active" />
            </n-form-item>
          </n-gi>
        </n-grid>
        <n-form-item label="排序权重" path="sort_order">
          <n-input-number v-model:value="form.sort_order" :min="0" placeholder="数值越小越靠前" style="width:100%" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="handleSave">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </n-space>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import {
  NSpace, NCard, NButton, NTag, NModal, NForm, NFormItem, NInput, NInputNumber,
  NSelect, NSwitch, NGrid, NGi, NPopconfirm, NSpin, NAlert, useMessage
} from 'naive-ui'

interface Plan {
  id: number
  name: string
  description: string
  price: number
  period: string
  period_label: string
  daily_chapter_limit: number
  max_novels: number
  features: string[]
  is_recommended: boolean
  is_active: boolean
  sort_order: number
}

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const showModal = ref(false)
const isEdit = ref(false)
const formRef = ref()

const periodOptions = [
  { label: '月付', value: 'monthly' },
  { label: '季付', value: 'quarterly' },
  { label: '年付', value: 'yearly' },
  { label: '永久', value: 'lifetime' }
]

const periodLabelMap: Record<string, string> = {
  monthly: '月',
  quarterly: '季',
  yearly: '年',
  lifetime: '永久'
}

const defaultForm = () => ({
  id: 0,
  name: '',
  description: '',
  price: 0,
  period: 'monthly',
  daily_chapter_limit: 10,
  max_novels: 5,
  features: [''],
  is_recommended: false,
  is_active: true,
  sort_order: 0
})

const form = reactive(defaultForm())

const rules = {
  name: [{ required: true, message: '请输入套餐名称', trigger: 'blur' }],
  price: [{ required: true, type: 'number', message: '请输入价格', trigger: 'blur' }],
  period: [{ required: true, message: '请选择周期', trigger: 'change' }]
}

const plans = ref<Plan[]>([
  {
    id: 1, name: '免费版', description: '适合体验和轻量创作', price: 0, period: 'monthly',
    period_label: '月', daily_chapter_limit: 3, max_novels: 2,
    features: ['每日 3 章生成额度', '最多 2 个项目', '基础提示词模板'],
    is_recommended: false, is_active: true, sort_order: 0
  },
  {
    id: 2, name: '专业版', description: '适合持续连载的创作者', price: 39, period: 'monthly',
    period_label: '月', daily_chapter_limit: 30, max_novels: 20,
    features: ['每日 30 章生成额度', '最多 20 个项目', '全量提示词', 'RAG 记忆增强', '优先支持'],
    is_recommended: true, is_active: true, sort_order: 1
  },
  {
    id: 3, name: '旗舰版', description: '无限制专业创作', price: 99, period: 'monthly',
    period_label: '月', daily_chapter_limit: 0, max_novels: 0,
    features: ['无限章节生成', '不限项目数量', '六维审查 + AI 润色', '专属客服', '优先新功能体验'],
    is_recommended: false, is_active: true, sort_order: 2
  }
])

const fetchPlans = async () => {
  loading.value = true
  error.value = null
  try {
    await new Promise(r => setTimeout(r, 400))
  } catch (e) {
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
}

const handleAdd = () => {
  isEdit.value = false
  Object.assign(form, defaultForm())
  showModal.value = true
}

const handleEdit = (plan: Plan) => {
  isEdit.value = true
  Object.assign(form, { ...plan, features: [...plan.features] })
  showModal.value = true
}

const handleSave = async () => {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    await new Promise(r => setTimeout(r, 500))
    const periodLabel = periodLabelMap[form.period] || form.period
    if (isEdit.value) {
      const idx = plans.value.findIndex(p => p.id === form.id)
      if (idx !== -1) {
        plans.value[idx] = { ...form, period_label: periodLabel, features: form.features.filter(f => f.trim()) }
      }
      message.success('套餐已更新')
    } else {
      plans.value.push({
        ...form,
        id: Date.now(),
        period_label: periodLabel,
        features: form.features.filter(f => f.trim())
      })
      message.success('套餐已创建')
    }
    showModal.value = false
  } catch {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const toggleActive = async (plan: Plan) => {
  plan.is_active = !plan.is_active
  message.success(plan.is_active ? '套餐已上架' : '套餐已下架')
}

const handleDelete = async (id: number) => {
  plans.value = plans.value.filter(p => p.id !== id)
  message.success('套餐已删除')
}

const addFeature = () => { form.features.push('') }
const removeFeature = (i: number) => { form.features.splice(i, 1) }

onMounted(fetchPlans)
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-title {
  font-size: 1rem;
  font-weight: 600;
  color: #fff;
}
.plans-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}
.plan-card {
  background: #141414;
  border: 1px solid #2A2A2A;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  transition: border-color 0.2s;
}
.plan-card:hover {
  border-color: #444;
}
.plan-recommended {
  border-color: #FFE500 !important;
  box-shadow: 0 0 0 1px rgba(255,229,0,0.2);
}
.plan-card-top {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.plan-badge-row {
  display: flex;
  gap: 6px;
}
.plan-name {
  font-size: 1.15rem;
  font-weight: 700;
  color: #fff;
}
.plan-price {
  display: flex;
  align-items: baseline;
  gap: 2px;
}
.price-currency {
  font-size: 0.9rem;
  color: #FFE500;
  font-weight: 600;
}
.price-amount {
  font-size: 2rem;
  font-weight: 800;
  color: #FFE500;
  line-height: 1;
}
.price-period {
  font-size: 0.85rem;
  color: #888;
  margin-left: 2px;
}
.plan-desc {
  font-size: 0.85rem;
  color: #888;
}
.plan-features {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}
.feature-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: #ccc;
}
.feature-check {
  color: #2ED573;
  font-weight: 700;
  font-size: 0.9rem;
}
.plan-actions {
  display: flex;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid #2A2A2A;
}
.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 60px 0;
}
.empty-icon {
  font-size: 3rem;
  margin-bottom: 12px;
}
.empty-text {
  color: #666;
  font-size: 0.95rem;
}
</style>

<!-- AIMETA P=后台模型目录配置_增删改章鱼1.0-3.0映射真实大模型与积分价档位|R=ModelCatalog CRUD|E=component:ModelCatalogConfig|X=ui|A=管理后台组件|D=vue,naive-ui|S=net -->
<template>
  <n-card :bordered="false">
    <template #header>
      <div class="card-header">
        <span class="card-title">🐙 模型目录（前台可选模型）</span>
        <n-space>
          <n-button quaternary size="small" :loading="loading" @click="load">刷新</n-button>
          <n-button type="primary" size="small" @click="openCreate">新增模型</n-button>
        </n-space>
      </div>
    </template>
    <n-spin :show="loading">
      <n-alert type="info" :bordered="false" style="margin-bottom: 16px">
        前台「模型」(如 章鱼1.0/2.0/3.0) 映射到真实大模型。<b>通道五键(真实模型/Base URL/Key引用/格式/推理档)留空则回退默认 llm.*</b>。
        显示名、积分价、最低档位、上架状态均可改，<b>保存后前台下次拉取即生效</b>。Key 请填 SystemConfig 键名(如 <code>llm.api_key</code>)，勿填明文。
      </n-alert>
      <n-data-table :columns="columns" :data="rows" :bordered="false" size="small" />
    </n-spin>

    <n-modal v-model:show="showModal" preset="card" :title="editing ? '编辑模型' : '新增模型'" style="max-width: 560px">
      <n-form label-placement="left" label-width="96">
        <n-form-item label="code">
          <n-input v-model:value="form.code" :disabled="!!editing" placeholder="稳定标识，如 octopus_v1" />
        </n-form-item>
        <n-form-item label="显示名">
          <n-input v-model:value="form.display_name" placeholder="章鱼1.0" />
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="form.description" placeholder="快速经济，适合走量" />
        </n-form-item>
        <n-form-item label="真实模型">
          <n-input v-model:value="form.real_model" placeholder="留空=回退 llm.model" />
        </n-form-item>
        <n-form-item label="Base URL">
          <n-input v-model:value="form.base_url" placeholder="留空=回退 llm.base_url" />
        </n-form-item>
        <n-form-item label="Key 引用">
          <n-input v-model:value="form.api_key_ref" placeholder="SystemConfig 键名，如 llm.api_key" />
        </n-form-item>
        <n-form-item label="API 格式">
          <n-input v-model:value="form.api_format" placeholder="留空=回退；可填 openai/anthropic 等" />
        </n-form-item>
        <n-form-item label="推理档">
          <n-input v-model:value="form.reasoning_effort" placeholder="留空=回退；minimal/low/medium/high" />
        </n-form-item>
        <n-form-item label="积分价/章">
          <n-input-number v-model:value="form.credit_price" :min="0" />
        </n-form-item>
        <n-form-item label="最低档位">
          <n-select v-model:value="form.min_tier" :options="tierOptions" />
        </n-form-item>
        <n-form-item label="排序">
          <n-input-number v-model:value="form.sort_order" :min="0" />
        </n-form-item>
        <n-form-item label="上架">
          <n-switch v-model:value="form.is_active" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </n-card>
</template>

<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import {
  NAlert, NButton, NCard, NDataTable, NForm, NFormItem, NInput, NInputNumber,
  NModal, NSelect, NSpace, NSpin, NSwitch, NTag, type DataTableColumns,
} from 'naive-ui'
import { ModelCatalogAPI, type ModelCatalogItem, type ModelCatalogPayload } from '@/api/model_catalog'
import { useAlert, globalAlert } from '@/composables/useAlert'

const { showAlert } = useAlert()

const TIER_LABEL: Record<string, string> = { free: '免费', creator: '创作者', flagship: '旗舰' }
const tierOptions = [
  { label: '免费 (free)', value: 'free' },
  { label: '创作者 (creator)', value: 'creator' },
  { label: '旗舰 (flagship)', value: 'flagship' },
]

const rows = ref<ModelCatalogItem[]>([])
const loading = ref(false)
const saving = ref(false)
const showModal = ref(false)
const editing = ref<ModelCatalogItem | null>(null)

function emptyForm(): ModelCatalogPayload {
  return {
    code: '', display_name: '', description: '', real_model: '', base_url: '',
    api_key_ref: '', api_format: '', reasoning_effort: '', credit_price: 10,
    min_tier: 'free', is_active: true, sort_order: 0,
  }
}
const form = reactive<ModelCatalogPayload>(emptyForm())

const columns: DataTableColumns<ModelCatalogItem> = [
  { title: '显示名', key: 'display_name', width: 110 },
  { title: 'code', key: 'code', width: 120, ellipsis: { tooltip: true } },
  { title: '真实模型', key: 'real_model', ellipsis: { tooltip: true }, render: (r) => r.real_model || h('span', { style: 'color:#666' }, '默认 llm.*') },
  { title: '积分/章', key: 'credit_price', width: 80, align: 'right' },
  { title: '最低档', key: 'min_tier', width: 80, render: (r) => TIER_LABEL[r.min_tier] || r.min_tier },
  {
    title: '上架', key: 'is_active', width: 70,
    render: (r) => h(NTag, { type: r.is_active ? 'success' : 'default', size: 'small' }, { default: () => (r.is_active ? '上架' : '下架') }),
  },
  {
    title: '操作', key: 'actions', width: 150,
    render: (r) =>
      h(NSpace, { size: 4 }, {
        default: () => [
          h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEdit(r) }, { default: () => '编辑' }),
          h(NButton, { size: 'tiny', quaternary: true, onClick: () => toggle(r) }, { default: () => (r.is_active ? '下架' : '上架') }),
          h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => remove(r) }, { default: () => '删除' }),
        ],
      }),
  },
]

async function load() {
  loading.value = true
  try {
    rows.value = await ModelCatalogAPI.list()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '加载模型目录失败', 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, emptyForm())
  showModal.value = true
}

function openEdit(row: ModelCatalogItem) {
  editing.value = row
  Object.assign(form, {
    code: row.code, display_name: row.display_name, description: row.description || '',
    real_model: row.real_model || '', base_url: row.base_url || '', api_key_ref: row.api_key_ref || '',
    api_format: row.api_format || '', reasoning_effort: row.reasoning_effort || '',
    credit_price: row.credit_price, min_tier: row.min_tier, is_active: row.is_active, sort_order: row.sort_order,
  })
  showModal.value = true
}

async function save() {
  if (!form.code || !form.display_name) {
    showAlert('code 与显示名必填', 'error')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await ModelCatalogAPI.update(editing.value.id, { ...form })
    } else {
      await ModelCatalogAPI.create({ ...form })
    }
    showAlert('已保存（前台下次拉取生效）', 'success')
    showModal.value = false
    await load()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function toggle(row: ModelCatalogItem) {
  try {
    await ModelCatalogAPI.toggle(row.id)
    await load()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '操作失败', 'error')
  }
}

async function remove(row: ModelCatalogItem) {
  const ok = await globalAlert.showConfirm(`确定删除模型「${row.display_name}」？`, '删除确认')
  if (!ok) return
  try {
    await ModelCatalogAPI.remove(row.id)
    await load()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '删除失败', 'error')
  }
}

onMounted(load)
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
</style>

<template>
  <n-space vertical size="large" class="payment-records">
    <!-- Stats Row -->
    <n-grid :cols="4" :x-gap="16">
      <n-gi v-for="stat in stats" :key="stat.label">
        <n-card :bordered="false" class="stat-card">
          <div class="stat-icon">{{ stat.icon }}</div>
          <div class="stat-value" :style="{ color: stat.color }">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- Records Table -->
    <n-card :bordered="false">
      <template #header>
        <div class="card-header">
          <span class="card-title">支付记录</span>
          <n-space :size="10">
            <n-select
              v-model:value="filters.channel"
              :options="channelOptions"
              placeholder="支付渠道"
              clearable
              style="width:130px"
              @update:value="handleFilter"
            />
            <n-select
              v-model:value="filters.status"
              :options="statusOptions"
              placeholder="状态"
              clearable
              style="width:110px"
              @update:value="handleFilter"
            />
            <n-date-picker
              v-model:value="filters.dateRange"
              type="daterange"
              clearable
              placeholder="选择日期范围"
              style="width:240px"
              @update:value="handleFilter"
            />
            <n-input
              v-model:value="filters.keyword"
              clearable
              placeholder="搜索用户名 / 订单号"
              style="width:200px"
              @update:value="handleFilter"
            />
            <n-button quaternary size="small" @click="fetchRecords" :loading="loading">
              刷新
            </n-button>
            <n-button size="small" @click="handleExport">
              导出 CSV
            </n-button>
          </n-space>
        </div>
      </template>

      <n-alert v-if="error" type="error" closable @close="error = null" style="margin-bottom:16px">
        {{ error }}
      </n-alert>

      <n-spin :show="loading">
        <n-data-table
          :columns="columns"
          :data="filteredRecords"
          :bordered="false"
          :pagination="pagination"
          :row-key="(row: PaymentRecord) => row.id"
          class="records-table"
        />
      </n-spin>
    </n-card>

    <!-- Detail Modal -->
    <n-modal v-model:show="showDetail" preset="card" title="支付详情" style="width:520px">
      <template v-if="selectedRecord">
        <n-descriptions :columns="1" label-placement="left" bordered>
          <n-descriptions-item label="订单号">{{ selectedRecord.order_id }}</n-descriptions-item>
          <n-descriptions-item label="用户">{{ selectedRecord.username }}</n-descriptions-item>
          <n-descriptions-item label="套餐">{{ selectedRecord.plan_name }}</n-descriptions-item>
          <n-descriptions-item label="金额">
            <span class="amount-text">¥{{ selectedRecord.amount.toFixed(2) }}</span>
          </n-descriptions-item>
          <n-descriptions-item label="支付渠道">
            <n-tag :type="channelTagType(selectedRecord.channel)" size="small">
              {{ channelLabel(selectedRecord.channel) }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="状态">
            <n-tag :type="statusTagType(selectedRecord.status)" size="small">
              {{ statusLabel(selectedRecord.status) }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="支付时间">{{ selectedRecord.paid_at || '—' }}</n-descriptions-item>
          <n-descriptions-item label="创建时间">{{ selectedRecord.created_at }}</n-descriptions-item>
          <n-descriptions-item label="渠道流水号">{{ selectedRecord.transaction_id || '—' }}</n-descriptions-item>
          <n-descriptions-item label="备注">{{ selectedRecord.remark || '无' }}</n-descriptions-item>
        </n-descriptions>
        <n-space justify="end" style="margin-top:16px">
          <n-button
            v-if="selectedRecord.status === 'pending'"
            type="warning"
            size="small"
            @click="handleRefund(selectedRecord)"
          >
            退款
          </n-button>
          <n-button @click="showDetail = false">关闭</n-button>
        </n-space>
      </template>
    </n-modal>
  </n-space>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, h } from 'vue'
import {
  NSpace, NCard, NGrid, NGi, NButton, NTag, NModal, NDescriptions, NDescriptionsItem,
  NDataTable, NSpin, NAlert, NSelect, NInput, NDatePicker, useMessage, type DataTableColumns
} from 'naive-ui'

interface PaymentRecord {
  id: number
  order_id: string
  username: string
  plan_name: string
  amount: number
  channel: string
  status: string
  paid_at: string | null
  created_at: string
  transaction_id: string | null
  remark: string | null
}

const message = useMessage()
const loading = ref(false)
const error = ref<string | null>(null)
const showDetail = ref(false)
const selectedRecord = ref<PaymentRecord | null>(null)

const filters = reactive({
  channel: null as string | null,
  status: null as string | null,
  dateRange: null as [number, number] | null,
  keyword: ''
})

const channelOptions = [
  { label: 'Stripe', value: 'stripe' },
  { label: '支付宝', value: 'alipay' },
  { label: '微信支付', value: 'wechat' }
]

const statusOptions = [
  { label: '待支付', value: 'pending' },
  { label: '已支付', value: 'paid' },
  { label: '已退款', value: 'refunded' },
  { label: '已取消', value: 'cancelled' },
  { label: '失败', value: 'failed' }
]

const channelLabel = (c: string) =>
  ({ stripe: 'Stripe', alipay: '支付宝', wechat: '微信支付' }[c] ?? c)

const channelTagType = (c: string): 'info' | 'success' | 'warning' | 'default' =>
  ({ stripe: 'info', alipay: 'info', wechat: 'success' }[c] as any ?? 'default')

const statusLabel = (s: string) =>
  ({ pending: '待支付', paid: '已支付', refunded: '已退款', cancelled: '已取消', failed: '失败' }[s] ?? s)

const statusTagType = (s: string): 'warning' | 'success' | 'error' | 'default' =>
  ({ pending: 'warning', paid: 'success', refunded: 'default', cancelled: 'default', failed: 'error' }[s] as any ?? 'default')

const stats = computed(() => {
  const paid = records.value.filter(r => r.status === 'paid')
  const refunded = records.value.filter(r => r.status === 'refunded')
  const total = paid.reduce((sum, r) => sum + r.amount, 0)
  return [
    { label: '总收入（元）', value: `¥${total.toFixed(2)}`, icon: '💰', color: '#FFE500' },
    { label: '成功订单数', value: paid.length, icon: '✅', color: '#2ED573' },
    { label: '退款订单', value: refunded.length, icon: '↩️', color: '#FF4757' },
    { label: '今日新增', value: records.value.filter(r => r.created_at.startsWith('2026-03-27')).length, icon: '📈', color: '#1890ff' }
  ]
})

const columns: DataTableColumns<PaymentRecord> = [
  {
    title: '订单号',
    key: 'order_id',
    width: 180,
    render: (row) => h('span', { class: 'order-id-text' }, row.order_id)
  },
  { title: '用户', key: 'username', width: 120 },
  { title: '套餐', key: 'plan_name', width: 100 },
  {
    title: '金额',
    key: 'amount',
    width: 100,
    render: (row) => h('span', { style: 'color:#FFE500;font-weight:600' }, `¥${row.amount.toFixed(2)}`)
  },
  {
    title: '渠道',
    key: 'channel',
    width: 100,
    render: (row) => h(NTag, { type: channelTagType(row.channel), size: 'small' }, { default: () => channelLabel(row.channel) })
  },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (row) => h(NTag, { type: statusTagType(row.status), size: 'small' }, { default: () => statusLabel(row.status) })
  },
  { title: '支付时间', key: 'paid_at', width: 160, render: (row) => row.paid_at ?? '—' },
  { title: '创建时间', key: 'created_at', width: 160 },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) =>
      h(NButton, { size: 'small', onClick: () => { selectedRecord.value = row; showDetail.value = true } }, { default: () => '详情' })
  }
]

const pagination = reactive({ page: 1, pageSize: 15, showSizePicker: true, pageSizes: [10, 15, 30, 50] })

const records = ref<PaymentRecord[]>([
  { id: 1, order_id: 'ORD-20260327-00001', username: 'alice', plan_name: '专业版', amount: 39, channel: 'alipay', status: 'paid', paid_at: '2026-03-27 10:20:00', created_at: '2026-03-27 10:18:44', transaction_id: '2026032722001400351234567890', remark: null },
  { id: 2, order_id: 'ORD-20260327-00002', username: 'bob_writer', plan_name: '旗舰版', amount: 99, channel: 'wechat', status: 'paid', paid_at: '2026-03-27 11:05:12', created_at: '2026-03-27 11:03:31', transaction_id: 'wx20260327110512abc123', remark: null },
  { id: 3, order_id: 'ORD-20260326-00098', username: 'carol', plan_name: '专业版', amount: 39, channel: 'stripe', status: 'refunded', paid_at: '2026-03-26 09:10:00', created_at: '2026-03-26 09:08:15', transaction_id: 'pi_3abc123XYZ', remark: '用户申请退款' },
  { id: 4, order_id: 'ORD-20260326-00097', username: 'dan_novel', plan_name: '旗舰版', amount: 99, channel: 'alipay', status: 'paid', paid_at: '2026-03-26 15:44:22', created_at: '2026-03-26 15:42:01', transaction_id: '2026032622001400354567890123', remark: null },
  { id: 5, order_id: 'ORD-20260326-00096', username: 'emma', plan_name: '专业版', amount: 39, channel: 'wechat', status: 'pending', paid_at: null, created_at: '2026-03-26 18:00:00', transaction_id: null, remark: null },
  { id: 6, order_id: 'ORD-20260325-00081', username: 'frank_lit', plan_name: '旗舰版', amount: 99, channel: 'stripe', status: 'paid', paid_at: '2026-03-25 08:30:00', created_at: '2026-03-25 08:28:11', transaction_id: 'pi_4def456ABC', remark: null },
  { id: 7, order_id: 'ORD-20260325-00080', username: 'grace', plan_name: '专业版', amount: 39, channel: 'alipay', status: 'cancelled', paid_at: null, created_at: '2026-03-25 14:12:00', transaction_id: null, remark: '超时未支付自动关闭' },
  { id: 8, order_id: 'ORD-20260324-00065', username: 'henry_99', plan_name: '旗舰版', amount: 99, channel: 'wechat', status: 'paid', paid_at: '2026-03-24 20:18:55', created_at: '2026-03-24 20:17:30', transaction_id: 'wx20260324201855xyz789', remark: null },
  { id: 9, order_id: 'ORD-20260323-00044', username: 'ivy_writer', plan_name: '专业版', amount: 39, channel: 'stripe', status: 'failed', paid_at: null, created_at: '2026-03-23 11:05:00', transaction_id: null, remark: '银行卡余额不足' },
  { id: 10, order_id: 'ORD-20260322-00033', username: 'jack', plan_name: '旗舰版', amount: 99, channel: 'alipay', status: 'paid', paid_at: '2026-03-22 16:30:00', created_at: '2026-03-22 16:28:00', transaction_id: '2026032222001400357890123456', remark: null }
])

const filteredRecords = computed(() => {
  return records.value.filter(r => {
    if (filters.channel && r.channel !== filters.channel) return false
    if (filters.status && r.status !== filters.status) return false
    if (filters.keyword) {
      const kw = filters.keyword.toLowerCase()
      if (!r.username.toLowerCase().includes(kw) && !r.order_id.toLowerCase().includes(kw)) return false
    }
    return true
  })
})

const handleFilter = () => {
  pagination.page = 1
}

const fetchRecords = async () => {
  loading.value = true
  error.value = null
  try {
    await new Promise(r => setTimeout(r, 400))
    message.success('数据已刷新')
  } catch {
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
}

const handleExport = () => {
  const headers = ['订单号', '用户', '套餐', '金额', '渠道', '状态', '支付时间', '创建时间']
  const rows = filteredRecords.value.map(r => [
    r.order_id, r.username, r.plan_name, r.amount, channelLabel(r.channel),
    statusLabel(r.status), r.paid_at ?? '', r.created_at
  ])
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `payment_records_${Date.now()}.csv`
  link.click()
  message.success('已导出 CSV')
}

const handleRefund = async (record: PaymentRecord) => {
  await new Promise(r => setTimeout(r, 500))
  record.status = 'refunded'
  record.remark = '管理员操作退款'
  showDetail.value = false
  message.success(`订单 ${record.order_id} 已退款`)
}

onMounted(fetchRecords)
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.card-title {
  font-size: 1rem;
  font-weight: 600;
  color: #fff;
}
.stat-card {
  text-align: center;
  padding: 4px 0;
}
.stat-icon {
  font-size: 1.5rem;
  margin-bottom: 6px;
}
.stat-value {
  font-size: 1.5rem;
  font-weight: 800;
  line-height: 1.2;
}
.stat-label {
  font-size: 0.8rem;
  color: #888;
  margin-top: 4px;
}
.order-id-text {
  font-family: monospace;
  font-size: 0.82rem;
  color: #aaa;
}
.amount-text {
  color: #FFE500;
  font-weight: 700;
}
</style>

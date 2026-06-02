<template>
  <n-space vertical size="large" class="payment-records">
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
            <n-button quaternary size="small" @click="fetchRecords" :loading="loading">
              刷新
            </n-button>
            <n-button size="small" @click="handleExport">
              导出本页 CSV
            </n-button>
          </n-space>
        </div>
      </template>

      <n-alert v-if="error" type="error" closable @close="error = null" style="margin-bottom:16px">
        {{ error }}
      </n-alert>

      <n-spin :show="loading">
        <n-data-table
          remote
          :columns="columns"
          :data="records"
          :bordered="false"
          :pagination="pagination"
          :row-key="(row: AdminPaymentOrder) => row.id"
          class="records-table"
          @update:page="onPageChange"
          @update:page-size="onPageSizeChange"
        />
      </n-spin>
    </n-card>

    <!-- Detail Modal -->
    <n-modal v-model:show="showDetail" preset="card" title="支付详情" style="width:520px">
      <template v-if="selectedRecord">
        <n-descriptions :columns="1" label-placement="left" bordered>
          <n-descriptions-item label="订单号">{{ selectedRecord.order_no }}</n-descriptions-item>
          <n-descriptions-item label="用户">{{ selectedRecord.username || `user_${selectedRecord.user_id}` }}</n-descriptions-item>
          <n-descriptions-item label="套餐">{{ selectedRecord.plan_name }}</n-descriptions-item>
          <n-descriptions-item label="金额">
            <span class="amount-text">{{ formatAmount(selectedRecord) }}</span>
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
          <n-descriptions-item label="支付时间">{{ fmtTime(selectedRecord.paid_at) }}</n-descriptions-item>
          <n-descriptions-item label="创建时间">{{ fmtTime(selectedRecord.created_at) }}</n-descriptions-item>
          <n-descriptions-item label="渠道流水号">{{ selectedRecord.transaction_id || '—' }}</n-descriptions-item>
          <n-descriptions-item label="备注">{{ selectedRecord.remark || '无' }}</n-descriptions-item>
        </n-descriptions>
        <n-space justify="end" style="margin-top:16px">
          <n-button @click="showDetail = false">关闭</n-button>
        </n-space>
      </template>
    </n-modal>
  </n-space>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, h } from 'vue'
import {
  NSpace, NCard, NButton, NTag, NModal, NDescriptions, NDescriptionsItem,
  NDataTable, NSpin, NAlert, NSelect, useMessage, type DataTableColumns
} from 'naive-ui'
import { paymentApi, type AdminPaymentOrder } from '@/api/payment'

const message = useMessage()
const loading = ref(false)
const error = ref<string | null>(null)
const showDetail = ref(false)
const selectedRecord = ref<AdminPaymentOrder | null>(null)

// 后端 admin/orders 仅支持 channel / status 过滤 + 分页（无关键字/日期范围检索）。
const filters = reactive({
  channel: null as string | null,
  status: null as string | null,
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

const fmtTime = (t?: string | null) => (t ? t.replace('T', ' ').slice(0, 19) : '—')

const CURRENCY_SYMBOL: Record<string, string> = { CNY: '¥', USD: '$', EUR: '€', GBP: '£', JPY: '¥', HKD: 'HK$' }
const formatAmount = (row: AdminPaymentOrder) => {
  const sym = CURRENCY_SYMBOL[(row.currency || 'CNY').toUpperCase()] ?? `${row.currency} `
  return `${sym}${Number(row.amount).toFixed(2)}`
}

const columns: DataTableColumns<AdminPaymentOrder> = [
  {
    title: '订单号',
    key: 'order_no',
    width: 200,
    render: (row) => h('span', { class: 'order-id-text' }, row.order_no)
  },
  { title: '用户', key: 'username', width: 120, render: (row) => row.username || `user_${row.user_id}` },
  { title: '套餐', key: 'plan_name', width: 100 },
  {
    title: '金额',
    key: 'amount',
    width: 110,
    render: (row) => h('span', { style: 'color:#FFE500;font-weight:600' }, formatAmount(row))
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
  { title: '支付时间', key: 'paid_at', width: 170, render: (row) => fmtTime(row.paid_at) },
  { title: '创建时间', key: 'created_at', width: 170, render: (row) => fmtTime(row.created_at) },
  {
    title: '操作',
    key: 'actions',
    width: 90,
    render: (row) =>
      h(NButton, { size: 'small', onClick: () => { selectedRecord.value = row; showDetail.value = true } }, { default: () => '详情' })
  }
]

const records = ref<AdminPaymentOrder[]>([])

const pagination = reactive({
  page: 1,
  pageSize: 15,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 15, 30, 50],
})

const fetchRecords = async () => {
  loading.value = true
  error.value = null
  try {
    const res = await paymentApi.adminListOrders({
      channel: filters.channel ?? undefined,
      status: filters.status ?? undefined,
      page: pagination.page,
      pageSize: pagination.pageSize,
    })
    records.value = res.items
    pagination.itemCount = res.total
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载支付记录失败'
  } finally {
    loading.value = false
  }
}

const handleFilter = () => {
  pagination.page = 1
  fetchRecords()
}

const onPageChange = (page: number) => {
  pagination.page = page
  fetchRecords()
}

const onPageSizeChange = (size: number) => {
  pagination.pageSize = size
  pagination.page = 1
  fetchRecords()
}

const handleExport = () => {
  const headers = ['订单号', '用户', '套餐', '金额', '货币', '渠道', '状态', '支付时间', '创建时间']
  const rows = records.value.map(r => [
    r.order_no, r.username || `user_${r.user_id}`, r.plan_name, Number(r.amount).toFixed(2), r.currency,
    channelLabel(r.channel), statusLabel(r.status), fmtTime(r.paid_at), fmtTime(r.created_at)
  ])
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `payment_records_p${pagination.page}.csv`
  link.click()
  message.success('已导出本页 CSV')
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

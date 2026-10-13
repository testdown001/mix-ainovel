<!-- AIMETA P=小说管理_管理员小说列表管理|R=小说列表_删除_统计|NR=不含普通用户功能|E=component:NovelManagement|X=ui|A=管理组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <n-card class="novel-management-card" size="large" :bordered="false">
    <template #header>
      <div class="card-header">
        <span class="card-title">小说管理</span>
        <n-tag size="small" type="primary" round>共 {{ novels.length }} 项</n-tag>
      </div>
    </template>

    <n-space vertical size="large">
      <n-alert type="info" :bordered="false">
        仅系统项目和 AI 测试项目可在后台删除，用户作品受保护。删除需在两个弹窗中分别输入“删除”。
      </n-alert>
      <n-alert v-if="success" type="success" closable @close="success = null">
        {{ success }}
      </n-alert>
      <n-alert v-if="error" type="error" closable @close="error = null">
        {{ error }}
      </n-alert>
      <n-space align="center">
        <n-button
          size="small"
          :disabled="selectionLocked || !deletableNovels.length || deletableNovels.length > 100"
          @click="selectAllDeletable"
        >
          全选可删除项目
        </n-button>
        <n-button
          size="small"
          :disabled="selectionLocked || !checkedProjectIds.length"
          @click="updateSelection([])"
        >
          清空选择
        </n-button>
        <n-button
          type="error"
          size="small"
          :disabled="selectionLocked || !selectedNovels.length"
          @click="startBatchDeletion"
        >
          批量删除（{{ selectedNovels.length }}）
        </n-button>
        <span class="table-subtitle">每批最多 100 项；用户作品不可选</span>
      </n-space>

      <n-spin :show="loading">
        <template #default>
          <n-empty
            v-if="!novels.length && !loading"
            description="暂无小说项目"
            class="empty-state"
          />
          <div v-else>
            <n-space v-if="isMobile" vertical size="large">
              <n-card
                v-for="novel in novels"
                :key="novel.id"
                size="small"
                embedded
                class="novel-card"
              >
                <template #header>
                  <div class="mobile-card-header">
                    <n-checkbox
                      :checked="checkedProjectIds.includes(novel.id)"
                      :disabled="!canDelete(novel) || selectionLocked"
                      @update:checked="(checked) => toggleSelection(novel, checked)"
                      >选择</n-checkbox
                    >
                    <span class="mobile-card-title">{{ novel.title }}</span>
                    <n-tag size="small" type="info" round>{{ novel.genre || '未分类' }}</n-tag>
                  </div>
                </template>
                <div class="mobile-meta">
                  <span class="mobile-label">编号</span>
                  <span class="mobile-value">{{ novel.id }}</span>
                </div>
                <div class="mobile-meta">
                  <span class="mobile-label">创作者</span>
                  <span class="mobile-value">{{ novel.owner_username }}</span>
                </div>
                <div class="mobile-meta">
                  <span class="mobile-label">来源</span>
                  <span class="mobile-value">{{ sourceLabel(novel) }}</span>
                </div>
                <div class="mobile-meta">
                  <span class="mobile-label">进度</span>
                  <span class="mobile-value">{{ formatProgress(novel) }}</span>
                </div>
                <div class="mobile-meta">
                  <span class="mobile-label">最近更新</span>
                  <span class="mobile-value">{{ formatDate(novel.last_edited) }}</span>
                </div>
                <template #footer>
                  <n-space vertical>
                    <n-button type="primary" size="small" block @click="viewDetails(novel.id)">
                      查看详情
                    </n-button>
                    <n-button
                      v-if="canDelete(novel)"
                      type="error"
                      size="small"
                      block
                      @click="startDeletion(novel)"
                    >
                      删除测试 / 系统项目
                    </n-button>
                  </n-space>
                </template>
              </n-card>
            </n-space>
            <n-data-table
              v-else
              :columns="columns"
              :data="novels"
              :pagination="pagination"
              :row-key="(row: AdminNovelSummary) => row.id"
              :checked-row-keys="checkedProjectIds"
              @update:checked-row-keys="updateSelection"
              :bordered="false"
              size="small"
              class="novel-table"
            />
          </div>
        </template>
      </n-spin>
    </n-space>
    <n-modal
      :show="showFirstConfirmation"
      preset="card"
      :title="isBatchDeletion ? '批量删除：第一次确认' : '删除项目：第一次确认'"
      style="width: min(480px, calc(100vw - 32px))"
      :closable="!confirming"
      :mask-closable="!confirming"
      :close-on-esc="!confirming"
      @update:show="cancelDeletion"
    >
      <n-space vertical>
        <div>将永久删除以下 {{ deletionTargets.length }} 个项目：</div>
        <div class="deletion-targets">
          <div v-for="novel in deletionTargets" :key="novel.id" class="deletion-target">
            <div>{{ novel.title }}</div>
            <div class="table-subtitle">项目编号：{{ novel.id }}</div>
          </div>
        </div>
        <n-alert type="warning">删除将永久移除该项目及关联章节、蓝图等数据。</n-alert>
        <n-alert v-if="deletionError" type="error">{{ deletionError }}</n-alert>
        <label for="first-delete-confirmation">请输入“删除”继续</label>
        <n-input
          v-model:value="firstConfirmation"
          placeholder="删除"
          :disabled="confirming"
          :input-props="{ id: 'first-delete-confirmation', autocomplete: 'off' }"
          @keydown.enter="confirmFirstDeletion"
        />
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button :disabled="confirming" @click="cancelDeletion">取消</n-button>
          <n-button
            type="warning"
            :loading="confirming"
            :disabled="firstConfirmation !== '删除' || confirming"
            @click="confirmFirstDeletion"
          >
            进入第二次确认
          </n-button>
        </n-space>
      </template>
    </n-modal>
    <n-modal
      :show="showSecondConfirmation"
      preset="card"
      :title="isBatchDeletion ? '批量删除：第二次确认' : '删除项目：第二次确认'"
      style="width: min(480px, calc(100vw - 32px))"
      :closable="!deleting"
      :mask-closable="!deleting"
      :close-on-esc="!deleting"
      @update:show="cancelDeletion"
    >
      <n-space vertical>
        <div>最终确认删除以下 {{ deletionTargets.length }} 个项目：</div>
        <div class="deletion-targets">
          <div v-for="novel in deletionTargets" :key="novel.id" class="deletion-target">
            <div>{{ novel.title }}</div>
            <div class="table-subtitle">项目编号：{{ novel.id }}</div>
          </div>
        </div>
        <n-alert type="error">此操作无法撤销。请再次输入“删除”完成最终确认。</n-alert>
        <n-alert v-if="deletionError" type="error">{{ deletionError }}</n-alert>
        <label for="second-delete-confirmation">再次输入“删除”</label>
        <n-input
          v-model:value="secondConfirmation"
          placeholder="删除"
          :disabled="deleting"
          :input-props="{ id: 'second-delete-confirmation', autocomplete: 'off' }"
          @keydown.enter="confirmSecondDeletion"
        />
      </n-space>
      <template #footer>
        <n-space justify="end">
          <n-button :disabled="deleting" @click="cancelDeletion">取消</n-button>
          <n-button
            type="error"
            :loading="deleting"
            :disabled="secondConfirmation !== '删除' || deleting"
            @click="confirmSecondDeletion"
          >
            永久删除 {{ deletionTargets.length }} 项
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </n-card>
</template>

<script setup lang="ts">
import { computed, h, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NDataTable,
  NEmpty,
  NInput,
  NModal,
  NSpin,
  NTag,
  NSpace,
  type DataTableColumns,
} from 'naive-ui'

import { AdminAPI } from '@/api/admin'
import type { AdminNovelSummary } from '@/api/admin'

const novels = ref<AdminNovelSummary[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const success = ref<string | null>(null)
const checkedProjectIds = ref<string[]>([])
const deletionTargets = ref<AdminNovelSummary[]>([])
const isBatchDeletion = ref(false)
const showFirstConfirmation = ref(false)
const showSecondConfirmation = ref(false)
const firstConfirmation = ref('')
const secondConfirmation = ref('')
const confirmationToken = ref('')
const confirming = ref(false)
const deleting = ref(false)
const deletionError = ref<string | null>(null)
const isMobile = ref(false)
const router = useRouter()

const pagination = {
  pageSize: 8,
  showSizePicker: false,
}

const updateLayout = () => {
  isMobile.value = window.innerWidth < 768
}

const formatDate = (value: string | null | undefined) => {
  if (!value) return '未记录'
  try {
    const date = new Date(value)
    if (isNaN(date.getTime())) return '未记录'

    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')

    return `${year}年${month}月${day}日 ${hours}:${minutes}`
  } catch (error) {
    return '未记录'
  }
}

const formatProgress = (
  novel: Pick<AdminNovelSummary, 'completed_chapters' | 'total_chapters'>,
) => {
  const total = novel.total_chapters || 0
  const completed = novel.completed_chapters || 0
  return `${completed} / ${total}`
}

const viewDetails = (novelId: string) => {
  router.push(`/admin/novel/${novelId}`)
}

const canDelete = (novel: AdminNovelSummary) =>
  novel.can_delete === true && ['system', 'ai_test'].includes(novel.creation_source)

const deletableNovels = computed(() => novels.value.filter(canDelete))
const selectedNovels = computed(() =>
  deletableNovels.value.filter((novel) => checkedProjectIds.value.includes(novel.id)),
)
const selectionLocked = computed(
  () =>
    showFirstConfirmation.value ||
    showSecondConfirmation.value ||
    confirming.value ||
    deleting.value,
)

const updateSelection = (keys: (string | number)[]) => {
  if (selectionLocked.value) return
  const eligible = new Set(deletableNovels.value.map((novel) => novel.id))
  checkedProjectIds.value = [...new Set(keys.map(String).filter((key) => eligible.has(key)))].slice(
    0,
    100,
  )
}

const selectAllDeletable = () => {
  if (deletableNovels.value.length <= 100)
    updateSelection(deletableNovels.value.map((novel) => novel.id))
}

const toggleSelection = (novel: AdminNovelSummary, checked: boolean) => {
  updateSelection(
    checked
      ? [...checkedProjectIds.value, novel.id]
      : checkedProjectIds.value.filter((id) => id !== novel.id),
  )
}

const sourceLabel = (novel: AdminNovelSummary) => {
  if (novel.creation_source === 'system') return '系统项目'
  if (novel.creation_source === 'ai_test') return 'AI 测试项目'
  if (novel.creation_source === 'user') return '用户作品（受保护）'
  return '来源未确认（受保护）'
}

const resetDeletion = () => {
  showFirstConfirmation.value = false
  showSecondConfirmation.value = false
  deletionTargets.value = []
  isBatchDeletion.value = false
  firstConfirmation.value = ''
  secondConfirmation.value = ''
  confirmationToken.value = ''
  deletionError.value = null
}

const cancelDeletion = () => {
  if (!confirming.value && !deleting.value) resetDeletion()
}

const beginDeletion = (targets: AdminNovelSummary[], batch: boolean) => {
  if (
    !targets.length ||
    targets.length > 100 ||
    targets.some((novel) => !canDelete(novel)) ||
    selectionLocked.value
  )
    return
  resetDeletion()
  success.value = null
  // Freeze the exact confirmation set, independently of later checkbox updates.
  deletionTargets.value = targets.map((novel) => ({ ...novel }))
  isBatchDeletion.value = batch
  showFirstConfirmation.value = true
}

const startDeletion = (novel: AdminNovelSummary) => beginDeletion([novel], false)

const startBatchDeletion = () => {
  if (selectedNovels.value.length !== checkedProjectIds.value.length) {
    error.value = '部分选择已失效，请刷新列表后重新选择'
    return
  }
  beginDeletion(selectedNovels.value, true)
}

const confirmFirstDeletion = async () => {
  const targets = deletionTargets.value
  if (
    !targets.length ||
    targets.some((novel) => !canDelete(novel)) ||
    !showFirstConfirmation.value ||
    firstConfirmation.value !== '删除' ||
    confirming.value
  )
    return
  confirming.value = true
  deletionError.value = null
  try {
    const ticket = isBatchDeletion.value
      ? await AdminAPI.confirmNovelsDeletion(
          targets.map((novel) => novel.id),
          firstConfirmation.value,
        )
      : await AdminAPI.confirmNovelDeletion(targets[0]!.id, firstConfirmation.value)
    confirmationToken.value = ticket.confirmation_token
    secondConfirmation.value = ''
    showFirstConfirmation.value = false
    showSecondConfirmation.value = true
  } catch (e) {
    deletionError.value = e instanceof Error ? e.message : '第一次删除确认失败'
  } finally {
    confirming.value = false
  }
}

const confirmSecondDeletion = async () => {
  const targets = deletionTargets.value
  if (
    !targets.length ||
    targets.some((novel) => !canDelete(novel)) ||
    !showSecondConfirmation.value ||
    secondConfirmation.value !== '删除' ||
    !confirmationToken.value ||
    deleting.value
  )
    return
  deleting.value = true
  deletionError.value = null
  try {
    const ids = targets.map((novel) => novel.id)
    if (isBatchDeletion.value) {
      await AdminAPI.deleteNovels(ids, secondConfirmation.value, confirmationToken.value)
    } else {
      await AdminAPI.deleteNovel(ids[0]!, secondConfirmation.value, confirmationToken.value)
    }
    const deletedIds = new Set(ids)
    novels.value = novels.value.filter((item) => !deletedIds.has(item.id))
    checkedProjectIds.value = checkedProjectIds.value.filter((id) => !deletedIds.has(id))
    success.value = `已删除 ${targets.length} 个项目`
    resetDeletion()
  } catch (e) {
    deletionError.value = e instanceof Error ? e.message : '删除失败，请重新完成两次确认后重试'
    // Failed/expired tickets must go through both confirmations again.
    confirmationToken.value = ''
    secondConfirmation.value = ''
    firstConfirmation.value = ''
    showSecondConfirmation.value = false
    showFirstConfirmation.value = true
  } finally {
    deleting.value = false
  }
}

const columns: DataTableColumns<AdminNovelSummary> = [
  {
    type: 'selection',
    disabled: (row) => !canDelete(row) || selectionLocked.value,
  },
  {
    title: '项目',
    key: 'title',
    ellipsis: { tooltip: true },
    render(row) {
      return h('div', { class: 'table-title-cell' }, [
        h('div', { class: 'table-title' }, row.title),
        h('div', { class: 'table-subtitle' }, row.id),
      ])
    },
  },
  {
    title: '类型',
    key: 'genre',
    render(row) {
      return h(
        NTag,
        { type: 'info', size: 'small', round: true, bordered: false },
        { default: () => row.genre || '未分类' },
      )
    },
  },
  {
    title: '创作者',
    key: 'owner_username',
    render(row) {
      return h('span', { class: 'table-owner' }, row.owner_username)
    },
  },
  {
    title: '来源',
    key: 'creation_source',
    render: sourceLabel,
  },
  {
    title: '进度',
    key: 'progress',
    render(row) {
      return h('span', { class: 'table-progress' }, formatProgress(row))
    },
  },
  {
    title: '最近更新',
    key: 'last_edited',
    render(row) {
      return h('span', { class: 'table-date' }, formatDate(row.last_edited))
    },
  },
  {
    title: '操作',
    key: 'actions',
    align: 'center',
    render(row) {
      const actions = [
        h(
          NButton,
          {
            size: 'small',
            type: 'primary',
            tertiary: true,
            onClick: () => viewDetails(row.id),
          },
          { default: () => '详情' },
        ),
      ]
      if (canDelete(row)) {
        actions.push(
          h(
            NButton,
            {
              size: 'small',
              type: 'error',
              tertiary: true,
              onClick: () => startDeletion(row),
            },
            { default: () => '删除' },
          ),
        )
      }
      return h(NSpace, { justify: 'center' }, { default: () => actions })
    },
  },
]

const fetchNovels = async () => {
  loading.value = true
  error.value = null
  try {
    novels.value = await AdminAPI.listNovels()
    updateSelection(checkedProjectIds.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '获取小说数据失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  updateLayout()
  window.addEventListener('resize', updateLayout)
  fetchNovels()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateLayout)
})
</script>

<style scoped>
.novel-management-card {
  width: 100%;
  box-sizing: border-box;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: #ffffff;
  font-family: 'Space Grotesk', sans-serif;
}

.novel-table {
  width: 100%;
}

.deletion-targets {
  max-height: 220px;
  overflow-y: auto;
}

.deletion-target {
  padding: 8px 0;
  border-bottom: 1px solid #2a2a2a;
}

.table-title-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.table-title {
  font-weight: 600;
  color: #ffffff;
}

.table-subtitle {
  font-size: 0.75rem;
  color: #888888;
  word-break: break-all;
}

.table-owner,
.table-progress,
.table-date {
  color: #cccccc;
}

.novel-card {
  border-radius: 12px;
  background: #1c1c1c !important;
  border: 1px solid #2a2a2a !important;
}

.mobile-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.mobile-card-title {
  font-size: 1rem;
  font-weight: 600;
  color: #ffffff;
}

.mobile-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
  font-size: 0.875rem;
  color: #cccccc;
  word-break: break-word;
}

.mobile-label {
  color: #888888;
}

.mobile-value {
  color: #ffffff;
  font-weight: 500;
  text-align: right;
  margin-left: 12px;
}

.empty-state {
  padding: 48px 0;
}

@media (max-width: 767px) {
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .card-title {
    font-size: 1.125rem;
  }
}
</style>

<template>
  <section class="my-6 rounded-xl border border-neutral-700 p-4 text-neutral-200">
    <div class="flex items-center justify-between gap-3">
      <h2 class="font-semibold">生成失败诊断（管理员）</h2>
      <button class="rounded border border-neutral-600 px-3 py-1" :disabled="loading" @click="refresh">
        {{ loading ? '加载中…' : '刷新日志' }}
      </button>
    </div>
    <p class="mt-2 text-sm text-neutral-400">最近 30 天，最多 100 次失败。重试记录独立保留，不增加创作任务卡片；旧失败无法补回未保存的审校报告。</p>
    <p v-if="error" role="alert" class="mt-3 text-red-400">{{ error }}</p>
    <p v-else-if="!loading && !records.length" class="mt-3 text-sm">暂无已记录的失败诊断。</p>
    <details v-for="record in records" :key="record.id" class="mt-3 rounded border border-neutral-700 p-3">
      <summary class="cursor-pointer">{{ record.chapter_number ? `第 ${record.chapter_number} 章` : record.task_type }} · {{ record.error_type }} · {{ record.created_at }}</summary>
      <p class="mt-2 whitespace-pre-wrap">{{ record.message }}</p>
      <p class="my-2 break-all text-xs text-neutral-400">阶段：{{ record.stage || '未上报' }}<br>任务：{{ record.task_id }}<br>执行：{{ record.execution_id || '旧版任务' }}<br>日志：{{ record.id }}</p>
      <div v-for="(issue, index) in record.issues" :key="index" class="my-2 rounded bg-neutral-800 p-3 text-sm">
        <strong>{{ issue.category }} · {{ issue.severity }}</strong>
        <p class="whitespace-pre-wrap">证据：{{ issue.evidence }}</p>
        <p class="whitespace-pre-wrap">原因：{{ issue.explanation }}</p>
      </div>
      <details><summary class="cursor-pointer text-sm">异常堆栈（已脱敏）</summary><pre class="mt-2 max-h-96 overflow-auto whitespace-pre-wrap break-all text-xs">{{ record.traceback }}</pre></details>
    </details>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { requestJson } from '@/api/http'

interface Diagnostic {
  id: string; created_at: string; chapter_number: number | null; task_type: string
  task_id: string; execution_id: string | null; stage: string; error_type: string
  message: string; traceback: string
  issues: { category: string; severity: string; evidence: string; explanation: string }[]
}
const props = defineProps<{ projectId: string }>()
const records = ref<Diagnostic[]>([])
const loading = ref(false)
const error = ref('')
let requestVersion = 0
async function refresh() {
  const version = ++requestVersion
  loading.value = true
  error.value = ''
  try {
    const result = await requestJson<{ records: Diagnostic[] }>(`/api/admin/novels/${encodeURIComponent(props.projectId)}/generation-diagnostics`)
    if (version === requestVersion) records.value = result.records
  } catch (err) {
    if (version === requestVersion) error.value = err instanceof Error ? err.message : '日志加载失败'
  } finally {
    if (version === requestVersion) loading.value = false
  }
}
watch(() => props.projectId, () => { records.value = []; void refresh() }, { immediate: true })
</script>

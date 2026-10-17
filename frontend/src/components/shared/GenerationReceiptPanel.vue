<template>
  <details class="generation-receipts">
    <summary>本版本实际依据与执行记录</summary>
    <p>版本 {{ versionId ?? '未知' }} · 报告完成不等于正文已修改。</p>
    <h4>实际上下文</h4>
    <p v-if="!boundContextReceipt">unknown：此版本没有可核验的上下文收据，不代表未使用上下文。</p>
    <pre v-else>{{ JSON.stringify(boundContextReceipt, null, 2) }}</pre>
    <h4>执行与修改</h4>
    <p v-if="!boundExecutionReceipt">unknown：此版本没有执行收据，不能推断检查已完成或修改已应用。</p>
    <pre v-else>{{ JSON.stringify(boundExecutionReceipt, null, 2) }}</pre>
    <p>参考卡片属于搜索资料 / AI 分析或仿写，不代表已读取原著全文；作者声音与本书人物行动优先。</p>
  </details>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { receiptForVersion } from '@/utils/generationReceipt'
const props = defineProps<{
  versionId?: number | null
  contextReceipt?: Record<string, unknown> | null
  executionReceipt?: Record<string, unknown> | null
}>()
const boundContextReceipt = computed(() => receiptForVersion(props.contextReceipt, props.versionId))
const boundExecutionReceipt = computed(() => receiptForVersion(props.executionReceipt, props.versionId))
</script>

<style scoped>
.generation-receipts { padding: 12px; border: 1px solid var(--md-outline-variant, #555); border-radius: 8px; margin: 12px 0; font-size: 12px; }
summary { cursor: pointer; font-weight: 600; }
p { color: var(--md-on-surface-variant, #888); line-height: 1.7; margin: 8px 0; }
h4 { font-weight: 600; margin-top: 8px; }
pre { max-height: 320px; overflow: auto; font-size: 11px; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>

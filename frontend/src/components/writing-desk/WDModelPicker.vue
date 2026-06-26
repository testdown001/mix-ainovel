<!-- AIMETA P=模型选择器_前台选模型+润色+积分余额|R=按档展示可选模型并v-model回传|NR=不含计费逻辑(后端)|E=component:WDModelPicker|X=ui|A=组件|D=vue,naive-ui|S=net -->
<template>
  <div v-if="models.length" class="model-picker">
    <span class="mp-label">🐙 模型</span>
    <n-select
      size="small"
      :value="modelCode"
      :options="options"
      :consistent-menu-width="false"
      style="min-width: 200px"
      @update:value="(v: string) => emit('update:modelCode', v)"
    />
    <n-checkbox
      size="small"
      :checked="enablePolish"
      @update:checked="(v: boolean) => emit('update:enablePolish', v)"
    >
      润色 <span class="mp-dim">+{{ polishPrice }}积分</span>
    </n-checkbox>
    <span class="mp-spacer" />
    <span class="mp-balance" title="本月剩余积分">积分余额 <b>{{ balance }}</b></span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NCheckbox, NSelect } from 'naive-ui'
import { ModelCatalogAPI, type AvailableModel } from '@/api/model_catalog'

const props = defineProps<{ modelCode: string | null; enablePolish: boolean }>()
const emit = defineEmits<{
  'update:modelCode': [v: string]
  'update:enablePolish': [v: boolean]
}>()

const models = ref<AvailableModel[]>([])
const polishPrice = ref(5)
const balance = ref<number | string>('—')

const options = computed(() =>
  models.value.map((m) => ({
    label: m.locked
      ? `${m.display_name}（需升级 · ${m.credit_price}积分）`
      : `${m.display_name} · ${m.credit_price}积分`,
    value: m.code,
    disabled: m.locked,
  })),
)

async function load() {
  try {
    const r = await ModelCatalogAPI.getAvailable()
    models.value = r.models || []
    polishPrice.value = r.polish_price ?? 5
    balance.value = r.credit?.balance ?? '—'
    // 默认选中首个未锁模型，使计费即时生效
    if (!props.modelCode) {
      const first = models.value.find((m) => !m.locked)
      if (first) emit('update:modelCode', first.code)
    }
  } catch {
    // 静默：拉取失败不阻断生成（后端 model_code 缺省时按默认通道、不计费）
  }
}

onMounted(load)
</script>

<style scoped>
.model-picker {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  margin-bottom: 8px;
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
  font-size: 13px;
  color: #ccc;
  flex-wrap: wrap;
}
.mp-label {
  font-weight: 600;
  color: #fff;
}
.mp-dim {
  color: #777;
  font-size: 12px;
}
.mp-spacer {
  flex: 1;
}
.mp-balance {
  color: #888;
}
.mp-balance b {
  color: #ffe500;
}
</style>

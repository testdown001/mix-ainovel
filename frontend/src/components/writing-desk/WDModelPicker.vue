<!-- AIMETA P=模型选择器_前台选模型+润色+积分余额|R=按档展示可选模型并v-model回传|NR=不含计费逻辑(后端)|E=component:WDModelPicker|X=ui|A=组件|D=vue,naive-ui|S=net -->
<template>
  <div v-if="models.length" class="model-picker">
    <span class="mp-label">模型</span>
    <n-select
      size="tiny"
      :value="modelCode"
      :options="options"
      :consistent-menu-width="false"
      style="min-width: 168px"
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
    <span class="mp-balance" title="当前可用积分(月度+永久)">
      <CoinIcon :size="12" /> <b>{{ balance }}</b>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NCheckbox, NSelect } from 'naive-ui'
import CoinIcon from '@/components/shared/CoinIcon.vue'
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
    // 余额展示两池总和(月度+永久充值);老后端无 total 字段时回退月度池
    balance.value = (r.credit as any)?.total ?? r.credit?.balance ?? '—'
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
/* 紧凑单行:降低视觉重量,别与写作区抢空间 */
.model-picker {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 10px;
  margin-bottom: 6px;
  background: var(--md-surface, #141414);
  border: 1px solid var(--md-outline-variant, #1c1c1c);
  border-radius: 8px;
  font-size: 12px;
  color: #aaa;
  flex-wrap: wrap;
}
.mp-label {
  font-weight: 600;
  font-size: 12px;
  color: #888;
  letter-spacing: 0.05em;
}
.mp-dim {
  color: #666;
  font-size: 11px;
}
.mp-spacer {
  flex: 1;
}
.mp-balance {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #777;
}
.mp-balance b {
  color: #ffe500;
  font-weight: 600;
}
</style>

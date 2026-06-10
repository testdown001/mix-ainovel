<!-- AIMETA P=能力门控配置_后台|R=会员能力/流水线开关的最低档位配置(覆写SystemConfig)|NR=不含门控判定逻辑|E=component:FeatureGatingConfig|X=ui|A=配置面板|D=vue,naive-ui|S=net|RD=./README.ai -->
<template>
  <div class="feature-gating-config">
    <n-spin :show="loading">
      <n-space vertical :size="20">
        <n-alert type="info" :show-icon="false">
          档位映射「代码给默认值、后台配置生效值」：此处保存的覆写写入 SystemConfig
          （feature_gating.min_tier_overrides / feature_gating.flow_override_min_tiers），
          同时驱动真实门控判定与定价页能力展示，二者永不漂移。清空覆写即回到代码默认。
        </n-alert>

        <n-card title="会员能力档位（定价页展示 + 功能门控）" size="small">
          <n-table :bordered="false" size="small">
            <thead>
              <tr><th>能力</th><th>说明</th><th style="width:160px">最低解锁档位</th></tr>
            </thead>
            <tbody>
              <tr v-for="cap in capabilities" :key="cap.key">
                <td>{{ cap.label }}<n-tag v-if="tierMap[cap.key] !== cap.default_min_tier" size="tiny" type="warning" style="margin-left:6px">已覆写</n-tag></td>
                <td class="desc">{{ cap.description }}</td>
                <td><n-select v-model:value="tierMap[cap.key]" :options="tierOptions" size="small" /></td>
              </tr>
            </tbody>
          </n-table>
          <n-button type="primary" :loading="saving === 'caps'" style="margin-top:12px" @click="saveCaps">保存能力档位</n-button>
        </n-card>

        <n-card title="流水线开关档位（flow_config 显式覆写门控）" size="small">
          <n-alert type="default" :show-icon="false" style="margin-bottom:12px">
            生成请求可经 flow_config 显式开启流水线开关；用户档位低于此处设置时请求被拒（403）。
            关闭开关与未传值不受限。
          </n-alert>
          <n-table :bordered="false" size="small">
            <thead>
              <tr><th>开关</th><th>键名</th><th style="width:160px">最低档位</th></tr>
            </thead>
            <tbody>
              <tr v-for="sw in flowOverrides" :key="sw.key">
                <td>{{ sw.label }}<n-tag v-if="flowTierMap[sw.key] !== sw.default_min_tier" size="tiny" type="warning" style="margin-left:6px">已覆写</n-tag></td>
                <td class="desc"><code>{{ sw.key }}</code></td>
                <td><n-select v-model:value="flowTierMap[sw.key]" :options="tierOptions" size="small" /></td>
              </tr>
            </tbody>
          </n-table>
          <n-button type="primary" :loading="saving === 'flow'" style="margin-top:12px" @click="saveFlow">保存开关档位</n-button>
        </n-card>
      </n-space>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { NSpin, NSpace, NCard, NTable, NSelect, NButton, NAlert, NTag, useMessage } from 'naive-ui'
import { plansApi, type PlanCapability } from '@/api/plans'
import { AdminAPI } from '@/api/admin'

const message = useMessage()
const loading = ref(false)
const saving = ref<string | null>(null)

const tierOptions = [
  { label: '免费版', value: 'free' },
  { label: '创作者版', value: 'creator' },
  { label: '旗舰版', value: 'flagship' },
]

const capabilities = ref<PlanCapability[]>([])
const flowOverrides = ref<PlanCapability[]>([])
const tierMap = reactive<Record<string, string>>({})
const flowTierMap = reactive<Record<string, string>>({})

const load = async () => {
  loading.value = true
  try {
    const data = await plansApi.capabilities()
    capabilities.value = data.capabilities || []
    flowOverrides.value = data.flow_overrides || []
    for (const c of capabilities.value) tierMap[c.key] = c.min_tier || c.default_min_tier || 'free'
    for (const s of flowOverrides.value) flowTierMap[s.key] = s.min_tier || s.default_min_tier || 'free'
  } catch {
    message.error('加载能力注册表失败')
  } finally {
    loading.value = false
  }
}

// 只把"偏离代码默认"的项写入覆写 JSON，与默认一致的项不落盘（清覆写即回默认）
const buildOverrides = (items: PlanCapability[], map: Record<string, string>) => {
  const overrides: Record<string, string> = {}
  for (const item of items) {
    if (map[item.key] && map[item.key] !== item.default_min_tier) overrides[item.key] = map[item.key]
  }
  return overrides
}

const saveCaps = async () => {
  saving.value = 'caps'
  try {
    await AdminAPI.upsertSystemConfig('feature_gating.min_tier_overrides', {
      value: JSON.stringify(buildOverrides(capabilities.value, tierMap)),
    })
    message.success('能力档位已保存')
  } catch {
    message.error('保存失败')
  } finally {
    saving.value = null
  }
}

const saveFlow = async () => {
  saving.value = 'flow'
  try {
    await AdminAPI.upsertSystemConfig('feature_gating.flow_override_min_tiers', {
      value: JSON.stringify(buildOverrides(flowOverrides.value, flowTierMap)),
    })
    message.success('开关档位已保存')
  } catch {
    message.error('保存失败')
  } finally {
    saving.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.feature-gating-config { padding: 4px; }
.desc { color: #888; font-size: 12px; }
</style>

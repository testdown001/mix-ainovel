<template>
  <div class="quality-loop">
    <n-spin :show="loading">
      <n-space vertical size="large">
        <n-alert type="info" :bordered="false">
          这四项都是<b>旗舰档专属</b>的质量增强回路，全部<b>默认关闭</b>。它们不改变生成流程的主干，
          只在定稿后额外做一次分析、并把结论作为后续章节的上下文注入。
          <b>改完即时生效，无需重启。</b>
        </n-alert>

        <n-card
          v-for="item in SWITCHES"
          :key="item.key"
          :bordered="false"
          class="switch-card"
        >
          <div class="row">
            <div class="info">
              <div class="title-line">
                <span class="title">{{ item.title }}</span>
                <n-tag size="small" :type="item.costType" :bordered="false">{{ item.costLabel }}</n-tag>
              </div>
              <p class="desc">{{ item.desc }}</p>
              <p v-if="item.warn" class="warn">⚠️ {{ item.warn }}</p>
            </div>
            <n-switch
              :value="form[item.key]"
              :loading="savingKey === item.key"
              :disabled="savingKey !== null"
              @update:value="(v: boolean) => onToggle(item.key, v)"
            />
          </div>
        </n-card>

        <n-alert type="default" :bordered="false" :show-icon="false" style="font-size:12px;color:#888">
          说明：前三项均为<b>异步执行</b>，失败自动降级，不会阻塞或拖慢正文生成。
          「两遍制」不同——它在生成链路内，会让单章耗时与成本明显上升。
          测试阶段建议先只开前三项观察效果，再决定两遍制是否值得。
        </n-alert>
      </n-space>
    </n-spin>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { NAlert, NCard, NSpace, NSpin, NSwitch, NTag } from 'naive-ui'
import { AdminAPI } from '@/api/admin'
import { useAlert } from '@/composables/useAlert'

const { showAlert } = useAlert()

type SwitchKey =
  | 'outline_revision'
  | 'volume_retrospective'
  | 'character_significance'
  | 'two_pass_draft'

const SWITCHES: Array<{
  key: SwitchKey
  title: string
  desc: string
  costLabel: string
  costType: 'success' | 'warning' | 'error'
  warn?: string
}> = [
  {
    key: 'outline_revision',
    title: '滚动细纲修订',
    desc: '每章定稿后，检查后续几章的大纲是否已被本章实际写出的内容写过时；有偏差就给对应章节留一条修订提示，写下一章时自动带上。',
    costLabel: '低成本 · 异步',
    costType: 'success',
  },
  {
    key: 'volume_retrospective',
    title: '卷级复盘重规划',
    desc: '一卷写完后，对比「当初的分卷规划」与「实际写成什么样」，产出复盘并据此修订下一卷的方向。作者也可在小说详情页「分卷规划」里手动换方向。',
    costLabel: '低成本 · 异步',
    costType: 'success',
  },
  {
    key: 'character_significance',
    title: '人物意义层',
    desc: '每章定稿后抽取「这一章对人物意味着什么」——信念变化、付出的代价、如何看待他人、没说破的事，作为后续章节的人物底色注入（只影响人物的选择与反应，不会被直接写进正文）。',
    costLabel: '低成本 · 异步',
    costType: 'success',
  },
  {
    key: 'two_pass_draft',
    title: '两遍制草稿-改写',
    desc: '先在少量约束下写一遍草稿（专注把故事写出劲道），再拿全部写作规则改写一遍（修掉违规处）。用于解决「规则堆太多导致文字平淡」。',
    costLabel: '高成本 · 生成链路内',
    costType: 'error',
    warn: '每章多一次整章级 LLM 调用，单章耗时与成本近乎翻倍。开启前建议先小样本对比质量增益是否值这个钱。',
  },
]

const KEY_PREFIX = 'quality_loop.'
const loading = ref(false)
const savingKey = ref<SwitchKey | null>(null)
const form = reactive<Record<SwitchKey, boolean>>({
  outline_revision: false,
  volume_retrospective: false,
  character_significance: false,
  two_pass_draft: false,
})

const load = async () => {
  loading.value = true
  try {
    const configs = await AdminAPI.listSystemConfigs()
    const map = new Map(configs.map((c) => [c.key, c.value]))
    for (const item of SWITCHES) {
      form[item.key] = (map.get(`${KEY_PREFIX}${item.key}`) || '').toLowerCase() === 'true'
    }
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '加载质量回路配置失败', 'error')
  } finally {
    loading.value = false
  }
}

const onToggle = async (key: SwitchKey, value: boolean) => {
  const item = SWITCHES.find((s) => s.key === key)!
  savingKey.value = key
  try {
    await AdminAPI.upsertSystemConfig(`${KEY_PREFIX}${key}`, {
      value: value ? 'true' : 'false',
      description: `${item.title}（旗舰档质量回路开关）`,
    })
    form[key] = value
    showAlert(`${item.title}已${value ? '开启' : '关闭'}，下一次生成即生效`, 'success')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '保存失败', 'error')
    await load()   // 保存失败时回读真实状态，避免开关停在假的位置
  } finally {
    savingKey.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.row { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.info { flex: 1; }
.title-line { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; flex-wrap: wrap; }
.title { font-weight: 600; font-size: 15px; }
.desc { margin: 0; font-size: 13px; line-height: 1.7; opacity: .75; }
.warn { margin: 8px 0 0; font-size: 12px; line-height: 1.6; color: #d97706; }
.switch-card { border-left: 3px solid rgba(128, 128, 128, .18); }
</style>

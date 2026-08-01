<template>
  <div class="volumes-section">
    <n-spin :show="loading">
      <n-empty
        v-if="!loading && !volumes.length"
        description="本书还没有分卷规划——生成蓝图时会自动产出分卷，或在蓝图里补充。"
      >
        <template #icon><span style="font-size:40px">📚</span></template>
      </n-empty>

      <n-space v-else vertical size="large">
        <n-alert type="info" :bordered="false" :show-icon="false" style="font-size:13px">
          分卷规划在开书时定下。每写完一卷，系统会对比「原规划」与「实际写成」做一次<b>复盘</b>，
          并据此修订下一卷方向；你也可以随时点「换个方向」让 AI 基于已写内容发散出几条迥异的走向。
          <b>修订后的方向会直接进入后续章节的生成上下文。</b>
        </n-alert>

        <n-card v-for="(vol, idx) in volumes" :key="idx" :bordered="false" class="volume-card">
          <template #header>
            <div class="vol-header">
              <span class="vol-title">
                第{{ idx + 1 }}卷 · {{ vol.name || '未命名' }}
              </span>
              <n-space :size="8" align="center">
                <n-tag size="small" :bordered="false">
                  第 {{ vol.start_chapter }}–{{ vol.end_chapter }} 章
                </n-tag>
                <n-tag v-if="vol.replan" size="small" type="success" :bordered="false">
                  {{ vol.replan.source === 'divergence' ? '已换方向' : '已重规划' }}
                </n-tag>
                <n-tag v-else-if="vol.retrospective" size="small" type="info" :bordered="false">已复盘</n-tag>
              </n-space>
            </div>
          </template>

          <!-- 当前生效方向：有 replan 就以它为准，否则用原规划 -->
          <div class="block">
            <div class="block-title">
              当前方向
              <span v-if="vol.replan" class="block-note">
                （{{ vol.replan.source === 'divergence' ? '来自你选择的发散方案' : '来自上一卷复盘' }}
                {{ vol.replan.title ? '·' + vol.replan.title : '' }}）
              </span>
              <span v-else class="block-note">（开书时的原规划）</span>
            </div>
            <div class="kv"><span>目标</span><p>{{ effective(vol).arc_goal || '—' }}</p></div>
            <div class="kv"><span>高潮</span><p>{{ effective(vol).climax_hint || '—' }}</p></div>
            <div v-if="vol.replan?.focus" class="kv"><span>抓住</span><p>{{ vol.replan.focus }}</p></div>
            <div v-if="vol.replan?.avoid" class="kv"><span>避免</span><p>{{ vol.replan.avoid }}</p></div>
          </div>

          <!-- 原规划：被重规划覆盖后仍保留为历史 -->
          <n-collapse v-if="vol.replan" style="margin-top:12px">
            <n-collapse-item title="查看开书时的原规划" name="orig">
              <div class="kv"><span>目标</span><p>{{ vol.arc_goal || '—' }}</p></div>
              <div class="kv"><span>高潮</span><p>{{ vol.climax_hint || '—' }}</p></div>
            </n-collapse-item>
          </n-collapse>

          <!-- 复盘 -->
          <div v-if="vol.retrospective" class="block retro">
            <div class="block-title">本卷复盘</div>
            <div class="kv"><span>实际达成</span><p>{{ vol.retrospective.achieved || '—' }}</p></div>
            <div class="kv"><span>与规划的偏差</span><p>{{ vol.retrospective.drift || '—' }}</p></div>
            <div v-if="vol.retrospective.unresolved?.length" class="kv">
              <span>遗留线索</span>
              <ul><li v-for="(u, i) in vol.retrospective.unresolved" :key="i">{{ u }}</li></ul>
            </div>
          </div>

          <template #action>
            <n-space justify="end">
              <n-button
                size="small"
                :loading="divergingIndex === idx"
                :disabled="divergingIndex !== null"
                @click="onDiverge(idx)"
              >
                ✨ 换个方向
              </n-button>
            </n-space>
          </template>
        </n-card>
      </n-space>
    </n-spin>

    <!-- 发散卡片选择 -->
    <n-modal
      v-model:show="cardsVisible"
      preset="card"
      style="max-width: 900px"
      :title="`第${(activeVolumeIndex ?? 0) + 1}卷 · 换个方向`"
    >
      <n-alert type="default" :bordered="false" :show-icon="false" style="margin-bottom:12px;font-size:12px">
        以下方案由 AI 基于<b>已经写出来的内容</b>发散，并按「意外性 / 承接度 / 张力」三轴打分。
        选中后会成为该卷的新方向，并立即进入后续章节的生成上下文——原规划仍会保留为历史。
      </n-alert>
      <n-empty v-if="!cards.length" description="这次没能生成可用方案，可以再试一次。" />
      <n-space v-else vertical size="large">
        <n-card
          v-for="(card, i) in cards"
          :key="i"
          :bordered="true"
          size="small"
          class="diverge-card"
        >
          <template #header>
            <div class="vol-header">
              <span class="vol-title">{{ card.title || `方案 ${i + 1}` }}</span>
              <n-space :size="6">
                <n-tag size="small" :bordered="false">意外 {{ card.surprise ?? '-' }}</n-tag>
                <n-tag size="small" :bordered="false">承接 {{ card.continuity ?? '-' }}</n-tag>
                <n-tag size="small" :bordered="false">张力 {{ card.tension ?? '-' }}</n-tag>
              </n-space>
            </div>
          </template>
          <div class="kv"><span>目标</span><p>{{ card.arc_goal }}</p></div>
          <div class="kv"><span>高潮</span><p>{{ card.climax_hint }}</p></div>
          <div class="kv"><span>抓住</span><p>{{ card.focus }}</p></div>
          <div class="kv"><span>避免</span><p>{{ card.avoid }}</p></div>
          <div v-if="card.hook" class="kv"><span>看点</span><p>{{ card.hook }}</p></div>
          <div v-if="card.comment" class="comment">评审：{{ card.comment }}</div>
          <template #action>
            <n-space justify="end">
              <n-button
                size="small"
                type="primary"
                :loading="applyingIndex === i"
                :disabled="applyingIndex !== null"
                @click="onApply(card, i)"
              >
                用这个方向
              </n-button>
            </n-space>
          </template>
        </n-card>
      </n-space>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  NAlert, NButton, NCard, NCollapse, NCollapseItem, NEmpty,
  NModal, NSpace, NSpin, NTag,
} from 'naive-ui'
import { VolumesAPI, type VolumeDivergenceCard, type VolumePlan } from '@/api/volumes'
import { useAlert } from '@/composables/useAlert'

const props = defineProps<{ projectId: string }>()
const { showAlert } = useAlert()

const loading = ref(false)
const volumes = ref<VolumePlan[]>([])

const cardsVisible = ref(false)
const cards = ref<VolumeDivergenceCard[]>([])
const activeVolumeIndex = ref<number | null>(null)
const divergingIndex = ref<number | null>(null)
const applyingIndex = ref<number | null>(null)

/** replan 存在即为当前生效方向；否则回落原规划。与后端读侧口径一致。 */
const effective = (vol: VolumePlan) => ({
  arc_goal: vol.replan?.arc_goal || vol.arc_goal,
  climax_hint: vol.replan?.climax_hint || vol.climax_hint,
})

const load = async () => {
  loading.value = true
  try {
    volumes.value = (await VolumesAPI.list(props.projectId)).volumes || []
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '加载分卷规划失败', 'error')
  } finally {
    loading.value = false
  }
}

const onDiverge = async (idx: number) => {
  divergingIndex.value = idx
  activeVolumeIndex.value = idx
  try {
    // 卷号 1-based
    const res = await VolumesAPI.diverge(props.projectId, idx + 1)
    cards.value = res.cards || []
    cardsVisible.value = true
    if (!cards.value.length) showAlert('这次没能生成可用方案，可以再试一次', 'info')
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '发散失败', 'error')
  } finally {
    divergingIndex.value = null
  }
}

const onApply = async (card: VolumeDivergenceCard, i: number) => {
  if (activeVolumeIndex.value === null) return
  applyingIndex.value = i
  try {
    await VolumesAPI.apply(props.projectId, activeVolumeIndex.value + 1, {
      title: card.title,
      arc_goal: card.arc_goal,
      climax_hint: card.climax_hint,
      focus: card.focus,
      avoid: card.avoid,
    })
    showAlert('已设为该卷的新方向，后续章节生成会按这个方向来', 'success')
    cardsVisible.value = false
    await load()
  } catch (err) {
    showAlert(err instanceof Error ? err.message : '应用失败', 'error')
  } finally {
    applyingIndex.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.vol-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.vol-title { font-weight: 600; }
.block { margin-top: 4px; }
.block.retro { margin-top: 16px; padding-top: 12px; border-top: 1px dashed rgba(128,128,128,.3); }
.block-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; opacity: .85; }
.block-note { font-weight: 400; font-size: 12px; opacity: .6; }
.kv { display: flex; gap: 10px; margin-bottom: 6px; font-size: 13px; line-height: 1.6; }
.kv > span { flex: 0 0 auto; min-width: 68px; opacity: .6; }
.kv > p, .kv > ul { margin: 0; flex: 1; }
.kv > ul { padding-left: 18px; }
.comment { margin-top: 8px; font-size: 12px; opacity: .65; }
.diverge-card { margin-bottom: 4px; }
</style>

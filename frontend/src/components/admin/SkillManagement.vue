<!-- AIMETA P=技能版本治理后台|R=技能卡_版本_发布_回滚_效果指标|NR=不执行技能代码|E=SkillManagement|X=ui|A=管理后台|D=vue,net -->
<template>
  <section class="skill-management">
    <div class="page-head">
      <div>
        <h2>写作技能治理</h2>
        <p>技能策略以版本快照进入生成链路；AI 改进只生成草稿，发布前必须人工审核。</p>
      </div>
      <n-button secondary :loading="loading" @click="load">刷新</n-button>
    </div>
    <n-alert v-if="error" type="error" closable @close="error = ''">{{ error }}</n-alert>
    <div class="skill-list">
      <n-card v-for="skill in skills" :key="skill.id" size="small" class="skill-card">
        <div class="skill-row">
          <span class="skill-icon">{{ skill.icon }}</span>
          <div class="skill-main">
            <div class="skill-title">{{ skill.name }} <n-tag size="small" type="info">{{ skill.version || '未发布' }}</n-tag></div>
            <div class="skill-desc">{{ skill.description }}</div>
            <div class="skill-meta">{{ categoryLabel(skill.category) }} · {{ skill.execution_mode === 'policy' ? '生成约束' : '可执行转换' }} · 使用 {{ skill.metrics?.usage_count || 0 }} 次 · 接受率 {{ rate(skill.metrics?.acceptance_rate) }}</div>
          </div>
          <n-space>
            <n-button size="small" secondary @click="toggleVersions(skill.id)">{{ expanded[skill.id] ? '收起版本' : '版本审计' }}</n-button>
            <n-button size="small" type="warning" ghost :loading="busy === skill.id" @click="makeDraft(skill)">生成改进草稿</n-button>
          </n-space>
        </div>
        <div v-if="expanded[skill.id]" class="versions">
          <div v-if="versionLoading === skill.id" class="muted">加载版本中…</div>
          <div v-for="version in versions[skill.id] || []" :key="version.id" class="version-row">
            <div><strong>{{ version.version_label }}</strong> <n-tag size="small" :type="version.status === 'published' ? 'success' : version.status === 'draft' ? 'warning' : 'default'">{{ statusLabel(version.status) }}</n-tag><span class="version-note">{{ version.change_note || '无变更说明' }}</span></div>
            <n-button v-if="version.status === 'draft'" size="tiny" type="primary" :loading="busyVersion === version.id" @click="publish(skill.id, version.id)">人工发布</n-button>
            <n-button v-else-if="version.status === 'retired'" size="tiny" tertiary @click="rollback(skill.id, version.id)">回滚到此版本</n-button>
          </div>
        </div>
      </n-card>
      <n-empty v-if="!loading && !skills.length" description="暂无可治理技能" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { NAlert, NButton, NCard, NEmpty, NSpace, NTag, useMessage } from 'naive-ui'
import { createSkillDraft, listSkillCatalog, listSkillVersions, publishSkillVersion, rollbackSkillVersion, type SkillInfo, type SkillVersion } from '@/api/skill'

const message = useMessage()
const skills = ref<SkillInfo[]>([])
const versions = reactive<Record<string, SkillVersion[]>>({})
const expanded = reactive<Record<string, boolean>>({})
const loading = ref(false)
const versionLoading = ref<string | null>(null)
const busy = ref<string | null>(null)
const busyVersion = ref<number | null>(null)
const error = ref('')
const categoryLabel = (value: string) => ({ style: '风格', dialogue: '对话', rhythm: '节奏', narrative: '叙事', emotion: '情绪', consistency: '一致性', foreshadowing: '伏笔' }[value] || value)
const statusLabel = (value: string) => ({ published: '已发布', draft: '草稿', retired: '已退役' }[value] || value)
const rate = (value?: number | null) => value == null ? '暂无' : `${Math.round(value * 100)}%`

async function load() {
  loading.value = true
  error.value = ''
  try { skills.value = await listSkillCatalog() } catch (e: any) { error.value = e?.response?.data?.detail || '技能目录加载失败' } finally { loading.value = false }
}
async function toggleVersions(skillId: string) {
  expanded[skillId] = !expanded[skillId]
  if (!expanded[skillId] || versions[skillId]) return
  versionLoading.value = skillId
  try { versions[skillId] = await listSkillVersions(skillId) } catch (e: any) { message.error(e?.response?.data?.detail || '版本加载失败') } finally { versionLoading.value = null }
}
async function makeDraft(skill: SkillInfo) {
  const snapshot = skill.version_snapshot
  if (!snapshot) return message.warning('当前技能没有可复制的已发布版本')
  busy.value = skill.id
  try { await createSkillDraft(skill.id, { ...snapshot, change_note: '基于当前版本生成的改进草稿，请人工审核' }); message.success('草稿已生成，未自动发布'); delete versions[skill.id]; expanded[skill.id] = false; await load() } catch (e: any) { message.error(e?.response?.data?.detail || '草稿生成失败') } finally { busy.value = null }
}
async function publish(skillId: string, versionId: number) {
  busyVersion.value = versionId
  try { await publishSkillVersion(skillId, versionId); message.success('技能版本已发布'); delete versions[skillId]; expanded[skillId] = false; await load() } catch (e: any) { message.error(e?.response?.data?.detail || '发布失败') } finally { busyVersion.value = null }
}
async function rollback(skillId: string, versionId: number) {
  try { await rollbackSkillVersion(skillId, versionId); message.success('已创建回滚版本并发布'); delete versions[skillId]; expanded[skillId] = false; await load() } catch (e: any) { message.error(e?.response?.data?.detail || '回滚失败') }
}
onMounted(load)
</script>

<style scoped>
.skill-management { max-width: 1100px; margin: 0 auto; color: #fff; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; }
h2 { margin: 0 0 6px; font-size: 24px; }
.page-head p, .skill-desc, .muted, .version-note { color: #888; }
.page-head p { margin: 0; }
.skill-list { display: grid; gap: 12px; margin-top: 16px; }
.skill-card { background: #141414; border-color: #2a2a2a; }
.skill-row { display: flex; align-items: flex-start; gap: 14px; }
.skill-icon { font-size: 28px; width: 38px; text-align: center; }
.skill-main { flex: 1; min-width: 0; }
.skill-title { font-weight: 600; font-size: 16px; display: flex; align-items: center; gap: 8px; }
.skill-desc { margin-top: 5px; font-size: 13px; }
.skill-meta { margin-top: 8px; color: #aaa; font-size: 12px; }
.versions { border-top: 1px solid #2a2a2a; margin-top: 14px; padding-top: 10px; display: grid; gap: 8px; }
.version-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; background: #1c1c1c; border-radius: 6px; }
.version-row strong { margin-right: 8px; }
.version-note { margin-left: 10px; font-size: 12px; }
</style>

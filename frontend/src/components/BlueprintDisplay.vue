<!-- AIMETA P=蓝图展示_蓝图详细信息|R=蓝图详情展示|NR=不含编辑功能|E=component:BlueprintDisplay|X=internal|A=展示组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="bp-panel">
    <h2 class="bp-title">你的故事蓝图已生成！</h2>

    <div v-if="aiMessage" class="bp-ai">
      <p>{{ aiMessage }}</p>
    </div>

    <div class="bp-body" v-html="formattedBlueprint"></div>

    <div v-if="isSaving" class="bp-saving">
      <div class="bp-saving-ring-wrap">
        <div class="bp-saving-ring"></div>
        <div class="bp-saving-core">
          <svg class="bp-saving-icon" fill="currentColor" viewBox="0 0 20 20">
            <path d="M7.707 10.293a1 1 0 10-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 11.586V6a1 1 0 10-2 0v5.586l-1.293-1.293z"></path>
            <path d="M5 4a2 2 0 012-2h6a2 2 0 012 2v1a1 1 0 11-2 0V4H7v1a1 1 0 11-2 0V4z"></path>
          </svg>
        </div>
      </div>
      <h3 class="bp-saving-title">正在保存蓝图...</h3>
      <p class="bp-saving-sub">即将跳转到写作工作台，开始您的创作之旅</p>
      <div class="bp-saving-bar">
        <div class="bp-saving-bar-fill"></div>
      </div>
    </div>

    <div v-else class="bp-actions">
      <button type="button" class="md-btn md-btn-outlined md-ripple" @click="confirmRegenerate">
        <svg class="bp-btn-icon" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
        </svg>
        重新生成
      </button>
      <button
        type="button"
        class="md-btn md-btn-filled md-ripple"
        :disabled="isSaving"
        @click="confirmBlueprint"
      >
        <svg class="bp-btn-icon" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
        </svg>
        确认并开始创作
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import type { Blueprint } from '@/api/novel'
import {
  formatReviewTarget,
  localizeReviewText,
  reviewDimensionLabel,
} from '@/utils/blueprintReviewLocalization'

interface DisplayField {
  label: string;
  value: any;
  priority: number;
}

type ExtractedFields = Record<string, DisplayField>;

interface Props {
  blueprint: Blueprint | null
  aiMessage?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  confirm: []
  regenerate: []
}>()

const isSaving = ref(false)

const confirmRegenerate = async () => {
  const confirmed = await globalAlert.showConfirm('重新生成会覆盖当前蓝图，确定继续吗？', '重新生成确认')
  if (confirmed) {
    emit('regenerate')
  }
}

const confirmBlueprint = async () => {
  isSaving.value = true
  try {
    await emit('confirm')
  } finally {
    isSaving.value = false
  }
}

const formattedBlueprint = computed(() => {
  if (!props.blueprint) {
    return '<p class="bp-error">抱歉，生成大纲失败，未能获取到最终数据。</p>'
  }

  const blueprint = props.blueprint

  const safe = (value: any, fallback = '待补充') => value || fallback

  const createSection = (title: string, content: string, icon: string) => `
    <div class="bp-section">
      <div class="bp-section-head">
        <div class="bp-icon">${icon}</div>
        <h3 class="bp-section-title">${title}</h3>
      </div>
      <div class="bp-section-body">${content}</div>
    </div>
  `

  const icons = {
    summary: '<svg class="bp-icon-svg" fill="currentColor" viewBox="0 0 20 20"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
    story: '<svg class="bp-icon-svg" fill="currentColor" viewBox="0 0 20 20"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>',
    world: '<svg class="bp-icon-svg" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM4.332 8.027a6.012 6.012 0 011.912-2.706C6.512 5.73 6.974 6 7.5 6A1.5 1.5 0 019 7.5V8a2 2 0 004 0 2 2 0 011.523-1.943A5.977 5.977 0 0116 10c0 .34-.028.675-.083 1H15a2 2 0 00-2 2v2.197A5.973 5.973 0 0110 16v-2a2 2 0 00-2-2 2 2 0 01-2-2 2 2 0 00-1.668-1.973z" clip-rule="evenodd"></path></svg>',
    characters: '<svg class="bp-icon-svg" fill="currentColor" viewBox="0 0 20 20"><path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"></path></svg>',
    relationships: '<svg class="bp-icon-svg" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"></path></svg>',
    chapters: '<svg class="bp-icon-svg" fill="currentColor" viewBox="0 0 20 20"><path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4zM18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z"></path></svg>'
  }

  const formatCharacters = (characters: any[]) => {
    if (!characters || characters.length === 0) return '<p class="bp-muted">暂无角色信息</p>'

    return characters.map(char => {
      if (typeof char === 'object' && char.name) {
        const name = char.name

        const fieldMappings = {
          identity: {
            keys: ['identity_background', 'identity', 'background', '身份背景', '身份'],
            label: '🎭 身份背景',
            priority: 1
          },
          personality: {
            keys: ['personality_traits', 'personality', 'traits', 'character', '性格特质', '性格'],
            label: '🎨 性格特质',
            priority: 2
          },
          goal: {
            keys: ['core_goal', 'goal', 'objectives', 'aims', '核心目标', '目标'],
            label: '🎯 核心目标',
            priority: 3
          },
          abilities: {
            keys: ['abilities_skills', 'abilities', 'skills', 'powers', '能力技能', '能力', '技能'],
            label: '⚡ 能力技能',
            priority: 4
          },
          relationship: {
            keys: ['relationship_with_protagonist', 'relationship_to_protagonist', 'relationship', 'relation', '与主角关系', '关系'],
            label: '🤝 与主角关系',
            priority: 5
          },
          role: {
            keys: ['role', 'character_role', 'story_role', '角色定位', '角色'],
            label: '👤 角色定位',
            priority: 0
          }
        }

        const extractedFields: ExtractedFields = {}
        const usedKeys = new Set(['name'])

        Object.entries(fieldMappings).forEach(([fieldType, mapping]) => {
          for (const key of mapping.keys) {
            if (char[key] && !usedKeys.has(key)) {
              extractedFields[fieldType] = {
                value: char[key],
                label: mapping.label,
                priority: mapping.priority
              }
              usedKeys.add(key)
              break
            }
          }
        })

        Object.entries(char).forEach(([key, value]) => {
          if (!usedKeys.has(key) && value && typeof value === 'string' && value.trim()) {
            const friendlyLabel = key
              .replace(/_/g, ' ')
              .replace(/([A-Z])/g, ' $1')
              .replace(/^./, str => str.toUpperCase())

            extractedFields[`unknown_${key}`] = {
              value: value,
              label: `📝 ${friendlyLabel}`,
              priority: 99
            }
            usedKeys.add(key)
          }
        })

        const sortedFields = Object.entries(extractedFields).sort(([,a], [,b]) => a.priority - b.priority)

        let fieldsHTML = ''
        sortedFields.forEach(([fieldType, field]) => {
          if (fieldType === 'role') {
            return
          }

          fieldsHTML += `
            <div class="bp-field">
              <span class="bp-field-label">${field.label}：</span>
              <span class="bp-field-value">${field.value}</span>
            </div>
          `
        })

        const roleField = extractedFields.role

        return `
          <div class="bp-card bp-accent-gold">
            <div class="bp-card-head">
              <h4 class="bp-card-title">
                <span class="bp-dot"></span>
                ${name}
              </h4>
              ${roleField ? `<span class="bp-chip">${roleField.value}</span>` : ''}
            </div>
            <div class="bp-stack">${fieldsHTML}</div>
          </div>
        `
      }
      else if (typeof char === 'object' && char.description) {
        const desc = char.description
        const identity = desc.identity || ''
        const personality = desc.personality || ''
        const relationship = desc.relationship_to_protagonist || ''

        return `
          <div class="bp-card bp-accent-gold">
            <h4 class="bp-card-title">
              <span class="bp-dot"></span>
              ${char.name}
            </h4>
            <div class="bp-stack">
              ${identity ? `<div class="bp-kv"><span class="bp-kv-k">身份：</span><span class="bp-kv-v">${identity}</span></div>` : ''}
              ${personality ? `<div class="bp-kv"><span class="bp-kv-k">性格：</span><span class="bp-kv-v">${personality}</span></div>` : ''}
              ${relationship ? `<div class="bp-kv"><span class="bp-kv-k">关系：</span><span class="bp-kv-v">${relationship}</span></div>` : ''}
            </div>
          </div>
        `
      }
      else {
        return `
          <div class="bp-card">
            <h4 class="bp-card-title">${char.name || '未知角色'}</h4>
            <p class="bp-text">${char.description || '无描述'}</p>
          </div>
        `
      }
    }).join('')
  }

  const formatWorldSetting = (worldSetting: any) => {
    if (!worldSetting || typeof worldSetting !== 'object') return '<p class="bp-muted">暂无世界设定信息</p>'

    let html = ''

    if (worldSetting.core_rules) {
      html += `
        <div class="bp-card bp-accent-gold">
          <h4 class="bp-card-title">核心设定</h4>
          <p class="bp-text">${worldSetting.core_rules}</p>
        </div>
      `
    }

    if (worldSetting.key_locations && worldSetting.key_locations.length > 0) {
      html += `
        <div class="bp-block">
          <h4 class="bp-label">关键地点</h4>
          <div class="bp-stack">
            ${worldSetting.key_locations.map((loc: any) => `
              <div class="bp-card bp-accent-teal">
                <h5 class="bp-card-name">${loc.name}</h5>
                <p class="bp-text">${loc.description}</p>
              </div>
            `).join('')}
          </div>
        </div>
      `
    }

    if (worldSetting.factions && worldSetting.factions.length > 0) {
      html += `
        <div class="bp-block">
          <h4 class="bp-label">主要势力</h4>
          <div class="bp-stack">
            ${worldSetting.factions.map((fac: any) => `
              <div class="bp-card bp-accent-violet">
                <h5 class="bp-card-name">${fac.name}</h5>
                <p class="bp-text">${fac.description}</p>
              </div>
            `).join('')}
          </div>
        </div>
      `
    }

    return html || '<p class="bp-muted">暂无世界设定详细信息</p>'
  }

  const scoreClass = (n: number) => (n >= 70 ? 'bp-score-ok' : n >= 55 ? 'bp-score-mid' : 'bp-score-bad')

  const severityClass = (severity: string) => {
    if ((severity || '').includes('高')) return 'bp-issue-high'
    if ((severity || '').includes('中')) return 'bp-issue-mid'
    return 'bp-issue-low'
  }

  const formatReviewReport = (report: any) => {
    if (!report || typeof report !== 'object') return ''
    const score = Number(report.total_score) || 0
    const dims = Object.entries(report.dimension_scores || {})
      .filter(([, v]) => typeof v === 'number')
      .map(([k, v]) => `
        <div class="bp-metric">
          <div class="bp-metric-label">${reviewDimensionLabel(k)}</div>
          <div class="bp-metric-score ${scoreClass(Number(v))}">${v}</div>
        </div>
      `).join('')
    const issues = (report.issues || []).map((issue: any) => {
      const sev = severityClass(issue.severity || '')
      return `
        <div class="bp-issue ${sev}">
          <div class="bp-issue-meta">
            <span class="bp-issue-badge">${issue.severity || '低'}</span>
            <span class="bp-muted">${formatReviewTarget(issue.target)}</span>
            <span class="bp-muted">${issue.dimension ? reviewDimensionLabel(issue.dimension) : ''}</span>
          </div>
          <p class="bp-text">${localizeReviewText(issue.problem)}</p>
          ${issue.fix_hint ? `<p class="bp-hint">修订方向：${localizeReviewText(issue.fix_hint)}</p>` : ''}
        </div>
      `
    }).join('')
    const strengths = (report.strengths || []).length
      ? `<div class="bp-block"><h4 class="bp-label">亮点</h4>${(report.strengths || []).map((s: string) => `<p class="bp-strength">· ${localizeReviewText(s)}</p>`).join('')}</div>`
      : ''
    return `
      <div class="bp-review-head">
        <div class="bp-review-score">
          <div class="bp-score-num ${scoreClass(score)}">${score}</div>
          <div class="bp-muted">商业量表总分</div>
        </div>
        <div class="bp-review-verdict">
          ${report.revised ? '<span class="bp-chip bp-chip-gold">已经过一轮定向修订</span>' : ''}
          <p class="bp-text">${localizeReviewText(report.verdict)}</p>
        </div>
      </div>
      ${dims ? `<div class="bp-metrics">${dims}</div>` : ''}
      ${issues ? `<h4 class="bp-label">待改进问题（${(report.issues || []).length}）</h4>${issues}` : '<p class="bp-strength">未发现待改进问题。</p>'}
      ${strengths}
    `
  }

  const formatVolumes = (volumes: any[]) => {
    if (!volumes || volumes.length === 0) return ''
    return `
      <div class="bp-stack">
        ${volumes.map((vol: any, i: number) => `
          <div class="bp-card bp-accent-sky">
            <div class="bp-card-head">
              <h4 class="bp-card-title">第${i + 1}卷 ${vol.name || '未命名卷'}</h4>
              <span class="bp-chip">第 ${vol.start_chapter ?? '?'} - ${vol.end_chapter ?? '?'} 章</span>
            </div>
            ${vol.arc_goal ? `<p class="bp-text"><span class="bp-field-label">卷目标：</span>${vol.arc_goal}</p>` : ''}
            ${vol.climax_hint ? `<p class="bp-text"><span class="bp-field-label">卷末高潮：</span>${vol.climax_hint}</p>` : ''}
          </div>
        `).join('')}
      </div>
    `
  }

  const formatGoldenFinger = (gf: any) => {
    if (!gf || typeof gf !== 'object' || !(gf.name || '').toString().trim()) return ''
    const rows = [
      ['类型', gf.type],
      ['机制', gf.description],
      ['限制与代价', gf.limitations],
      ['成长空间', gf.growth_potential]
    ].filter(([, v]) => v && String(v).trim())
      .map(([label, v]) => `<div class="bp-kv"><span class="bp-kv-k">${label}：</span><span class="bp-kv-v">${v}</span></div>`)
      .join('')
    return `
      <div class="bp-card bp-accent-gold">
        <h4 class="bp-card-title">✨ ${gf.name}</h4>
        ${rows}
      </div>
    `
  }

  const formatForeshadowings = (items: any[]) => {
    if (!items || items.length === 0) return ''
    return `
      <div class="bp-stack">
        ${items.map((fs: any) => `
          <div class="bp-card bp-accent-violet">
            <div class="bp-card-head">
              <span class="bp-card-name">${fs.name || '未命名伏笔'}</span>
              ${fs.tier ? `<span class="bp-chip">${fs.tier}</span>` : ''}
              <span class="bp-muted">第 ${fs.planted_chapter ?? '?'} 章埋设${fs.target_chapter ? ` → 第 ${fs.target_chapter} 章兑现` : ''}</span>
            </div>
            ${fs.description ? `<p class="bp-text">${fs.description}</p>` : ''}
          </div>
        `).join('')}
      </div>
    `
  }

  const formatRelationships = (relationships: any[]) => {
    if (!relationships || relationships.length === 0) return '<p class="bp-muted">暂无关系设定</p>'

    return `
      <div class="bp-stack">
        ${relationships.map(rel => {
          const fromChar = rel.character_from || rel.source || '角色A'
          const toChar = rel.character_to || rel.target || '角色B'
          const description = rel.description || '暂无描述'

          return `
            <div class="bp-card bp-accent-rose">
              <div class="bp-rel-row">
                <span class="bp-chip bp-chip-gold">${fromChar}</span>
                <svg class="bp-rel-arrow" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M12.293 5.293a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-2.293-2.293a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                </svg>
                <span class="bp-chip bp-chip-gold">${toChar}</span>
              </div>
              <p class="bp-text"><span class="bp-field-label">关系描述：</span>${description}</p>
            </div>
          `
        }).join('')}
      </div>
    `
  }

  const headerHTML = `
    <div class="bp-hero">
      <h1 class="bp-hero-title">${safe(blueprint.title, '未知标题')}</h1>
      <div class="bp-hero-tags">
        <span class="bp-chip">${safe(blueprint.genre, '未指定')}</span>
        <span class="bp-chip">${safe(blueprint.style, '未指定')}</span>
        <span class="bp-chip">${safe(blueprint.tone, '未指定')}</span>
        <span class="bp-chip">${safe(blueprint.target_audience, '未指定')}</span>
      </div>
    </div>
  `

  const summaryHTML = createSection(
    '故事梗概',
    `
    <div class="bp-quote">
      <h4 class="bp-label">一句话总结</h4>
      <p class="bp-quote-text">“${safe(blueprint.one_sentence_summary)}”</p>
    </div>
    <div class="bp-block">
      <h4 class="bp-label">完整简介</h4>
      <p class="bp-text">${safe(blueprint.full_synopsis)}</p>
    </div>
    `,
    icons.summary
  )

  const chaptersHTML = `
    <div class="bp-stack">
      ${(blueprint.chapter_outline || []).map((ch) => {
        const planning: any = (ch as any).metadata?.planning || null
        const badges = planning ? [
          planning.chapter_function ? `<span class="bp-chip">${planning.chapter_function}</span>` : '',
          planning.coolpoint ? `<span class="bp-chip bp-chip-warm">爽点：${planning.coolpoint}</span>` : '',
          planning.hook_type ? `<span class="bp-chip bp-chip-teal">钩子：${planning.hook_type}</span>` : ''
        ].filter(Boolean).join('') : ''
        return `
        <div class="bp-chapter">
          <div class="bp-chapter-num">${ch.chapter_number}</div>
          <div class="bp-chapter-body">
            <h4 class="bp-card-title">第 ${ch.chapter_number} 章: ${ch.title}</h4>
            <p class="bp-text">${ch.summary}</p>
            ${badges ? `<div class="bp-hero-tags">${badges}</div>` : ''}
          </div>
        </div>
      `}).join('')}
    </div>
  `

  const reviewHTML = formatReviewReport((blueprint as any).review_report)
  const volumesHTML = formatVolumes((blueprint as any).volumes || [])
  const goldenFingerHTML = formatGoldenFinger((blueprint as any).golden_finger)
  const foreshadowingsHTML = formatForeshadowings((blueprint as any).foreshadowings || [])

  return `
    ${headerHTML}
    ${reviewHTML ? createSection('审稿报告（商业量表）', reviewHTML, icons.summary) : ''}
    ${summaryHTML}
    ${createSection('世界设定', formatWorldSetting(blueprint.world_setting), icons.world)}
    ${goldenFingerHTML ? createSection('金手指', goldenFingerHTML, icons.story) : ''}
    ${createSection('主要角色', formatCharacters(blueprint.characters || []), icons.characters)}
    ${createSection('角色关系', formatRelationships(blueprint.relationships || []), icons.relationships)}
    ${volumesHTML ? createSection('分卷规划', volumesHTML, icons.chapters) : ''}
    ${foreshadowingsHTML ? createSection('伏笔清单', foreshadowingsHTML, icons.story) : ''}
    ${createSection('章节大纲', chaptersHTML, icons.chapters)}
  `
})
</script>

<style scoped>
.bp-panel {
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 16px;
  padding: 28px;
  color: #e5e5e5;
  animation: bpFadeIn 0.45s ease-out;
}
@keyframes bpFadeIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.bp-title {
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  text-align: center;
  margin-bottom: 18px;
}

.bp-ai {
  margin-bottom: 18px;
  padding: 14px 16px;
  background: rgba(255, 229, 0, 0.08);
  border: 1px solid rgba(255, 229, 0, 0.25);
  border-radius: 10px;
  color: #ddd;
  font-size: 14px;
  line-height: 1.65;
}

.bp-body {
  color: #e5e5e5;
}

.bp-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 24px;
}

.bp-btn-icon {
  width: 18px;
  height: 18px;
}

.bp-saving { text-align: center; padding: 28px 0 8px; }
.bp-saving-ring-wrap { position: relative; width: 64px; height: 64px; margin: 0 auto 16px; }
.bp-saving-ring {
  position: absolute; inset: 0; border-radius: 50%;
  border: 3px solid #2a2a2a; border-top-color: #ffe500;
  animation: bpSpin 1s linear infinite;
}
.bp-saving-core {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  color: #ffe500;
}
.bp-saving-icon { width: 22px; height: 22px; }
@keyframes bpSpin { to { transform: rotate(360deg); } }
.bp-saving-title { font-size: 16px; font-weight: 600; color: #fff; }
.bp-saving-sub { margin-top: 6px; font-size: 13px; color: #888; }
.bp-saving-bar {
  max-width: 200px; height: 4px; margin: 16px auto 0;
  background: #2a2a2a; border-radius: 2px; overflow: hidden;
}
.bp-saving-bar-fill {
  width: 100%; height: 100%;
  background: linear-gradient(90deg, #ffe500, #ffb800);
  animation: bpPulse 1.2s ease-in-out infinite;
}
@keyframes bpPulse { 50% { opacity: 0.45; } }

:deep(.bp-hero) {
  text-align: center;
  margin-bottom: 16px;
  padding: 28px 20px;
  background: linear-gradient(165deg, #1c1a08 0%, #141414 62%);
  border: 1px solid rgba(255, 229, 0, 0.28);
  border-radius: 14px;
}
:deep(.bp-hero-title) {
  font-size: 26px;
  font-weight: 800;
  color: #ffe500;
  margin-bottom: 16px;
  line-height: 1.35;
}
:deep(.bp-hero-tags) {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

:deep(.bp-section) {
  background: #1c1c1c;
  border: 1px solid #2a2a2a;
  border-radius: 12px;
  padding: 18px;
  margin-bottom: 14px;
}
:deep(.bp-section-head) {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
:deep(.bp-icon) {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 229, 0, 0.12);
  border-radius: 8px;
  color: #ffe500;
}
:deep(.bp-icon-svg) { width: 18px; height: 18px; }
:deep(.bp-section-title) { font-size: 17px; font-weight: 700; color: #fff; }

:deep(.bp-card) {
  background: #242424;
  border: 1px solid #2a2a2a;
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 10px;
}
:deep(.bp-accent-gold) { border-left: 3px solid #ffe500; }
:deep(.bp-accent-teal) { border-left: 3px solid #2ed573; }
:deep(.bp-accent-violet) { border-left: 3px solid #a78bfa; }
:deep(.bp-accent-sky) { border-left: 3px solid #38bdf8; }
:deep(.bp-accent-rose) { border-left: 3px solid #fb7185; }

:deep(.bp-card-head) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
:deep(.bp-card-title) {
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
}
:deep(.bp-card-name) { font-size: 14px; font-weight: 600; color: #fff; }
:deep(.bp-dot) {
  width: 7px; height: 7px; border-radius: 50%;
  background: #ffe500; flex-shrink: 0;
}

:deep(.bp-chip) {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: #ccc;
  background: #2a2a2a;
  border: 1px solid #333;
  border-radius: 999px;
  padding: 3px 12px;
}
:deep(.bp-chip-gold) {
  color: #ffe500;
  background: rgba(255, 229, 0, 0.08);
  border-color: rgba(255, 229, 0, 0.28);
}
:deep(.bp-chip-warm) {
  color: #ffb86b;
  background: rgba(255, 159, 67, 0.1);
  border-color: rgba(255, 159, 67, 0.28);
}
:deep(.bp-chip-teal) {
  color: #5eead4;
  background: rgba(46, 213, 115, 0.1);
  border-color: rgba(46, 213, 115, 0.25);
}

:deep(.bp-label) {
  font-size: 13px;
  font-weight: 600;
  color: #ffe500;
  margin: 10px 0 8px;
}
:deep(.bp-text) { font-size: 14px; line-height: 1.7; color: #ddd; }
:deep(.bp-muted) { font-size: 12px; color: #888; }
:deep(p.bp-muted) { font-style: italic; }
:deep(.bp-error) { text-align: center; color: #ff8a9a; }
:deep(.bp-stack) { display: flex; flex-direction: column; gap: 8px; }
:deep(.bp-block) { margin-top: 8px; }

:deep(.bp-field) {
  background: #1c1c1c;
  border-radius: 8px;
  padding: 10px 12px;
}
:deep(.bp-field-label) { font-size: 12px; color: #888; }
:deep(.bp-field .bp-field-label) { display: block; margin-bottom: 4px; }
:deep(.bp-field-value) { font-size: 13px; color: #e8e8e8; line-height: 1.6; }
:deep(.bp-kv) { display: flex; gap: 8px; font-size: 13px; line-height: 1.65; }
:deep(.bp-kv-k) { flex-shrink: 0; color: #888; min-width: 48px; }
:deep(.bp-kv-v) { color: #ddd; }

:deep(.bp-quote) {
  background: rgba(255, 229, 0, 0.06);
  border: 1px solid rgba(255, 229, 0, 0.2);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 12px;
}
:deep(.bp-quote-text) {
  font-size: 16px;
  font-style: italic;
  color: #ffe500;
  line-height: 1.6;
}

:deep(.bp-review-head) {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-bottom: 14px;
}
:deep(.bp-review-score) { text-align: center; min-width: 72px; }
:deep(.bp-score-num) { font-size: 40px; font-weight: 800; line-height: 1; }
:deep(.bp-review-verdict) { flex: 1; }
:deep(.bp-metrics) {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}
:deep(.bp-metric) {
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 10px 8px;
  text-align: center;
}
:deep(.bp-metric-label) { font-size: 11px; color: #888; }
:deep(.bp-metric-score) { font-size: 18px; font-weight: 700; margin-top: 4px; }
:deep(.bp-score-ok) { color: #2ed573; }
:deep(.bp-score-mid) { color: #ffe500; }
:deep(.bp-score-bad) { color: #ff4757; }

:deep(.bp-issue) {
  border: 1px solid #2a2a2a;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  background: #141414;
}
:deep(.bp-issue-high) { border-color: rgba(255, 71, 87, 0.45); background: rgba(255, 71, 87, 0.08); }
:deep(.bp-issue-mid) { border-color: rgba(255, 229, 0, 0.35); background: rgba(255, 229, 0, 0.06); }
:deep(.bp-issue-low) { border-color: #2a2a2a; }
:deep(.bp-issue-meta) { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
:deep(.bp-issue-badge) {
  font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px;
  background: #2a2a2a; color: #ccc;
}
:deep(.bp-issue-high .bp-issue-badge) { background: rgba(255, 71, 87, 0.2); color: #ff8a9a; }
:deep(.bp-issue-mid .bp-issue-badge) { background: rgba(255, 229, 0, 0.15); color: #ffe500; }
:deep(.bp-hint) { font-size: 12px; color: #b8a84a; margin-top: 6px; }
:deep(.bp-strength) { font-size: 13px; color: #2ed573; line-height: 1.6; }

:deep(.bp-rel-row) {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
:deep(.bp-rel-arrow) { width: 16px; height: 16px; color: #888; }

:deep(.bp-chapter) {
  display: flex;
  gap: 12px;
  background: #242424;
  border: 1px solid #2a2a2a;
  border-left: 3px solid #ffe500;
  border-radius: 10px;
  padding: 14px 16px;
}
:deep(.bp-chapter-num) {
  flex-shrink: 0;
  width: 36px; height: 36px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255, 229, 0, 0.12);
  color: #ffe500;
  font-weight: 700;
  font-size: 13px;
  border-radius: 8px;
}
:deep(.bp-chapter-body) { flex: 1; min-width: 0; }
:deep(.bp-chapter-body .bp-hero-tags) { justify-content: flex-start; margin-top: 8px; }
</style>

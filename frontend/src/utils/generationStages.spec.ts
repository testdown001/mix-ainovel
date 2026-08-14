import { describe, expect, it } from 'vitest'
import { looksLikeMachineName, resolveStage } from './generationStages'

describe('resolveStage（阶段名与进度的唯一解释处）', () => {
  it('已知阶段给中文名和百分比', () => {
    expect(resolveStage('generate_versions')).toEqual({
      label: '撰写正文（多版本）',
      percent: 45,
    })
    expect(resolveStage('post_six_dimension').label).toBe('六维质量评审')
  })

  it('后处理链每一步都有名字——这条链占一章约四成时长，不能是空白', () => {
    const postSteps = [
      'post_combined_revision',
      'post_consistency',
      'post_humanization',
      'post_optimizer',
      'post_polish',
      'post_enrichment',
      'post_density_compression',
      'post_six_dimension',
      'post_auto_refine',
      'post_six_dimension_rescore',
      'post_guardrail_rewrite',
    ]
    for (const key of postSteps) {
      const resolved = resolveStage(key)
      expect(resolved.percent, key).toBeTypeOf('number')
      expect(looksLikeMachineName(resolved.label), `${key} 的文案不该是机器名`).toBe(false)
    }
  })

  it('进度随流程推进单调递增', () => {
    const order = [
      'starting',
      'build_generation_prompt',
      'generate_versions',
      'post_combined_revision',
      'post_six_dimension',
      'persist_versions',
      'completed',
    ]
    const percents = order.map((key) => resolveStage(key).percent as number)
    for (let i = 1; i < percents.length; i++) {
      expect(percents[i], order[i]).toBeGreaterThan(percents[i - 1])
    }
  })

  it('批量任务的机器名也要翻译（此前直接显示 batch_generating）', () => {
    expect(resolveStage('batch_generating', '正在生成第 3 章 (3/5)').label).toBe('连续生成中')
  })

  it('Agent 阶段用后端中文消息，进度按环节粗分', () => {
    const resolved = resolveStage('agent:zhongshu:start', '规划智能体启动')
    expect(resolved.label).toBe('规划智能体启动')
    expect(resolved.percent).toBe(30)
  })

  it('认不出的阶段用后端消息兜底，但不乱动进度', () => {
    const resolved = resolveStage('some_new_stage', '正在做一件新事')
    expect(resolved.label).toBe('正在做一件新事')
    expect(resolved.percent).toBeNull()
  })

  it('既认不出 key 又没消息时给通用文案，不把机器名甩给用户', () => {
    expect(resolveStage('', '').label).toBe('处理中')
  })
})

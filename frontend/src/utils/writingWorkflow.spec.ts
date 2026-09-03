import { describe, expect, it } from 'vitest'
import {
  AUTHORING_STAGES,
  invalidatePrediction,
  resolveAuthoringStage,
} from './writingWorkflow'

describe('两步式章节创作流程', () => {
  it('只向用户展示章节规划和正文创作', () => {
    expect(AUTHORING_STAGES).toEqual([
      { id: 1, label: '章节规划' },
      { id: 2, label: '正文创作' },
    ])
  })

  it('情节梳理仍属于规划，生成与检查状态都归入正文创作', () => {
    expect(resolveAuthoringStage({})).toBe(1)
    expect(resolveAuthoringStage({ generationStatus: 'generating' })).toBe(2)
    expect(resolveAuthoringStage({ generationStatus: 'evaluating' })).toBe(2)
    expect(resolveAuthoringStage({ hasContent: true })).toBe(2)
    expect(resolveAuthoringStage({ hasEvaluation: true })).toBe(2)
  })

  it('修改规划时只失效旧情节梳理，不丢失其他元数据', () => {
    expect(
      invalidatePrediction({
        planning: { chapter_function: '转折' },
        prediction: { beats: ['旧节拍'] },
        revision_hint: '保留提示',
      }),
    ).toEqual({
      planning: { chapter_function: '转折' },
      revision_hint: '保留提示',
    })
  })
})

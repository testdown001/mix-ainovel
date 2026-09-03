import { describe, expect, it } from 'vitest'
import { resolveChapterRailStatus } from './chapterRailStatus'

describe('resolveChapterRailStatus（章节轨状态唯一解释处）', () => {
  it('批量章纲生成成功后显示完成态“已规划”，而不是“规划中”', () => {
    expect(resolveChapterRailStatus({})).toEqual({ kind: 'planned', label: '已规划' })
  })

  it('正文选版成功才计为“已完成”', () => {
    expect(resolveChapterRailStatus({ generationStatus: 'successful' })).toEqual({
      kind: 'done',
      label: '已完成',
    })
  })

  it('待确认和失败不会再被混入笼统的“进行中”', () => {
    expect(resolveChapterRailStatus({ generationStatus: 'waiting_for_confirm' })).toEqual({
      kind: 'confirm',
      label: '待确认',
    })
    expect(resolveChapterRailStatus({ generationStatus: 'failed' }).label).toBe('生成失败')
    expect(resolveChapterRailStatus({ generationStatus: 'evaluation_failed' }).label).toBe(
      '评审失败',
    )
  })

  it('内部情节梳理不再增加用户可见阶段', () => {
    expect(resolveChapterRailStatus({ hasPrediction: true })).toEqual({
      kind: 'planned',
      label: '已规划',
    })
    expect(resolveChapterRailStatus({ generating: true }).label).toBe('生成中')
    expect(resolveChapterRailStatus({ evaluating: true }).label).toBe('评审中')
  })
})

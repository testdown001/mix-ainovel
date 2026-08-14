import { describe, expect, it } from 'vitest'
import { describeSkippedSteps, extractSkippedSteps } from './budgetSkip'

describe('extractSkippedSteps（被时间预算跳过的精修步骤）', () => {
  it('读异步任务路径的扁平字段', () => {
    expect(extractSkippedSteps({ skipped_for_budget: ['consistency', 'six_dimension'] })).toEqual([
      'consistency',
      'six_dimension',
    ])
  })

  it('读同步/SSE 路径版本 metadata 里的 review_summaries', () => {
    const payload = {
      variants: [
        { metadata: {} },
        {
          metadata: {
            review_summaries: { time_budget: { exceeded: true, skipped: ['humanization'] } },
          },
        },
      ],
    }
    expect(extractSkippedSteps(payload)).toEqual(['humanization'])
  })

  it('正常完成的生成没有跳过项', () => {
    expect(
      extractSkippedSteps({ variants: [{ metadata: { review_summaries: { consistency: {} } } }] }),
    ).toEqual([])
    expect(extractSkippedSteps(null)).toEqual([])
    expect(extractSkippedSteps('x')).toEqual([])
  })
})

describe('describeSkippedSteps（说明文案）', () => {
  it('把步骤名翻成用户语言并去重', () => {
    const text = describeSkippedSteps(['consistency', 'six_dimension', 'consistency'])
    expect(text).toContain('一致性校对')
    expect(text).toContain('六维质量评审')
    expect(text.match(/一致性校对/g)).toHaveLength(1)
  })

  it('认不出的步骤名原样带出，总比丢掉信息强', () => {
    expect(describeSkippedSteps(['brand_new_step'])).toContain('brand_new_step')
  })

  it('没有跳过项就不说话', () => {
    expect(describeSkippedSteps([])).toBe('')
  })
})

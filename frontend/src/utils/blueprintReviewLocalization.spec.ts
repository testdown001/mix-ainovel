import { describe, expect, it } from 'vitest'

import {
  formatReviewTarget,
  localizeReviewText,
  reviewDimensionLabel,
} from './blueprintReviewLocalization'

describe('蓝图审稿字段中文化', () => {
  it('翻译当前商业量表的七个评分项', () => {
    expect(reviewDimensionLabel('opening_strength')).toBe('开局强度')
    expect(reviewDimensionLabel('first_coolpoint_timing')).toBe('首个爽点时机')
    expect(reviewDimensionLabel('hook_chain')).toBe('章末钩子链')
    expect(reviewDimensionLabel('volume_escalation')).toBe('分卷升级梯度')
    expect(reviewDimensionLabel('foreshadowing_payoff')).toBe('伏笔兑现')
    expect(reviewDimensionLabel('anticipation_delivery')).toBe('期待感兑现')
    expect(reviewDimensionLabel('toxic_recheck')).toBe('毒点复查')
  })

  it('把问题定位转换为自然中文', () => {
    expect(formatReviewTarget('chapters:4-5')).toBe('第4—5章')
    expect(formatReviewTarget('chapters:12-12')).toBe('第12章')
    expect(formatReviewTarget('settings:volumes')).toBe('设定：分卷规划')
    expect(formatReviewTarget('settings:golden_finger')).toBe('设定：金手指设定')
  })

  it('翻译问题描述和修订建议中的内部字段名', () => {
    const text = '在第一卷volumes[0].arc_goal补充KPI，并让climax_hint形成plant→payoff闭环。'
    expect(localizeReviewText(text)).toBe(
      '在第1卷的卷目标补充关键指标，并让卷末高潮形成埋设→兑现闭环。',
    )
    expect(localizeReviewText('第一卷arc_goal或climax_hint缺少利益冲突')).toBe(
      '第一卷的卷目标或卷末高潮缺少利益冲突',
    )
  })

  it('不向界面暴露未知的英文 snake_case 字段', () => {
    expect(reviewDimensionLabel('future_unknown_score')).toBe('其他指标')
    expect(formatReviewTarget('settings:future_unknown_block')).toBe('设定：其他设定项')
    expect(localizeReviewText('检查future_unknown_field是否完整')).toBe('检查对应字段是否完整')
  })
})

import { describe, expect, it } from 'vitest'
import { detectUpgradeHint } from './upgradeHint'

describe('detectUpgradeHint（402/403 升级引导判定）', () => {
  it('识别 http.ts 包装的 402 错误', () => {
    expect(detectUpgradeHint('请求失败(402): 积分不足：本次需 40 积分，剩余 0。')).toBe('credits')
  })

  it('识别后端 detail 原文的积分不足（SSE / 异步任务路径）', () => {
    expect(
      detectUpgradeHint('积分不足：本次需 45 积分，剩余 10。可升级套餐或等待月度重置。'),
    ).toBe('credits')
  })

  it('识别预设档位 403（feature_gating 文案）', () => {
    expect(detectUpgradeHint('「标准模式」需要创作者版（当前：免费版）')).toBe('tier')
    expect(detectUpgradeHint('「精品模式」需要旗舰版（当前：创作者版）')).toBe('tier')
  })

  it('识别模型档位 403', () => {
    expect(detectUpgradeHint('该模型需要旗舰版会员')).toBe('tier')
  })

  it('项目归属等无关 403 不触发升级引导', () => {
    expect(detectUpgradeHint('请求失败(403): 无权访问该项目')).toBeNull()
  })

  it('普通错误与空消息返回 null', () => {
    expect(detectUpgradeHint('生成失败: 网络超时')).toBeNull()
    expect(detectUpgradeHint('')).toBeNull()
  })
})

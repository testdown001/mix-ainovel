import { describe, expect, it } from 'vitest'
import { StreamInterruptedError, isStreamInterruption } from './streamInterruption'

describe('isStreamInterruption（断线与生成失败的区分）', () => {
  it('识别流中断专用错误类型', () => {
    expect(isStreamInterruption(new StreamInterruptedError())).toBe(true)
  })

  it('识别带 interrupted 标记的普通对象', () => {
    expect(isStreamInterruption({ interrupted: true, message: 'x' })).toBe(true)
  })

  it('识别各内核的网络中断文案', () => {
    for (const message of [
      'Failed to fetch',
      'NetworkError when attempting to fetch resource.',
      'Load failed',
      'The network connection was lost.',
      'The operation was aborted.',
    ]) {
      expect(isStreamInterruption(new Error(message)), message).toBe(true)
    }
  })

  it('业务错误一律不算中断——重试无用，误判会诱导用户再花一次生成', () => {
    for (const message of [
      '请求失败(402): 积分不足，请购买加油包',
      '请求失败(403): 该生成档位需要旗舰版',
      '请求失败(502): 正文校验未通过',
      '请求失败，状态码: 500',
      '生成失败: 上游返回空内容',
    ]) {
      expect(isStreamInterruption(new Error(message)), message).toBe(false)
    }
  })

  it('业务错误文案里含 aborted 也不误判（状态码优先）', () => {
    expect(isStreamInterruption(new Error('请求失败(500): task aborted by upstream'))).toBe(false)
  })

  it('空值与未知错误不算中断', () => {
    expect(isStreamInterruption(null)).toBe(false)
    expect(isStreamInterruption(undefined)).toBe(false)
    expect(isStreamInterruption(new Error('未知错误'))).toBe(false)
  })
})

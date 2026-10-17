import { describe, expect, it, vi } from 'vitest'
import { formatReleaseTime, releaseSourceLabel } from './versionInformation'

describe('系统发布时间显示', () => {
  it('缺失或无效时间保持未知，不使用当前时间或提交时间代替', () => {
    for (const value of [
      null,
      undefined,
      '',
      'not-a-date',
      '2026-10-17',
      '2026-10-17T04:40:00',
      '0',
      '1',
    ]) {
      expect(formatReleaseTime(value)).toEqual({ text: '未知', title: '未记录有效时间' })
    }
  })

  it('接受 API 返回的带小数秒 UTC 时间', () => {
    expect(formatReleaseTime('2026-10-17T04:34:56.123456Z').title).toBe(
      '2026-10-17T04:34:56.123Z (UTC)',
    )
  })

  it('使用浏览器时区格式化，并提供 UTC ISO 悬停提示', () => {
    const formatter = vi.spyOn(Date.prototype, 'toLocaleString').mockReturnValue('本地部署时间')
    expect(formatReleaseTime('2026-10-17T12:34:56+08:00')).toEqual({
      text: '本地部署时间',
      title: '2026-10-17T04:34:56.000Z (UTC)',
    })
    expect(formatter).toHaveBeenCalledWith(
      undefined,
      expect.objectContaining({ second: '2-digit', timeZoneName: 'short' }),
    )
    expect(formatter.mock.calls[0]?.[1]).not.toHaveProperty('timeZone')
    formatter.mockRestore()
  })

  it('明确区分镜像、环境与开发目录信息', () => {
    expect(releaseSourceLabel('image')).toBe('构建镜像')
    expect(releaseSourceLabel('environment')).toBe('部署环境')
    expect(releaseSourceLabel('git')).toBe('开发目录 Git')
    expect(releaseSourceLabel('unknown')).toBe('未知来源')
  })
})

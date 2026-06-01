import { describe, it, expect } from 'vitest'
import { formatDate, formatDateTime, formatRelativeTime } from './date'

describe('date utils', () => {
  it('对空值返回占位符 "-"', () => {
    expect(formatDate(null)).toBe('-')
    expect(formatDate(undefined)).toBe('-')
    expect(formatDateTime(null)).toBe('-')
    expect(formatRelativeTime('')).toBe('-')
  })

  it('对非法日期字符串原样返回', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date')
    expect(formatDateTime('not-a-date')).toBe('not-a-date')
  })

  it('formatDate 返回年月日中文格式', () => {
    // 使用带时区的时间戳，断言结构而非具体日（规避本地时区漂移）
    const out = formatDate('2026-06-01T12:00:00Z')
    expect(out).toMatch(/^\d{4}年\d{2}月\d{2}日$/)
  })

  it('formatDateTime 返回含时分的中文格式', () => {
    const out = formatDateTime('2026-06-01T12:00:00Z')
    expect(out).toMatch(/^\d{4}年\d{2}月\d{2}日 \d{2}:\d{2}$/)
  })

  it('formatRelativeTime 对刚刚发生的时间返回 "刚刚"', () => {
    const now = new Date().toISOString()
    expect(formatRelativeTime(now)).toBe('刚刚')
  })
})

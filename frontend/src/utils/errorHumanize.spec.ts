import { describe, expect, it } from 'vitest'
import { humanizeGenerationError } from './errorHumanize'

describe('humanizeGenerationError（生成路径错误文案用户化）', () => {
  it('正文校验 502：告知已重试 + 积分已退，引导直接重生成', () => {
    const out = humanizeGenerationError('请求失败(502): 正文校验未通过')
    expect(out.title).toBe('AI 产出未达标')
    expect(out.message).toContain('积分已退回')
    expect(out.action).toBe('retry')
  })

  it('SSE 透传的正文校验 detail（无状态码）同样命中', () => {
    const out = humanizeGenerationError('高级生成失败: 正文校验未通过，已重试仍不合格')
    expect(out.title).toBe('AI 产出未达标')
  })

  it('不计费操作（快速成书）不提积分退回', () => {
    const out = humanizeGenerationError('请求失败(502): 正文校验未通过', { billed: false })
    expect(out.message).not.toContain('积分')
    expect(out.action).toBe('retry')
  })

  it('已扣费的深度打磨失败仍提示积分已退回', () => {
    const out = humanizeGenerationError('请求失败(500): 章纲生成不完整', { billed: true })
    expect(out.message).toContain('积分已退回')
  })

  it('搜索通道未配置 503：指向管理员配置而非让用户重试', () => {
    const out = humanizeGenerationError(
      '请求失败(503): 未配置参考小说搜索模型（llm_search.*），已跳过网络搜索',
    )
    expect(out.title).toBe('联网搜索不可用')
    expect(out.message).toContain('管理员尚未配置联网搜索模型')
    expect(out.action).toBe('contact_admin')
  })

  it('500/上游超时：解释超时 + 积分已退', () => {
    expect(humanizeGenerationError('请求失败(500): Internal Server Error').title).toBe(
      '服务端处理超时',
    )
    expect(humanizeGenerationError('请求失败，状态码: 500').title).toBe('服务端处理超时')
    const out = humanizeGenerationError('生成章节失败: 上游读取超时')
    expect(out.message).toContain('积分已退回')
    expect(humanizeGenerationError('upstream request timeout').title).toBe('服务端处理超时')
  })

  it('429/限流：建议稍等', () => {
    expect(humanizeGenerationError('请求失败(429)').title).toBe('操作太频繁')
    expect(humanizeGenerationError('操作过于频繁，请稍后再试').action).toBe('wait')
    expect(humanizeGenerationError('Too Many Requests: rate limit exceeded').title).toBe(
      '操作太频繁',
    )
  })

  it('网关并发上限的定制文案走兜底、原文保留（它比通用文案更具体）', () => {
    const raw = '当前并发任务数已达上限，请等待其他任务完成后再生成蓝图'
    const out = humanizeGenerationError(raw, { billed: false })
    expect(out.message).toContain(raw)
  })

  it('兜底：保留原文并补求助出口', () => {
    const out = humanizeGenerationError('数据库连接中断')
    expect(out.message).toContain('数据库连接中断')
    expect(out.message).toContain('如反复出现请联系管理员')
    expect(out.title).toBe('生成失败')
  })

  it('空消息不产出空文案', () => {
    const out = humanizeGenerationError('')
    expect(out.message).toContain('未知错误')
  })
})

describe('humanizeGenerationError（网关 50x 与正文校验分离，2026-10-23）', () => {
  it('裸 502（网关上游不可用）不再说成 AI 产出未达标，也不断言已退款', () => {
    const out = humanizeGenerationError('请求失败(502): 服务暂时不可用')
    expect(out.title).toBe('服务暂时不可用')
    expect(out.message).not.toContain('积分已退回')
    expect(out.message).toContain('积分明细')
    expect(out.action).toBe('wait')
  })

  it('503/504 与 HTML 错误页走同一条「服务暂时不可用」', () => {
    expect(humanizeGenerationError('请求失败(504): 服务暂时不可用').title).toBe('服务暂时不可用')
    expect(humanizeGenerationError('<html><head><title>502 Bad Gateway</title></head></html>').title).toBe(
      '服务暂时不可用',
    )
    const unbilled = humanizeGenerationError('请求失败(503): 服务暂时不可用', { billed: false })
    expect(unbilled.message).not.toContain('积分')
  })

  it('正文校验 502 仍按 detail 原文识别，不依赖状态码', () => {
    expect(humanizeGenerationError('请求失败(502): 正文校验未通过').title).toBe('AI 产出未达标')
    expect(humanizeGenerationError('正文校验未通过，已重试仍不合格').title).toBe('AI 产出未达标')
  })

  it('超时匹配不区分大小写与连字符写法', () => {
    expect(humanizeGenerationError('Upstream Time-out').title).toBe('服务端处理超时')
    expect(humanizeGenerationError('request TIMED OUT').title).toBe('服务端处理超时')
  })
})

describe('humanizeGenerationError 接受错误对象 / 409', () => {
  it('ApiError 按 status 判定，兜底文案去掉「请求失败(NNN):」前缀', async () => {
    const { ApiError } = await import('./apiError')
    const gw = humanizeGenerationError(new ApiError('请求失败(502): Bad Gateway', 502, 'Bad Gateway'))
    expect(gw.title).toBe('服务暂时不可用')
    const conflict = humanizeGenerationError(new ApiError('请求失败(409): 本章正在生成中', 409, '本章正在生成中'))
    expect(conflict.title).toBe('当前状态不允许此操作')
    expect(conflict.message).toContain('本章正在生成中')
    expect(conflict.message).not.toContain('退回')
    const other = humanizeGenerationError(new ApiError('请求失败(400): 章节大纲缺失', 400, '章节大纲缺失'))
    expect(other.message.startsWith('章节大纲缺失')).toBe(true)
    expect(other.message).not.toContain('请求失败(400)')
  })

  it('字符串 409 也识别', () => {
    expect(humanizeGenerationError('请求失败(409): 蓝图已锁定').title).toBe('当前状态不允许此操作')
  })
})

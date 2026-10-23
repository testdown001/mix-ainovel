import { describe, expect, it } from 'vitest'
import { ApiError, errorStatus, formatValidationDetail, readFetchError, stripRequestPrefix, userFacingMessage } from './apiError'

describe('ApiError / userFacingMessage（去掉「请求失败(NNN):」前缀，422 数组可读化）', () => {
  it('ApiError 保留 message 形态给正则检测，detail 单独可取', () => {
    const err = new ApiError('请求失败(402): 积分不足：本次需 40 积分', 402, '积分不足：本次需 40 积分')
    expect(err.message).toBe('请求失败(402): 积分不足：本次需 40 积分')
    expect(errorStatus(err)).toBe(402)
    expect(userFacingMessage(err)).toBe('积分不足：本次需 40 积分')
  })

  it('普通 Error 也能解析前缀与状态码', () => {
    const err = new Error('请求失败(409): 立项书尚未生成，无法倒推骨架')
    expect(errorStatus(err)).toBe(409)
    expect(userFacingMessage(err)).toBe('立项书尚未生成，无法倒推骨架')
    expect(stripRequestPrefix('请求失败，状态码: 503')).toBe('')
    expect(errorStatus('请求失败，状态码: 503')).toBe(503)
  })

  it('detail 为空时按状态码给中文兜底，5xx 不露 HTML/英文', () => {
    expect(userFacingMessage(new ApiError('请求失败，状态码: 409', 409, ''))).toBe('当前状态不允许此操作，请刷新后重试')
    expect(userFacingMessage(new ApiError('请求失败，状态码: 429', 429, ''))).toBe('操作太频繁，请稍后再试')
    expect(userFacingMessage(new ApiError('请求失败，状态码: 502', 502, ''))).toBe('服务暂时不可用，请稍后重试')
    expect(userFacingMessage(new ApiError('请求失败(504): Gateway Time-out', 504, 'Gateway Time-out'))).toBe('服务暂时不可用，请稍后重试')
    expect(userFacingMessage(null)).toBe('未知错误')
    expect(userFacingMessage(undefined, '请稍后重试')).toBe('请稍后重试')
  })

  it('FastAPI 422 detail 数组 → 一行中文', () => {
    const detail = [
      { loc: ['body', 'email'], msg: 'value is not a valid email address', type: 'value_error' },
      { loc: ['body', 'password'], msg: 'ensure this value has at least 8 characters', type: 'value_error' },
    ]
    expect(formatValidationDetail(detail)).toBe('参数校验失败：email: value is not a valid email address（等 2 项）')
    expect(formatValidationDetail([])).toBe('')
    expect(formatValidationDetail('x')).toBe('')
  })

  it('readFetchError：HTML 错误页不进消息，422 数组可读，JSON detail 原样', async () => {
    const html = new Response('<html><body>502 Bad Gateway</body></html>', { status: 502, headers: { 'content-type': 'text/html' } })
    const e1 = await readFetchError(html, '登录失败')
    expect(e1.status).toBe(502)
    expect(userFacingMessage(e1)).toBe('服务暂时不可用，请稍后重试')
    expect(e1.message).not.toContain('<html')

    const v = new Response(JSON.stringify({ detail: [{ loc: ['body', 'username'], msg: 'field required' }] }), {
      status: 422, headers: { 'content-type': 'application/json' },
    })
    expect(userFacingMessage(await readFetchError(v, '注册失败'))).toBe('参数校验失败：username: field required')

    const d = new Response(JSON.stringify({ detail: '用户名已存在' }), { status: 400, headers: { 'content-type': 'application/json' } })
    expect(userFacingMessage(await readFetchError(d, '注册失败'))).toBe('用户名已存在')

    const broken = new Response('not json', { status: 500, headers: { 'content-type': 'application/json' } })
    expect(userFacingMessage(await readFetchError(broken, '登录失败'))).toBe('服务暂时不可用，请稍后重试')
  })
})

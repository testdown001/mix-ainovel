/**
 * API 错误对象与用户可见文案。
 *
 * http.ts 抛出的错误 message 形态固定为 `请求失败(NNN): detail`，upgradeHint / errorHumanize
 * 里的正则都认这个前缀，不能改。但这串前缀不该出现在给用户看的提示里
 * （2026-10-23 审计：UpgradePrompt 里显示「请求失败(402): 积分不足…」，422 显示整段 JSON）。
 * 所以：错误对象额外带 status/detail，展示时统一走 userFacingMessage()。
 */

const PREFIX_RE = /^请求失败(?:\((\d{3})\))?(?:，状态码:\s*(\d{3}))?:?\s*/

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(message: string, status: number, detail: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export const isApiError = (err: unknown): err is ApiError =>
  err instanceof ApiError || (typeof err === 'object' && err !== null && (err as any).name === 'ApiError' && typeof (err as any).status === 'number')

/** 从任意错误里取 HTTP 状态码：优先对象字段，其次从 message 前缀解析。 */
export const errorStatus = (err: unknown): number | null => {
  if (isApiError(err)) return err.status
  const message = err instanceof Error ? err.message : typeof err === 'string' ? err : ''
  const match = PREFIX_RE.exec(message)
  const code = match?.[1] || match?.[2]
  return code ? Number(code) : null
}

const STATUS_FALLBACK: Record<number, string> = {
  400: '请求参数有误，请检查后重试',
  403: '没有权限执行此操作',
  404: '请求的内容不存在或已被删除',
  408: '请求超时，请稍后重试',
  409: '当前状态不允许此操作，请刷新后重试',
  413: '内容过大，请精简后重试',
  422: '参数校验失败，请检查输入',
  429: '操作太频繁，请稍后再试',
}

export const statusFallbackMessage = (status: number | null): string | null => {
  if (status == null) return null
  if (status >= 500) return '服务暂时不可用，请稍后重试'
  return STATUS_FALLBACK[status] ?? null
}

/** 去掉 http.ts 的前缀，只留后端 detail。 */
export const stripRequestPrefix = (message: string): string => message.replace(PREFIX_RE, '').trim()

/**
 * 给用户看的错误文案：
 * - ApiError：detail（已去前缀）；detail 为空按状态码给通用中文；
 * - 其它 Error：message 去前缀；
 * - 兜底「未知错误」。
 */
export const userFacingMessage = (err: unknown, fallback = '未知错误'): string => {
  const status = errorStatus(err)
  let text = ''
  if (isApiError(err)) {
    text = (err.detail || '').trim()
  } else if (err instanceof Error) {
    text = stripRequestPrefix(err.message)
  } else if (typeof err === 'string') {
    text = stripRequestPrefix(err)
  }
  // 状态码兜底：detail 为空，或 detail 本身只是个状态码/英文短语
  if (!text || /^\d{3}$/.test(text) || /^(bad gateway|service unavailable|gateway time-?out|internal server error|not found|conflict|unauthorized|forbidden)$/i.test(text)) {
    return statusFallbackMessage(status) ?? (text || fallback)
  }
  return text
}

/** FastAPI 422 的 detail 数组 → 一行可读中文。 */
export const formatValidationDetail = (detail: unknown): string => {
  if (!Array.isArray(detail) || detail.length === 0) return ''
  const first = detail[0] as any
  const loc = Array.isArray(first?.loc) ? first.loc.filter((p: unknown) => typeof p === 'string' && p !== 'body' && p !== 'query' && p !== 'path') : []
  const field = loc.length ? String(loc[loc.length - 1]) : ''
  const msg = typeof first?.msg === 'string' ? first.msg : ''
  const head = field && msg ? `${field}: ${msg}` : field || msg || '输入不符合要求'
  const more = detail.length > 1 ? `（等 ${detail.length} 项）` : ''
  return `参数校验失败：${head}${more}`
}

/**
 * 裸 fetch 调用（注册/找回密码等不走 http.ts 的页面）读取错误：
 * 永远不让 `res.json()` 的解析异常（「Unexpected token <」）或 422 数组原样露给用户。
 */
export const readFetchError = async (res: Response, fallback: string): Promise<ApiError> => {
  let detail = ''
  const contentType = (res.headers.get('content-type') || '').toLowerCase()
  if (contentType.includes('application/json')) {
    const data = await res.json().catch(() => null as any)
    if (typeof data?.detail === 'string') detail = data.detail.trim()
    else if (Array.isArray(data?.detail)) detail = formatValidationDetail(data.detail)
    else if (typeof data?.message === 'string') detail = data.message.trim()
  } else {
    await res.text().catch(() => '')
  }
  const text = detail || statusFallbackMessage(res.status) || fallback
  return new ApiError(`请求失败(${res.status}): ${text}`, res.status, text)
}

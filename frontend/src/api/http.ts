import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import { ApiError, formatValidationDetail } from '@/utils/apiError'

export { ApiError }

interface ApiRequestOptions<T> extends RequestInit {
  notFoundValue?: T
  errorFallbackValue?: T
  errorMessage?: string
}

const buildHeaders = (options: RequestInit): Headers => {
  const headers = new Headers(options.headers)

  if (options.body instanceof FormData) {
    headers.delete('Content-Type')
  } else if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const authStore = useAuthStore()
  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }

  return headers
}

const extractErrorDetail = async (response: Response): Promise<string> => {
  const contentType = (response.headers.get('content-type') || '').toLowerCase()

  if (contentType.includes('application/json')) {
    const errorData = await response.json().catch(() => null as any)
    if (typeof errorData?.detail === 'string' && errorData.detail.trim()) {
      return errorData.detail.trim()
    }
    if (typeof errorData?.message === 'string' && errorData.message.trim()) {
      return errorData.message.trim()
    }
    if (typeof errorData?.error?.message === 'string' && errorData.error.message.trim()) {
      return errorData.error.message.trim()
    }
    // FastAPI 422：detail 是 [{loc,msg,type}] 数组——以前整段 JSON.stringify 给用户看
    if (Array.isArray(errorData?.detail)) {
      return formatValidationDetail(errorData.detail)
    }
    if (typeof errorData?.detail === 'object' && errorData?.detail !== null && typeof errorData.detail.message === 'string') {
      return String(errorData.detail.message).trim()
    }
    return ''
  }

  // 非 JSON（nginx/网关的 HTML 错误页、纯文本）：读掉但不进消息，交给状态码兜底文案
  await response.text().catch(() => '')
  return ''
}

const REQUEST_OPTION_KEYS = [
  'body',
  'headers',
  'method',
  'mode',
  'credentials',
  'cache',
  'redirect',
  'referrer',
  'referrerPolicy',
  'integrity',
  'keepalive',
  'signal',
  'notFoundValue',
  'errorFallbackValue',
  'errorMessage'
] as const

const isApiRequestOptions = <T>(value: unknown): value is ApiRequestOptions<T> => {
  if (!value || typeof value !== 'object') {
    return false
  }

  return REQUEST_OPTION_KEYS.some((key) => key in (value as Record<string, unknown>))
}

const serializeRequestBody = (payload: unknown): BodyInit | null | undefined => {
  if (typeof payload === 'undefined') {
    return undefined
  }
  if (payload === null) {
    return null
  }
  if (
    typeof payload === 'string' ||
    payload instanceof FormData ||
    payload instanceof URLSearchParams ||
    payload instanceof Blob ||
    payload instanceof ArrayBuffer ||
    ArrayBuffer.isView(payload)
  ) {
    return payload as BodyInit
  }

  return JSON.stringify(payload)
}

const normalizeWriteOptions = <T>(
  payloadOrOptions?: unknown,
  maybeOptions?: ApiRequestOptions<T>
): ApiRequestOptions<T> => {
  if (typeof maybeOptions !== 'undefined') {
    return {
      ...maybeOptions,
      body: serializeRequestBody(payloadOrOptions)
    }
  }

  if (isApiRequestOptions<T>(payloadOrOptions)) {
    return payloadOrOptions
  }

  return {
    body: serializeRequestBody(payloadOrOptions)
  }
}

export const requestJson = async <T = any>(url: string, options: ApiRequestOptions<T> = {}): Promise<T> => {
  const { notFoundValue, errorFallbackValue, errorMessage, ...fetchOptions } = options
  const response = await fetch(url, {
    ...fetchOptions,
    headers: buildHeaders(fetchOptions)
  })

  if (response.status === 401) {
    const authStore = useAuthStore()
    authStore.logout()
    router.push('/login')
    throw new ApiError('会话已过期，请重新登录', 401, '会话已过期，请重新登录')
  }

  if (response.status === 404 && typeof notFoundValue !== 'undefined') {
    return notFoundValue
  }

  if (!response.ok) {
    if (typeof errorFallbackValue !== 'undefined') {
      return errorFallbackValue
    }

    // message 形态保持不变（upgradeHint / errorHumanize 的正则认 `(NNN)` 前缀）；
    // 给用户看的文案走 utils/apiError.userFacingMessage()，它读 status/detail 而不是 message。
    const detail = await extractErrorDetail(response)
    if (errorMessage) {
      throw new ApiError(detail ? `${errorMessage}: ${detail}` : errorMessage, response.status, detail || errorMessage)
    }
    if (detail) {
      const clipped = detail.length > 600 ? `${detail.slice(0, 600)}...` : detail
      throw new ApiError(`请求失败(${response.status}): ${clipped}`, response.status, clipped)
    }
    throw new ApiError(`请求失败，状态码: ${response.status}`, response.status, '')
  }

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = (response.headers.get('content-type') || '').toLowerCase()
  if (contentType.includes('application/json')) {
    return response.json() as Promise<T>
  }

  return (await response.text()) as T
}

const createHttpWrapper = () => ({
  async get<T = any>(url: string, options?: ApiRequestOptions<T>): Promise<{ data: T }> {
    const data = await requestJson<T>(url, { ...options, method: 'GET' })
    return { data }
  },
  async post<T = any>(
    url: string,
    payloadOrOptions?: unknown,
    maybeOptions?: ApiRequestOptions<T>
  ): Promise<{ data: T }> {
    const data = await requestJson<T>(url, {
      ...normalizeWriteOptions<T>(payloadOrOptions, maybeOptions),
      method: 'POST'
    })
    return { data }
  },
  async put<T = any>(
    url: string,
    payloadOrOptions?: unknown,
    maybeOptions?: ApiRequestOptions<T>
  ): Promise<{ data: T }> {
    const data = await requestJson<T>(url, {
      ...normalizeWriteOptions<T>(payloadOrOptions, maybeOptions),
      method: 'PUT'
    })
    return { data }
  },
  async delete<T = any>(
    url: string,
    payloadOrOptions?: unknown,
    maybeOptions?: ApiRequestOptions<T>
  ): Promise<{ data: T }> {
    const data = await requestJson<T>(url, {
      ...normalizeWriteOptions<T>(payloadOrOptions, maybeOptions),
      method: 'DELETE'
    })
    return { data }
  },
})

export const http = createHttpWrapper()

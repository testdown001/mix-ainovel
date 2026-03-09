import { useAuthStore } from '@/stores/auth'
import router from '@/router'

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
    if (errorData) {
      return JSON.stringify(errorData)
    }
    return ''
  }

  return (await response.text().catch(() => '')).trim()
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
    throw new Error('会话已过期，请重新登录')
  }

  if (response.status === 404 && typeof notFoundValue !== 'undefined') {
    return notFoundValue
  }

  if (!response.ok) {
    if (typeof errorFallbackValue !== 'undefined') {
      return errorFallbackValue
    }

    const detail = await extractErrorDetail(response)
    if (errorMessage) {
      throw new Error(detail ? `${errorMessage}: ${detail}` : errorMessage)
    }
    if (detail) {
      const clipped = detail.length > 600 ? `${detail.slice(0, 600)}...` : detail
      throw new Error(`请求失败(${response.status}): ${clipped}`)
    }
    throw new Error(`请求失败，状态码: ${response.status}`)
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

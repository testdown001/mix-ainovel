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

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// node 环境没有 localStorage（仓库未装 jsdom）：给一个最小内存实现，store 模块加载时就会用到
const memoryStorage = (() => {
  let data: Record<string, string> = {}
  return {
    getItem: (k: string) => (k in data ? data[k] : null),
    setItem: (k: string, v: string) => { data[k] = String(v) },
    removeItem: (k: string) => { delete data[k] },
    clear: () => { data = {} },
  }
})()
vi.stubGlobal('localStorage', memoryStorage)

const { useAuthStore } = await import('./auth')

function mockFetch(status: number, body: unknown = {}) {
  const response = {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers(),
    json: async () => body,
  }
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))
}

describe('authStore.fetchUser 只在鉴权失败时登出', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', memoryStorage) // unstubAllGlobals 会把它一起清掉，每个用例重新挂
    setActivePinia(createPinia())
    localStorage.setItem('token', 'tok')
    vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  afterEach(() => {
    memoryStorage.clear()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('401 登出并清 token', async () => {
    const store = useAuthStore()
    store.token = 'tok'
    mockFetch(401, { detail: 'expired' })
    expect(await store.fetchUser()).toBe(false)
    expect(store.token).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('500 不登出：token 与已知用户都保留', async () => {
    const store = useAuthStore()
    store.token = 'tok'
    store.user = { id: 1, username: 'u', is_admin: false, is_premium: false, must_change_password: false, plan_tier: 'free', effective_tier: 'free' } as any
    mockFetch(500, {})
    expect(await store.fetchUser()).toBe(false)
    expect(store.token).toBe('tok')
    expect(store.user?.username).toBe('u')
    expect(localStorage.getItem('token')).toBe('tok')
  })

  it('网络错误不登出', async () => {
    const store = useAuthStore()
    store.token = 'tok'
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    expect(await store.fetchUser()).toBe(false)
    expect(store.token).toBe('tok')
  })

  it('200 写入用户并返回 true', async () => {
    const store = useAuthStore()
    store.token = 'tok'
    mockFetch(200, { id: 7, username: 'neo', is_admin: true, plan_tier: 'creator', effective_tier: 'creator' })
    expect(await store.fetchUser()).toBe(true)
    expect(store.user?.id).toBe(7)
    expect(store.user?.is_admin).toBe(true)
  })
})

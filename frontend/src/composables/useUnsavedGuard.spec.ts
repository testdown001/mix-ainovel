import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/composables/useAlert', () => ({
  globalAlert: { showConfirm: vi.fn() },
}))

import { globalAlert } from '@/composables/useAlert'
import {
  anyRegisteredDirty,
  registerDirtyChecker,
  useUnsavedGuard,
} from './useUnsavedGuard'

describe('useUnsavedGuard', () => {
  beforeEach(() => {
    vi.mocked(globalAlert.showConfirm).mockReset()
  })

  it('不脏时直接放行，不弹确认', async () => {
    const { confirmDiscard } = useUnsavedGuard({ isDirty: () => false })
    await expect(confirmDiscard()).resolves.toBe(true)
    expect(globalAlert.showConfirm).not.toHaveBeenCalled()
  })

  it('脏时弹 globalAlert.showConfirm，并把用户的选择原样返回', async () => {
    vi.mocked(globalAlert.showConfirm).mockResolvedValueOnce(false)
    const { confirmDiscard } = useUnsavedGuard({ isDirty: () => true, message: '自定义文案' })
    await expect(confirmDiscard()).resolves.toBe(false)
    expect(globalAlert.showConfirm).toHaveBeenCalledWith('自定义文案', '放弃未保存的修改？')

    vi.mocked(globalAlert.showConfirm).mockResolvedValueOnce(true)
    await expect(confirmDiscard()).resolves.toBe(true)
  })

  it('isDirty 抛错按不脏处理，不会把用户卡住', async () => {
    const { confirmDiscard } = useUnsavedGuard({ isDirty: () => { throw new Error('boom') } })
    await expect(confirmDiscard()).resolves.toBe(true)
  })

  it('跨组件登记：任一登记的检查器为脏即为脏，注销后不再计入', () => {
    expect(anyRegisteredDirty()).toBe(false)
    const unregisterClean = registerDirtyChecker(() => false)
    const unregisterDirty = registerDirtyChecker(() => true)
    expect(anyRegisteredDirty()).toBe(true)
    unregisterDirty()
    expect(anyRegisteredDirty()).toBe(false)
    unregisterClean()
  })
})

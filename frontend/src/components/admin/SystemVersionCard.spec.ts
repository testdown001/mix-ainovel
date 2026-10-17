import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRenderer, nextTick, ssrContextKey } from 'vue'
import { AdminAPI, type SystemInformation } from '@/api/admin'
import SystemVersionCard from './SystemVersionCard.vue'

vi.mock('@/api/admin', () => ({ AdminAPI: { getSystemInformation: vi.fn() } }))

const renderer = createRenderer<any, any>({
  createElement: () => ({}),
  createText: () => ({}),
  createComment: () => ({}),
  insert: () => {},
  remove: () => {},
  setText: () => {},
  setElementText: () => {},
  parentNode: () => null,
  nextSibling: () => null,
  patchProp: () => {},
})
let app: ReturnType<typeof renderer.createApp> | undefined
const release: SystemInformation = {
  git_commit: '3c274163c274163c274163c274163c274163c27416',
  git_short_commit: '3c27416',
  git_branch: 'main',
  git_commit_time: '2026-10-17T04:00:00Z',
  git_dirty: false,
  built_at: '2026-10-17T04:30:00Z',
  deployed_at: '2026-10-17T04:40:00Z',
  deployment_id: 'release-20261017',
  source: 'image',
}

async function mount() {
  app = renderer.createApp({ ...SystemVersionCard, render: () => null })
  app.provide(ssrContextKey, { modules: new Set() })
  app.mount({})
  for (let i = 0; i < 6; i++) {
    await Promise.resolve()
    await nextTick()
  }
  return (app as any)._instance.setupState
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(AdminAPI.getSystemInformation).mockResolvedValue(release)
})

afterEach(() => {
  app?.unmount()
  app = undefined
  vi.unstubAllGlobals()
})

describe('管理员系统版本卡片', () => {
  it('独立读取系统发布信息，不请求统计或调用其他接口', async () => {
    const vm = await mount()
    expect(AdminAPI.getSystemInformation).toHaveBeenCalledExactlyOnceWith()
    expect(vm.information).toEqual(release)
    expect(vm.loading).toBe(false)
    expect(vm.error).toBeNull()
    expect(vm.timeFields.map((item: { label: string }) => item.label)).toEqual([
      '提交时间',
      '构建时间',
      '部署时间',
    ])
  })

  it('读取失败保持卡内错误，并可独立重试', async () => {
    vi.mocked(AdminAPI.getSystemInformation).mockRejectedValueOnce(new Error('版本读取失败'))
    const vm = await mount()
    expect(vm.error).toBe('版本读取失败')
    expect(vm.information).toBeNull()
    expect(vm.loading).toBe(false)
    await vm.loadInformation()
    expect(vm.error).toBeNull()
    expect(vm.information.git_commit).toBe(release.git_commit)
  })

  it('缺失部署时间显示未知，其他时间不能代替', async () => {
    vi.mocked(AdminAPI.getSystemInformation).mockResolvedValue({ ...release, deployed_at: null })
    const vm = await mount()
    expect(vm.timeFields[2].formatted.text).toBe('未知')
    expect(vm.timeFields[1].formatted.text).not.toBe('未知')
  })

  it('复制完整提交，而不是短 SHA', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const vm = await mount()
    await vm.copyCommit()
    expect(writeText).toHaveBeenCalledExactlyOnceWith(release.git_commit)
    expect(vm.copied).toBe(true)
    expect(vm.copyError).toBeNull()
  })

  it('浏览器复制不可用时展开完整提交供手动复制', async () => {
    vi.stubGlobal('navigator', {})
    const vm = await mount()
    await vm.copyCommit()
    expect(vm.copied).toBe(false)
    expect(vm.showFullCommit).toBe(true)
    expect(vm.copyError).toContain('手动复制')
  })

  it('刷新到另一提交后，迟到的复制结果不标记新提交已复制', async () => {
    let finishCopy!: () => void
    const writeText = vi.fn().mockReturnValue(
      new Promise<void>((resolve) => {
        finishCopy = resolve
      }),
    )
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const vm = await mount()
    const pendingCopy = vm.copyCommit()
    vi.mocked(AdminAPI.getSystemInformation).mockResolvedValue({
      ...release,
      git_commit: 'a'.repeat(40),
      git_short_commit: 'a'.repeat(12),
    })
    await vm.loadInformation()
    finishCopy()
    await pendingCopy
    expect(vm.copied).toBe(false)
    expect(vm.copyError).toBeNull()
  })
})

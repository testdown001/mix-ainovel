import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createRenderer, nextTick, ssrContextKey } from 'vue'
import NovelManagement from './NovelManagement.vue'
import { AdminAPI, type AdminNovelSummary } from '@/api/admin'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/api/admin', () => ({
  AdminAPI: {
    listNovels: vi.fn(),
    confirmNovelDeletion: vi.fn(),
    deleteNovel: vi.fn(),
    confirmNovelsDeletion: vi.fn(),
    deleteNovels: vi.fn(),
  },
}))

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
const testNovel = {
  id: 'test-book',
  title: '测试小说',
  owner_id: 2,
  owner_username: 'bench@local',
  genre: '玄幻',
  last_edited: '',
  completed_chapters: 3,
  total_chapters: 6,
  creation_source: 'ai_test',
  can_delete: true,
} as AdminNovelSummary
const userNovel = { ...testNovel, id: 'user-book', creation_source: 'user', can_delete: false }
async function flush() {
  for (let i = 0; i < 6; i++) {
    await Promise.resolve()
    await nextTick()
  }
}
async function mount() {
  app = renderer.createApp({ ...NovelManagement, render: () => null })
  app.provide(ssrContextKey, { modules: new Set() })
  app.mount({})
  await flush()
  return (app as any)._instance.setupState
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.stubGlobal('window', {
    innerWidth: 1024,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })
  vi.mocked(AdminAPI.listNovels).mockResolvedValue([testNovel, userNovel])
  vi.mocked(AdminAPI.confirmNovelDeletion).mockResolvedValue({
    confirmation_token: 'ticket',
    expires_in: 300,
  })
  vi.mocked(AdminAPI.deleteNovel).mockResolvedValue(undefined)
  vi.mocked(AdminAPI.confirmNovelsDeletion).mockResolvedValue({
    confirmation_token: 'batch-ticket',
    expires_in: 300,
  })
  vi.mocked(AdminAPI.deleteNovels).mockResolvedValue(undefined)
})

describe('管理员小说批量删除', () => {
  const systemNovel = { ...testNovel, id: 'system-book', creation_source: 'system' }

  it('全选排除用户作品，锁定清单并经过两次输入后批量删除', async () => {
    const vm = await mount()
    vm.novels = [testNovel, systemNovel, userNovel]
    vm.selectAllDeletable()
    expect(vm.checkedProjectIds).toEqual(['test-book', 'system-book'])
    vm.startBatchDeletion()
    expect(vm.deletionTargets.map((novel: AdminNovelSummary) => novel.id)).toEqual([
      'test-book',
      'system-book',
    ])
    vm.updateSelection([])
    expect(vm.checkedProjectIds).toHaveLength(2)
    await vm.confirmFirstDeletion()
    expect(AdminAPI.confirmNovelsDeletion).not.toHaveBeenCalled()
    vm.firstConfirmation = '删除'
    await vm.confirmFirstDeletion()
    expect(AdminAPI.confirmNovelsDeletion).toHaveBeenCalledExactlyOnceWith(
      ['test-book', 'system-book'],
      '删除',
    )
    expect(AdminAPI.deleteNovels).not.toHaveBeenCalled()
    expect(vm.secondConfirmation).toBe('')
    vm.secondConfirmation = '删除'
    await vm.confirmSecondDeletion()
    expect(AdminAPI.deleteNovels).toHaveBeenCalledExactlyOnceWith(
      ['test-book', 'system-book'],
      '删除',
      'batch-ticket',
    )
    expect(vm.novels.map((novel: AdminNovelSummary) => novel.id)).toEqual(['user-book'])
    expect(vm.checkedProjectIds).toEqual([])
    expect(AdminAPI.deleteNovel).not.toHaveBeenCalled()
  })

  it('手机选择及表格选择均排除受保护项目且每批不超过100项', async () => {
    const vm = await mount()
    vm.toggleSelection(userNovel, true)
    expect(vm.checkedProjectIds).toEqual([])
    vm.toggleSelection(testNovel, true)
    expect(vm.checkedProjectIds).toEqual(['test-book'])
    vm.toggleSelection(testNovel, false)
    expect(vm.checkedProjectIds).toEqual([])
    vm.novels = Array.from({ length: 101 }, (_, i) => ({ ...testNovel, id: `test-${i}` }))
    vm.updateSelection(vm.novels.map((novel: AdminNovelSummary) => novel.id))
    expect(vm.checkedProjectIds).toHaveLength(100)
  })

  it('被篡改或失效的选择拒绝整批确认', async () => {
    const vm = await mount()
    vm.checkedProjectIds = ['test-book', 'user-book']
    vm.startBatchDeletion()
    expect(vm.showFirstConfirmation).toBe(false)
    expect(AdminAPI.confirmNovelsDeletion).not.toHaveBeenCalled()
  })

  it('失败时保留整批列表和选择，重新要求两次确认', async () => {
    const vm = await mount()
    vm.novels = [testNovel, systemNovel, userNovel]
    vm.selectAllDeletable()
    vm.startBatchDeletion()
    vm.firstConfirmation = '删除'
    await vm.confirmFirstDeletion()
    vi.mocked(AdminAPI.deleteNovels).mockRejectedValueOnce(new Error('整批删除已拒绝'))
    vm.secondConfirmation = '删除'
    await vm.confirmSecondDeletion()
    expect(vm.novels).toHaveLength(3)
    expect(vm.checkedProjectIds).toHaveLength(2)
    expect(vm.showFirstConfirmation).toBe(true)
    expect(vm.showSecondConfirmation).toBe(false)
    expect(vm.confirmationToken).toBe('')
    expect(vm.firstConfirmation).toBe('')
    expect(vm.secondConfirmation).toBe('')
  })

  it('取消后重新批量删除不会沿用输入或凭证', async () => {
    const vm = await mount()
    vm.selectAllDeletable()
    vm.startBatchDeletion()
    vm.firstConfirmation = '删除'
    await vm.confirmFirstDeletion()
    vm.cancelDeletion()
    vm.startBatchDeletion()
    expect(vm.firstConfirmation).toBe('')
    expect(vm.confirmationToken).toBe('')
    expect(vm.showFirstConfirmation).toBe(true)
    expect(AdminAPI.deleteNovels).not.toHaveBeenCalled()
  })
})
afterEach(() => {
  app?.unmount()
  vi.unstubAllGlobals()
})

describe('管理员小说双重删除确认', () => {
  it('两个独立弹窗都输入删除后才调用删除接口', async () => {
    const vm = await mount()
    vm.startDeletion(testNovel)
    expect(vm.showFirstConfirmation).toBe(true)
    expect(vm.showSecondConfirmation).toBe(false)
    vm.firstConfirmation = '确认'
    await vm.confirmFirstDeletion()
    expect(AdminAPI.confirmNovelDeletion).not.toHaveBeenCalled()
    vm.firstConfirmation = '删除'
    await vm.confirmFirstDeletion()
    expect(AdminAPI.confirmNovelDeletion).toHaveBeenCalledWith('test-book', '删除')
    expect(AdminAPI.deleteNovel).not.toHaveBeenCalled()
    expect(vm.showFirstConfirmation).toBe(false)
    expect(vm.showSecondConfirmation).toBe(true)
    expect(vm.secondConfirmation).toBe('')
    await vm.confirmSecondDeletion()
    expect(AdminAPI.deleteNovel).not.toHaveBeenCalled()
    vm.secondConfirmation = '删除'
    await vm.confirmSecondDeletion()
    expect(AdminAPI.deleteNovel).toHaveBeenCalledExactlyOnceWith('test-book', '删除', 'ticket')
    expect(vm.novels.map((n: AdminNovelSummary) => n.id)).toEqual(['user-book'])
    expect(vm.showSecondConfirmation).toBe(false)
  })

  it('用户作品及未知来源即使收到可删除标志也不开放删除', async () => {
    const vm = await mount()
    for (const novel of [
      userNovel,
      { ...userNovel, can_delete: true },
      { ...testNovel, creation_source: 'unknown' },
    ]) {
      vm.startDeletion(novel)
      expect(vm.showFirstConfirmation).toBe(false)
    }
    expect(AdminAPI.confirmNovelDeletion).not.toHaveBeenCalled()
    expect(AdminAPI.deleteNovel).not.toHaveBeenCalled()
  })

  it('取消第二次确认后清除凭证和两次输入', async () => {
    const vm = await mount()
    vm.startDeletion(testNovel)
    vm.firstConfirmation = '删除'
    await vm.confirmFirstDeletion()
    vm.secondConfirmation = '删除'
    vm.cancelDeletion()
    vm.startDeletion(testNovel)
    expect(vm.firstConfirmation).toBe('')
    expect(vm.secondConfirmation).toBe('')
    expect(vm.confirmationToken).toBe('')
    await vm.confirmSecondDeletion()
    expect(AdminAPI.deleteNovel).not.toHaveBeenCalled()
  })

  it('删除失败保留列表并要求从第一次确认重新开始', async () => {
    const vm = await mount()
    vi.mocked(AdminAPI.deleteNovel).mockRejectedValueOnce(new Error('确认已失效'))
    vm.startDeletion(testNovel)
    vm.firstConfirmation = '删除'
    await vm.confirmFirstDeletion()
    vm.secondConfirmation = '删除'
    await vm.confirmSecondDeletion()
    expect(vm.novels).toHaveLength(2)
    expect(vm.showFirstConfirmation).toBe(true)
    expect(vm.showSecondConfirmation).toBe(false)
    expect(vm.firstConfirmation).toBe('')
    expect(vm.confirmationToken).toBe('')
    expect(vm.deletionError).toBe('确认已失效')
  })

  it('第一次确认失败保持第一弹窗，不执行删除', async () => {
    const vm = await mount()
    vi.mocked(AdminAPI.confirmNovelDeletion).mockRejectedValueOnce(new Error('用户作品受保护'))
    vm.startDeletion(testNovel)
    vm.firstConfirmation = '删除'
    await vm.confirmFirstDeletion()
    expect(vm.showFirstConfirmation).toBe(true)
    expect(vm.showSecondConfirmation).toBe(false)
    expect(AdminAPI.deleteNovel).not.toHaveBeenCalled()
  })
})

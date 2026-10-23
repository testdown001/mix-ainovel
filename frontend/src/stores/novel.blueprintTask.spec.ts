import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { BlueprintStillRunningError, readPendingBlueprintTask, useNovelStore } from './novel'
import { TaskAPI } from '@/api/task'
import { NovelAPI } from '@/api/novel'

vi.mock('@/api/task', () => ({ TaskAPI: { submitBlueprintGenerate: vi.fn(), pollUntilDone: vi.fn(), getTaskStatus: vi.fn() } }))
vi.mock('@/api/novel', () => ({ NovelAPI: { getNovel: vi.fn(), generateBlueprint: vi.fn() } }))

const memory = new Map<string, string>()

describe('蓝图任务的 sessionStorage 记录', () => {
  beforeEach(() => {
    memory.clear()
    vi.resetAllMocks()
    setActivePinia(createPinia())
    vi.stubGlobal('sessionStorage', {
      getItem: (k: string) => memory.get(k) ?? null,
      setItem: (k: string, v: string) => void memory.set(k, v),
      removeItem: (k: string) => void memory.delete(k),
    })
    vi.mocked(NovelAPI.getNovel).mockResolvedValue({ id: 'p1', chapters: [], blueprint: { title: 'x' } } as any)
  })

  it('客户端轮询超时：保留任务记录并抛「仍在后台生成」，而不是服务端超时/退款', async () => {
    const store = useNovelStore()
    store.setCurrentProject({ id: 'p1', chapters: [] } as any)
    vi.mocked(TaskAPI.submitBlueprintGenerate).mockResolvedValue({ task_id: 't-1' } as any)
    vi.mocked(TaskAPI.pollUntilDone).mockRejectedValue(new Error('任务超时'))
    await expect(store.generateBlueprint('deep')).rejects.toBeInstanceOf(BlueprintStillRunningError)
    await expect(store.generateBlueprint('deep')).rejects.toThrow('蓝图仍在后台生成')
    expect(readPendingBlueprintTask('p1')).toBe('t-1')
  })

  it('任务完成或真正失败：清掉记录', async () => {
    const store = useNovelStore()
    store.setCurrentProject({ id: 'p1', chapters: [] } as any)
    vi.mocked(TaskAPI.submitBlueprintGenerate).mockResolvedValue({ task_id: 't-2' } as any)
    vi.mocked(TaskAPI.pollUntilDone).mockResolvedValue({ status: 'completed', result: { blueprint: { title: 'x' }, ai_message: 'ok' } } as any)
    const result = await store.generateBlueprint('fast')
    expect(result.blueprint.title).toBe('x')
    expect(readPendingBlueprintTask('p1')).toBeNull()

    vi.mocked(TaskAPI.submitBlueprintGenerate).mockResolvedValue({ task_id: 't-3' } as any)
    vi.mocked(TaskAPI.pollUntilDone).mockRejectedValue(new Error('任务执行失败'))
    await expect(store.generateBlueprint('fast')).rejects.toThrow('任务执行失败')
    expect(readPendingBlueprintTask('p1')).toBeNull()
  })

  it('带 resumeTaskId 时不重新提交任务', async () => {
    const store = useNovelStore()
    store.setCurrentProject({ id: 'p1', chapters: [] } as any)
    vi.mocked(TaskAPI.pollUntilDone).mockResolvedValue({ status: 'completed', result: { blueprint: { title: 'y' }, ai_message: '' } } as any)
    await store.generateBlueprint('deep', { resumeTaskId: 't-old' })
    expect(TaskAPI.submitBlueprintGenerate).not.toHaveBeenCalled()
    expect(TaskAPI.pollUntilDone).toHaveBeenCalledWith('t-old', undefined, 3000, 1_200_000)
  })

  it('checkPendingBlueprintTask：running 返回任务 ID，completed 清记录并刷新项目，查不到则清记录', async () => {
    const store = useNovelStore()
    memory.set('arboris.blueprint_task.p1', 't-9')
    vi.mocked(TaskAPI.getTaskStatus).mockResolvedValueOnce({ status: 'running' } as any)
    expect(await store.checkPendingBlueprintTask('p1')).toEqual({ state: 'running', taskId: 't-9' })
    vi.mocked(TaskAPI.getTaskStatus).mockResolvedValueOnce({ status: 'completed' } as any)
    expect(await store.checkPendingBlueprintTask('p1')).toEqual({ state: 'completed' })
    expect(readPendingBlueprintTask('p1')).toBeNull()
    memory.set('arboris.blueprint_task.p1', 't-10')
    vi.mocked(TaskAPI.getTaskStatus).mockRejectedValueOnce(new Error('404'))
    expect(await store.checkPendingBlueprintTask('p1')).toBeNull()
    expect(readPendingBlueprintTask('p1')).toBeNull()
  })
})

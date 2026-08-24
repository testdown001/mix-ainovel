import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ isAuthenticated: false, token: null, user: null }),
}))
vi.mock('@/router', () => ({ default: { push: vi.fn() } }))

import { TaskAPI, type TaskStatus } from './task'

function taskStatus(status: TaskStatus['status'], progress: number): TaskStatus {
  return {
    task_id: 'task-1',
    type: 'chapter:batch_generate',
    status,
    progress,
    stage: status === 'completed' ? 'completed' : 'batch_generating',
    message: status === 'completed' ? '任务完成' : '仍在生成',
    error: '',
    result: status === 'completed' ? { completed: 2, failed: 0 } : null,
    created_at: '2026-08-24T00:00:00Z',
    started_at: '2026-08-24T00:00:01Z',
    completed_at: status === 'completed' ? '2026-08-24T00:20:00Z' : null,
    retry_count: 0,
  }
}

describe('TaskAPI.pollUntilDone', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('未设置客户端期限时，超过十分钟仍以后端终态为准', async () => {
    vi.useFakeTimers()
    const getStatus = vi
      .spyOn(TaskAPI, 'getTaskStatus')
      .mockResolvedValueOnce(taskStatus('running', 50))
      .mockResolvedValueOnce(taskStatus('completed', 100))

    const pending = TaskAPI.pollUntilDone('task-1', undefined, 11 * 60 * 1000, null)
    await vi.runAllTimersAsync()

    await expect(pending).resolves.toMatchObject({ status: 'completed', progress: 100 })
    expect(getStatus).toHaveBeenCalledTimes(2)
  })

  it('显式期限仍可用于蓝图等有界等待场景', async () => {
    vi.useFakeTimers()
    vi.spyOn(TaskAPI, 'getTaskStatus').mockResolvedValue(taskStatus('running', 10))

    const pending = TaskAPI.pollUntilDone('task-1', undefined, 1000, 1500)
    const rejection = expect(pending).rejects.toThrow('任务超时')
    await vi.advanceTimersByTimeAsync(2001)

    await rejection
  })
})

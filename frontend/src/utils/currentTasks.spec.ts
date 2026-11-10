import { describe, expect, it } from 'vitest'
import { currentProjectTasks } from './currentTasks'
import type { TaskStatus } from '@/api/task'

const task = (id: string, chapter: number, status: TaskStatus['status'], date = '2026-11-10T10:00:00Z') => ({
  task_id: id, project_id: 'book', type: 'chapter:generate', chapter_number: chapter,
  status, created_at: date,
}) as TaskStatus

describe('currentProjectTasks', () => {
  it('collapses failures and keeps the active attempt in the same chapter', () => {
    const result = currentProjectTasks([task('failed', 2, 'failed'), task('active', 2, 'running'), task('older', 2, 'failed')], 'book')
    expect(result.map(t => t.task_id)).toEqual(['active'])
  })
  it('keeps latest terminal status and different chapters separate', () => {
    const result = currentProjectTasks([task('old', 2, 'failed', '2026-11-09T10:00:00Z'), task('done', 2, 'completed'), task('other', 3, 'failed')], 'book')
    expect(result.map(t => t.task_id)).toEqual(['done', 'other'])
  })
  it('does not merge unknown scopes by display name or include other books', () => {
    const a = task('a', 0, 'failed'), b = task('b', 0, 'failed')
    expect(currentProjectTasks([a, b, { ...a, task_id: 'elsewhere', project_id: 'other' }], 'book')).toHaveLength(2)
  })
  it('uses stable server key for a narrowed batch retry', () => {
    const a = { ...task('a', 0, 'failed'), task_key: 'batch:1,2,3' }
    const b = { ...task('b', 0, 'queued'), task_key: 'batch:1,2,3' }
    expect(currentProjectTasks([a,b], 'book').map(t => t.task_id)).toEqual(['b'])
  })
})

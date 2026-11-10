import type { TaskStatus } from '@/api/task'

export const isTaskActive = (task: TaskStatus) =>
  ['pending', 'queued', 'running', 'retrying'].includes(task.status)

export function taskWorkKey(task: TaskStatus): string {
  if (task.task_key) return task.task_key
  if (task.type === 'chapter:generate' && task.chapter_number) {
    return `${task.project_id}:${task.type}:${task.chapter_number}`
  }
  // Unknown legacy scopes must not merge unrelated chapters by their display name.
  return task.parent_task_id || task.task_id
}

export function currentProjectTasks(tasks: TaskStatus[], projectId: string): TaskStatus[] {
  const groups = new Map<string, TaskStatus>()
  const sorted = tasks.filter((task) => task.project_id === projectId)
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
  for (const task of sorted) {
    const key = taskWorkKey(task)
    const existing = groups.get(key)
    if (!existing || (isTaskActive(task) && !isTaskActive(existing))) groups.set(key, task)
  }
  return [...groups.values()].sort((a, b) => Number(isTaskActive(b)) - Number(isTaskActive(a)))
}

export interface ReferenceNovelChoice {
  id: number
  title: string
}

export interface ReferenceNovelSelectionState {
  rows: string[]
  selectedIds: Array<number | null>
}

/**
 * 将书库里的小说加入参考列表。
 *
 * 书库是多选入口：已有内容时优先填充空行，其次追加新行；只有达到上限时，
 * 才替换用户当前打开书库的那一行。这样从第一本小说的入口继续选择第二本时，
 * 不会再静默覆盖第一本。
 */
export function addLibraryReference(
  state: ReferenceNovelSelectionState,
  targetIndex: number,
  novel: ReferenceNovelChoice,
  maxItems = 3,
): ReferenceNovelSelectionState {
  const rows = state.rows.slice(0, maxItems)
  const selectedIds = state.selectedIds.slice(0, maxItems)

  while (selectedIds.length < rows.length) selectedIds.push(null)

  if (selectedIds.includes(novel.id)) {
    return { rows, selectedIds }
  }

  const emptyIndex = rows.findIndex((title) => !title.trim())
  if (emptyIndex >= 0) {
    rows[emptyIndex] = novel.title
    selectedIds[emptyIndex] = novel.id
    return { rows, selectedIds }
  }

  if (rows.length < maxItems) {
    rows.push(novel.title)
    selectedIds.push(novel.id)
    return { rows, selectedIds }
  }

  const replacementIndex = Math.min(Math.max(targetIndex, 0), rows.length - 1)
  rows[replacementIndex] = novel.title
  selectedIds[replacementIndex] = novel.id
  return { rows, selectedIds }
}

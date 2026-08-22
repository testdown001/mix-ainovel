import { describe, expect, it } from 'vitest'

import { addLibraryReference } from './referenceNovelSelection'

describe('addLibraryReference', () => {
  it('appends a second library novel instead of replacing the first one', () => {
    const result = addLibraryReference(
      { rows: ['大医凌然'], selectedIds: [11] },
      0,
      { id: 22, title: '重生97，我在市局破悬案' },
    )

    expect(result).toEqual({
      rows: ['大医凌然', '重生97，我在市局破悬案'],
      selectedIds: [11, 22],
    })
  })

  it('fills an existing empty row before appending', () => {
    const result = addLibraryReference(
      { rows: ['大医凌然', ''], selectedIds: [11, null] },
      0,
      { id: 22, title: '重生97，我在市局破悬案' },
    )

    expect(result.rows).toEqual(['大医凌然', '重生97，我在市局破悬案'])
    expect(result.selectedIds).toEqual([11, 22])
  })

  it('does not add the same library novel twice', () => {
    const result = addLibraryReference(
      { rows: ['大医凌然'], selectedIds: [11] },
      0,
      { id: 11, title: '大医凌然' },
    )

    expect(result).toEqual({ rows: ['大医凌然'], selectedIds: [11] })
  })

  it('replaces the targeted row only after the three-book limit is reached', () => {
    const result = addLibraryReference(
      { rows: ['甲', '乙', '丙'], selectedIds: [1, 2, 3] },
      1,
      { id: 4, title: '丁' },
    )

    expect(result).toEqual({ rows: ['甲', '丁', '丙'], selectedIds: [1, 4, 3] })
  })
})

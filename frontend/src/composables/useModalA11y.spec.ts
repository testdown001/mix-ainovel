import { describe, expect, it, vi } from 'vitest'

import { handleModalKeydown } from './useModalA11y'

// node 环境无 DOM：用最小的鸭子类型模拟容器与元素
function fakeContainer(items: Array<{ focus: () => void; hidden?: boolean }>) {
  const els = items.map((it) => ({
    focus: it.focus,
    hasAttribute: (name: string) => name === 'hidden' && !!it.hidden,
    getAttribute: () => null,
  }))
  return {
    els,
    container: {
      querySelectorAll: () => els,
      contains: (el: unknown) => els.includes(el as (typeof els)[number]),
    } as unknown as HTMLElement,
  }
}

const keyEvent = (key: string, shiftKey = false) => ({ key, shiftKey, preventDefault: vi.fn() })

describe('handleModalKeydown', () => {
  it('Escape 可关闭时返回 close 并阻止默认行为', () => {
    const ev = keyEvent('Escape')
    expect(handleModalKeydown(ev, null, null, true)).toBe('close')
    expect(ev.preventDefault).toHaveBeenCalled()
  })

  it('Escape 在不可关闭（提交中）时不处理', () => {
    const ev = keyEvent('Escape')
    expect(handleModalKeydown(ev, null, null, false)).toBeNull()
    expect(ev.preventDefault).not.toHaveBeenCalled()
  })

  it('Tab 在最后一个可聚焦元素上循环回第一个', () => {
    const first = { focus: vi.fn() }
    const last = { focus: vi.fn() }
    const { container, els } = fakeContainer([first, last])
    const ev = keyEvent('Tab')
    expect(handleModalKeydown(ev, container, els[1] as unknown as Element, true)).toBe('wrapped')
    expect(first.focus).toHaveBeenCalled()
    expect(ev.preventDefault).toHaveBeenCalled()
  })

  it('Shift+Tab 在第一个元素上循环到最后一个；中间元素不干预', () => {
    const first = { focus: vi.fn() }
    const mid = { focus: vi.fn() }
    const last = { focus: vi.fn() }
    const { container, els } = fakeContainer([first, mid, last])
    expect(handleModalKeydown(keyEvent('Tab', true), container, els[0] as unknown as Element, true)).toBe('wrapped')
    expect(last.focus).toHaveBeenCalled()
    expect(handleModalKeydown(keyEvent('Tab'), container, els[1] as unknown as Element, true)).toBeNull()
  })

  it('焦点在弹窗外时 Tab 把焦点拉回弹窗；隐藏元素不算可聚焦', () => {
    const first = { focus: vi.fn() }
    const hidden = { focus: vi.fn(), hidden: true }
    const { container } = fakeContainer([hidden, first])
    expect(handleModalKeydown(keyEvent('Tab'), container, null, true)).toBe('wrapped')
    expect(first.focus).toHaveBeenCalled()
    expect(hidden.focus).not.toHaveBeenCalled()
  })

  it('其它按键不处理', () => {
    expect(handleModalKeydown(keyEvent('Enter'), null, null, true)).toBeNull()
  })
})

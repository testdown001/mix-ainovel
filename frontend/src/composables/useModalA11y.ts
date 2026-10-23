// AIMETA P=自定义弹窗可访问性|R=Escape关闭_焦点进入与归还_Tab焦点圈闭|NR=不含弹窗样式|E=useModalA11y|X=internal|A=组合函数|D=vue|S=dom|RD=./README.ai
/**
 * 项目里不少弹窗是手写的 fixed 遮罩（不用 Naive UI 的 n-modal）：PricingView 收银台、
 * NovelWorkspace 删除确认、ReferenceNovelLibrary、作品页分享面板……它们原来既不响应 Escape，
 * 打开时焦点也留在遮罩后面，Tab 还能跑到页面底层（2026-10-23 交互审计 P2）。
 *
 * 用法：
 *   const dialogEl = ref<HTMLElement | null>(null)
 *   useModalA11y({ open: () => showX.value, container: dialogEl, onClose: closeX })
 * 模板上的容器元素仍要自己加 role="dialog" aria-modal="true" aria-labelledby/aria-label。
 *
 * 行为：open 变 true → 记住当前焦点元素，下一帧把焦点放进容器（优先 [autofocus]，否则第一个
 * 可聚焦元素，再不行容器本身）；Escape → onClose；Tab/Shift+Tab 在容器内循环；
 * open 变 false → 焦点归还给打开前的元素。所有 DOM 访问都做了存在性判断，SSR/测试环境下安全。
 */
import { onBeforeUnmount, watch, type Ref } from 'vue'

export interface ModalA11yOptions {
  open: () => boolean
  container: Ref<HTMLElement | null>
  onClose: () => void
  /** 为 false 时 Escape 不关闭（例如提交中） */
  closeOnEscape?: () => boolean
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function focusableElements(root: HTMLElement | null): HTMLElement[] {
  if (!root) return []
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => !el.hasAttribute('hidden') && el.getAttribute('aria-hidden') !== 'true',
  )
}

/**
 * 纯函数：给定按键事件与容器，决定如何处理。返回值便于在 node 环境下测试：
 * 'close' = 应关闭；'wrapped' = Tab 已在首尾之间循环；null = 不处理。
 */
export function handleModalKeydown(
  event: Pick<KeyboardEvent, 'key' | 'shiftKey' | 'preventDefault'>,
  container: HTMLElement | null,
  activeElement: Element | null,
  canClose: boolean,
): 'close' | 'wrapped' | null {
  if (event.key === 'Escape' || event.key === 'Esc') {
    if (!canClose) return null
    event.preventDefault()
    return 'close'
  }
  if (event.key !== 'Tab') return null
  const items = focusableElements(container)
  if (items.length === 0) {
    event.preventDefault()
    return 'wrapped'
  }
  const first = items[0]
  const last = items[items.length - 1]
  const inside = container ? container.contains(activeElement) : false
  if (event.shiftKey) {
    if (!inside || activeElement === first) {
      event.preventDefault()
      last.focus()
      return 'wrapped'
    }
    return null
  }
  if (!inside || activeElement === last) {
    event.preventDefault()
    first.focus()
    return 'wrapped'
  }
  return null
}

export function useModalA11y(options: ModalA11yOptions) {
  let opener: HTMLElement | null = null
  let listening = false

  const onKeydown = (event: KeyboardEvent) => {
    if (!options.open()) return
    const canClose = options.closeOnEscape ? options.closeOnEscape() : true
    const result = handleModalKeydown(event, options.container.value, document.activeElement, canClose)
    if (result === 'close') options.onClose()
  }

  const attach = () => {
    if (listening || typeof document === 'undefined') return
    document.addEventListener('keydown', onKeydown, true)
    listening = true
  }
  const detach = () => {
    if (!listening || typeof document === 'undefined') return
    document.removeEventListener('keydown', onKeydown, true)
    listening = false
  }

  const focusInto = () => {
    const root = options.container.value
    if (!root) return
    const target = (root.querySelector<HTMLElement>('[autofocus]') ?? focusableElements(root)[0]) ?? root
    if (target === root && !root.hasAttribute('tabindex')) root.setAttribute('tabindex', '-1')
    try {
      target.focus({ preventScroll: true })
    } catch {
      /* jsdom / 不可聚焦元素：忽略 */
    }
  }

  const restoreFocus = () => {
    const el = opener
    opener = null
    if (el && typeof el.focus === 'function' && document.contains(el)) {
      try {
        el.focus({ preventScroll: true })
      } catch {
        /* ignore */
      }
    }
  }

  watch(
    options.open,
    (isOpen) => {
      if (typeof document === 'undefined') return
      if (isOpen) {
        opener = (document.activeElement as HTMLElement | null) ?? null
        attach()
        // 容器在 v-if 之后才挂载，等一帧再聚焦
        requestAnimationFrame(() => {
          if (options.open()) focusInto()
        })
      } else {
        detach()
        restoreFocus()
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    detach()
    restoreFocus()
  })
}

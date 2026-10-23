// AIMETA P=未保存编辑守卫|R=切换前确认丢弃_beforeunload提示|NR=不含表单逻辑|E=compose:useUnsavedGuard|X=internal|A=useUnsavedGuard函数|D=vue,useAlert|S=dom|RD=./README.ai
/**
 * 「有未保存编辑时，切换/关闭前先问一句」的统一实现。
 *
 * 2026-10-23 审计：章节大纲切章、编辑章节弹窗点遮罩、提示词管理换条目、后台切菜单、
 * 故事骨架重新倒推——五处都无声丢掉用户输入。这里只做一件事：不脏直接放行，脏了弹
 * globalAlert.showConfirm（绝不用原生 confirm，沙箱会拦，且全站其它地方都用 globalAlert）。
 */
import { onBeforeUnmount, onMounted } from 'vue'
import { globalAlert } from '@/composables/useAlert'

export interface UnsavedGuardOptions {
  isDirty: () => boolean
  /** 确认框正文；默认「有尚未保存的修改，离开将丢失。确定放弃吗？」 */
  message?: string
  title?: string
  /** 为 true 时在组件挂载期间注册 beforeunload（浏览器关闭/刷新提示） */
  beforeUnload?: boolean
}

export const DEFAULT_UNSAVED_MESSAGE = '有尚未保存的修改，离开将丢失。确定放弃吗？'

export function useUnsavedGuard(options: UnsavedGuardOptions) {
  const confirmDiscard = async (): Promise<boolean> => {
    let dirty = false
    try {
      dirty = options.isDirty()
    } catch {
      dirty = false
    }
    if (!dirty) return true
    return globalAlert.showConfirm(options.message || DEFAULT_UNSAVED_MESSAGE, options.title || '放弃未保存的修改？')
  }

  if (options.beforeUnload) {
    const handler = (event: BeforeUnloadEvent) => {
      let dirty = false
      try {
        dirty = options.isDirty()
      } catch {
        dirty = false
      }
      if (!dirty) return
      event.preventDefault()
      // 现代浏览器只看 returnValue 是否被设置，文案由浏览器决定
      event.returnValue = ''
    }
    onMounted(() => window.addEventListener('beforeunload', handler))
    onBeforeUnmount(() => window.removeEventListener('beforeunload', handler))
  }

  return { confirmDiscard }
}

// ---------------------------------------------------------------------------
// 跨组件登记：后台面板把自己的 dirty 检查登记进来，AdminView 切菜单前统一询问。
// 用模块级注册表而不是 provide/inject：面板经 <component :is> 动态挂载，注册/注销
// 跟随各自的生命周期即可，AdminView 不必知道有哪些面板。
// ---------------------------------------------------------------------------
const dirtyCheckers = new Set<() => boolean>()

export function registerDirtyChecker(checker: () => boolean): () => void {
  dirtyCheckers.add(checker)
  return () => {
    dirtyCheckers.delete(checker)
  }
}

export function anyRegisteredDirty(): boolean {
  for (const checker of dirtyCheckers) {
    try {
      if (checker()) return true
    } catch {
      // 单个检查器出错不影响其它
    }
  }
  return false
}

/** 组件挂载期间登记自己的 dirty 检查，卸载时自动注销。 */
export function useRegisteredDirtyChecker(checker: () => boolean) {
  let unregister: (() => void) | null = null
  onMounted(() => {
    unregister = registerDirtyChecker(checker)
  })
  onBeforeUnmount(() => {
    unregister?.()
    unregister = null
  })
}

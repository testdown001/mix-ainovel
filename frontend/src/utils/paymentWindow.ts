// AIMETA P=支付跳转开窗|R=在用户手势内同步开空白窗_拿到支付链接后再导航|NR=不含下单|E=openPaymentWindow|X=internal|A=工具|D=none|S=dom|RD=./README.ai
/**
 * `window.open` 只有在用户点击的同步调用栈里才被浏览器当成「用户手势」；原来三处收银台都是
 * `await createOrder()` 之后再 open，Safari / Chrome 严格模式下直接被拦，用户只看到
 * 「已在新窗口打开支付页」却没有窗口（2026-10-23 交互审计）。
 *
 * 用法：点击处理函数一进来就 `const w = openPaymentWindow()`，拿到 pay_url 后 `w.navigate(url)`，
 * 失败时 `w.close()`。开窗被拦（返回 null）或在非浏览器环境下，navigate 退化为 window.open，
 * 由页面上的「前往支付」兜底链接接住。
 */
export interface PaymentWindowHandle {
  navigate: (url: string) => void
  close: () => void
  readonly blocked: boolean
}

const PLACEHOLDER_HTML =
  '<!doctype html><title>正在跳转到支付页…</title>' +
  '<body style="font-family:sans-serif;background:#0d0d0d;color:#ccc;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">' +
  '正在创建订单并跳转到支付页，请稍候…</body>'

export function openPaymentWindow(): PaymentWindowHandle {
  let win: Window | null = null
  if (typeof window !== 'undefined' && typeof window.open === 'function') {
    try {
      win = window.open('', '_blank')
      if (win) {
        try {
          win.document.write(PLACEHOLDER_HTML)
        } catch {
          /* 跨域或已被导航：忽略 */
        }
      }
    } catch {
      win = null
    }
  }
  const blocked = !win
  return {
    blocked,
    navigate(url: string) {
      if (win && !win.closed) {
        try {
          win.location.href = url
          return
        } catch {
          /* 落到下面的兜底 */
        }
      }
      if (typeof window !== 'undefined' && typeof window.open === 'function') {
        window.open(url, '_blank')
      }
    },
    close() {
      if (win && !win.closed) {
        try {
          win.close()
        } catch {
          /* ignore */
        }
      }
      win = null
    },
  }
}

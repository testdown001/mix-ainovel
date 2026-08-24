/**
 * 构建产物校验：M3 组件样式必须在产物里，且落在 @layer components 内。
 *
 * 源码层面的约定由 src/assets/styleContract.spec.ts 守着，但有一类失败只在产物里看得见：
 * 2026-08-14 把 `@import "./m3-components.css"` 放到了 `@plugin` 之后——@import 只能出现
 * 在所有规则之前，于是整条被丢弃，一千行组件样式从产物中消失，构建**零报错、零警告**。
 * 单测和 type-check 也全绿，只有打开页面才会发现整站没了样式。
 *
 * 用法：npm run build 之后 `node scripts/check-css-layers.mjs`
 */
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

// URL.pathname 在 Windows 会得到 `/D:/...`，Node 文件 API 无法识别；转成本机路径后
// 本地与 Linux 构建容器才能使用同一条产物校验命令。
const distAssets = fileURLToPath(new URL('../dist/assets/', import.meta.url))
const PROBE = '.md-btn-filled' // 只在 m3-components.css 里定义，不会与 scoped 样式混淆

let files
try {
  files = readdirSync(distAssets).filter((name) => name.endsWith('.css'))
} catch {
  fail('找不到 dist/assets，请先运行 npm run build')
}

const target = files.find((name) => readFileSync(join(distAssets, name), 'utf8').includes(PROBE))
if (!target) {
  fail(`产物里找不到 ${PROBE}：M3 组件样式没有进构建（检查 main.css 里 @import 的位置）`)
}

const css = readFileSync(join(distAssets, target), 'utf8')
const layer = layerOf(css, css.indexOf(PROBE))
if (layer !== 'components') {
  fail(
    `${PROBE} 落在 ${layer === null ? 'layer 之外' : `@layer ${layer}`}，应在 components 层。` +
      '\n无 layer 的 CSS 恒定胜过 layered CSS，组件类跑到层外会反过来压掉 Tailwind 工具类。',
  )
}

console.log(`✓ 组件样式在 ${target} 的 @layer components 内`)

/** 找出某个位置所处的最内层 @layer 名（不在任何 layer 内返回 null）。 */
function layerOf(text, index) {
  const stack = []
  let depth = 0
  for (const match of text.slice(0, index).matchAll(/@layer\s+([a-z.]+)\s*\{|\{|\}/g)) {
    const token = match[0]
    if (token.startsWith('@layer')) {
      stack.push([depth, match[1]])
      depth += 1
    } else if (token === '{') {
      depth += 1
    } else {
      depth -= 1
      while (stack.length && stack[stack.length - 1][0] >= depth) stack.pop()
    }
  }
  return stack.length ? stack[stack.length - 1][1] : null
}

function fail(message) {
  console.error(`✗ ${message}`)
  process.exit(1)
}

/**
 * 样式体系边界的守卫。
 *
 * 三套样式共存（设计令牌 / M3 组件类 / Tailwind 工具类，外加 Naive UI 自己的注入），
 * 谁覆盖谁由 CSS 层叠层决定，而**无 layer 的 CSS 恒定胜过任何 layered CSS**。
 * 「.prose 白字白底」那次事故就是这条规则：无 layer 的 `.prose{color:白}` 压掉了元素上
 * 显式写的 text-gray-700，白卡片上的正文全部隐形，而且不报任何错。
 *
 * 这里把边界钉成可执行的断言，而不是靠人记住约定。
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const assets = resolve(__dirname)
const mainCss = readFileSync(resolve(assets, 'main.css'), 'utf8')
const componentsCss = readFileSync(resolve(assets, 'm3-components.css'), 'utf8')

describe('样式分层边界', () => {
  it('组件层通过 layer(components) 导入，且紧跟 tailwindcss 之后', () => {
    const lines = mainCss.split('\n').map((line) => line.trim())
    const tailwindAt = lines.indexOf('@import "tailwindcss";')
    const componentsAt = lines.indexOf('@import "./m3-components.css" layer(components);')
    const pluginAt = lines.findIndex((line) => line.startsWith('@plugin'))

    expect(tailwindAt).toBeGreaterThanOrEqual(0)
    expect(componentsAt).toBe(tailwindAt + 1)
    // @import 必须在所有规则之前：放到 @plugin 之后会被整条丢弃，组件样式静默消失、
    // 构建不报错——2026-08-14 就这么踩过一次
    expect(pluginAt).toBeGreaterThan(componentsAt)
  })

  it('main.css 里除 :root 外不出现无 layer 的颜色规则', () => {
    const offenders = collectUnlayeredColorRules(mainCss)
    expect(offenders).toEqual([])
  })

  it('组件文件不写自己的 @layer（层归属由 import 决定，写了会变成子层）', () => {
    const withoutComments = componentsCss.replace(/\/\*[\s\S]*?\*\//g, '')
    expect(withoutComments).not.toMatch(/@layer/)
  })

  it('组件文件不定义设计令牌，也不写元素级默认值', () => {
    expect(componentsCss).not.toMatch(/:root\s*\{/)
    expect(componentsCss).not.toMatch(/^\s*(html|body)\s*[,{]/m)
  })
})

describe('设计令牌对比度', () => {
  // 前景/背景成对的令牌：任一对失守就是「看不见的文字」
  const PAIRS: Array<[string, string]> = [
    ['--md-on-background', '--md-background'],
    ['--md-on-surface', '--md-surface'],
    ['--md-on-surface-variant', '--md-surface'],
    ['--md-on-surface-variant', '--md-surface-container'],
    ['--md-on-primary', '--md-primary'],
    ['--md-on-primary-container', '--md-primary-container'],
    ['--md-on-secondary-container', '--md-secondary-container'],
    ['--md-on-error', '--md-error'],
    ['--md-on-error-container', '--md-error-container'],
    ['--md-on-success', '--md-success'],
    ['--md-on-success-container', '--md-success-container'],
  ]

  it.each(PAIRS)('%s 落在 %s 上要可读', (fg, bg) => {
    const ratio = contrast(tokenValue(fg), tokenValue(bg))
    expect(ratio, `${fg} on ${bg} = ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5)
  })
})

function tokenValue(name: string): string {
  const match = mainCss.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{3,8})`))
  if (!match) throw new Error(`令牌 ${name} 未定义或不是十六进制`)
  return match[1]
}

function contrast(a: string, b: string): number {
  const la = luminance(a)
  const lb = luminance(b)
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

function luminance(hex: string): number {
  const normalized =
    hex.length === 4
      ? `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`
      : hex.slice(0, 7)
  const channels = [1, 3, 5].map((i) => parseInt(normalized.slice(i, i + 2), 16) / 255)
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** 找出不在 @layer / :root 里、却设置了颜色的规则。 */
function collectUnlayeredColorRules(css: string): string[] {
  const masked = css.replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[{}]/g, ' '))
  const rawLines = css.split('\n')
  const maskedLines = masked.split('\n')

  const offenders: string[] = []
  let depth = 0
  let layerDepth: number | null = null
  let selector = ''

  for (let i = 0; i < rawLines.length; i++) {
    const raw = rawLines[i]
    const line = maskedLines[i]
    const trimmed = raw.trim()

    if (trimmed.startsWith('@layer')) layerDepth = depth
    if (line.includes('{') && !trimmed.startsWith('@')) selector = trimmed.replace(/\{.*/, '').trim()

    if (layerDepth === null && selector !== ':root' && /^\s*(color|background|background-color)\s*:/.test(raw)) {
      offenders.push(`${i + 1}: ${selector} → ${trimmed}`)
    }

    depth += (line.match(/\{/g) || []).length - (line.match(/\}/g) || []).length
    if (layerDepth !== null && depth <= layerDepth) layerDepth = null
  }
  return offenders
}

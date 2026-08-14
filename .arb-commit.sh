#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
cat > /tmp/arb-msg9.txt <<'MSG'
refactor(style): 样式体系定边界——组件类进 components 层，令牌只留一份

三套样式共存（设计令牌 / M3 组件类 / Tailwind 工具类，外加 Naive UI 注入），谁覆盖谁
靠层叠层决定，而无 layer 的 CSS 恒定胜过任何 layered CSS。M3 组件类此前全在层外，
「.prose 白字白底」事故就是这条规则的直接后果。

1. 一千行 .md-* 组件类拆到 m3-components.css，由 main.css 以 layer(components) 导入。
   边界因此是结构性的：写进那个文件就在 components 层，工具类能正常覆盖它，不必指望
   每个人记得手写 @layer。元素级默认值（*/html/body）也补进了 @layer base——body 的
   默认前景/背景色此前在层外，同样会压掉页面上的工具类。

2. 删掉 base.css：Vue 脚手架残留，从未被 import，却带着一整套浅色令牌（--color-*），
   谁误用一个就是浅色值落在深色面板上。

3. WritingDesk 里复制了一整份调色板（35 个令牌，值与 :root 逐字相同），删掉只留真正
   不同的字体族。两份定义的代价是无声的：改了 :root 漏改这里，页面停在旧值，而针对
   令牌的检查只看得到 :root 那份，全绿却修不到实际页面。

4. --md-on-error 由白改黑：白字落在 #FF4757 上只有 3.34:1，低于可读线（错误按钮上的
   「重试」正是这个组合），黑字 6.27:1，也与亮黄上用黑字的做法一致。

护栏两道：
- src/assets/styleContract.spec.ts（15 例）钉住分层约定与 11 对前景/背景令牌的对比度；
- npm run check:css 校验构建产物里组件样式确实存在且在 components 层内，已进 CI。
  这道必须查产物：本次就踩到 @import 写在 @plugin 之后被整条丢弃——@import 只能出现在
  所有规则之前——一千行组件样式从产物中消失，而构建零报错、单测与 type-check 全绿。
MSG
git add -A
git commit -F /tmp/arb-msg9.txt
rm -f /tmp/arb-msg9.txt
git push origin main 2>&1 | tail -1
git log --oneline -1

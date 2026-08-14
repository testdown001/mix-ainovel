#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
rm -f .arb-check.sh
cat > /tmp/arb-msg7.txt <<'MSG'
feat(progress): 补上写作前那段 40-50 秒的静默

修好 SSE 转发后实测：事件序列是「开始生成章节」→ 沉默 48 秒 → 一堆中间产物。
最长的一段沉默反而在最前面——检索与使命规划这一段一直没有阶段事件，只有 trace 里的
span。补两条：prepare_context「检索相关剧情与设定」、generate_chapter_mission
「规划本章任务」，前后端阶段表同步加行。
MSG
git add -A
git commit -F /tmp/arb-msg7.txt
rm -f /tmp/arb-msg7.txt
git push origin main 2>&1 | tail -1
git log --oneline -1

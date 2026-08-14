#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
rm -f .arb-check.sh .arb-verify.sh
cat > /tmp/arb-msg8.txt <<'MSG'
feat(progress): 精修被时间预算跳过时如实告知用户

线上验证进度序列时发现的：上游变慢后，标准档一章 380 秒（使命规划 120s + 正文 259s），
整条后处理链一步没跑——一致性校对、人性化、六维评审全被时间预算跳过。用户按标准档
付了钱，拿到的是没过质检的初稿，而界面上一点痕迹都没有。

结论本来就在响应里（review_summaries.time_budget.skipped），只是从来没人读它。异步
路径的 payload 不含 review_summaries，按 missing_scenes / polish_undelivered 的老办法
在 worker 里把结论带出来。前端 utils/budgetSkip 兼容两种载荷形状，生成完成后把跳过的
步骤用中文列出来，并说明正文已交付、可稍后重生成。
MSG
git add -A
git commit -F /tmp/arb-msg8.txt
rm -f /tmp/arb-msg8.txt
git push origin main 2>&1 | tail -1
git log --oneline -1

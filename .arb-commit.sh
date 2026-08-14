#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
rm -f .arb-check.sh
cat > /tmp/arb-msg5.txt <<'MSG'
feat(progress): 进度通道统一——一个状态机、一套阶段词汇、降级如实告知

P1「进度通道统一」。三条进度来路（网关异步任务 WS / SSE 直连 / 降级轮询）此前各自
往同一个 streamingStage 里塞字符串，谁最后写谁赢；进度百分比则在两个地方按中文关键词
各猜一遍——前端 ChapterGenerating 一张表、后端 task_worker 一张表，都建立在「阶段文案
里恰好含某个词」之上。结果是：单章路径显示中文、批量路径直接把 generate_versions /
batch_generating 甩给用户看；改一句阶段文案，两条进度条各自悄悄失准。

1. 后处理链不再静默。这条链是 6-10 次顺序 LLM 调用、约占一章四成时长，此前一个阶段
   事件都不发：最后一条停在「多版本生成中」，用户盯着不动的进度条一分多钟，只能理解
   为卡死。现在每步开工时报一条（发在结束时等于永远显示上一步），跳过的步骤不报。

2. 阶段词汇表按 stage key 定义，不再按文案措辞猜：后端 task_worker._STAGE_PROGRESS
   与前端 utils/generationStages.ts 各一张，key 是稳定契约（agent:* 仍走关键词兜底，
   保持 Agent 模式旧行为）。改文案不会再动进度，加阶段就是两边各加一行。

3. useGenerationProgress 收口成单状态机：所有来源走 applyStage，百分比单调不回退
   （后处理链有并行与跳过，事件顺序不保证递增，回退会被读成「重来了一遍」），
   认不出的阶段用后端中文消息兜底但不乱动进度——猜错的进度比不动更伤信任。

4. 降级变成状态并显性告知：网关不可用→直连生成、实时推送断开→每 2 秒轮询，都会在
   进度卡片上写明。此前这两种降级完全无声，用户不知道自己看的进度是哪一种、也不知道
   还能不能关页面。

回归：后端 971 passed（新增 test_post_processing_stage_events.py 5 例 + 转发器 3 例），
前端 42 passed（新增阶段表 7 例、状态机 9 例），type-check 干净。
MSG
git add -A
git commit -F /tmp/arb-msg5.txt
rm -f /tmp/arb-msg5.txt
git push origin main 2>&1 | tail -1
git log --oneline -1

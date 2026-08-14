#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
rm -f .arb-test.sh
cat > /tmp/arb-msg12.txt <<'MSG'
feat(reference): 参考小说桥段库——从「书名印象」到按情境检索的剧情手法

参考小说此前是「一次检索 + 三路全书级摘要」：几百万字压成一段百科式摘要，
MemoryCard 只有形容词（节奏快、爽点密），正文生成默认只收到蒸馏后的 fusion_dna，
蓝图章纲阶段零参考——用户「没参考到小说、剧情思考不深」的感受完全属实。

1. 检索多维度化：一次改五路并行（主线/人物/桥段/节奏/写法），各维度独立缓存 24h，
   单维度失败降级、全失败才 502；四路抽取各吃对应维度，不再共享一段大杂烩。

2. 新产物「桥段库」（reference_novels.beat_library，迁移 e5a6b7c8d9f0）：8-15 条
   「情境→手法」条目（什么局面、怎么铺、靠什么转、情绪在哪兑现、照搬怎么翻车）
   + 全书级结构手法（分卷节奏/冲突升级/章末钩子）。generate_structured + Pydantic
   校验，走搜索通道 responder；抽取失败软降级为 None，老三样照常落库。

3. 三处消费全接通：灵感对话注入桥段索引（构思能点名引用具体手法）；蓝图章纲阶段
   注入结构手法（此前该阶段零参考）；正文生成新增 [参考桥段] 段——按本章情境
   （标题+摘要+使命要点）语义检索 top-3 注入，600 token 预算。规模 ≤45 条不建
   Qdrant collection：一次 batch embedding + 内存余弦（utils/vector_math），情境向量
   按 (novel_id, updated_at) 缓存；嵌入不可用回退标签/bigram 打分——降级可以变糙，
   不能变没有。开关 enable_reference_beats：standard/premium 默认开（未绑定参考
   小说时天然 no-op），fast 关，flow_config 白名单可覆写。

4. memory_card 注入改字段级：剧情思考字段（冲突模版/爽点/伏笔/悬念）优先，不再
   整段 JSON dump 拦腰截 800 字——缩进吃预算、截断点全凭运气、低价值字段永远活着。

5. 老数据兼容：beat_library 为 NULL 的旧行全链路 no-op；详情页展示桥段库 + 补齐
   提示，「重新分析」按钮对 ready 状态开放。

回归：后端 994 passed（新增 3 个测试文件 16 例 + 更新 3 处旧断言），前端 63 passed，
type-check 干净。
MSG
git add -A
git commit -F /tmp/arb-msg12.txt
rm -f /tmp/arb-msg12.txt
git push origin main 2>&1 | tail -1
git log --oneline -1

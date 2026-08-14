#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
rm -f .arb-check.sh .arb-deploy.sh
cat > /tmp/arb-msg6.txt <<'MSG'
fix(deploy): SSE 直连 FastAPI——网关的 fasthttp 反代会缓冲整个响应体

线上实测：直连 app 立刻收到 started/stage 事件，经 nginx→Go 网关的同一个请求 25 秒
一个字节都没有。网关反代用的是 Fiber proxy.Do()（fasthttp 客户端），它把响应体整个
读完才返回，没有流式转发能力——于是生产环境里 SSE 的逐字草稿与阶段进度全程不可见，
要等生成结束才一次性吐出，用户看到的就是一个不动的转圈。上一批刚加的后处理链分步
播报，在 SSE 这条路上同样会被它吃掉（异步任务路径走 Redis→WS，不受影响）。

nginx 用精确匹配把这一个端点直连 FastAPI。丢掉的只是网关侧限流：该端点自身校验 JWT、
走档位门控与积分扣费，FastAPI 也有自己的 RateLimitMiddleware。
MSG
git add -A
git commit -F /tmp/arb-msg6.txt
rm -f /tmp/arb-msg6.txt
git push origin main 2>&1 | tail -1
git log --oneline -1

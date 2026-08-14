#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
git add -A && git commit -q -m "fix(deploy): SSE 直连 FastAPI——网关的 fasthttp 反代会缓冲整个响应体

线上实测：直连 app 立刻收到 started/stage 事件，经 nginx→Go 网关同样的请求 25 秒
一个字节都没有。网关反代用的是 Fiber proxy.Do()（fasthttp 客户端），它把响应体整个
读完才返回，没有流式转发能力——于是生产环境里 SSE 的逐字草稿与阶段进度全程不可见，
要等生成结束才一次性吐出，用户看到的就是一个不动的转圈。

nginx 用精确匹配把这一个端点直连 FastAPI。丢掉的只是网关侧限流：该端点自身校验 JWT、
走档位门控与积分扣费，FastAPI 也有自己的限流中间件。" && git push -q origin main
git log --oneline -1

sshpass -p 'M4eAdZFXKJ5rJW3P' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -p 22 root@142.91.105.227 'bash -s' <<'REMOTE'
set -e
cd /home/jack/mix-ainovel
git fetch --all -q && git reset --hard origin/main -q
cd deploy
export COMPOSE_FILE=docker-compose.prod.yml
docker compose exec -T nginx nginx -t </dev/null 2>&1 | tail -2 || true
docker compose restart nginx 2>&1 | tail -1
sleep 5
curl -sS -o /dev/null -w 'health=%{http_code}\n' http://127.0.0.1/api/health

TOKEN=$(curl -sS -X POST http://127.0.0.1/api/auth/token -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=admin&password=10086asd@' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

echo
echo "=== 经 nginx 的 SSE：40 秒内应能看到事件序列 ==="
timeout 45 curl -sS -N -X POST http://127.0.0.1/api/writer/advanced/generate/stream \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"project_id":"3daa1417-1aa9-4fb1-9ece-d039b05930a6","chapter_number":14,"flow_config":{"preset":"fast"}}' \
  2>/dev/null | python3 -u -c "
import sys, time
start=time.time(); n=0
for line in sys.stdin:
    if line.startswith('event:'):
        n+=1
        print(f'{time.time()-start:5.1f}s  {line.strip()}')
        if n>=8: break
" || true
REMOTE

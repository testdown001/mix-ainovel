#!/usr/bin/env bash
set -e
sshpass -p 'M4eAdZFXKJ5rJW3P' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -p 22 root@142.91.105.227 'bash -s' <<'REMOTE'
set -e
cd /home/jack/mix-ainovel
git fetch --all -q && git reset --hard origin/main -q
git log --oneline -1
cd deploy
export COMPOSE_FILE=docker-compose.prod.yml
docker compose exec -T nginx nginx -t </dev/null 2>&1 | tail -2 || true
docker compose restart nginx 2>&1 | tail -1
sleep 6
curl -sS -o /dev/null -w 'health=%{http_code}\n' http://127.0.0.1/api/health

TOKEN=$(curl -sS -X POST http://127.0.0.1/api/auth/token -H 'Content-Type: application/x-www-form-urlencoded' --data 'username=admin&password=10086asd@' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

echo
echo "=== 经 nginx 的 SSE：45 秒内应看到事件序列 ==="
timeout 50 curl -sS -N -X POST http://127.0.0.1/api/writer/advanced/generate/stream \
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

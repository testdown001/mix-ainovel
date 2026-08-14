#!/usr/bin/env bash
set -e
sshpass -p 'M4eAdZFXKJ5rJW3P' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 -p 22 root@142.91.105.227 'bash -s' <<'REMOTE'
set -e
cd /home/jack/mix-ainovel
git fetch --all -q && git reset --hard origin/main -q
git log --oneline -1
cd deploy
export COMPOSE_FILE=docker-compose.prod.yml
docker compose build app 2>&1 | tail -2
docker compose up -d --no-deps app 2>&1 | tail -2
sleep 25
docker compose ps --format '{{.Name}} {{.Status}}' | grep app
curl -sS -o /dev/null -w 'health=%{http_code}\n' http://127.0.0.1/api/health
echo "--- 迁移（stamp/upgrade 由脚本自判）---"
RUN=1 bash /home/jack/mix-ainovel/deploy/scripts/run_migrations.sh 2>&1 | tail -5 || true
echo "--- beat_library 列是否存在 ---"
docker compose exec -T app python -c "
import asyncio
from sqlalchemy import text
from app.db.session import AsyncSessionLocal
async def main():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(text('SHOW COLUMNS FROM reference_novels'))).fetchall()
        print([r[0] for r in rows])
asyncio.run(main())
" < /dev/null
REMOTE

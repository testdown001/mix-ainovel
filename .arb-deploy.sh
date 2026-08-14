#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
git rm -q --cached .arb-commit.sh 2>/dev/null || true
git commit -q -am "chore: 清理临时脚本" 2>/dev/null || true
git push -q origin main
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
curl -sS -o /dev/null -w 'health=%{http_code}\n' http://127.0.0.1/api/health
REMOTE

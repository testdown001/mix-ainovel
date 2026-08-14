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
docker compose ps --format '{{.Name}} {{.Status}}' | grep -E "app|nginx"
curl -sS -o /dev/null -w 'health=%{http_code}\n' http://127.0.0.1/api/health
REMOTE

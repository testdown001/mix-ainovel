#!/usr/bin/env bash
# E2E 冒烟的被测服务：uvicorn 同源托管 API + 前端 dist（不用 vite，免去代理层差异）。
# 由 playwright.config.ts 的 webServer 调用；先建库播种再起服务。
set -euo pipefail
cd "$(dirname "$0")/../../backend"

# 本地开发有 .venv 就用；CI 直接装进解释器环境
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export SECRET_KEY="${SECRET_KEY:-e2e-secret-key}"
export ADMIN_DEFAULT_PASSWORD="${ADMIN_DEFAULT_PASSWORD:-e2e-admin-password}"
export DB_PROVIDER=sqlite
export SQLITE_PATH="${E2E_SQLITE_PATH:-/tmp/arboris-e2e.db}"
export FRONTEND_DIST_DIR="$(cd ../frontend/dist && pwd)"
export DEBUG=true

# 每次全新建库，测试间零残留
rm -f "$SQLITE_PATH"
python scripts/seed_e2e_user.py

exec python -m uvicorn app.main:app --host 127.0.0.1 --port "${E2E_PORT:-8130}"

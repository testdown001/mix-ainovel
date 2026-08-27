#!/usr/bin/env bash
# =============================================================================
# 数据库结构校验脚本
#
# 校验两件事（都在 app 容器内执行，复用应用自己的数据库配置）：
#   1) Alembic 版本是否落在 head 上；
#   2) ORM 元数据（Base.metadata）与实际库结构有无漂移——缺表、缺列。
#
# 比对模型元数据而不是硬编码一串历史表名：加了新模型/新列忘记迁移，这里会直接报出来，
# 不需要有人记得回来更新校验清单。
#
# 用法：
#     bash deploy/scripts/verify_migration.sh
#     COMPOSE_FILE=docker-compose.prod.yml bash deploy/scripts/verify_migration.sh
#
# 退出码：0 = 无漂移且版本在 head；1 = 存在问题（详见输出）。
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/_common.sh
. "$SCRIPT_DIR/_common.sh"

echo "========================================="
echo " 数据库结构校验"
echo "========================================="

require_docker
load_env
info "compose 文件：$(compose_desc)"
info "数据库提供方：${DB_PROVIDER:-sqlite}"

# 这些调用一律 </dev/null：docker exec 会接管 stdin，本脚本经 ssh 管道执行时
# 会把调用者剩下的脚本吞掉（见 _common.sh 中 app_exec 的说明）。
if ! app_exec sh -c 'exit 0' </dev/null >/dev/null 2>&1; then
    die "app 容器不可用。请先启动服务：cd $DEPLOY_DIR && ${DC[*]} up -d"
fi

FAILED=0

# ---- 1. Alembic 版本 ---------------------------------------------------------
echo ""
info "1. Alembic 版本"
# Alembic revision ids are not limited to hexadecimal characters.  This
# project intentionally uses readable ids such as `i3d4e5f6g7h8`, so parsing
# only `[0-9a-f]` would report a false "no alembic_version" even after a
# successful upgrade.  Accept the id characters Alembic emits while keeping
# the match anchored to the beginning of the line.
CURRENT="$(app_exec alembic current </dev/null 2>/dev/null | grep -oE '^[[:alnum:]_-]{6,}' | head -n 1 || true)"
HEADS="$(app_exec alembic heads </dev/null 2>/dev/null | grep -oE '^[[:alnum:]_-]{6,}' || true)"
HEAD_COUNT="$(printf '%s\n' "$HEADS" | grep -c . || true)"

if [ -z "$CURRENT" ]; then
    warn "   库里没有 alembic_version（尚未纳管）→ 先跑 bash deploy/scripts/run_migrations.sh"
    FAILED=1
elif [ "$HEAD_COUNT" -gt 1 ]; then
    warn "   检测到多个 head，upgrade 会失败，需要先 merge："
    printf '     %s\n' $HEADS
    FAILED=1
elif [ "$CURRENT" = "$HEADS" ]; then
    ok "   当前版本 $CURRENT（= head）"
else
    warn "   当前 $CURRENT ≠ head $HEADS → 有未应用的迁移"
    FAILED=1
fi

# ---- 2. ORM 元数据 vs 实际库结构 ---------------------------------------------
echo ""
info "2. 模型与库结构漂移"
if app_exec python - <<'PY'
import asyncio
import sys

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  触发全部模型注册
from app.core.config import settings
from app.db.base import Base


def collect(conn):
    insp = inspect(conn)
    tables = set(insp.get_table_names())
    columns = {t: {c["name"] for c in insp.get_columns(t)} for t in tables}
    return tables, columns


async def main() -> int:
    engine = create_async_engine(settings.sqlalchemy_database_uri)
    try:
        async with engine.connect() as conn:
            db_tables, db_columns = await conn.run_sync(collect)
    finally:
        await engine.dispose()

    missing_tables = []
    missing_columns = []
    for name, table in sorted(Base.metadata.tables.items()):
        if name not in db_tables:
            missing_tables.append(name)
            continue
        for column in table.columns:
            if column.name not in db_columns[name]:
                missing_columns.append(f"{name}.{column.name}")

    if missing_tables:
        print(f"   缺表 {len(missing_tables)} 张：")
        for name in missing_tables:
            print(f"     - {name}")
    if missing_columns:
        print(f"   缺列 {len(missing_columns)} 个：")
        for item in missing_columns:
            print(f"     - {item}")
    if not missing_tables and not missing_columns:
        print(f"   模型 {len(Base.metadata.tables)} 张表全部就位，无缺表缺列")
        return 0
    return 1


sys.exit(asyncio.run(main()))
PY
then
    ok "   无漂移"
else
    warn "   存在漂移：库结构落后于模型定义"
    warn "   处理：确认 backend/migrations/ 里有对应 revision，然后 bash deploy/scripts/run_migrations.sh"
    warn "   （应用启动时的 init_db() create_all + _ensure_columns 也会补一部分，可先重启 app 观察）"
    FAILED=1
fi

echo ""
echo "========================================="
if [ "$FAILED" = 0 ]; then
    ok "校验通过"
else
    warn "校验发现问题（见上）"
fi
echo "========================================="
exit "$FAILED"

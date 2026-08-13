#!/usr/bin/env bash
# =============================================================================
# 数据库迁移执行脚本（Alembic 版）
#
# 迁移的唯一正路：在 app 容器内执行 alembic。容器复用应用自己的
# settings.sqlalchemy_database_uri，因此 MySQL / SQLite 都不用另外配连接串，
# 也不需要宿主机装 mysql 客户端、更不需要把数据库端口暴露到公网
# （生产栈已刻意不发布 mysql/redis/qdrant 端口，见 docker-compose.prod.yml）。
#
# 用法（在仓库任意目录）：
#     bash deploy/scripts/run_migrations.sh
#
#   生产栈（多文件叠加，用 docker 原生 COMPOSE_FILE）：
#     COMPOSE_FILE=docker-compose.prod.yml:docker-compose.https.yml \
#       bash deploy/scripts/run_migrations.sh
#
#   可选环境变量：
#     SKIP_BACKUP=1   跳过迁移前备份（备份失败时非交互环境必须显式声明）
#     LEGACY_SQL=1    改跑已归档的 backend/db/migrations/*.sql 原始 SQL 路径（见文末）
#
# 首次在「由 init_db() create_all 建出来的库」上运行时，脚本会识别出没有
# alembic_version 表，执行 `alembic stamp head` 把现状登记为基线（而不是傻乎乎
# upgrade 一遍——那会在已存在的表上建表失败）。之后每次部署再跑就是增量升级。
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/_common.sh
. "$SCRIPT_DIR/_common.sh"

echo "========================================="
echo " 数据库迁移（Alembic）"
echo "========================================="

require_docker
load_env
info "compose 文件：$(compose_desc)"
info "数据库提供方：${DB_PROVIDER:-sqlite}"

# ---- 0. app 容器必须在跑（alembic 在容器内执行）-------------------------------
if ! app_exec sh -c 'exit 0' >/dev/null 2>&1; then
    die "app 容器不可用。请先启动服务：cd $DEPLOY_DIR && ${DC[*]} up -d"
fi
ok "app 容器可用"

# ---- 1. 迁移前备份（MySQL：借 mysql 容器自带的 mysqldump）---------------------
# 口令通过容器自身环境变量取，不出现在宿主机进程列表里。
backup_mysql() {
    local svc="${MYSQL_SERVICE:-${MYSQL_HOST:-mysql}}"
    local dir="$PROJECT_ROOT/backups"
    mkdir -p "$dir"
    local file="$dir/backup_$(date +%Y%m%d_%H%M%S).sql"
    if dc exec -T "$svc" sh -c \
        'exec mysqldump --single-transaction -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
        > "$file" 2>/dev/null && [ -s "$file" ]; then
        ok "备份已保存：$file（$(du -h "$file" | cut -f1)）"
        return 0
    fi
    rm -f "$file"
    return 1
}

if [ "${SKIP_BACKUP:-0}" = "1" ]; then
    warn "按 SKIP_BACKUP=1 跳过迁移前备份"
elif [ "${DB_PROVIDER:-sqlite}" = "mysql" ]; then
    info "创建迁移前备份…"
    if ! backup_mysql; then
        warn "备份失败（mysql 服务名不对？外部托管数据库？）"
        if [ -t 0 ]; then
            echo -e "${YELLOW}没有备份也要继续迁移吗？(yes/no)${NC}"
            read -r _resp
            [ "$_resp" = "yes" ] || die "已取消"
        else
            die "非交互环境下拒绝无备份迁移。确认可接受再重跑：SKIP_BACKUP=1 bash $0"
        fi
    fi
else
    warn "SQLite 后端（开发用）跳过备份；需要的话请自行复制 storage/ 数据卷"
fi

# ---- 2. 判定库的状态：已纳管 / create_all 建的存量库 / 全新空库 ----------------
# 用应用自己的引擎探测，避免再引一套连接配置。
# 结果用 SCHEMA_STATE= 前缀标记后再提取，import 期间的任何杂输出都不会干扰判定。
SCHEMA_STATE="$(app_exec python - <<'PY' 2>/dev/null | sed -n 's/^SCHEMA_STATE=//p' | tail -n 1
import asyncio

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def main() -> None:
    engine = create_async_engine(settings.sqlalchemy_database_uri)
    try:
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
    finally:
        await engine.dispose()
    if "alembic_version" in tables:
        state = "MANAGED"
    elif tables:
        state = "LEGACY"
    else:
        state = "EMPTY"
    print(f"SCHEMA_STATE={state}")


asyncio.run(main())
PY
)" || true   # 探测失败不要被 set -e 直接掐掉，交给下面的 case 给出可操作的提示

case "$SCHEMA_STATE" in
    MANAGED|LEGACY|EMPTY) ok "库状态：$SCHEMA_STATE" ;;
    *) die "无法探测数据库状态（返回：${SCHEMA_STATE:-空}）。手工排查：cd $DEPLOY_DIR && ${DC[*]} exec app alembic current" ;;
esac

# ---- 3. 执行迁移 -------------------------------------------------------------
if [ "$SCHEMA_STATE" = "LEGACY" ]; then
    info "存量库由 init_db() create_all 建出、尚未纳入 Alembic；登记基线（stamp head）…"
    app_exec alembic stamp head
    ok "已登记为 head（本次不改结构；后续新增 revision 会走增量升级）"
else
    info "执行 alembic upgrade head …"
    app_exec alembic upgrade head
    ok "迁移完成"
fi

echo ""
info "当前版本："
app_exec alembic current || true

# ---- 4. 已归档的原始 SQL 路径（仅 LEGACY_SQL=1 时执行）------------------------
# backend/db/migrations/*.sql 是 Alembic 之前的历史产物：这些表/列如今由
# init_db() create_all + _ensure_columns 负责，基线 revision 也已覆盖。
# 保留仅为考古与极端手工修复，正常部署不要开。
if [ "${LEGACY_SQL:-0}" = "1" ]; then
    echo ""
    warn "==================== 已归档路径 ===================="
    warn "正在执行 backend/db/migrations/*.sql（Alembic 之前的历史 SQL）。"
    warn "这些变更已被基线 revision 与 init_db() 覆盖，重复执行通常只会报'已存在'。"
    warn "==================================================="
    svc="${MYSQL_SERVICE:-${MYSQL_HOST:-mysql}}"
    for f in "$PROJECT_ROOT"/backend/db/migrations/*.sql; do
        [ -f "$f" ] || continue
        info "执行 $(basename "$f") …"
        if dc exec -T "$svc" sh -c \
            'exec mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' < "$f" 2>/dev/null; then
            ok "$(basename "$f") 完成"
        else
            warn "$(basename "$f") 失败或已执行过（可忽略）"
        fi
    done
fi

echo ""
echo "========================================="
ok "迁移流程结束"
echo "========================================="
echo ""
echo "校验结果：bash deploy/scripts/verify_migration.sh"

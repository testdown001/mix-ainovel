#!/usr/bin/env bash
# =============================================================================
# 数据库回滚脚本
#
# 用法：
#     bash deploy/scripts/rollback.sh [备份文件名]
#     COMPOSE_FILE=docker-compose.prod.yml bash deploy/scripts/rollback.sh backup_20260813_120000.sql
#
# 不传文件名则列出 backups/ 下的备份并交互选择。
#
# 与旧版的区别：mysql 操作全部走 mysql 容器（宿主机不需要 mysql 客户端，
# 生产栈也不再对外发布 3306）。因此回滚时只停应用容器、保留数据库容器在跑
# —— 老脚本 `docker-compose down` 把数据库一起停了，之后的 restore 必然失败。
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=deploy/scripts/_common.sh
. "$SCRIPT_DIR/_common.sh"

echo "========================================="
echo " 数据库回滚"
echo "========================================="

require_docker
load_env

[ "${DB_PROVIDER:-sqlite}" = "mysql" ] || die "本脚本只处理 MySQL 回滚；SQLite 请直接还原 storage/ 数据卷"

MYSQL_SVC="${MYSQL_SERVICE:-${MYSQL_HOST:-mysql}}"
BACKUP_DIR="$PROJECT_ROOT/backups"
[ -d "$BACKUP_DIR" ] || die "未找到备份目录 $BACKUP_DIR"

# ---- 选择备份文件 -------------------------------------------------------------
BACKUP_NAME="${1:-}"
if [ -z "$BACKUP_NAME" ]; then
    echo ""
    echo "可用备份："
    ls -lh "$BACKUP_DIR"/*.sql 2>/dev/null || die "$BACKUP_DIR 下没有任何 .sql 备份"
    echo ""
    [ -t 0 ] || die "非交互环境请把备份文件名作为参数传入：bash $0 backup_YYYYmmdd_HHMMSS.sql"
    echo -e "${YELLOW}请输入要恢复的备份文件名：${NC}"
    read -r BACKUP_NAME
fi

BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
[ -f "$BACKUP_PATH" ] || die "备份文件不存在：$BACKUP_PATH"

# ---- 确认 ---------------------------------------------------------------------
echo ""
warn "回滚将覆盖当前数据库！"
echo "  备份文件：$BACKUP_PATH"
echo "  文件大小：$(du -h "$BACKUP_PATH" | cut -f1)"
echo "  创建时间：$(stat -c %y "$BACKUP_PATH" 2>/dev/null || stat -f %Sm "$BACKUP_PATH")"
echo "  目标数据库：${MYSQL_DATABASE:-arboris}（容器服务 $MYSQL_SVC）"
echo ""
if [ "${ASSUME_YES:-0}" != "1" ]; then
    [ -t 0 ] || die "非交互环境需显式声明 ASSUME_YES=1 才会执行回滚"
    echo -e "${YELLOW}确认执行回滚吗？(yes/no)${NC}"
    read -r response
    [ "$response" = "yes" ] || die "已取消"
fi

mysql_in_container() {
    dc exec -T "$MYSQL_SVC" sh -c 'exec mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
}

# ---- 先给当前状态留一份安全备份 -----------------------------------------------
echo ""
info "备份当前数据库（回滚失败时的退路）…"
SAFETY_BACKUP="$BACKUP_DIR/safety_backup_$(date +%Y%m%d_%H%M%S).sql"
if dc exec -T "$MYSQL_SVC" sh -c \
    'exec mysqldump --single-transaction -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
    </dev/null > "$SAFETY_BACKUP" 2>/dev/null && [ -s "$SAFETY_BACKUP" ]; then
    ok "安全备份：$SAFETY_BACKUP"
else
    rm -f "$SAFETY_BACKUP"
    die "无法备份当前数据库（mysql 容器 $MYSQL_SVC 在跑吗？），拒绝在没有退路的情况下回滚"
fi

# ---- 停应用（保留数据库容器，否则没法 restore）--------------------------------
echo ""
info "停止应用容器（数据库容器保持运行）…"
dc stop "$APP_SERVICE" >/dev/null 2>&1 || true
dc stop gateway >/dev/null 2>&1 || true
ok "应用已停止"

# ---- 恢复 ---------------------------------------------------------------------
echo ""
info "恢复数据库…"
mysql_in_container < "$BACKUP_PATH"
ok "数据已恢复"

# ---- 重启并检查 ---------------------------------------------------------------
echo ""
info "重启服务…"
dc up -d

info "等待服务就绪…"
HEALTHY=false
for _ in $(seq 1 60); do
    # </dev/null：docker exec 会接管 stdin，脚本经管道执行时会吞掉调用者剩余内容。
    if dc exec -T "$APP_SERVICE" curl -fs http://127.0.0.1:8000/api/health </dev/null >/dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    sleep 2
done

if [ "$HEALTHY" != true ]; then
    warn "健康检查失败，回滚到安全备份…"
    mysql_in_container < "$SAFETY_BACKUP" || warn "安全备份恢复也失败了，请人工介入：$SAFETY_BACKUP"
    dc up -d || true
    warn "最近日志："
    dc logs --tail=50 "$APP_SERVICE" || true
    die "回滚后服务未能就绪，已尝试还原到回滚前状态"
fi

echo ""
echo "========================================="
ok "回滚成功"
echo "========================================="
echo ""
echo "  已恢复：$BACKUP_NAME"
echo "  回滚前状态存于：$SAFETY_BACKUP"
echo ""

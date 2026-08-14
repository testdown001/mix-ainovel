#!/usr/bin/env bash
set -e
cd /home/aikev/code/arboris-novel
cat > /tmp/arb-msg13.txt <<'MSG'
fix(migrations): 新列迁移必须做存在性守卫——启动修复永远先于迁移执行

部署顺序恒为「先起新容器（init_db._ensure_columns 把列补上）、后跑迁移」，
不守卫的 ADD COLUMN 在已管理的库上必然撞 Duplicate column，e5a6b7c8d9f0 首次
上线即中。守卫后迁移的职责退化为推进 alembic_version。规约记入 CLAUDE.md。
MSG
git add -A
git commit -F /tmp/arb-msg13.txt
rm -f /tmp/arb-msg13.txt
git push origin main 2>&1 | tail -1
git log --oneline -1

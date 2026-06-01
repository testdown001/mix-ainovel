# 数据库迁移（Alembic）

本目录为版本化迁移脚手架。**应用启动仍由 `init_db()` 的 `create_all` 做 bootstrap**，
Alembic 作为后续 schema 演进的受控路径，逐步取代启动期硬编码"补列/补索引"逻辑。

## 常用命令

```bash
cd backend && source .venv/bin/activate
# 基于模型与当前库差异自动生成迁移（务必人工核对生成结果）
alembic revision --autogenerate -m "describe change"
# 应用到最新
alembic upgrade head
# 回滚一步
alembic downgrade -1
```

URL 由 `migrations/env.py` 从 `app.core.config.settings.sqlalchemy_database_uri` 读取，
SQLite / MySQL 自适应，无需在 `alembic.ini` 配置。

## 基线与采用方式

已生成基线迁移 `versions/3d0894d473c4_baseline_schema.py`（down_revision=None，覆盖全量表，
重新 `--autogenerate` 验证为无残余差异）。

由于应用启动仍用 `create_all` 建表，**在已被 create_all 建好的库上采用 Alembic 的方式是
`alembic stamp head`（标记基线已应用，不重复建表）**，而非 `alembic upgrade head`。
全新空库可直接 `alembic upgrade head`。

## 迁移落地建议

1. 现网/既有库：先 `alembic stamp 3d0894d473c4`（或 `stamp head`）。
2. 后续 schema 变更：改模型 → `alembic revision --autogenerate -m "..."` → 核对 → `alembic upgrade head`。
3. 把现有 `init_db.py` 的"补列/补索引"（如 `project_memories.book_summary`、
   `chapters`/`chapter_outlines` 的 `(project_id, chapter_number)` 复合索引）逐步迁移为 Alembic 版本。
4. CI 可加 `alembic upgrade head`（空库冒烟）校验迁移可应用。

#!/usr/bin/env python3
"""向量库存量补录 CLI：批量遍历项目做 RAG 增量重建（服务器运维工具）。

背景：生产 Qdrant 曾因 SSL 配置故障导致章节向量入库静默失败，存量已完成章节
在向量库为空。入库失败的章节 rag_ingest_hash 恰好没写成功，增量重建的 hash
比对语义能精准捞出全部漏录章节，重复执行天然幂等。

用法示例（在 backend/ 下，激活 .venv）：
  python backfill_vectors.py --dry-run            # 先看规模：各项目待补章节数，零 embedding 调用
  python backfill_vectors.py                      # 实跑：全部项目增量补录
  python backfill_vectors.py --project-id <uuid>  # 只跑一个项目
  python backfill_vectors.py --user-id 42         # 只跑某用户的项目
  python backfill_vectors.py --force-full         # 无视 hash 全量重建（慎用，embedding 全量重算）

退出码：0 全部成功；1 有章节/项目失败（可直接重跑，增量语义只补失败部分）；2 配置/环境错误。
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 测试注入口：设为可调用的 session 工厂后，不再触碰开发库
_SESSION_FACTORY = None


class CLIError(Exception):
    """带人话消息的 CLI 错误（打印后以退出码 2 结束）。"""


# ---------------------------------------------------------------------------
# 启动校验
# ---------------------------------------------------------------------------
def _ensure_app_importable() -> Optional[str]:
    """校验 backend/.env 可加载（SECRET_KEY 等必填项齐全），返回人话错误或 None。"""
    try:
        from app.core.config import settings  # noqa: F401
        return None
    except Exception as exc:  # noqa: BLE001
        return (
            "无法加载应用配置：\n"
            f"  {type(exc).__name__}: {exc}\n"
            "请确认 backend/.env 存在且至少包含 SECRET_KEY 与 ADMIN_DEFAULT_PASSWORD\n"
            "（参考 backend/env.example），并从 backend/ 目录运行本脚本。"
        )


def _get_session_factory():
    if _SESSION_FACTORY is not None:
        return _SESSION_FACTORY
    from app.db.session import AsyncSessionLocal

    return AsyncSessionLocal


async def _check_db(session_factory) -> None:
    from sqlalchemy import text

    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise CLIError(
            "无法连接数据库：\n"
            f"  {type(exc).__name__}: {exc}\n"
            "请确认 backend/.env 的 DB_PROVIDER / MYSQL_* / SQLITE_PATH 配置，"
            "以及数据库已启动。"
        ) from exc


def _check_vector_store():
    """向量库可用性检查，不可用直接人话报错退出。返回 VectorStoreService 实例。"""
    from app.core.config import settings
    from app.services.writer_shared import create_vector_store_or_none

    if not settings.vector_store_enabled:
        raise CLIError(
            "向量库未启用（QDRANT_HOST 为空）——补录没有写入目标。\n"
            "请在 backend/.env 配置 QDRANT_HOST / QDRANT_PORT 后重试。"
        )
    vector_store = create_vector_store_or_none()
    if vector_store is None:
        raise CLIError(
            "向量库初始化失败（QDRANT_HOST 已配置但连接/初始化不成功）。\n"
            "请确认 Qdrant 服务可达（含 SSL 证书配置），再重试。"
        )
    return vector_store


# ---------------------------------------------------------------------------
# 项目遍历
# ---------------------------------------------------------------------------
async def _load_projects(
    session, project_id: Optional[str], user_id: Optional[int]
) -> List[tuple]:
    """返回 (id, title, user_id) 列表，按 updated_at 升序（老项目先跑）。"""
    from sqlalchemy import select

    from app.models.novel import NovelProject

    stmt = select(NovelProject.id, NovelProject.title, NovelProject.user_id)
    if project_id:
        stmt = stmt.where(NovelProject.id == project_id)
    if user_id is not None:
        stmt = stmt.where(NovelProject.user_id == user_id)
    stmt = stmt.order_by(NovelProject.updated_at.asc(), NovelProject.id.asc())
    result = await session.execute(stmt)
    return list(result.all())


def _print_chapter_progress(event: Dict[str, Any]) -> None:
    kind = event.get("event")
    if kind == "ingest_done":
        print(
            f"    章节 {event['chapter_number']} 入库完成 "
            f"({event['seq']}/{event['total']})",
            flush=True,
        )
    elif kind == "ingest_failed":
        print(
            f"    章节 {event['chapter_number']} 入库失败 "
            f"({event['seq']}/{event['total']}): {str(event.get('error'))[:200]}",
            flush=True,
        )


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
async def run_backfill(args) -> int:
    session_factory = _get_session_factory()
    await _check_db(session_factory)
    vector_store = _check_vector_store()

    from app.services.llm_service import LLMService
    from app.services.rag_rebuild_service import rebuild_project_rag

    async with session_factory() as session:
        projects = await _load_projects(session, args.project_id, args.user_id)

    if not projects:
        if args.project_id:
            raise CLIError(f"项目不存在: {args.project_id}")
        if args.user_id is not None:
            print(f"用户 {args.user_id} 名下没有项目，无事可做。")
        else:
            print("库中没有任何项目，无事可做。")
        return 0

    mode = "full" if args.force_full else "incremental"
    print(
        f"共 {len(projects)} 个项目待处理"
        f"（{'dry-run 仅统计，零 embedding 调用' if args.dry_run else '实跑'}，mode={mode}）。",
        flush=True,
    )

    total_pending = 0
    total_indexed = 0
    total_skipped = 0
    total_failed = 0
    total_removed = 0
    project_rows: List[str] = []
    failed_projects: List[tuple] = []

    for idx, (pid, title, owner_id) in enumerate(projects, start=1):
        label = f"[{idx}/{len(projects)}] {pid} 《{title}》"
        try:
            # 逐项目独立 session：单项目失败不污染后续项目的事务状态
            async with session_factory() as session:
                llm_service = LLMService(session)
                stats = await rebuild_project_rag(
                    session,
                    llm_service,
                    pid,
                    user_id=owner_id,
                    force_full=args.force_full,
                    skip_bm25=True,
                    vector_store=vector_store,
                    dry_run=args.dry_run,
                    continue_on_error=True,
                    progress_cb=None if args.dry_run else _print_chapter_progress,
                )
        except Exception as exc:  # noqa: BLE001 - 单项目失败绝不中断整批
            message = f"{type(exc).__name__}: {exc}"
            print(f"{label} 项目级失败: {message}", flush=True)
            failed_projects.append((pid, title, message))
            project_rows.append(f"  {label} → 项目级失败: {message[:160]}")
            continue

        if args.dry_run:
            pending = len(stats["pending"])
            total_pending += pending
            line = (
                f"{label} 待补 {pending} 章"
                f"（可索引 {stats['chapters']} 章，已最新 {stats['skipped']} 章"
                + (f"，过期 {len(stats['stale'])} 章" if stats["stale"] else "")
                + "）"
            )
            print(line, flush=True)
            if pending:
                project_rows.append(f"  {label} → 待补 {pending} 章")
        else:
            print(f"{label} 开始，待补 {len(stats['pending'])} 章 ...", flush=True)
            total_indexed += stats["indexed"]
            total_skipped += stats["skipped"]
            total_failed += stats["failed"]
            total_removed += stats["removed"]
            summary = (
                f"indexed={stats['indexed']}, skipped={stats['skipped']}, "
                f"failed={stats['failed']}, removed={stats['removed']}"
            )
            print(f"{label} 完成: {summary}", flush=True)
            project_rows.append(f"  {label} → {summary}")

    print("\n===== 汇总 =====", flush=True)
    if args.dry_run:
        for row in project_rows:
            print(row)
        print(
            f"合计：{len(projects)} 个项目，待补 {total_pending} 章"
            f"（项目级失败 {len(failed_projects)} 个）。"
        )
        if total_pending:
            print("确认规模无误后，去掉 --dry-run 实跑补录。")
    else:
        for row in project_rows:
            print(row)
        print(
            f"合计：{len(projects)} 个项目，indexed={total_indexed}, "
            f"skipped={total_skipped}, failed={total_failed}, removed={total_removed}"
            f"（项目级失败 {len(failed_projects)} 个）。"
        )
    if failed_projects:
        print("项目级失败清单：")
        for pid, title, message in failed_projects:
            print(f"  - {pid} 《{title}》: {message[:200]}")
    if total_failed or failed_projects:
        print("存在失败项，修复后直接重跑本脚本即可——增量语义只会补失败部分。")
        return 1
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backfill_vectors.py",
        description="批量遍历项目做 RAG 向量增量补录（hash 比对，幂等可重跑）",
    )
    parser.add_argument("--project-id", default=None, help="只跑指定项目 UUID")
    parser.add_argument("--user-id", type=int, default=None, help="只跑指定用户 id 名下的项目")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅统计各项目待补章节数（hash 比对，零 embedding 调用），建议先跑一次看规模",
    )
    parser.add_argument(
        "--force-full", action="store_true",
        help="无视 hash 全量重建（默认增量，仅补 hash 缺失/变化章节）",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # 相对路径锚定 backend/（.env / sqlite / storage 不随调用方 CWD 漂移）
    os.chdir(BACKEND_DIR)

    env_error = _ensure_app_importable()
    if env_error:
        print(env_error, file=sys.stderr)
        return 2

    async def _run_with_teardown() -> int:
        try:
            return await run_backfill(args)
        finally:
            # 事件循环关闭前收尾 redis 连接，否则进程退出时 __del__ 在已关循环上
            # 析构连接，刷出 "RuntimeError: Event loop is closed" 噪音 traceback
            try:
                from app.services.cache_service import close_all_cache_clients

                await close_all_cache_clients()
            except Exception:
                pass

    try:
        return asyncio.run(_run_with_teardown())
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(
            "\n已中断。已入库章节的 hash 已写入，直接重跑本脚本即可从断点续补（增量幂等）。",
            file=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    sys.exit(main())

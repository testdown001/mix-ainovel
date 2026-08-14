"""E2E 冒烟种子脚本：初始化数据库并直插一个普通用户。

绕过注册流程（邮箱验证码/Turnstile）；不用 admin（首登会被强制改密拦截）。
幂等：用户已存在则直接退出。从 backend/ 目录运行：python scripts/seed_e2e_user.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

E2E_USERNAME = "e2euser"
E2E_PASSWORD = "e2e-password-123"


async def main() -> None:
    from sqlalchemy import select

    from app.core.security import hash_password
    from app.db.init_db import init_db
    from app.db.session import AsyncSessionLocal, engine
    from app.models import User

    await init_db()
    try:
        async with AsyncSessionLocal() as session:
            existing = (
                await session.execute(select(User).where(User.username == E2E_USERNAME))
            ).scalars().first()
            if existing:
                print(f"e2e user '{E2E_USERNAME}' already exists (id={existing.id})")
                return
            user = User(
                username=E2E_USERNAME,
                email="e2e@example.com",
                hashed_password=hash_password(E2E_PASSWORD),
                is_admin=False,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            print(f"e2e user '{E2E_USERNAME}' created (id={user.id})")
    finally:
        # 必须显式收掉连接池：aiosqlite >= 0.22 的连接线程不再随解释器退出，
        # 不 dispose 进程就挂在 exit 上——CI 里表现为 webServer 等健康检查
        # 吃满 120s 超时、uvicorn 根本没起（2026-08-14 实测）。
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

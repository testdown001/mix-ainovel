# AIMETA P=章节状态显示规则_给generating加保鲜期|R=effective_chapter_status|E=effective_chapter_status|X=internal|A=纯函数|D=|S=
"""章节生成状态的读取期规则。

`generating` 由生成流程开工时提交，只由同一次流程的结束路径改写。凡是没走完结束
路径的情况都会留下一个**永久**的「生成中」：容器在生成途中被重启或 OOM kill、进程
被强杀、Python 进程整体消失——没有任何代码会再碰这一行。前端对 generating 的表现
是转圈 + 每 10 秒轮询，于是用户盯着一个永不结束的进度条，而后端早已什么都不在跑。

这里按「最后更新时间」给它加保鲜期：超期即按失败呈现，与真实失败路径
(`_set_chapter_failed_status`) 落的状态一致，前端因此显示重试入口而不是假进度。
只影响读取时的呈现、不写库：下一次真实生成会自然覆盖状态，且多副本部署下也不会
出现「A 副本把 B 副本正在写的章节判死」的竞态。

保鲜期取 30 分钟：远大于单章实测上限（标准档约 1.8 分钟、精品档数分钟，即使时间
预算全额熔断也在 10 分钟量级），同时短到用户不会真的干等。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from ..schemas.novel import ChapterGenerationStatus

STALE_GENERATING_AFTER = timedelta(minutes=30)


def effective_chapter_status(
    status: Optional[str],
    updated_at: Optional[datetime],
    *,
    now: Optional[datetime] = None,
) -> str:
    """把超过保鲜期的 generating 呈现为 failed，其余状态原样返回。"""
    resolved = status or ChapterGenerationStatus.NOT_GENERATED.value
    if resolved != ChapterGenerationStatus.GENERATING.value or updated_at is None:
        return resolved

    # updated_at 的时区取决于驱动（MySQL 常为 naive、SQLite 为 naive、部分驱动带 tz），
    # 统一到 aware 再比较，避免 naive/aware 相减直接 TypeError 把整个章节读取打挂
    reference = now or datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)

    if reference - updated_at > STALE_GENERATING_AFTER:
        return ChapterGenerationStatus.FAILED.value
    return resolved

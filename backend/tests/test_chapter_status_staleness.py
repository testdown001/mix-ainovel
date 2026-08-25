"""generating 幽灵状态的保鲜期规则。

进程在生成途中消失（容器重启/OOM kill/强杀）时，没有任何代码会再改写这一行的
status，章节就永远停在 generating：前端画着转圈 + 每 10 秒轮询，用户看到「卡死」，
后端其实早就什么都不在跑。这里锁住读取期的判定，包括 naive/aware 混用不许抛异常
——一旦抛，整个章节读取接口就挂了。
"""
from datetime import datetime, timedelta, timezone

from app.utils.chapter_status import STALE_GENERATING_AFTER, effective_chapter_status


def test_fresh_generating_stays_generating():
    assert effective_chapter_status("generating", datetime.utcnow()) == "generating"


def test_generating_just_inside_window_stays():
    updated = datetime.utcnow() - (STALE_GENERATING_AFTER - timedelta(minutes=1))
    assert effective_chapter_status("generating", updated) == "generating"


def test_stale_generating_reads_as_failed():
    updated = datetime.utcnow() - (STALE_GENERATING_AFTER + timedelta(minutes=1))
    assert effective_chapter_status("generating", updated) == "failed"


def test_aware_updated_at_does_not_raise():
    # MySQL/SQLite 驱动给回的时区性不一致，naive 与 aware 相减会 TypeError
    updated = datetime.now(timezone.utc) - timedelta(hours=3)
    assert effective_chapter_status("generating", updated) == "failed"


def test_other_statuses_untouched_however_old():
    ancient = datetime.utcnow() - timedelta(days=365)
    for status in ("successful", "waiting_for_confirm", "failed", "evaluating", "not_generated"):
        assert effective_chapter_status(status, ancient) == status


def test_missing_updated_at_keeps_status():
    # 没有时间戳就无法判断陈旧，宁可保留 generating（等真实结束路径改写）
    assert effective_chapter_status("generating", None) == "generating"


def test_empty_status_falls_back_to_not_generated():
    assert effective_chapter_status(None, None) == "not_generated"


def test_failed_or_stale_generation_keeps_selected_body_successful():
    ancient = datetime.utcnow() - STALE_GENERATING_AFTER - timedelta(minutes=1)
    assert effective_chapter_status("failed", ancient, has_selected_version=True) == "successful"
    assert effective_chapter_status("generating", ancient, has_selected_version=True) == "successful"


def test_explicit_now_is_respected():
    updated = datetime(2026, 1, 1, 0, 0, 0)
    assert effective_chapter_status("generating", updated, now=datetime(2026, 1, 1, 0, 10, 0)) == "generating"
    assert effective_chapter_status("generating", updated, now=datetime(2026, 1, 1, 2, 0, 0)) == "failed"
